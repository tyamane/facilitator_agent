from typing import Dict, Any, Optional
from google.adk.sessions.session import Session
from models.schema import ThreadState, RESULT_TYPE_CONTINUE, RESULT_TYPE_HANDOFF, RESULT_TYPE_ANSWER, AgentResponse
from facilitator.agent import create_facilitator_agent
from specialists.search_agent.tools import call_search_agent
from specialists.ops_agent.tools import call_ops_agent

# Tool Registry for Sticky Session calling
TOOL_REGISTRY = {
    "SearchAgent": call_search_agent,
    "OpsAgent": call_ops_agent
}

class FacilitatorRuntime:
    def __init__(self):
        self.facilitator = create_facilitator_agent()
        # In a real app, this would be initialized per request or injected
        
    def handle_message(self, user_message: str, session: Session) -> str:
        """
        Main Loop: Handles a user message and returns the system response.
        """
        # 1. Load or Initialize ThreadState
        state_dict = session.state.get("thread_state", {})
        thread_state = ThreadState(**state_dict) if state_dict else ThreadState(status="OPEN")
        
        response_text = ""

        # 2. Check for Sticky Session (Active Agent)
        if thread_state.active_agent and thread_state.active_agent in TOOL_REGISTRY:
            # Bypass Facilitator LLM (Sticky Routing)
            agent_func = TOOL_REGISTRY[thread_state.active_agent]
            
            # Prepare context
            context = {
                "user_id": "user_mock", # TODO: Get from session/request
                "thread_history_summary": thread_state.context_summary 
            }
            
            # Call the tool directly
            # Note: We need to parse previous agent_state if any
            agent_metrics = agent_func(
                query=user_message,
                agent_state=thread_state.agent_state,
                context=context
            )
            
            # Process Result
            response_text = self._process_agent_response(agent_metrics, thread_state, session)
            
        else:
            # 3. Standard Flow: Call Facilitator LLM via ADK Runner
            # Note: For production, we should reuse a single Runner instance and manage Request/Session properly.
            # This is a simplified synchronous wrapper for demonstration.
            from google.adk.runtime import Runner
            from google.adk.apps import App
            
            # Re-create app/runner to ensure context (in a real server, this is done differently)
            app = App(name="fac_app", root_agent=self.facilitator)
            runner = Runner(app=app)
            
            # Mocking InvocationContext for synchronous run if needed, but runner.run_async is standard.
            # Since ADK is async, and we are in a script, we might need asyncio.run
            # For this 'design' verification, we assume a synchronous helper or just print 'Routing via LLM...'.
            
            # Placeholder for actual LLM call:
            response_text = "Facilitator (LLM) would decide routing here. For simulation, please invoke specific agents."
            # In a real implementation:
            # result = runner.run(input=user_message, session_id=session.session_id)
            # response_text = result.output
            
        return response_text

    def _process_agent_response(self, response: AgentResponse, thread_state: ThreadState, session: Session) -> str:
        """
        Updates state based on AgentResponse.
        """
        result_text = ""
        
        if response.result_type == RESULT_TYPE_CONTINUE:
            thread_state.active_agent = response.agent_name
            thread_state.agent_state = response.agent_state
            result_text = str(response.content)
            
        elif response.result_type == RESULT_TYPE_ANSWER:
            thread_state.active_agent = None
            thread_state.agent_state = None
            result_text = str(response.content)
            
        elif response.result_type == RESULT_TYPE_HANDOFF:
            # Handoff logic: Clear current agent, set intermediate state if needed, 
            # or immediately route to next if hinted.
            # For now, we clear active agent and let Facilitator route next time OR auto-route.
            thread_state.active_agent = None # Reset sticky
            # Ideally we pass this data back to Facilitator to decide next step
            result_text = f"HANDOFF: {response.content}"
        
        # Save state
        session.state["thread_state"] = thread_state.dict()
        return result_text
