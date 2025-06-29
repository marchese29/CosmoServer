import logging
from contextlib import ExitStack, asynccontextmanager
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from strands import Agent

import util
from agent import get_agent, initialize_agent
from mcps import MCPServer
from models.api import CosmoRequest, CosmoResponse
from util import EnvKey

load_dotenv()
logger = logging.getLogger(__name__)


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
def anagram_greeter(first_name: str, middle_name: str, last_name: str) -> str:
    agent = Agent(model=util.get_env_required(EnvKey.MODEL_ID))
    resp = agent(
        f"Come up with a fun anagram for '{first_name} {middle_name} {last_name}' "
        "Only use letters the same number of times they appear in the name"
    )
    return resp.message["content"][0]["text"]  # type: ignore


@app.post("/user_message")
async def handle_user_message(
    request: CosmoRequest, agent: Annotated[Agent, Depends(get_agent)]
) -> CosmoResponse:
    """Endpoint which handles messages from the user."""
    agent(request.message)

    # Use the summarizer agent to decide how to respond to the user based on the most
    # recent conversation turn
    return agent.structured_output(
        CosmoResponse,
        (
            "Respond to the user by either playing an acknowledgement sound, or "
            "providint the text to read aloud to them.  This will be the first thing "
            "they hear since their initial request.  If their request is simple or your "
            "response is very short, then simply acknowledge, otherwise give them an "
            "appropriate answer.  The user likely doesn't care to hear about your "
            "thinking process or which tools you used.  In any case, you may include "
            "metadata in the response for your own future reference if you want."
        ),
    )
