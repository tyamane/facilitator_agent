import logging
import uvicorn
from google.adk.apps import App
from facilitator_agent.facilitator.agent import create_facilitator_agent

# Configure Logging
logging.basicConfig(level=logging.INFO)

# Create the Agent
facilitator_agent = create_facilitator_agent()

# Create the App
app = App(
    name="facilitator_app",
    root_agent=facilitator_agent,
    description="Slack Facilitator Agent App"
)

if __name__ == "__main__":
    # For local testing via python main.py
    # Ideally use 'adk web .' or 'adk run .'
    print("Please use 'adk web .' to run this agent.")
