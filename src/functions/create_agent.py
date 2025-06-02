def lambda_handler(event, context):
    import os
    import boto3

    bedrock_client = boto3.client("bedrock-agent")

    agent_name = "rag-bedrock-agent-v10"
    model_id = os.environ["MODEL_ID"]
    agent_role_arn = os.environ["AGENT_ROLE_ARN"]
    knowledgebas_id = os.environ["knowledge_base_id"]
    AGENT_ID = os.environ["AGENT_ID"]

    base_prompt_template = """
{
  "system": "Agent Description:\\nYou are a technical assistant that generates email reports based on device information provided in JSON format. You must compare the device information to a knowledge base and generate a professional email with the following format:\\n\\nSubject: <subject of the email>  \\nBody:  \\n<full body of the email>  \\nRecommendations:  \\n- <recommendation 1>  \\n- <recommendation 2>  \\n\\nAlways follow these instructions:\\n- Do not assume any information. All required parameters must come from the User's JSON input or the knowledge base.\\n- If the User's request cannot be served or is unclear, ask clarifying questions.\\n- Before taking action, always generate a Thought within <thinking> </thinking> tags. In the Thought, answer:  \\n  (1) What is the User's goal?  \\n  (2) What information has just been provided?  \\n  (3) What is the best action plan to fulfill the request?  \\n  (4) Are all steps complete? If not, what’s next?  \\n  (5) Which action should I execute next?  \\n  (6) What information is required and where can I get it?  \\n  (7) Do I have everything I need?  \\n- If the request requires calling external APIs, do so and incorporate the data.\\n- When the request is complete, generate the final email response in the specified format.\\n- Do not reveal internal tools or processes.\\n- If a request is not supported, respond with an appropriate message.",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "text": "$question$"
        }
      ]
    },
    {
      "role": "assistant",
      "content": [
        {
          "text": "$agent_scratchpad$"
        }
      ]
    },
    {
      "role": "assistant",
      "content": [
        {
          "text": "Thought: <thinking>\\n(1) The user wants an email report based on their JSON input.\\n(2) The user provided JSON data.\\n(3) I will first compare it with the knowledge base, then format the email accordingly.\\n(4) Let me proceed.\\n</thinking>"
        }
      ]
    },
    {
      "role": "user",
      "content": [
        {
          "text": "$follow_up_question_or_confirmation$"
        }
      ]
    }
  ]
}
"""

    response = bedrock_client.create_agent(
        agentName=agent_name,
        foundationModel="us.meta.llama3-1-8b-instruct-v1:0",
        instruction=(
            "You are a helpful assistant. You have access to a knowledge base. "
            "Use it to answer every question when possible. Always cite the documents "
            "used in your answer. If you can't find information in the knowledge base, say so. "
            "Do not guess or make up information. Show the source title or file name in your response if available."
        ),
        agentResourceRoleArn=agent_role_arn,

        promptOverrideConfiguration={
            "promptConfigurations": [
                {
                    "promptCreationMode": "OVERRIDDEN",
                    "promptType": "ORCHESTRATION",
                    "basePromptTemplate": base_prompt_template,
                    "inferenceConfiguration": {
                        "temperature": 0.7,
                        "topP": 1.0
                    }
                }
            ]
        }
    )
    associate_response = bedrock_client.associate_agent_knowledge_base(
        agentId=AGENT_ID,
        knowledgeBaseId=knowledgebas_id,
        description="Primary knowledge base for the agent",
        knowledgeBaseState="ENABLED"
    )

    return {
        "statusCode": 200,
        "body": {
            "agentId": response["agent"]["agentId"],
            "status": response["agent"]["agentStatus"],
            "associationStatus": associate_response["agentKnowledgeBase"]["agentKnowledgeBaseStatus"]
        }
    }
