from flask import Flask, render_template, request, jsonify
import requests
import json
import webbrowser
import urllib.parse
import os
import base64
from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

#####################
# Backend API details for additional data fetching
base_url = "http://system.edenmea.com"
header = {
    "Authorization": "token 92420cab12d4143:54f1bb6f943e856"
}
#####################
app = Flask(__name__)

# Azure OpenAI Configuration
endpoint = os.getenv("ENDPOINT_URL", "https://ai-moustafaawad6281ai930228111241.openai.azure.com/")
deployment = os.getenv("DEPLOYMENT_NAME", "gpt-4o-mini")
subscription_key = os.getenv("AZURE_OPENAI_API_KEY", "22jtOiYXuu43EctfKGvEQCKYqtS6t4EVZMjp0Hn4HErT5dmmMUFvJQQJ99BAACHYHv6XJ3w3AAAAACOGOeyL")

# Initialize Azure OpenAI client with API key
client = AzureOpenAI(
    azure_endpoint=endpoint,
    api_key=subscription_key,
    api_version="2024-05-01-preview"
)

# Chat history storage
chat_histories = {}

def get_ai_response(user_message, session_id, api_data=None):
    # Initialize chat history for new sessions
    if session_id not in chat_histories:
        chat_histories[session_id] = []
    
    # System message
    system_message = {
        "role": "system",
        "content": """You're an Eden ERP assistant. Your goal is to help users understand their ERP data by summarizing it in a simple, readable way or providing meaningful insights based on their queries and the JSON data provided.

### Here's How You Respond:
1. **Understand the Query**:
   - What does the user really want? Do they need a summary of the data? Are they looking for trends, totals, or patterns? Keep it simple and relevant.

2. **Present Data Nicely**:
   - If it's about showing the data, make it easy to read. Use bullet points, or short paragraphs. Highlight what matters most, like totals, statuses, or key details.

3. **Give Insights if Asked**:
   - If the query is about "why" or "what does this mean," dig a little deeper. Add up totals, find patterns, or compare the data to offer meaningful insights.

4. **Be Conversational**:
   - Talk to the user like you're chatting with a colleague. Be friendly but professional.

5. **Handle Gaps Gracefully**:
   - If the query or data is unclear, ask for clarification.
6. **currencies are also in EGP unless stated otherwise**"""
    }

    # Prepare messages including history (limited to last 10 messages)
    messages = [system_message]
    messages.extend(chat_histories[session_id][-10:])  # Keep last 10 messages
    
    # Add current user message and API data if available
    current_message = {
        "role": "user",
        "content": [
            {"type": "text", "text": user_message}
        ]
    }
    if api_data:
        current_message["content"].append({"type": "text", "text": json.dumps(api_data)})
    
    messages.append(current_message)

    try:
        # Get completion from Azure OpenAI
        completion = client.chat.completions.create(
            model=deployment,
            messages=messages,
            max_tokens=800,
            temperature=0.7,
            top_p=0.95,
            frequency_penalty=0,
            presence_penalty=0,
            stop=None,
            stream=False
        )

        # Extract the response
        ai_response = completion.choices[0].message.content

        # Store the conversation
        chat_histories[session_id].append(current_message)
        chat_histories[session_id].append({
            "role": "assistant",
            "content": [{"type": "text", "text": ai_response}]
        })

        return ai_response

    except Exception as e:
        return f"Error getting AI response: {str(e)}"

