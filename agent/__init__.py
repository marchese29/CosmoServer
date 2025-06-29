import os

import boto3
from strands import Agent
from strands.models import BedrockModel

from mcps import MCPServer
from util import EnvKey, InitItem, get_env_required

# The agent instance
_AGENT: InitItem[Agent] = InitItem()


def _system_prompt() -> str:
    """The system prompt for Cosmo"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_path = os.path.join(current_dir, "main_prompt.txt")
    with open(prompt_path) as f:
        return f.read()


def initialize_agent():
    """Initializes the agent for Cosmo"""
    session = boto3.Session()
    bedrock_model = BedrockModel(
        model_id=get_env_required(EnvKey.MODEL_ID), boto_session=session
    )
    _AGENT.initialize(
        Agent(  # type: ignore
            model=bedrock_model,
            tools=MCPServer.HUBITAT.tools() + MCPServer.RULES.tools(),
            max_parallel_tools=4,
            system_prompt=_system_prompt(),
        )
    )


def get_agent() -> Agent:
    """Gets the agent instance"""
    return _AGENT.get()
