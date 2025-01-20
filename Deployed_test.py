import boto3
import json

# Initialize SageMaker runtime client with explicit credentials
sagemaker_runtime = boto3.client(
    'sagemaker-runtime',
    region_name='us-east-1',
    aws_access_key_id='AKIA2UC3BLIX2LGV4WQR',
    aws_secret_access_key='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'
)

# Endpoint name
endpoint_name = "test-2-agent"

# Input payload
payload = {
    "inputs": "human: what is the recipe of mayonnaise?",
    "parameters": {
        "max_new_tokens": 256,
        "temperature": 0.6,
        "top_p": 0.9
    }
}

# Invoke the endpoint
response = sagemaker_runtime.invoke_endpoint(
    EndpointName=endpoint_name,
    Body=json.dumps(payload),
    ContentType="application/json"
)

# Parse the response
result = json.loads(response['Body'].read().decode())

# Extract and clean the bot's response
if "generated_text" in result:
    generated_text = result["generated_text"]
    # Process the generated text to remove repetitive or unwanted patterns
    cleaned_response = generated_text.split("human:")[0].strip()  # Remove repeated "human:" prompts
    print("Bot says:", cleaned_response)
else:
    print("Error: No 'generated_text' found in the response.")
