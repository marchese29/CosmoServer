import logging
import os
from collections.abc import Generator
from typing import Annotated

import boto3
from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from mcp import StdioServerParameters, stdio_client
from pydantic import BaseModel
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient

import util

logger = logging.getLogger(__name__)


class HelloResponse(BaseModel):
    """Response from the hello endpoint"""

    name: str
    anagram: str


load_dotenv()

app = FastAPI()
session = boto3.Session()
bedrock_model = BedrockModel(
    model_id=util.get_env_required("DEFAULT_BEDROCK_MODEL_ID"), boto_session=session
)


def system_prompt() -> str:
    """The system prompt for Cosmo"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_path = os.path.join(current_dir, "main_prompt.txt")
    with open(prompt_path) as f:
        return f.read()


def hubitat_mcp() -> Generator[MCPClient]:
    """Supplies the hubitat MCP Client"""
    with MCPClient(
        lambda: stdio_client(
            StdioServerParameters(
                command="uv",
                args=[
                    "run",
                    "--project",
                    "/Users/daniel/Workplace/HubitatAutomationMCP",
                    "fastmcp",
                    "run",
                    "/Users/daniel/Workplace/HubitatAutomationMCP/main.py",
                ],
                env={
                    "HE_ADDRESS": util.get_env_required("HE_ADDRESS"),
                    "HE_APP_ID": util.get_env_required("HE_APP_ID"),
                    "HE_ACCESS_TOKEN": util.get_env_required("HE_ACCESS_TOKEN"),
                },
            )
        )
    ) as client:
        yield client


def hubitat_rules_mcp() -> Generator[MCPClient]:
    """Supplies the rules MCP Client"""
    with MCPClient(
        lambda: stdio_client(
            StdioServerParameters(
                command="uv",
                args=[
                    "run",
                    "--project",
                    "/Users/daniel/Workplace/HubitatRulesMCP",
                    "fastmcp",
                    "run",
                    "/Users/daniel/Workplace/HubitatRulesMCP/main.py",
                ],
                env={
                    "HE_ADDRESS": util.get_env_required("HE_ADDRESS"),
                    "HE_APP_ID": util.get_env_required("HE_APP_ID"),
                    "HE_ACCESS_TOKEN": util.get_env_required("HE_ACCESS_TOKEN"),
                },
            )
        )
    ) as client:
        yield client


@app.get("/")
def root() -> str:
    return "🤖 Cosmo Server"


@app.get("/hello/{first_name}/{middle_name}/{last_name}")
def anagram_greeter(first_name: str, middle_name: str, last_name: str) -> HelloResponse:
    agent = Agent(model=bedrock_model)
    return agent.structured_output(
        HelloResponse,
        f"Come up with a fun anagram for '{first_name} {middle_name} {last_name}'",
    )


@app.get("/user_message")
async def handle_user_message(
    prompt: Annotated[str, Depends(system_prompt)],
    hubitat_mcp: Annotated[MCPClient, Depends(hubitat_mcp)],
    rules_mcp: Annotated[MCPClient, Depends(hubitat_rules_mcp)],
):
    """Endpoint which handles messages from the user."""
    agent = Agent(
        model=bedrock_model,
        tools=hubitat_mcp.list_tools_sync() + rules_mcp.list_tools_sync(),
        system_prompt=prompt,
    )
    return agent("Tell me about the layout of the house and the devices in it")
