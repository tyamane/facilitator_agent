from typing import Dict, Any, Optional
from ...models.schema import AgentResponse, RESULT_TYPE_ANSWER

def call_search_agent(query: str, agent_state: Optional[Dict[str, Any]] = None, context: Dict[str, Any] = {}) -> AgentResponse:
    """
    Search for information in the FAQ database.
    """
    # Mock implementation
    return AgentResponse(
        agent_name="SearchAgent",
        result_type=RESULT_TYPE_ANSWER,
        content=f"Stub search result for: {query}",
        confidence=0.8
    )
