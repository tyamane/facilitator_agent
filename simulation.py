import logging
import uuid
from google.adk.sessions.session import Session

# Use simpler in-memory session for simulation if possible, or mock
# ADK uses SQLite by default.

# Mocking Session object for simplicity since we are testing Runtime logic
class MockState:
    def __init__(self):
        self.data = {}
    def get(self, key, default=None):
        return self.data.get(key, default)
    def __setitem__(self, key, value):
        self.data[key] = value
    def __getitem__(self, key):
        return self.data[key]

class MockSession:
    def __init__(self):
        self.state = MockState()
        self.session_id = str(uuid.uuid4())

# Import Runtime
from facilitator_agent.facilitator.runtime import FacilitatorRuntime
from facilitator_agent.models.schema import ThreadState

def run_simulation():
    print("=== Starting Simulation: Ops Agent Flow ===\n")
    
    runtime = FacilitatorRuntime()
    session = MockSession()
    
    # 1. User initiates request
    # To bypass LLM routing, we forcefully set the active agent to 'OpsAgent' 
    # as if the Facilitator LLM had already decided.
    print("[Setup] Force Routing to OpsAgent...")
    thread_state = ThreadState(
        status="IN_PROGRESS", 
        active_agent="OpsAgent", 
        goal="Create Account",
        agent_state={} # Initial empty state
    )
    session.state["thread_state"] = thread_state.dict()
    
    user_input_1 = "Create account for tyamane role admin"
    print(f"User: {user_input_1}")
    
    # Run
    response_1 = runtime.handle_message(user_input_1, session)
    print(f"System: {response_1}")
    
    # Check State
    ts = session.state["thread_state"]
    print(f"[Debug] Active Agent: {ts['active_agent']}")
    print(f"[Debug] Agent State: {ts['agent_state']}")
    
    print("-" * 20)
    
    # 2. User confirms
    # Should automatically route to OpsAgent due to sticky session
    user_input_2 = "yes, please"
    print(f"User: {user_input_2}")
    
    response_2 = runtime.handle_message(user_input_2, session)
    print(f"System: {response_2}")
    
    # Check State (Should be HANDOFF -> cleared active agent)
    ts = session.state["thread_state"]
    print(f"[Debug] Active Agent: {ts['active_agent']}")
    
    if "HANDOFF" in response_2:
        print("\nSUCCESS: Flow completed with HANDOFF.")
    else:
        print("\nFAILURE: Did not handoff.")

if __name__ == "__main__":
    run_simulation()
