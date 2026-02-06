"""Utility functions and decorators for agents"""

import asyncio
import functools
import json
import logging
import time
from typing import Any, Callable, TypeVar, cast

from finbot.core.messaging import event_bus

logger = logging.getLogger(__name__)

# Type variable for generic function typing
F = TypeVar("F", bound=Callable[..., Any])


def agent_tool(func: F) -> F:
    """Decorator for agent tool calls that emits events at start and end of execution.

    This decorator:
    - Emits a 'tool_call_start' event when the tool is called
    - Emits a 'tool_call_success' event when the tool completes successfully
    - Emits a 'tool_call_failure' event when the tool fails
    - Includes duration metrics in success/failure events

    Usage:
        class MyAgent(BaseAgent):
            @agent_tool
            def my_tool(self, param1: str, param2: int) -> dict:
                # Tool implementation
                return {"result": "success"}

            @agent_tool
            async def my_async_tool(self, param1: str) -> dict:
                # Async tool implementation
                return {"result": "success"}

    Args:
        func: The function to decorate. Can be sync or async.
              Must be a method of an agent class with 'agent_name', 'session_context', and 'workflow_id' attributes.

    Returns:
        Decorated function that emits events before and after execution
    """

    @functools.wraps(func)
    async def async_wrapper(self, *args: Any, **kwargs: Any) -> Any:
        """Async wrapper for tool calls"""
        tool_name = func.__name__
        agent_name = getattr(self, "agent_name", "unknown_agent")
        session_context = getattr(self, "session_context", None)
        workflow_id = getattr(self, "workflow_id", None)

        if session_context is None:
            logger.warning(
                "Tool %s called without session_context, skipping event emission",
                tool_name,
            )
            return await func(self, *args, **kwargs)

        # Emit tool_call_start event
        start_time = time.time()
        await event_bus.emit_agent_event(
            agent_name=agent_name,
            event_type="tool_call_start",
            event_subtype="tool",
            event_data={
                "tool_name": tool_name,
                "args": str(args) if args else "",
                "kwargs": str(kwargs) if kwargs else "",
            },
            session_context=session_context,
            workflow_id=workflow_id,
            summary=f"Calling tool: {tool_name}",
        )

        try:
            # Execute the tool
            if asyncio.iscoroutinefunction(func):
                result = await func(self, *args, **kwargs)
            else:
                result = func(self, *args, **kwargs)

            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Emit tool_call_success event
            await event_bus.emit_agent_event(
                agent_name=agent_name,
                event_type="tool_call_success",
                event_subtype="tool",
                event_data={
                    "tool_name": tool_name,
                    "args": str(args) if args else "",
                    "kwargs": str(kwargs) if kwargs else "",
                    "duration_ms": duration_ms,
                    "tool_output": json.dumps(result) if result else "",
                },
                session_context=session_context,
                workflow_id=workflow_id,
                summary=f"Tool completed: {tool_name} ({duration_ms:.0f}ms)",
            )

            return result

        except Exception as e:
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Emit tool_call_failure event
            await event_bus.emit_agent_event(
                agent_name=agent_name,
                event_type="tool_call_failure",
                event_subtype="tool",
                event_data={
                    "tool_name": tool_name,
                    "args": str(args) if args else "",
                    "kwargs": str(kwargs) if kwargs else "",
                    "duration_ms": duration_ms,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                session_context=session_context,
                workflow_id=workflow_id,
                summary=f"Tool failed: {tool_name} ({type(e).__name__})",
            )

            # Re-raise the exception
            raise

    @functools.wraps(func)
    def sync_wrapper(self, *args: Any, **kwargs: Any) -> Any:
        """Sync wrapper that converts to async execution"""
        # For sync functions, we need to run the async wrapper in the event loop
        tool_name = func.__name__
        agent_name = getattr(self, "agent_name", "unknown_agent")
        session_context = getattr(self, "session_context", None)
        workflow_id = getattr(self, "workflow_id", None)

        if session_context is None:
            logger.warning(
                "Tool %s called without session_context, skipping event emission",
                tool_name,
            )
            return func(self, *args, **kwargs)

        # Create async function for event emission and execution
        async def execute_with_events() -> Any:
            start_time = time.time()

            # Emit tool_call_start event
            await event_bus.emit_agent_event(
                agent_name=agent_name,
                event_type="tool_call_start",
                event_subtype="tool",
                event_data={
                    "tool_name": tool_name,
                    "args": str(args) if args else "",
                    "kwargs": str(kwargs) if kwargs else "",
                },
                session_context=session_context,
                workflow_id=workflow_id,
                summary=f"Calling tool: {tool_name}",
            )

            try:
                # Execute the tool
                result = func(self, *args, **kwargs)

                # Calculate duration
                duration_ms = (time.time() - start_time) * 1000

                # Emit tool_call_success event
                await event_bus.emit_agent_event(
                    agent_name=agent_name,
                    event_type="tool_call_success",
                    event_subtype="tool",
                    event_data={
                        "tool_name": tool_name,
                        "args": str(args) if args else "",
                        "kwargs": str(kwargs) if kwargs else "",
                        "duration_ms": duration_ms,
                        "tool_output": json.dumps(result) if result else "",
                    },
                    session_context=session_context,
                    workflow_id=workflow_id,
                    summary=f"Tool completed: {tool_name} ({duration_ms:.0f}ms)",
                )

                return result

            except Exception as e:
                # Calculate duration
                duration_ms = (time.time() - start_time) * 1000

                # Emit tool_call_failure event
                await event_bus.emit_agent_event(
                    agent_name=agent_name,
                    event_type="tool_call_failure",
                    event_subtype="tool",
                    event_data={
                        "tool_name": tool_name,
                        "args": str(args) if args else "",
                        "kwargs": str(kwargs) if kwargs else "",
                        "duration_ms": duration_ms,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    },
                    session_context=session_context,
                    workflow_id=workflow_id,
                    summary=f"Tool failed: {tool_name} ({type(e).__name__})",
                )

                # Re-raise the exception
                raise

        # Try to get the current event loop
        try:
            loop = asyncio.get_running_loop()
            # If we're already in an event loop, create a task
            return loop.create_task(execute_with_events())
        except RuntimeError:
            # No event loop running, run in a new loop
            return asyncio.run(execute_with_events())

    # Return the appropriate wrapper based on whether the function is async
    if asyncio.iscoroutinefunction(func):
        return cast(F, async_wrapper)
    else:
        return cast(F, sync_wrapper)
