from typing import Dict, Any, Optional, Literal, List
from pydantic import BaseModel, Field
from ...models.schema import AgentResponse, RESULT_TYPE_ANSWER, RESULT_TYPE_CONTINUE, RESULT_TYPE_HANDOFF

# State Model specific to Ops Agent
class OpsAgentState(BaseModel):
    phase: Literal["COLLECTING", "CONFIRMING", "COMPLETED"] = "COLLECTING"
    task_type: Optional[str] = None
    collected_params: Dict[str, Any] = {}
    missing_params: List[str] = []
    execution_plan: Optional[str] = None

def call_ops_agent(query: str, agent_state: Optional[Dict[str, Any]] = None, context: Dict[str, Any] = {}) -> AgentResponse:
    """
    Handle operational requests.
    Supports: Account Creation (requires 'username', 'role')
    """
    # 1. Restore State
    state = OpsAgentState(**agent_state) if agent_state else OpsAgentState()
    
    response_content = ""
    result_type = RESULT_TYPE_CONTINUE
    
    # 2. Logic based on Phase
    if state.phase == "COLLECTING":
        # Simple extraction logic (Mocking NLP extraction)
        if "account" in query or "create" in query:
            state.task_type = "create_account"
            
        if "admin" in query:
            state.collected_params["role"] = "admin"
        if "user" in query:
            state.collected_params["role"] = "user"
            
        # Basic parsing for username (very naive)
        words = query.split()
        for i, w in enumerate(words):
            if w == "for" and i + 1 < len(words):
                state.collected_params["username"] = words[i+1]
        
        # Check requirements
        required = ["username", "role"]
        state.missing_params = [p for p in required if p not in state.collected_params]
        
        if state.missing_params:
            response_content = f"I need the following parameters: {', '.join(state.missing_params)}"
            result_type = RESULT_TYPE_CONTINUE
        else:
            state.execution_plan = f"Create account for {state.collected_params['username']} with role {state.collected_params['role']}"
            state.phase = "CONFIRMING"
            response_content = f"Plan created: {state.execution_plan}. Do you approve? (yes/no)"
            result_type = RESULT_TYPE_CONTINUE
            
    elif state.phase == "CONFIRMING":
        if "yes" in query.lower():
            response_content = {"plan": state.execution_plan, "status": "APPROVED"}
            result_type = RESULT_TYPE_HANDOFF
            state.phase = "COMPLETED"
        elif "no" in query.lower():
            state.phase = "COLLECTING"
            state.collected_params = {} # Reset
            response_content = "Plan cancelled. Please state your request again."
            result_type = RESULT_TYPE_CONTINUE
        else:
            response_content = "Please answer yes or no."
            result_type = RESULT_TYPE_CONTINUE
            
    return AgentResponse(
        agent_name="OpsAgent",
        result_type=result_type,
        content=response_content,
        confidence=1.0,
        agent_state=state.dict()
    )
