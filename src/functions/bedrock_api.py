import os
import uuid
import json
import boto3
import logging
import time
import sys
from botocore.exceptions import ClientError
from langchain.prompts import PromptTemplate

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Define the LangChain prompt template here
PROMPT_TEMPLATE = """
{
  "system": "Vous êtes un expert en communication client. Voici les variables fournies : \\n- {retrieved_context} \\n- {anomaly_context}",
  "messages": [
    {{
      "role": "user",
      "content": [
        {{
          "text": "Merci, pouvez-vous générer l'e-mail maintenant ?"
        }}
      ]
    }}
  ]
}
"""

class AgentInvoker:
    def __init__(self):
        self.agents_runtime_client = boto3.client("bedrock-agent-runtime")
        self.agents_client = boto3.client("bedrock-agent")
        self.full_alias = os.environ["AGENT_ALIAS_ID"]
        self.agent_id, self.agent_alias_id = self.full_alias.split("|")

    def build_dynamic_prompt(self, retrieved_context, anomaly_context):
        # Use LangChain PromptTemplate to inject variables
        prompt = PromptTemplate.from_template(PROMPT_TEMPLATE)
        return prompt.format(
            retrieved_context=retrieved_context or "AUCUN CONTEXTE",
            anomaly_context=anomaly_context or "AUCUN CONTEXTE"
        )

    def update_agent_with_prompt(self, retrieved_context, anomaly_context):
        logger.info("Updating agent with dynamic prompt...")

        dynamic_prompt = self.build_dynamic_prompt(retrieved_context, anomaly_context)

        instruction = "you are a helpful assistant..."

        self.agents_client.update_agent(
            agentId=self.agent_id,
            agentName="test-bedrock-agent-v3",
            foundationModel="us.meta.llama3-1-8b-instruct-v1:0",
            agentResourceRoleArn="arn:aws:iam::539279406888:role/demo-bedrock-second-stack-AmazonBedrockExecutionRol-curBRrwP1l8T",
            promptOverrideConfiguration={
                "promptConfigurations": [
                    {
                        "promptType": "ORCHESTRATION",
                        "promptState": "ENABLED",
                        "promptCreationMode": "OVERRIDDEN",
                        "parserMode": "DEFAULT",
                        "inferenceConfiguration": {
                            "maximumLength": 2048,
                            "stopSequences": ["Human:"],
                            "temperature": 0.0,
                            "topK": 1,
                            "topP": 1.0
                        },
                        "basePromptTemplate": dynamic_prompt
                    }
                ]
            },
            instruction=instruction
        )

    def sleep_for_a_while(self, seconds, tick=12):
        spinner_parts = "|/-\\"
        wait_count = 0
        while wait_count < seconds:
            for frame in range(tick):
                sys.stdout.write(f"\r{spinner_parts[frame % len(spinner_parts)]}")
                sys.stdout.flush()
                time.sleep(1 / tick)
            wait_count += 1
        sys.stdout.write("\r")
        sys.stdout.flush()

    def create_agent_version(self):
        logger.info("Creating agent version...")
        version = self.agents_client.prepare_agent(agentId=self.agent_id)["agentVersion"]

        # Wait until the agent is prepared
        while True:
            agent_status = self.agents_client.get_agent(agentId=self.agent_id)["agent"]["agentStatus"]
            if agent_status == "PREPARED":
                break
            logger.info(f"Waiting for agent to be prepared... Current status: {agent_status}")
            self.sleep_for_a_while(5)

        return version

    def update_alias(self, version):
        logger.info("Updating agent alias to new version...")
        self.agents_client.update_agent_alias(
            agentId=self.agent_id,
            agentAliasId=self.agent_alias_id,
            agentAliasName="default",
            routingConfiguration=[
                {"agentVersion": version}  # Use the actual version
            ]
        )

    def invoke_agent(self, question):
        session_id = str(uuid.uuid4())
        completion = ""
        citations = []

        try:
            logger.info(f"Invoking agent {self.agent_id} with alias {self.agent_alias_id}")
            response = self.agents_runtime_client.invoke_agent(
                agentId=self.agent_id,
                agentAliasId=self.agent_alias_id,
                sessionId=session_id,
                inputText=question
            )

            for event in response.get("completion", []):
                if "chunk" in event:
                    completion += event["chunk"]["bytes"].decode()
                elif "trace" in event:
                    trace = event["trace"]
                    logger.info(f"Trace: {json.dumps(trace)}")

                    if trace.get("type") == "KNOWLEDGE_BASE":
                        kb_output = trace.get("knowledgeBaseLookupOutput", {})
                        references = kb_output.get("retrievedReferences", [])
                        for ref in references:
                            source = ref.get("location", {}).get("s3Location", {}).get("uri", "Unknown source")
                            page = ref.get("metadata", {}).get("x-amz-bedrock-kb-document-page-number", "N/A")
                            citations.append({
                                "source": source,
                                "page": page
                            })

            return {
                "answer": completion,
                "citations": citations
            }

        except ClientError as e:
            logger.error(f"Couldn't invoke agent: {e}")
            raise


def lambda_handler(event, context):
    try:
        if "body" in event:
            body = json.loads(event["body"])
        else:
            body = event

        retrieved_context = body.get("retrieved_context", "")
        anomaly_context = body.get("anomaly_context", "")
        question = body.get("question", "Merci, pouvez-vous générer l'e-mail maintenant ?")

        invoker = AgentInvoker()
        invoker.update_agent_with_prompt(retrieved_context, anomaly_context)
        version = invoker.create_agent_version()
        invoker.update_alias(version)

        logger.info("Sending final question to agent...")
        result = invoker.invoke_agent(question)

        return {
            "statusCode": 200,
            "body": json.dumps(result)
        }

    except Exception as e:
        logger.error(f"Error in Lambda handler: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
