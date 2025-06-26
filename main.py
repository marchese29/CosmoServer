import boto3
from fastapi import FastAPI
from pydantic import BaseModel
from strands import Agent
from strands.models import BedrockModel


class HelloResponse(BaseModel):
    """Response from the hello endpoint"""

    name: str
    anagram: str


app = FastAPI()
session = boto3.Session(profile_name="cosmo")
bedrock_model = BedrockModel(
    model_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0", boto_session=session
)


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
