import logging
from contextlib import ExitStack, asynccontextmanager
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from strands import Agent

from agent import get_complex_agent, get_simple_agent, initialize_agents
from mcps import MCPServer
from models.api import CosmoRequest
from util import strip_xml_tags

load_dotenv()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    with ExitStack() as stack:
        # Initialize the MCP Server processes
        for server in MCPServer:
            stack.enter_context(server.client())  # type: ignore

        # Initialize the agents
        initialize_agents()

        # Setup is complete
        yield


app = FastAPI(lifespan=lifespan)


@app.get("/")
def root() -> str:
    return "🐇🤖 Cosmo Server"


@app.get("/hello")
def introduce_cosmo() -> str:
    return (
        "Hello, my name is Cosmo - I am the AI brain of your smart home. I can control "
        "the devices in your smart home, curate scenes, and manage automations."
    )


@app.post("/simple")
async def handle_simple_request(
    request: CosmoRequest, agent: Annotated[Agent, Depends(get_simple_agent)]
) -> str:
    """Endpoint for simple home control requests using only Hubitat MCP."""
    resp = agent(request.message)
    raw_response = resp.message["content"][0]["text"]  # type: ignore
    return strip_xml_tags(raw_response)


@app.post("/complex")
async def handle_complex_request(
    request: CosmoRequest, agent: Annotated[Agent, Depends(get_complex_agent)]
) -> str:
    """Endpoint for complex requests including rules, scenes, and advanced automation."""
    resp = agent(request.message)
    raw_response = resp.message["content"][0]["text"]  # type: ignore
    return strip_xml_tags(raw_response)


########################
# TODO: Direct Control #
########################
