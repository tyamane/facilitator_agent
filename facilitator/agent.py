from google.adk.agents import Agent
from facilitator.custom_agent import FacilitatorAgent

def create_facilitator_agent(model_name: str = "gemini-2.0-flash-exp") -> Agent:
    """
    Creates and returns the Custom Facilitator Agent.
    """
    return FacilitatorAgent(model_name=model_name)

# Expose the agent for ADK CLI
root_agent = create_facilitator_agent()

