import os

import boto3
from strands import Agent
from strands.models import BedrockModel

from ..mcps import MCPServer
from ..util import EnvKey, InitItem, get_env_required

# The agent instances
_SIMPLE_AGENT: InitItem[Agent] = InitItem()
_COMPLEX_AGENT: InitItem[Agent] = InitItem()


def _simple_system_prompt() -> str:
    """The system prompt for the simple Cosmo agent"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_path = os.path.join(current_dir, "simple_prompt.txt")
    with open(prompt_path) as f:
        return f.read()


def _complex_system_prompt() -> str:
    """The system prompt for the complex Cosmo agent"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_path = os.path.join(current_dir, "complex_prompt.txt")
    with open(prompt_path) as f:
        return f.read()


def initialize_agents():
    """Initializes both simple and complex agents for Cosmo"""
    session = boto3.Session()

    # Initialize simple agent with cheaper model and only Hubitat tools
    simple_model = BedrockModel(
        model_id=get_env_required(EnvKey.SIMPLE_MODEL_ID), boto_session=session
    )
    _SIMPLE_AGENT.initialize(
        Agent(
            model=simple_model,
            tools=MCPServer.HUBITAT.tools(),
            system_prompt=_simple_system_prompt(),
        )
    )

    # Initialize complex agent with full model and all tools
    complex_model = BedrockModel(
        model_id=get_env_required(EnvKey.MODEL_ID), boto_session=session
    )
    _COMPLEX_AGENT.initialize(
        Agent(
            model=complex_model,
            tools=MCPServer.HUBITAT.tools() + MCPServer.RULES.tools(),
            system_prompt=_complex_system_prompt(),
        )
    )


def get_simple_agent() -> Agent:
    """Gets the simple agent instance for basic home control"""
    return _SIMPLE_AGENT.get()


def get_complex_agent() -> Agent:
    """Gets the complex agent instance for rules and advanced automation"""
    return _COMPLEX_AGENT.get()
