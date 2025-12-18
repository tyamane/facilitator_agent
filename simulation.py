import logging
import asyncio
import os
from google.genai import types
from google.adk.runners import Runner
from google.adk.apps import App
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.sessions.session import Session
from facilitator.custom_agent import FacilitatorAgent
from models.schema import ThreadState

# Configure logging
logging.basicConfig(level=logging.INFO)

async def run_simulation():
    print("=== Starting Simulation: Custom Facilitator Agent (Sticky Session) ===\n")
    
    # 1. Setup ADK Components
    agent = FacilitatorAgent()
    session_service = InMemorySessionService()
    
    # Create App to wrap agent
    app = App(
        name="facilitator_app",
        root_agent=agent
    )
    
    # Create Session explicitly to manipulate state
    session = await session_service.create_session(app_name="facilitator_app", user_id="sim_user")
    print(f"Session Created: {session.id}")
    
    # 2. Setup Sticky Session state manually
    print("[Setup] Force Routing to OpsAgent...")
    thread_state = ThreadState(
        status="IN_PROGRESS", 
        active_agent="OpsAgent", 
        goal="Create Account",
        agent_state={} 
    )
    session.state["thread_state"] = thread_state.dict()
    
    # HACK: Manually sync session to InMemorySessionService storage
    # Because get_session might return a copy, or we modified a copy.
    if hasattr(session_service, "sessions"):
        session_service.sessions["facilitator_app"]["sim_user"][session.id] = session
        print("[Setup] Synced session state to InMemory Service.")
    
    # 3. User Input (Phase 1: Collecting)
    user_input_1 = "Create account for tyamane role admin"
    print(f"User: {user_input_1}")
    runner = Runner(app=app, session_service=session_service)
    
    # Run 1
    response_text_1 = ""
    # Runner.run_async takes new_message (Content)
    content_1 = types.Content(parts=[types.Part(text=user_input_1)])
    
    async for event in runner.run_async(session_id=session.id, user_id="sim_user", new_message=content_1):
        if event.content and event.content.parts:
            part = event.content.parts[0]
            if part.text:
                response_text_1 += part.text
        elif event.error_message:
             print(f"Error Event: {event.error_message}")
             
    print(f"System: {response_text_1}")
    
    # Debug State
    ts = session.state["thread_state"]
    print(f"[Debug] Active Agent: {ts['active_agent']}")
    print(f"[Debug] Agent State: {ts['agent_state']}")
    print("-" * 20)
    
    # 4. User Input (Phase 2: Confirming)
    user_input_2 = "yes, please"
    print(f"User: {user_input_2}")
    
    response_text_2 = ""
    content_2 = types.Content(parts=[types.Part(text=user_input_2)])
    
    async for event in runner.run_async(session_id=session.id, user_id="sim_user", new_message=content_2):
        if event.content and event.content.parts:
            part = event.content.parts[0]
            if part.text:
                response_text_2 += part.text

            
    print(f"System: {response_text_2}")
    
    # Debug State (Should be HANDOFF)
    ts = session.state["thread_state"]
    print(f"[Debug] Active Agent: {ts['active_agent']}")
    
    if "HANDOFF" in response_text_2:
        print("\nSUCCESS: Flow completed with HANDOFF via Custom Agent.")
    else:
        print("\nFAILURE: Did not handoff.")

if __name__ == "__main__":
    asyncio.run(run_simulation())
