from google.adk.agents import LlmAgent
from .prompts import SYSTEM_INSTRUCTION
from .tools import FACILITATOR_TOOLS

def create_facilitator_agent(model_name: str = "gemini-2.0-flash-exp") -> LlmAgent:
    """
    Creates and returns the Facilitator LlmAgent.
    """
    return LlmAgent(
        name="facilitator",
        model=model_name,
        instruction=SYSTEM_INSTRUCTION,
        tools=FACILITATOR_TOOLS,
        description="A facilitator agent that orchestrates the conversation and delegates tasks to specialists."
    )
