import os
import uuid
import json
import boto3
import logging
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

PROMPT_TEXT = """Human:
<question>{{question}}</question>

<thinking>Réflexion sur la bonne formulation du message.</thinking>
<action>Générer l'e‑mail client basé sur les instructions métier et le contexte</action>
<action_input>Contenu RAG, données JSON sur les anomalies</action_input>
<observation>Email généré</observation>

<thinking>L’e‑mail est rédigé selon les règles définies.</thinking>
<answer>Email final prêt à être envoyé au client.</answer>

<context>
{{instruction}}

### Modèle d’email (basé sur les documents PDF RAG)  
{{RETRIEVED_CONTEXT}}

### Données disponibles  
{{ANOMALY_CONTEXT}}
</context>

Assistant:"""

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
                    "templateType": "TEXT",
                    "promptType": "ORCHESTRATION",
                    "promptState": "ENABLED",
                    "promptCreationMode": "OVERRIDDEN",
                    "parserMode": "OVERRIDDEN",
                    "inferenceConfiguration": {
                        "maximumLength": 2048,
                        "stopSequences": ["Human:"],
                        "temperature": 0.0,
                        "topK": 1,
                        "topP": 1.0
                    },
                    "templateConfiguration": {
                        "text": {
                            "inputVariables": [
                                {"name": "instruction"},
                                {"name": "question"},
                                {"name": "RETRIEVED_CONTEXT"},
                                {"name": "ANOMALY_CONTEXT"}
                            ],
                            "text": PROMPT_TEXT
                        }
                    }
                }
            ]
        }

    def update_agent_with_prompt(self):
        logger.info("Updating agent with prompt override configuration...")
        self.agents_client.update_agent(
            agentId=self.agent_id,
            promptOverrideConfiguration=self.get_prompt_override_config()
        )

    def create_agent_version(self):
        logger.info("Creating agent version...")
        return self.agents_client.create_agent_version(agentId=self.agent_id)["agentVersion"]

    def update_alias(self, version):
        logger.info("Updating agent alias to new version...")
        self.agents_client.update_agent_alias(
            agentId=self.agent_id,
            agentAliasId=self.agent_alias_id,
            agentVersion=version
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
        invoker.update_alias(version)

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
