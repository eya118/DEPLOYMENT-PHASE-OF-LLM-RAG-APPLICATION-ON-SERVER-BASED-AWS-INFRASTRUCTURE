import os
import uuid
import json
import boto3
import logging
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class AgentInvoker:
    def __init__(self):
        self.agents_runtime_client = boto3.client("bedrock-agent-runtime")
        self.full_alias = os.environ["AGENT_ALIAS_ID"]
        self.agent_id, self.agent_alias_id = self.full_alias.split("|")

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
