from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import requests
import json
import webbrowser
import urllib.parse
import os
import base64
from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from functools import wraps
from datetime import datetime, timedelta

#####################
# Backend API details for additional data fetching
# base_url = "https://system.edenmea.com"
# header = {"Authorization": "token 92420cab12d4143:54f1bb6f943e856"}
#####################
app = Flask(__name__)

# Add a secret key for session management
app.secret_key = os.getenv("FLASK_SECRET_KEY", "your-secret-key-here")  # In production, use a proper secret key

# Add session configuration
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=24),  # Session lasts 24 hours
)

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

# Add a state tracker dictionary (new)
session_states = {}

# Simplified state management (new)
STATES = {
    'NAVIGATION': 'navigation',  # For menu navigation and form creation
    'DATA_ANALYSIS': 'data_analysis'  # For viewing and analyzing data
}

# User credentials and their corresponding base URLs and headers
user_credentials = {
    "admin": {
        "password": "admin",
        "base_url": "https://system.edenmea.com",
        "header": {
            "Authorization": "token 92420cab12d4143:54f1bb6f943e856"
        }
    },
    "peter": {
        "password": "peter",
        "base_url": "https://system.edenmea.com",
        "header": {
            "Authorization": "token d514a87307f1336:a9e7400aa1387ac"
        }
    }
}

# Function to create the URL for data entry
def generate_url(input_string):
    # Check if the input matches specific cases
    if input_string == "New Employee Attendance Tool":
        url = f"{session['base_url']}/app/employee-attendance-tool"
    elif input_string == "New Upload Attendance":
        url = f"{session['base_url']}/app/upload-attendance"
    else:
        # Replace spaces with hyphens to form the URL
        doctype = input_string.lower().replace("new ", "").replace(" ", "-")
        # Construct the URL dynamically
        url = f"{session['base_url']}/app/{doctype}/new-{doctype}"
    return url

# For dashboards
def generate_url_dashboards(input_string):
        dashboard = input_string.lower().replace(" dashboards", "").replace(" ", "%")
        dasboard_url = f"{session['base_url']}/app/dashboard-view/{dashboard}"
        return dasboard_url

