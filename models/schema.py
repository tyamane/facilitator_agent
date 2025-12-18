from typing import Literal, Optional, Any, Dict, List
from pydantic import BaseModel, Field

# Result Types for Agent Response
RESULT_TYPE_ANSWER = "ANSWER"
RESULT_TYPE_HANDOFF = "HANDOFF"
RESULT_TYPE_CONTINUE = "CONTINUE"
RESULT_TYPE_ERROR = "ERROR"

ResultType = Literal["ANSWER", "HANDOFF", "CONTINUE", "ERROR"]

class AgentResponse(BaseModel):
    """
    Standard response format from Specialist Agents (FunctionTools).
    """
    agent_name: str = Field(..., description="Name of the agent returning this response")
    result_type: ResultType = Field(..., description="Type of the result: ANSWER, HANDOFF, CONTINUE, or ERROR")
    content: str | Dict[str, Any] = Field(..., description="Content to display to the user or pass to the next agent")
    confidence: float = Field(..., description="Confidence score of the result (0.0 to 1.0)")
    agent_state: Optional[Dict[str, Any]] = Field(None, description="Updated internal state of the agent to be persisted")
    next_agent_hint: Optional[str] = Field(None, description="Hint for the next agent to call (only for HANDOFF)")

class ThreadState(BaseModel):
    """
    State of the conversation thread managed by the Facilitator.
    Persisted in ADK Session State.
    """
    status: Literal["OPEN", "IN_PROGRESS", "WAITING_FOR_USER", "RESOLVED"] = Field("OPEN", description="Current status of the thread")
    goal: str = Field("", description="Current goal or objective of the thread")
    context_summary: str = Field("", description="Summary of the conversation context")
    last_action: str = Field("", description="Description of the last action taken")
    active_agent: Optional[str] = Field(None, description="Name of the currently active agent (Sticky Session)")
    agent_state: Optional[Dict[str, Any]] = Field(None, description="Persisted internal state of the active agent")
