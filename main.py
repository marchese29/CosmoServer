import logging
from contextlib import ExitStack, asynccontextmanager
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from pydantic import BaseModel
from strands import Agent

import util
from agent import get_agent, initialize_agent
from mcps import MCPServer
from util import EnvKey

logger = logging.getLogger(__name__)


class CosmoRequest(BaseModel):
    """Request to the Cosmo server"""

    message: str


class HelloResponse(BaseModel):
    """Response from the hello endpoint"""

    name: str
    anagram: str


load_dotenv()


@asynccontextmanager
async def lifespan(fastapi: FastAPI):
    with ExitStack() as stack:
        # Initialize the MCP Server processes
        for server in MCPServer:
            stack.enter_context(server.client())  # type: ignore

        # Initialize the agent
        initialize_agent()

        # Setup is complete
        yield


app = FastAPI(lifespan=lifespan)


@app.get("/")
def root() -> str:
    return "🐇🤖 Cosmo Server"


@app.get("/hello/{first_name}/{middle_name}/{last_name}")
def anagram_greeter(first_name: str, middle_name: str, last_name: str) -> HelloResponse:
    agent = Agent(model=util.get_env_required(EnvKey.MODEL_ID))
    return agent.structured_output(
        HelloResponse,
        f"Come up with a fun anagram for '{first_name} {middle_name} {last_name}'",
    )


@app.post("/user_message")
async def handle_user_message(
    request: CosmoRequest, agent: Annotated[Agent, Depends(get_agent)]
) -> str:
    """Endpoint which handles messages from the user."""
    return agent(request.message).message["content"][0]["text"]  # type: ignore
