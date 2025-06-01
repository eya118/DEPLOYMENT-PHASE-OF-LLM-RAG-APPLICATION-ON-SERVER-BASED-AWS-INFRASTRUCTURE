import boto3
import os

def lambda_handler(event, context):
    bedrock_client = boto3.client("bedrock-agent")

    agent_name = os.environ["AGENT_NAME"]
    model_id = os.environ["MODEL_ID"]
    agent_role_arn = os.environ["AGENT_ROLE_ARN"]

    response = bedrock_client.create_agent(
        agentName=agent_name,
        foundationModel=model_id,
        instruction=(
            "You are a helpful assistant. You have access to a knowledge base. "
            "Use it to answer every question when possible. Always cite the documents "
            "used in your answer. If you can't find information in the knowledge base, say so. "
            "Do not guess or make up information. Show the source title or file name in your response if available."
        ),
        agentResourceRoleArn=agent_role_arn,
        autoPrepare=True,
        promptOverrideConfiguration={
            "parserMode": "OVERRIDDEN",
            "promptConfigurations": [
                {
                    "promptType": "USER_INPUT",
                    "promptTemplate": "Answer this question strictly using the knowledge base: {input}  then generate the answer in a format of an email and then say thank you",
                    "inferenceConfiguration": {
                        "temperature": 0.7,
                        "topP": 1.0,
                        "maxTokens": 1000
                    }
                }
            ]
        }
    )

    return {
        "statusCode": 200,
        "body": {
            "agentId": response["agent"]["agentId"],
            "status": response["agent"]["agentStatus"]
        }
    }