def get_ai_response(user_message, session_id, state_action=None, api_data=None):
    if session_id not in chat_histories:
        chat_histories[session_id] = []
    
    # Initialize or get session state
    if session_id not in session_states:
        session_states[session_id] = STATES['NAVIGATION']
    
    # Update state based on explicit state action
    if state_action:
        session_states[session_id] = STATES.get(state_action, STATES['NAVIGATION'])

    # Define the two system messages
    system_messages = {
        STATES['NAVIGATION']: {
            "role": "system",
            "content": """You are Ramzy, Eden ERP Assistant. You help users navigate through the Eden Assistant website and the underlying ERPNext system if the user needs help.

Your primary role is to:
1. Guide users through the main menu options
2. Help them understand what each section does
3. Provide clear navigation instructions

Main Menu Structure:
- Accounting: Journal Entry, Payment Entry, Sales Invoice, Purchase Invoice
- Purchasing: Purchase Invoice, Purchase Receipt
- Selling: Sales Invoice, Sales Order, Quotations
- CRM: Lead, Opportunity, Customer
- Payroll: Payroll Entry, Salary Slip
- Stock: Stock Entry, Stock Reconciliation
- Manufacturing: BOM, Work Order, Job Card
- System Reports: Various report categories
- HR: Leave Applications, Attendance Tools
- Create New: access to create any document creating any document is done there(New Accounting, New Purchasing, New Selling, New CRM , New HR, New Payroll, New Stock, New Manufacturing, Other(New Prospect
, New Maintenance Schedule)) all of these are buttons in Create New. Guide the user to the right button based on the user input.

Remember:
- Keep responses focused on navigation and guidance
- Explain options clearly and concisely
- Help users find the right tool for their needs
- Currencies are in EGP unless stated otherwise
- make your presentation simple and easy to read"""
        },
        STATES['DATA_ANALYSIS']: {
        "role": "system",
        "content": """You're Ramzy an Eden ERP assistant. Your goal is to help users understand their ERP data by summarizing it in a simple, readable way or providing meaningful insights based on their queries and the JSON data provided.

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
    }

    # Use the appropriate system message based on current state
    current_state = session_states[session_id]
    system_message = system_messages.get(current_state, system_messages[STATES['NAVIGATION']])

    # Prepare messages including history
    messages = [system_message]
    messages.extend(chat_histories[session_id][-10:])
    
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
def chatbot_response(message, session_id, state_action=None):
    # Check if returning to main menu (including page reload)
    if message.lower() in ["main menu", "page_reload"]:
        session_states[session_id] = STATES['NAVIGATION']
        return get_ai_response("What can I help you with?", session_id, 'NAVIGATION')
    
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
        "system reports": "What group of reports do you need?",
        "hr": "What HR service do you need?",
        "create new": "What type of data do you want to create?",
        "show projects": "what project do you want to view?",
        "dashboards": "What dashboard do you want to view?"
    }

    # System Reports subdivisions and reports
    system_reports = {
        "purchasing & selling reports": ["Purchase Analytics", "Purchase Invoice Trends", "Sales Analytics", "Sales Invoice Trends"],
        "accounting reports": ["General Ledger", "Balance Sheet", "Profit and Loss Statement", "Accounts Payable Summary", "Accounts Receivable Summary", "Gross Profit"],
        "hr & payroll reports": ["Employee Attendance", "Salary Register"],
        "stock reports": ["Stock Summary", "Stock Ledger"]
    }

    # System Data Entry subdivisions and documents
    system_data_entry = {
        "new accounting": ["New Journal Entry", "New Payment Entry", "New Sales Invoice", "New Purchase Invoice"],
        "new purchasing": [ "New Purchase Invoice", "New Purchase Receipt" ],
        "new selling": [ "New Sales Invoice", "New Sales Order",  "New Quotation", "New Supplier Quotation", "New Request for Quotation" ],
        "new crm": [ "New Lead", "New Opportunity", "New Customer" ],
        "new hr": [ "New Leave Policy Assignment", "New Leave Application", "New Employee Attendance Tool", "New Upload Attendance", "New Employee" ],
        "new payroll": ["New Payroll Entry", "New Salary Slip" ],
        "new stock": [ "New Stock Entry", "New Stock Reconciliation"],
        "new manufacturing": ["New BOM", "New Work Order", "New Job Card"],
        "other": ["New Prospect",  "New Maintenance Schedule" ]
    }

    # Sub-services APIs
    service_apis = {
        # Accounting 
        "journal entry": "/api/resource/Journal Entry?filters=[]&fields=[\"title\",\"voucher_type\",\"total_debit\",\"name\"]",
        "payment entry": "/api/resource/Payment Entry?filters=[[\"docstatus\",\"=\",\"1\"]]&fields=[\"title\",\"status\", \"payment_type\", \"posting_date\", \"mode_of_payment\", \"name\"]",
        "sales invoice": "/api/resource/Sales Invoice?filters=[[\"docstatus\",\"=\",\"1\"],[\"posting_date\",\"Timespan\",\"this year\"]]&fields=[\"title\",\"status\",\"posting_date\",\"grand_total\",\"name\",\"customer\",\"company\"]",
        "purchase invoice": "/api/resource/Purchase Invoice?filters=[[\"docstatus\",\"=\",\"1\"],[\"posting_date\",\"Timespan\",\"this year\"]]&fields=[\"title\",\"status\",\"posting_date\",\"grand_total\",\"name\",\"company\"]",

        # selling
        "quotation" : "/api/resource/Quotation?filters=[]&fields=[\"title\",\"status\",\"grand_total\",\"name\",\"valid_till\"]",
        "delivery note" : '/api/resource/Delivery Note?filters=[]&fields=["title", "status", "grand_total", "installation_status", "name"]',

        # CRM
        "lead": "/api/resource/Lead?filters=[]&fields=[\"lead_name\", \"status\", \"job_title\", \"territory\", \"name\"]",
        "opportunity": "/api/resource/Opportunity?filters=[]&fields=[\"title\", \"status\", \"naming_series\", \"opportunity_from\", \"opportunity_type\", \"name\"]",
        "customer": "/api/resource/Customer?filters=[]&fields=[\"name\", \"customer_group\", \"territory\", \"customer_name\"]",

        # HR
        "employee" : '/api/resource/Employee?filters=[]&fields=["first_name", "last_name", "status", "designation", "name"]',

        # Payroll
        "payroll entry": "/api/resource/Payroll Entry?filters=[]&fields=[\"name\", \"status\", \"company\", \"currency\", \"branch\"]",
        "salary slip": "/api/resource/Salary Slip?filters=[]&fields=[\"employee_name\", \"status\", \"employee\", \"company\", \"posting_date\", \"name\"]",

        # Stock
        "stock entry": "/api/resource/Stock Entry?filters=[]&fields=[\"stock_entry_type\", \"purpose\", \"source_address_display\", \"target_address_display\", \"name\"]",
        "stock reconciliation": "/api/resource/Stock Reconciliation?filters=[]&fields=[\"name\", \"posting_date\", \"posting_time\"]",

        # Manufacturing
        "bom": "/api/resource/BOM?filters=[]&fields=[\"name\", \"item\", \"is_active\", \"is_default\"]",
        "work order": "/api/resource/Work Order?filters=[]&fields=[\"production_item\", \"status\", \"name\"]",
        "job card": "/api/resource/Job Card?filters=[]&fields=[\"*\"]",

        # Projects
        "task": "/api/resource/Task?filters=[]&fields=[\"subject\", \"status\", \"project\", \"priority\", \"name\"]",
        "project": "/api/resource/Project?filters=[]&fields=[\"project_name\", \"percent_complete\", \"project_type\", \"expected_end_date\", \"estimated_costing\", \"name\"]",
        "employee checkin" : "/api/resource/Employee Checkin?filters=[]&fields=[\"employee_name\", \"log_type\", \"time\", \"name\"]&order_by=time desc",
        "timesheet" : "/api/resource/Timesheet?filters=[]&fields=[\"title\", \"status\", \"start_date\", \"total_billed_amount\", \"name\"]"
    }

    system_dashboards = {
        "Dashboards": ['Accounts Dashboard', 'Buying Dashboard', 'Selling Dasboard', 'CRM Dasboard', 'HR Dasboard', 'Payroll Dasboard', 'Stock Dasboard', 'Manufactring Dasboard', 'Project Dashboard']
    }


    # For navigation requests, set to NAVIGATION mode
    if normalized_message in services:
        session_states[session_id] = STATES['NAVIGATION']
        return services[normalized_message]
    
    # Check if the message corresponds to a subdivision in System Reports
    elif normalized_message in system_reports:
        session_states[session_id] = STATES['NAVIGATION']
        reports = system_reports[normalized_message]
        return f"Which report do you need?\n"
    
    # Check if the message corresponds to a subdivision in Data Entry
    elif normalized_message in system_data_entry:
        session_states[session_id] = STATES['NAVIGATION']
        new_docs = system_data_entry[normalized_message]
        return f"Which document do you want to add?\n"

    # Check if it's a service API request
    elif normalized_message in service_apis:
        try:
            api_url = session['base_url'] + service_apis[normalized_message]
            response = requests.get(api_url, headers=session['header'])
            response.raise_for_status()
            data = response.json()
            
            # Set state to DATA_ANALYSIS and keep it there
            session_states[session_id] = STATES['DATA_ANALYSIS']
            return get_ai_response(message, session_id, 'DATA_ANALYSIS', data)
            
        except requests.exceptions.RequestException as e:
            return f"Error retrieving data: {str(e)}"
        


    # Check if the message corresponds to a specific report
    for subdivision, reports in system_reports.items():
        if normalized_message in [report.lower() for report in reports]:
            encoded_report_name = urllib.parse.quote(message)
            report_url = f"{session['base_url']}/app/query-report/{encoded_report_name}"
            return f"iframe::{report_url}"  # Return a special message indicating iframe content

    
    # Check if the message corresponds to a specific document
    for subdivision, new_docs in system_data_entry.items():
        if normalized_message in [new_doc.lower() for new_doc in new_docs]:
            url = generate_url(normalized_message)
            return f"iframe::{url}"  # Return a special message indicating iframe content
        
    for subdivision, dashs in system_dashboards.items():
        if normalized_message in [dash.lower() for dash in dashs]:
            url = generate_url_dashboards(normalized_message)
            return f"iframe::{url}"  # Return a special message indicating iframe content


    # If we're in DATA_ANALYSIS mode, stay there and process with AI
    if session_id in session_states and session_states[session_id] == STATES['DATA_ANALYSIS']:
        return get_ai_response(message, session_id, 'DATA_ANALYSIS')

    # Default case: process with AI in current state
    return get_ai_response(message, session_id, 'NAVIGATION')




@app.route("/login", methods=["GET"])
def login():
    return render_template("login.html")

@app.route("/authenticate", methods=["POST"])
def authenticate():
    try:
        username = request.json.get("username")
        password = request.json.get("password")
        
        if username in user_credentials and user_credentials[username]["password"] == password:
            # Make session permanent
            session.permanent = True
            
            # Store the base_url and header in the session
            session['base_url'] = user_credentials[username]["base_url"]
            session['header'] = user_credentials[username]["header"]
            session['username'] = username
            
            # Ensure session is saved
            session.modified = True
            
            return jsonify({"success": True, "redirect": url_for('chatbot')})
        
        return jsonify({"success": False, "message": "Invalid credentials"}), 401
    except Exception as e:
        print(f"Authentication error: {str(e)}")  # For debugging
        return jsonify({"success": False, "message": "Authentication error"}), 500

@app.route("/")
def home():
    return redirect(url_for('login'))

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            if 'base_url' not in session or 'header' not in session:
                print("Session missing required data")  # For debugging
                return redirect(url_for('login'))
            # Verify session data is valid
            if not isinstance(session.get('base_url'), str) or not isinstance(session.get('header'), dict):
                print("Invalid session data format")  # For debugging
                session.clear()
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        except Exception as e:
            print(f"Login verification error: {str(e)}")  # For debugging
            session.clear()
            return redirect(url_for('login'))
    return decorated_function

@app.before_request
def before_request():
    # Check if we have a valid session
    if 'username' in session:
        # Refresh session data if needed
        username = session['username']
        if username in user_credentials:
            session['base_url'] = user_credentials[username]["base_url"]
            session['header'] = user_credentials[username]["header"]
            session.modified = True

@app.route("/chatbot")
@login_required
def chatbot():
    return render_template("index.html")

@app.route("/get_response", methods=["POST"])
@login_required
def get_response():
    user_message = request.json.get("message")
    session_id = request.json.get("session_id", "default")
    response = chatbot_response(user_message,session_id)
    return jsonify({"response": response})

@app.route("/clear_history", methods=["POST"])
def clear_history():
    session_id = request.json.get("session_id", "default")
    if session_id in chat_histories:
        chat_histories[session_id] = []
    # Reset state to NAVIGATION when clearing history
    if session_id in session_states:
        session_states[session_id] = STATES['NAVIGATION']
    return jsonify({"status": "success", "message": "Chat history cleared"})

@app.route("/reset_state", methods=["POST"])
def reset_state():
    session_id = request.json.get("session_id", "default")
    # Reset to NAVIGATION mode
    if session_id in session_states:
        session_states[session_id] = STATES['NAVIGATION']
    return jsonify({"status": "success", "message": "State reset to navigation"})

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(debug=True)

