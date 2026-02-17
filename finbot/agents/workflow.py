import yaml
import json
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
import logging

class WorkflowState(str, Enum):
    STARTED = "started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class WorkflowEvent:
    def __init__(self, workflow_id: str, state: WorkflowState, step: str, context: dict):
        self.workflow_id = workflow_id
        self.state = state
        self.step = step
        self.context = context

    def emit(self):
        # Placeholder for event emission (could integrate with finbot.core.messaging.events)
        logging.info(f"[WorkflowEvent] {self.workflow_id} {self.state} step={self.step} context={self.context}")

class AgentBase:
    def __init__(self, name: str):
        self.name = name

    def run(self, context: dict) -> dict:
        """Run the agent with the given context. Returns updated context/results."""
        raise NotImplementedError

    def rollback(self, context: dict) -> None:
        """Rollback/compensate if needed. Override in subclasses."""
        pass

class WorkflowOrchestrator:
    def __init__(self, workflow_def: dict, agent_registry: Dict[str, AgentBase]):
        self.workflow_def = workflow_def
        self.agent_registry = agent_registry
        self.state = WorkflowState.STARTED
        self.current_step = None
        self.context = {}
        self.workflow_id = workflow_def.get("id", "workflow")

    def emit_event(self, state: WorkflowState, step: str):
        event = WorkflowEvent(self.workflow_id, state, step, self.context.copy())
        event.emit()

    async def run(self, initial_context: dict = None) -> dict:
        self.state = WorkflowState.STARTED
        self.context = initial_context.copy() if initial_context else {}
        steps = self.workflow_def["steps"]
        self.emit_event(WorkflowState.STARTED, step="start")
        try:
            for step in steps:
                self.state = WorkflowState.IN_PROGRESS
                self.current_step = step["agent"]
                agent_name = step["agent"]
                agent = self.agent_registry[agent_name]
                self.emit_event(WorkflowState.IN_PROGRESS, step=agent_name)
                run_method = getattr(agent, "run", None)
                if run_method is None:
                    raise RuntimeError(f"Agent {agent_name} missing run method")
                if getattr(run_method, "__code__", None) and run_method.__code__.co_flags & 0x80:
                    # async def (CO_COROUTINE)
                    self.context = await run_method(self.context)
                else:
                    self.context = run_method(self.context)
            self.state = WorkflowState.COMPLETED
            self.emit_event(WorkflowState.COMPLETED, step="end")
            return self.context
        except Exception as e:
            self.state = WorkflowState.FAILED
            self.emit_event(WorkflowState.FAILED, step=self.current_step)
            # Rollback/compensate in reverse order
            for step in reversed(steps):
                agent_name = step["agent"]
                agent = self.agent_registry[agent_name]
                try:
                    agent.rollback(self.context)
                except Exception as re:
                    logging.error(f"Rollback failed for {agent_name}: {re}")
            raise

    @staticmethod
    def load_workflow_definition(path: str) -> dict:
        if path.endswith(".yaml") or path.endswith(".yml"):
            with open(path, "r") as f:
                return yaml.safe_load(f)
        elif path.endswith(".json"):
            with open(path, "r") as f:
                return json.load(f)
        else:
            raise ValueError("Unsupported workflow definition format")
