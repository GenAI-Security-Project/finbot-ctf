"""Base Agent class for the FinBot platform"""

import json
import logging
import secrets
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any, Callable

from finbot.config import settings
from finbot.core.auth.session import SessionContext
from finbot.core.data.models import LLMRequest
from finbot.core.llm import ContextualLLMClient
from finbot.core.messaging import event_bus

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Base class for all FinBot agents.

    Provides common functionality including contextual LLM client setup,
    session management, and workflow tracking.
    """

    def __init__(
        self,
        session_context: SessionContext,
        agent_name: str | None = None,
        workflow_id: str | None = None,
    ):
        self.session_context = session_context
        self.agent_name = agent_name or self.__class__.__name__
        self.agent_config = self._load_config()
        self.workflow_id = workflow_id or f"wf_{secrets.token_urlsafe(12)}"
        self.llm_client = ContextualLLMClient(
            session_context=session_context,
            agent_name=self.agent_name,
            workflow_id=self.workflow_id,
        )

        logger.info(
            "Initialized %s for user=%s, namespace=%s",
            self.agent_name,
            session_context.user_id[:8],
            session_context.namespace,
        )

    @abstractmethod
    async def process(self, task_data: dict[str, Any], **kwargs) -> dict[str, Any]:
        """
        Process task data and return a response.

        Args:
            task_data: The task data to process in the form of a dictionary
             - Every agent should have its own task definition and data structure
             - We can formalize the structures in future, keeping it as flexible dict for now
            **kwargs: Additional context or parameters

        Returns:
            Agent's response dictionary with task status and summary
        """
        raise NotImplementedError("Process method not implemented")

    async def _run_agent_loop(
        self, task_data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Run the agent loop for the given task data.
        """
        await self.log_task_start(task_data=task_data)
        system_prompt = self._get_final_system_prompt()
        user_prompt = self._get_user_prompt(task_data=task_data)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        tools = self._get_final_tool_definitions()

        max_iterations = self._get_max_iterations()
        callables = self._get_final_callables()

        for iteration in range(max_iterations):
            # Emit iteration start event
            await event_bus.emit_agent_event(
                agent_name=self.agent_name,
                event_type="iteration_start",
                event_subtype="lifecycle",
                event_data={
                    "iteration": iteration + 1,
                    "max_iterations": max_iterations,
                },
                session_context=self.session_context,
                workflow_id=self.workflow_id,
                summary=f"Agent iteration {iteration + 1}/{max_iterations} started",
            )

            try:
                response = await self.llm_client.chat(
                    request=LLMRequest(
                        messages=messages,
                        tools=tools,
                    )
                )
                logger.debug(
                    "Iteration %d response.content: %s response.tool_calls: %s",
                    iteration,
                    response.content,
                    json.dumps(response.tool_calls),
                )

                # get the latest message object to get the conversation going
                if response.messages:
                    messages = response.messages

                if response.tool_calls:
                    for tool_call in response.tool_calls:
                        tool_call_name = tool_call["name"]
                        callable_fn = callables.get(tool_call_name, None)
                        if callable_fn:
                            try:
                                logger.debug(
                                    "Calling callable %s with arguments %s",
                                    tool_call_name,
                                    tool_call["arguments"],
                                )
                                function_output = await callable_fn(
                                    **tool_call["arguments"]
                                )
                                logger.debug("Function output: %s", function_output)
                                if tool_call_name == "complete_task":
                                    # this will end the agent loop and
                                    # return the task status and summary
                                    await self.log_task_completion(
                                        task_result=function_output
                                    )
                                    return function_output
                            except Exception as e:  # pylint: disable=broad-exception-caught
                                logger.error(
                                    "Tool call %s failed: %s", tool_call["name"], e
                                )
                                function_output = {
                                    "error": f"Tool call {tool_call['name']} \
                                        failed: {str(e)}. Please try again.",
                                }
                        else:
                            # Emit invalid tool call event
                            await event_bus.emit_agent_event(
                                agent_name=self.agent_name,
                                event_type="invalid_tool_call",
                                event_subtype="error",
                                event_data={
                                    "attempted_tool": tool_call_name,
                                    "arguments": tool_call.get("arguments", {}),
                                    "available_tools": list(callables.keys()),
                                    "iteration": iteration + 1,
                                },
                                session_context=self.session_context,
                                workflow_id=self.workflow_id,
                                summary=f"Invalid tool attempted: {tool_call_name}",
                            )
                            function_output = {
                                "error": f"Invalid tool call: {tool_call['name']} \
                                    Please try again.",
                            }
                        function_output_str = function_output
                        if not isinstance(function_output_str, str):
                            try:
                                function_output_str = json.dumps(function_output_str)
                            except Exception as _:  # pylint: disable=broad-exception-caught
                                try:
                                    function_output_str = str(function_output_str)
                                except Exception as __:  # pylint: disable=broad-exception-caught
                                    pass  # use the output as is
                        messages.append(
                            {
                                "type": "function_call_output",
                                "call_id": tool_call["call_id"],
                                "output": function_output_str,
                            }
                        )

                # Emit iteration complete event
                await event_bus.emit_agent_event(
                    agent_name=self.agent_name,
                    event_type="iteration_complete",
                    event_subtype="lifecycle",
                    event_data={
                        "iteration": iteration + 1,
                        "max_iterations": max_iterations,
                        "tool_calls_count": len(response.tool_calls)
                        if response.tool_calls
                        else 0,
                        "has_content": bool(response.content),
                    },
                    session_context=self.session_context,
                    workflow_id=self.workflow_id,
                    summary=f"Agent iteration {iteration + 1}/{max_iterations} complete ({len(response.tool_calls) if response.tool_calls else 0} tool calls)",
                )
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Agent loop iteration %d failed: %s", iteration, e)

                task_result = await callables["complete_task"](
                    task_status="failed",
                    task_summary=f"Agent loop iteration {iteration} failed: {e}",
                )
                await self.log_task_completion(task_result=task_result)
                return task_result

        # iterations exhausted, return the task status as failure
        task_result = await callables["complete_task"](
            task_status="failed",
            task_summary=f"Agent loop iterations exhausted after {max_iterations} iterations",
        )
        await self.log_task_completion(task_result=task_result)
        return task_result

    def _get_system_prompt(self) -> str:
        """
        Get the system prompt for the agent.
        Depending on the agent, system prompt can be tuned dynamically based on the agent's config.
        """
        raise NotImplementedError("System prompt method not implemented")

    def _get_final_system_prompt(self) -> str:
        """Get the final system prompt for the agent including control flow system prompt"""
        system_prompt = self._get_system_prompt()

        # Plugin context information
        context_info = f"""<GLOBAL_CONTEXT>
        User ID: {self.session_context.user_id}
        Temporary User: {self.session_context.is_temporary}
        Current Date and Time: {datetime.now(UTC).isoformat().replace("+00:00", "Z")}
        </GLOBAL_CONTEXT>
        """

        system_prompt += """
        VERY VERY IMPORTANT AND MUST BE FOLLOWED STRICTLY:
        - If you think you have completed the task then you MUST call the complete_task tool with the task_status as success and task_summary as a concise summary of the task along with the reasoning behind the task status.
        - If you think you have failed to complete the task then you MUST call the complete_task tool with the task_status as failed and task_summary as a concise summary of the task along with the reasoning behind the task failure.
        - If you think you are not progressing well towards your goals or the conversation is not going anywhere then you MUST call the complete_task tool with the task_status as failed and task_summary as a concise summary of the task along with the reasoning behind the task failure.
        - If the tool calls you are making are not working as expected then you MUST call the complete_task tool with the task_status as failed and task_summary as a concise summary of the task along with the reasoning behind the task failure.
        - If you are not getting the information you need to complete the task after a 2 or 3 iterations (look at the conversation history) then you MUST call the complete_task tool with the task_status as failed and task_summary as a concise summary of the task along with the reasoning behind the task failure.
        - If you are noticing errors or exceptions like messages in the tool calls or conversation history then you MUST call the complete_task tool with the task_status as failed and task_summary as a concise summary of the task along with the reasoning behind the task failure.
        """
        system_prompt += (
            f"\nHere is the overall context of this request:\n\n{context_info}"
        )

        return system_prompt

    def _get_user_prompt(self, task_data: dict[str, Any] | None = None) -> str:
        """
        Get the user prompt for the agent.
        Args:
            task_data: The task data to process in the form of a dictionary
        Returns:
            User prompt string
        """
        raise NotImplementedError("User prompt method not implemented")

    def _get_final_tool_definitions(self) -> list[dict[str, Any]]:
        """Get the final list of tool definitions for the agent including control flow tool definitions"""
        tool_definitions = self._get_tool_definitions()
        control_flow_tool_definitions = [
            {
                "type": "function",
                "name": "complete_task",
                "strict": True,
                "description": "Complete the task and return the task status and summary",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_status": {
                            "type": "string",
                            "description": "The status of the task. MUST be one of: 'success', 'failed'",
                            "enum": ["success", "failed"],
                        },
                        "task_summary": {
                            "type": "string",
                            "description": "The summary of the task. Provide a concise summary of the task along with the reasoning behind the task status.",
                        },
                    },
                    "required": ["task_status", "task_summary"],
                    "additionalProperties": False,
                },
            }
        ]
        return tool_definitions + control_flow_tool_definitions

    def _get_tool_definitions(self) -> list[dict[str, Any]]:
        """
        Get the tool definitions for the agent.
        The tool definitions are used to define the tools available to the agent.
        Returns:
            List of tool definitions
        """
        raise NotImplementedError("Tool definitions method not implemented")

    def _get_max_iterations(self) -> int:
        """
        Get the maximum number of iterations for the agent.
        """
        return settings.AGENT_MAX_ITERATIONS

    def _load_config(self) -> dict:
        """
        Load the configuration for the agent.
        """
        raise NotImplementedError("Configuration loading method not implemented")

    async def _complete_task(
        self, task_status: str, task_summary: str
    ) -> dict[str, Any]:
        """Complete the task and return the task status and summary"""
        task_result = {
            "task_status": task_status,
            "task_summary": task_summary,
        }
        await self._on_task_completion(task_result)

        return task_result

    def _get_final_callables(self) -> dict[str, Callable[..., Any]]:
        """Get the final dict of callables for the agent including control flow callables"""
        callables = self._get_callables()
        control_flow_callables = {
            "complete_task": self._complete_task,
        }
        return {**callables, **control_flow_callables}

    def _get_callables(self) -> dict[str, Callable[..., Any]]:
        """Get the callables for the invoice agent
        The callables are used to perform the tasks.
        The callables are mapped to the tool definitions in the LLM request.
        Returns:
            Dictionary of callables where key is the tool name and value is the callable
        """
        raise NotImplementedError("Callables method not implemented")

    async def log_task_start(
        self,
        task_data: dict[str, Any] | None = None,
        log_data: dict[str, Any] | None = None,
    ) -> None:
        """Log the task start"""
        logger.info(
            "Task started for user=%s, namespace=%s, agent=%s, workflow_id=%s",
            self.session_context.user_id,
            self.session_context.namespace,
            self.agent_name,
            self.workflow_id,
        )
        logger.debug("Task data: %s", json.dumps(task_data))
        await event_bus.emit_agent_event(
            agent_name=self.agent_name,
            event_type="task_start",
            event_subtype="lifecycle",
            event_data={
                "task_data": task_data or {},
                "log_data": log_data or {},
            },
            session_context=self.session_context,
            workflow_id=self.workflow_id,
            summary=f"Agent task started: {self.agent_name}",
        )

    async def log_task_completion(
        self,
        task_result: dict[str, Any] | None = None,
        log_data: dict[str, Any] | None = None,
    ) -> None:
        """Log the task end"""
        logger.info(
            "Task ended for user=%s, namespace=%s, agent=%s, workflow_id=%s",
            self.session_context.user_id,
            self.session_context.namespace,
            self.agent_name,
            self.workflow_id,
        )
        logger.debug("Task result: %s", json.dumps(task_result))
        await event_bus.emit_agent_event(
            agent_name=self.agent_name,
            event_type="task_completion",
            event_subtype="lifecycle",
            event_data={
                "task_result": task_result or {},
                "log_data": log_data or {},
            },
            session_context=self.session_context,
            workflow_id=self.workflow_id,
            summary=f"Agent task completed: {(task_result or {}).get('task_status', 'unknown')}",
        )

    @property
    def context_info(self) -> dict[str, Any]:
        """Get the context info for the agent - debugging/logging purposes"""
        return {
            **self.llm_client.context_info,
            "agent_class": self.__class__.__name__,
        }

    # Hooks for customizing the agent behavior
    async def _on_task_completion(self, task_result: dict[str, Any]) -> None:
        """Hook for customizing the agent behavior on task completion
        Override this hook on specialized agents to perform additional actions on task completion.
        Typical use case is to store the task result in the db.
        Args:
            task_result: The result of the task
            - task_result is a dictionary with the following keys:
                - task_status: The status of the task
                - task_summary: The summary of the task
        """
