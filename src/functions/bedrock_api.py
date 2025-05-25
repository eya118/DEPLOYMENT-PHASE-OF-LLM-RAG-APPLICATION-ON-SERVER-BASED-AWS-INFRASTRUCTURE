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

    def get_prompt_override_config(self):
        config = {
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
                            "text": """Human:
<question>{{question}}</question>

<thinking>Réflexion sur la bonne formulation du message.</thinking>
<action>Générer l'e‑mail client basé sur les instructions métier et le contexte</action>
<action_input>Contenu RAG, données JSON sur les anomalies</action_input>
<observation>Email généré</observation>

<thinking>L’e‑mail est rédigé selon les règles définies.</thinking>
<answer>Email final prêt à être envoyé au client.</answer>

<context>
{{instruction}}

### Modèle d’e‑mail (basé sur les documents PDF RAG)  
{{RETRIEVED_CONTEXT}}

### Données disponibles  
{{ANOMALY_CONTEXT}}
</context>

Assistant:"""
                        }
                    }
                }
            ]
        }
        return config

    def invoke_agent(self, instruction, question, retrieved_context, anomaly_context):
        session_id = str(uuid.uuid4())
        completion = ""
        citations = []

        prompt_input = {
            "instruction": instruction,
            "question": question,
            "RETRIEVED_CONTEXT": retrieved_context,
            "ANOMALY_CONTEXT": anomaly_context
        }

        try:
            logger.info(f"Invoking agent {self.agent_id} with alias {self.agent_alias_id}")
            response = self.agents_runtime_client.invoke_agent(
                agentId=self.agent_id,
                agentAliasId=self.agent_alias_id,
                sessionId=session_id,
                inputText=json.dumps(prompt_input),
                promptOverrideConfiguration=self.get_prompt_override_config()
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

        question = body.get("prompt", "")
        instruction = body.get("instruction", "")
        retrieved_context = body.get("RETRIEVED_CONTEXT", "")
        anomaly_context = body.get("ANOMALY_CONTEXT", "")

        if not question:
            return {"statusCode": 400, "body": "Missing 'prompt' in the input."}

        invoker = AgentInvoker()
        result = invoker.invoke_agent(instruction, question, retrieved_context, anomaly_context)

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
