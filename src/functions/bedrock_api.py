import os
import uuid
import json
import boto3
import logging
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

BASE_PROMPT_TEMPLATE = json.dumps({

    "system": """{{instruction}}
You are a helpful assistant called eya  with tool/function calling capabilities.

Given the following tools/functions, please respond with a JSON for a tool/function call with its proper arguments that best answers the given prompt. Respond in the format {"name": tool/function name, "parameters": dictionary of argument name and its value}. Do not use variables.

If you need an input parameter for a tool/function, ask the user to provide that parameter before making a call to that function/tool. You will have access to a separate tool/function that you MUST use to ask questions to the user{{respond_to_user_follow_up}}. Never call a tool/function before gathering all parameters required for the tool/function call.

It is your responsibility to pick the correct tools/functions that are going to help you answer the user questions. Continue using the provided tools/functions until the initial user request is perfectly addressed. If you do not have the necessary tools/functions to address the initial request, call it out and terminate conversation.

When you receive a tool/function call response, use the output to format an answer to the original user question.

Provide your final answer to the user's question {{final_answer_guideline}}{{respond_to_user_final_answer_guideline}}.
{{knowledge_base_additional_guideline}}
{{respond_to_user_knowledge_base_additional_guideline}}
{{memory_guideline}}
{{memory_content}}
{{memory_action_guideline}}
{{prompt_session_attributes}}""",
    "messages": [
        {
            "role": "user",
            "content": [
                {
                    "text": "{{question}}"
                }
            ]
        },
        {
            "role": "assistant",
            "content": [
                {
                    "text": "{{agent_scratchpad}}"
                }
            ]
        }
    ]
})


class AgentInvoker:
    def __init__(self):
        self.agents_runtime_client = boto3.client("bedrock-agent-runtime")
        self.agents_client = boto3.client("bedrock-agent")
        self.full_alias = os.environ["AGENT_ALIAS_ID"]
        self.agent_id, self.agent_alias_id = self.full_alias.split("|")

    def get_prompt_override_config(self):
        return {
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
                    "basePromptTemplate": BASE_PROMPT_TEMPLATE
                }]
        }

    def update_agent_with_prompt(self):
        logger.info("Updating agent with prompt override configuration...")
        self.agents_client.update_agent(
            agentId=self.agent_id,
            agentName="test-bedrock-agent-v3",
            foundationModel="us.meta.llama3-1-8b-instruct-v1:0",
            agentResourceRoleArn="arn:aws:iam::539279406888:role/demo-bedrock-second-stack-AmazonBedrockExecutionRol-curBRrwP1l8T",
            promptOverrideConfiguration=self.get_prompt_override_config()
        )

    def create_agent_version(self):
        logger.info("Creating agent version...")
        return self.agents_client.prepare_agent(agentId=self.agent_id)["agentVersion"]

    def update_alias(self, version):
        logger.info("Updating agent alias to new version...")
        self.agents_client.update_agent_alias(
            agentId=self.agent_id,
            agentAliasId=self.agent_alias_id,
            agentAliasName="dev-alias"
        )

    def invoke_agent(self, prompt):
        session_id = str(uuid.uuid4())
        completion = ""
        citations = []

        try:
            logger.info(f"Invoking agent {self.agent_id} with alias {self.agent_alias_id}")
            response = self.agents_runtime_client.invoke_agent(
                agentId=self.agent_id,
                agentAliasId=self.agent_alias_id,
                sessionId=session_id,
                inputText=prompt,
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

        prompt = body.get("prompt", "")
        if not prompt:
            return {"statusCode": 400, "body": "Missing 'prompt' in the input."}

        invoker = AgentInvoker()
        invoker.update_agent_with_prompt()
        version = invoker.create_agent_version()
        # invoker.update_alias(version)

        result = invoker.invoke_agent(prompt)

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