# Chatbot logic
def chatbot_response(message, session_id):
    # Normalize the message
    normalized_message = message.lower()

    # Main services
    services = {
        "accounting": "What accounting service do you need?",
        "purchasing": "What purchasing service do you need?",
        "selling": "What selling service do you need?",
        "crm": "What CRM service do you need?",
        "payroll": "What payroll service do you need?",
        "stock": "What stock service do you need?",
        "manufacturing": "What manufacturing service do you need?",
        "system reports": "What gorup of reports do you need?",
        "hr": "Taking you to HR"
    }

    # System Reports subdivisions and reports
    system_reports = {
        "purchasing & selling reports": ["Purchase Analytics", "Purchase Invoice Trends", "Sales Analytics", "Sales Invoice Trends"],
        "accounting reports": ["General Ledger", "Balance Sheet", "Profit and Loss Statement", "Accounts Payable Summary", "Accounts Receivable Summary", "Gross Profit"],
        "hr & payroll reports": ["Employee Attendance", "Salary Register"],
        "stock reports": ["Stock Summary", "Stock Ledger"]
    }

    # Sub-services APIs
    service_apis = {
        # Accounting
        "journal entry": "/api/resource/Journal Entry?filters=[]&fields=[\"title\",\"voucher_type\",\"total_debit\",\"name\"]",
        "payment entry": "/api/resource/Payment Entry?filters=[[\"docstatus\",\"=\",\"1\"]]&fields=[\"title\",\"status\", \"payment_type\", \"posting_date\", \"mode_of_payment\", \"name\"]",
        "sales invoice": "/api/resource/Sales Invoice?filters=[[\"docstatus\",\"=\",\"1\"],[\"posting_date\",\"Timespan\",\"this year\"]]&fields=[\"title\",\"status\",\"posting_date\",\"grand_total\",\"name\",\"customer\",\"company\"]",
        "purchase invoice": "/api/resource/Purchase Invoice?filters=[[\"docstatus\",\"=\",\"1\"],[\"posting_date\",\"Timespan\",\"this year\"]]&fields=[\"title\",\"status\",\"posting_date\",\"grand_total\",\"name\",\"company\"]",

        # CRM
        "lead": "/api/resource/Lead?filters=[]&fields=[\"lead_name\", \"status\", \"job_title\", \"territory\", \"name\"]",
        "opportunity": "/api/resource/Opportunity?filters=[]&fields=[\"title\", \"status\", \"naming_series\", \"opportunity_from\", \"opportunity_type\", \"name\"]",
        "customer": "/api/resource/Customer?filters=[]&fields=[\"name\", \"customer_group\", \"territory\", \"customer_name\"]",

        # Payroll
        "payroll entry": "/api/resource/Payroll Entry?filters=[]&fields=[\"name\", \"status\", \"company\", \"currency\", \"branch\"]",
        "salary slip": "/api/resource/Salary Slip?filters=[]&fields=[\"employee_name\", \"status\", \"employee\", \"company\", \"posting_date\", \"name\"]",

        # Stock
        "stock entry": "/api/resource/Stock Entry?filters=[]&fields=[\"stock_entry_type\", \"purpose\", \"source_address_display\", \"target_address_display\", \"name\"]",
        "stock reconciliation": "/api/resource/Stock Reconciliation?filters=[]&fields=[\"name\", \"posting_date\", \"posting_time\"]",

        # Manufacturing
        "bom": "/api/resource/BOM?filters=[]&fields=[\"name\", \"item\", \"is_active\", \"is_default\"]",
        "work order": "/api/resource/Work Order?filters=[]&fields=[\"production_item\", \"status\", \"name\"]",
        "job card": "/api/resource/Job Card?filters=[]&fields=[\"*\"]"
    }

    # Check if the message corresponds to a main service
    if normalized_message in services:
        return services[normalized_message]

    # Check if the message corresponds to a subdivision in System Reports
    if normalized_message in system_reports:
        reports = system_reports[normalized_message]
        return f"Which report do you need?\n"

    # Check if the message corresponds to a specific report
    for subdivision, reports in system_reports.items():
        if normalized_message in [report.lower() for report in reports]:
            encoded_report_name = urllib.parse.quote(message)
            report_url = f"https://system.edenmea.com/app/query-report/{encoded_report_name}"
            return f"iframe::{report_url}"

    # Check if the message corresponds to a sub-service
    if normalized_message in service_apis:
        # Make the API call
        api_url = base_url + service_apis[normalized_message]
        try:
            response = requests.get(api_url, headers=header)
            response.raise_for_status()
            data = response.json()
            return get_ai_response(message, session_id, data)
        except requests.exceptions.RequestException as e:
            return f"Error retrieving data: {str(e)}"

    # Instead of returning the default message, pass unrecognized input to the AI
    return get_ai_response(message, session_id)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/get_response", methods=["POST"])
def get_response():
    user_message = request.json.get("message")
    session_id = request.json.get("session_id", "default")  # Get or create session ID
    response = chatbot_response(user_message, session_id)
    return jsonify({"response": response})

@app.route("/clear_history", methods=["POST"])
def clear_history():
    session_id = request.json.get("session_id", "default")
    if session_id in chat_histories:
        chat_histories[session_id] = []
    return jsonify({"status": "success", "message": "Chat history cleared"})

if __name__ == "__main__":
    app.run(debug=True)
