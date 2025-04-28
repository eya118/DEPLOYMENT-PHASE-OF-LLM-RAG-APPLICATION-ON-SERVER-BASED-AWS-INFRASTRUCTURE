import json
import os
import boto3
import urllib.parse

def lambda_handler(event, context):
    bedrock_agent_client = boto3.client('bedrock-agent')

    knowledge_base_id = os.environ['knowledge_base_id']
    full_id = os.environ['data_source_id']
    data_source_id = full_id.split('|')[1]

    print(f"Knowledge Base ID: {knowledge_base_id}")
    print(f"Data Source ID: {data_source_id}")

    for record in event.get('Records', []):
        bucket = record['s3']['bucket']['name']
        key = urllib.parse.unquote_plus(record['s3']['object']['key'])

        print(f"New file uploaded: s3://{bucket}/{key}")

    response = bedrock_agent_client.start_ingestion_job(
        dataSourceId=data_source_id,
        knowledgeBaseId=knowledge_base_id,
        description=f"Triggered Ingestion - {event.get('time', 'no-time')}",
    )

    message = f"Ingestion job with ID: {response['ingestionJob']['ingestionJobId']} started at {response['ingestionJob']['startedAt']} with current status: {response['ingestionJob']['status']}"
    print(message)

    return {
        'statusCode': 200,
        'body': json.dumps({
            'result': message
        })
    }
