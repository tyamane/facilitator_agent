from typing import Dict, Any, Optional, List, AsyncGenerator
import logging
from google.adk.agents import Agent, LlmAgent
from google.adk.sessions.session import Session
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.events.event_actions import EventActions
from google.genai import types

from models.schema import ThreadState, RESULT_TYPE_CONTINUE, RESULT_TYPE_HANDOFF, RESULT_TYPE_ANSWER, AgentResponse
from facilitator.tools import FACILITATOR_TOOLS, call_ops_agent, call_search_agent
from facilitator.prompts import SYSTEM_INSTRUCTION

logger = logging.getLogger(__name__)

# Tool Registry for direct access
TOOL_REGISTRY = {
    "SearchAgent": call_search_agent,
    "OpsAgent": call_ops_agent
}

import contextvars

# ContextVar for thread-safe session access
active_session_var = contextvars.ContextVar("active_session")

class FacilitatorAgent(Agent):
    """
    Custom Facilitator Agent that implements Sticky Session routing.
    """
    llm_router: LlmAgent = None
    
    def __init__(self, model_name: str = "gemini-2.0-flash-exp"):
        super().__init__(name="facilitator")
        
        # The internal LLM agent for routing/decision making
        self.llm_router = LlmAgent(
            name="facilitator_router",
            model=model_name,
            instruction=SYSTEM_INSTRUCTION,
            tools=FACILITATOR_TOOLS,
        )
        # Attach callback (will use ContextVar)
        self.llm_router.after_tool_callback = self._after_tool_callback

    async def _run_async_impl(self, parent_context: InvocationContext) -> AsyncGenerator[Event, None]:
        """
        Main execution loop compatible with ADK Runner.
        """
        session = parent_context.session
        logger.info(f"FacilitatorAgent running for session {session.id}")
        
        # Set ContextVar
        token = active_session_var.set(session)

        try:
            # 1. Load State
            state_dict = session.state.get("thread_state", {})
            thread_state = ThreadState(**state_dict) if state_dict else ThreadState(status="OPEN")
            
            # Extract user text from context
            user_message = ""
            if parent_context.user_content and parent_context.user_content.parts:
                # Assuming text part is at 0 or iterating
                for part in parent_context.user_content.parts:
                    if hasattr(part, "text") and part.text:
                        user_message += part.text
            
            # 2. Sticky Session Check
            if thread_state.active_agent and thread_state.active_agent in TOOL_REGISTRY:
                logger.info(f"Sticky Session Active: Routing to {thread_state.active_agent}")
                
                agent_func = TOOL_REGISTRY[thread_state.active_agent]
                context = {"user_id": "user"} 
                
                try:
                    # Direct Tool Execution
                    agent_metrics = agent_func(
                        query=user_message,
                        agent_state=thread_state.agent_state,
                        context=context
                    )
                    
                    # Process Result
                    response_text = self._process_agent_response(agent_metrics, thread_state, session)
                    
                    # Create State Delta for Event (Keep it for correctness)
                    state_delta = {"session": {"thread_state": thread_state.dict()}}
                    
                    # Manual Sync (Reliable Persistence)
                    if hasattr(parent_context.session_service, "sessions"):
                        service = parent_context.session_service
                        app_name = session.app_name
                        user_id = session.user_id
                        if app_name in service.sessions and user_id in service.sessions[app_name]:
                            service.sessions[app_name][user_id][session.id] = session

                    # Yield Event with Actions
                    yield Event(
                        author="facilitator", 
                        content=types.Content(parts=[types.Part(text=str(response_text))]),
                        actions=EventActions(stateDelta=state_delta)
                    )
                    
                except Exception as e:
                    logger.error(f"Error in sticky tool execution: {e}")
                    thread_state.active_agent = None
                    session.state["thread_state"] = thread_state.dict()
                    yield Event(
                        author="facilitator", 
                        error_message=f"System Error: {str(e)}"
                    )
                
            else:
                # --- STANDARD FLOW: Delegate to LLM Router ---
                logger.info("Standard Flow: Delegating to LLM Router")
                
                # Delegate and yield events from sub-agent
                async for event in self.llm_router.run_async(parent_context):
                    yield event
                    
        finally:
            active_session_var.reset(token)

    async def _after_tool_callback(self, **kwargs):
        """
        Intercepts tool outputs to update session state via ContextVar.
        Manually syncs to SessionService to ensure persistence.
        """
        # Get Session from ContextVar
        session = active_session_var.get(None)
        if not session:
            logger.warning("Callback called but no active session found in ContextVar!")
            return kwargs.get("tool_response")

        tool_response = kwargs.get("tool_response")
        tool_context = kwargs.get("tool_context")
        
        # Logic to process response
        state_dict = session.state.get("thread_state", {})
        thread_state = ThreadState(**state_dict) if state_dict else ThreadState(status="OPEN")
        
        updated = False
        
        # Handle list or single
        outputs = tool_response if isinstance(tool_response, list) else [tool_response]
        
        for output in outputs:
            if isinstance(output, AgentResponse):
                self._process_agent_response(output, thread_state, session)
                updated = True
            elif isinstance(output, dict) and "result_type" in output:
                 try:
                     resp_obj = AgentResponse(**output)
                     self._process_agent_response(resp_obj, thread_state, session)
                     updated = True
                 except:
                     pass
        
        if updated:
            session.state["thread_state"] = thread_state.dict()
            logger.info("Session state updated from callback.")
            
            # Manual Sync to SessionService (HACK for Standard Flow persistence)
            if tool_context and hasattr(tool_context, "session_service"):
                service = tool_context.session_service
                if hasattr(service, "sessions"):
                     # app_name 'facilitator_app' is hardcoded here matching simulation?
                     # Ideally retrieve app_name from session.
                     app_name = session.app_name
                     user_id = session.user_id
                     if app_name in service.sessions and user_id in service.sessions[app_name]:
                         service.sessions[app_name][user_id][session.id] = session

        return tool_response

    def _process_agent_response(self, response: AgentResponse, thread_state: ThreadState, session: Session) -> str:
        # Same logic
        result_text = ""
        if response.result_type == RESULT_TYPE_CONTINUE:
            thread_state.active_agent = response.agent_name
            thread_state.agent_state = response.agent_state
            if isinstance(response.content, dict) and "plan" in response.content:
                 result_text = response.content["plan"] 
            else:
                 result_text = str(response.content)

        elif response.result_type == RESULT_TYPE_ANSWER:
            thread_state.active_agent = None
            thread_state.agent_state = None
            result_text = str(response.content)
            
        elif response.result_type == RESULT_TYPE_HANDOFF:
            thread_state.active_agent = None
            result_text = f"HANDOFF: {response.content}"
        
        session.state["thread_state"] = thread_state.dict()
        return result_text
