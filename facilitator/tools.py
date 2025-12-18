from specialists.search_agent.tools import call_search_agent
from specialists.ops_agent.tools import call_ops_agent

# List of tools available to the Facilitator
FACILITATOR_TOOLS = [
    call_search_agent,
    call_ops_agent
]
