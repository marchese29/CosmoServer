import boto3
from strands import Agent
from strands.models import BedrockModel


def main():
    session = boto3.Session(profile_name="cosmo")
    bedrock_model = BedrockModel(
        model_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0", boto_session=session
    )

    agent = Agent(model=bedrock_model)
    agent("Tell me about Amazon Bedrock.")
    print()


if __name__ == "__main__":
    main()
