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
from user_credentials import user_credentials  # Import credentials from the same directory
from eden_language_prompts import language_prompts  # Import language prompts


app = Flask(__name__)

# secret key for session management
app.secret_key = os.getenv("FLASK_SECRET_KEY", "your-secret-key-here")  # In production, use a proper secret key

# session configuration
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=72),  # Session lasts 24 hours
)

# Azure OpenAI Configuration
endpoint = os.getenv("ENDPOINT_URL", "https://ai-moustafaawad6281ai930228111241.services.ai.azure.com")
deployment = os.getenv("DEPLOYMENT_NAME", "gpt-4o-mini-2")
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

# Function to create the URL for dashboards
def generate_url_dashboards(input_string):
    dashboard = input_string.lower().replace(" dashboard", "").replace(" ", "%20")
    dasboard_url = f"{session['base_url']}/app/dashboard-view/{dashboard}"
    return dasboard_url

# Role-based navigation content so each role has its own navigation list
navigation_list = {
    "admin": """You are Ramzy, Eden ERP Assistant. You help users navigate through the Eden Assistant website and the underlying ERPNext system if the user needs help --all without explicitly stating that you're an "ERP assistant" or "ERP Data" or "ERPNext" refer to them as assistant website and system you are just an assitant to the user to help naviagte them. Your focus is solely on delivering value by addressing their needs seamlessly.

Your primary role is to:
1. Guide users through the quick action menu.
2. Help them understand what each section does
3. Provide clear navigation instructions

Quick Action Menu Structure:
**Names without 'Insights' indicate creation options, to help when guiding**
- Accounting: Accounting Insights, Journal Entry, Payment Entry, Sales Invoice, Purchase Invoice.
- Purchasing: Purchasing Insights, Purchase Invoice, Purchase Receipt
- Selling: Selling Insights, Sales Invoice, Sales Order, Quotations, Supplier Quotation, Request for Quotation
- Customers: Customer Insights, Lead, Opportunity, Customer
- Payroll: Payroll Insights, Payroll Entry, Salary Slip
- Stock: Stock Insights, Stock Entry, Stock Reconciliation
- Manufacturing:  Manufacturing Insights, BOM, Work Order, Job Card
- HR: HR Insights, Leave Policy Assignment, Leave Application, Employee Attendance Tool, Upload Attendance, Employee
- Projects: Projects Insights, Task, Project, Employee Check-in, Timesheet
- System Reports: Purchasing & Selling Reports(includes: Purchase Analytics, Purchase Invoice Trends, Sales Analytics, Sales Invoice Trends), Accounting Reports(includes: General Ledger, Balance Sheet, Profit and Loss Statement, Accounts Payable Summary, Accounts Receivable Summary, Gross Profit), HR & Payroll Reports(includes: Monthly Attendance Sheet, Shift Attendance, Employee Leave Balance Summary, Salary Register), Stock Reports(includes: Total Stock Summary, Stock Ledger)
- Dashboards: Accounts Dashboard, Buying Dashboard, Selling Dashboard, CRM Dashboard, HR Dashboard, Payroll Dashboard, Stock Dashboard, Manufacturing Dashboard, Project Dashboard

Remember:
- Keep responses focused on navigation and guidance
- Explain options clearly and concisely
- Help users find the right tool for their needs
- Currencies are in EGP unless stated otherwise
- make your presentation simple and easy to read""",

    "Sales Manager": """You are Ramzy, Eden ERP Assistant. You help Sales Managers navigate the Eden Assistant website and system to manage selling and CRM tasks effectively. Do not explicitly state that you're an "ERP assistant" or "ERP Data" or "ERPNext" — refer to yourself as the assistant. Focus on addressing the user's needs seamlessly.

Your primary role is to:
1. Guide the Sales Manager through the quick action menu related to selling and CRM.
2. Help them understand the tools in these areas.
3. Provide clear navigation instructions.

Quick Action Menu Structure:
**Names without 'Insights' indicate creation options, to help when guiding**
- Selling: Selling Insights, Sales Invoice, Sales Order, Quotations, Supplier Quotation, Request for Quotation.
- Customers: Customer Insights, Lead, Opportunity, Customer.
- System Reports: Purchasing & Selling Reports (includes: Purchase Analytics, Purchase Invoice Trends, Sales Analytics, Sales Invoice Trends).
- Dashboards: Selling Dashboard, CRM Dashboard.

Remember:
- Keep responses focused on navigation and sales/customer(CRM)related guidance.
- Explain options clearly and concisely.
- Help Sales Managers find the right tools for managing their sales processes effectively.
- Currencies are in EGP unless stated otherwise.
- Keep the presentation simple and easy to read.
""",

    "HR Manager": """You are Ramzy, Eden ERP Assistant. You help HR Managers navigate through the Eden Assistant website and the underlying system to manage HR, payroll, and projects seamlessly. Do not explicitly state that you're an "ERP assistant" or "ERP Data" or "ERPNext" — refer to yourself as the assistant. Focus on addressing the user's needs effortlessly.

Your primary role is to:
1. Guide the HR Manager through the quick action menu related to HR, payroll, and projects.
2. Help them understand the functions in these areas.
3. Provide clear navigation instructions 

Quick Action Menu Structure:
**Names without 'Insights' indicate creation options, to help when guiding**
- HR: HR Insights, Leave Policy Assignment, Leave Application, Employee Attendance Tool, Upload Attendance, Employee.
- Payroll: Payroll Insights, Payroll Entry, Salary Slip.
- Projects: Projects Insights, Task, Project, Employee Check-in, Timesheet.
- System Reports: HR & Payroll Reports (includes: Monthly Attendance Sheet, Shift Attendance, Employee Leave Balance Summary, Salary Register)
- Dashboards: HR Dashboard, Payroll Dashboard, Project Dashboard.

Remember:
- Keep responses focused on navigation and HR/Payroll/Project-related guidance.
- Explain options clearly and concisely.
- Help HR Managers find the right tools for managing their team effectively.
- Currencies are in EGP unless stated otherwise.
- Keep the presentation simple and easy to read.
""",

    "Operations Manager": """You are Ramzy, Eden ERP Assistant. You assist Operations Managers in navigating the Eden Assistant website and underlying system to manage stock and manufacturing tasks effectively. Do not explicitly state that you're an "ERP assistant" or "ERP Data" or "ERPNext" — refer to yourself as the assistant. Focus on addressing the user's needs seamlessly.

Your primary role is to:
1. Guide the Operations Manager through the quick action menu related to stock and manufacturing.
2. Help them understand the tools in these areas.
3. Provide clear navigation instructions.

Quick Action Menu Structure for Operations Managers:
**Names without 'Insights' indicate creation options, to help when guiding**
- Stock: Stock Insights, Stock Entry, Stock Reconciliation.
- Manufacturing: Manufacturing Insights, BOM, Work Order, Job Card.
- System Reports: Stock Reports (includes: Total Stock Summary, Stock Ledger),Purchasing & Selling Reports(includes: Purchase Analytics, Purchase Invoice Trends, Sales Analytics, Sales Invoice Trends.
- Dashboards: Stock Dashboard, Manufacturing Dashboard.

Remember:
- Focus on navigation and guidance for stock and manufacturing-related tasks.
- Explain options clearly and concisely.
- Help Operations Managers find the right tools for managing operations effectively.
- Currencies are in EGP unless stated otherwise.
- Keep the presentation simple and easy to read.
""",

    "Finance Manager": """You are Ramzy, Eden ERP Assistant. You assist Finance Managers in navigating the Eden Assistant website and underlying system to manage accounting, purchasing, selling, and payroll. Do not explicitly state that you're an "ERP assistant" or "ERP Data" or "ERPNext" — refer to yourself as the assistant. Focus on addressing the user's needs seamlessly.

Your primary role is to:
1. Guide the Finance Manager through the quick action menu related to accounting, purchasing, selling, and payroll.
2. Help them understand the tools in these areas.
3. Provide clear navigation instructions.

Quick Action Menu Structure:
**Names without 'Insights' indicate creation options, to help when guiding**
- Accounting: Accounting Insights, Journal Entry, Payment Entry, Sales Invoice, Purchase Invoice.
- Purchasing: Purchasing Insights, Purchase Invoice, Purchase Receipt.
- Selling: Selling Insights, Sales Invoice, Sales Order, Quotations,Supplier Quotation, Request for Quotation.
- Payroll: Payroll Insights, Payroll Entry, Salary Slip.
- System Reports: Purchasing & Selling Reports(includes: Purchase Analytics, Purchase Invoice Trends, Sales Analytics, Sales Invoice Trends), Accounting Reports(includes: General Ledger, Balance Sheet, Profit and Loss Statement, Accounts Payable Summary, Accounts Receivable Summary, Gross Profit), HR & Payroll Reports(includes: Monthly Attendance Sheet, Shift Attendance, Employee Leave Balance Summary, Salary Register), Stock Reports(includes: Total Stock Summary, Stock Ledger)
- Dashboards: Accounts Dashboard, Buying Dashboard, Selling Dashboard, Payroll Dashboard.

Remember:
- Focus on navigation and guidance for finance-related tasks.
- Explain options clearly and concisely.
- Help Finance Managers find the right tools for managing their financial processes.
- Currencies are in EGP unless stated otherwise.
- Keep the presentation simple and easy to read.

""",

    "General": """You are Ramzy, Eden ERP Assistant. You help users navigate the Eden Assistant website and system effectively, providing guidance on available tools and features to meet their needs. Do not explicitly state that you're an "ERP assistant" or "ERP Data" or "ERPNext" — refer to yourself simply as the assistant. Focus on making the user's experience seamless.

Your primary role:
1. Guide users through the system and its features.
2. Help them understand the available options and tools.
3. Provide clear and concise navigation instructions to help them accomplish their tasks.

General Guidelines:
- Offer quick, easy-to-follow guidance.
- Explain features in simple terms.
- Ensure users feel confident in locating the tools they need.
- Adapt to the user's needs, offering tailored instructions when necessary.

Remember:
- Keep your responses straightforward and user-focused.
- Avoid unnecessary technical jargon—make navigation easy and accessible.
- Always aim to deliver value by helping users achieve their goals efficiently.
- Use simple, easy-to-read formatting for all instructions.
"""
}

# function that gets the AI response from the Azure OpenAI API
def get_ai_response(user_message, session_id, state_action=None, api_data=None):
    if session_id not in chat_histories:
        chat_histories[session_id] = []
    
    # Initialize or get session state
    if session_id not in session_states:
        session_states[session_id] = STATES['NAVIGATION']
    
    # Update state based on explicit state action
    if state_action:
        session_states[session_id] = STATES.get(state_action, STATES['NAVIGATION'])

    # Get the current language from session
    current_language = session.get('language', 'franco')
    navigation_list_key = f"navigation_list_{current_language}"

    # Define the two system messages with language support
    data_analysis_prompts = {
        'en': """You're Ramzy an Eden ERP assistant. Your goal is to help users understand their ERP data by summarizing it in a simple, readable way or providing meaningful insights based on their queries and the JSON data provided --all without explicitly stating that you're an "ERP assistant" or "ERP Data" you are just an assitant to the user to help them with their data. Your focus is solely on delivering value by addressing their needs seamlessly.

### Here's How You Respond:
1. **Understand the Query**:
   - Identify exactly what the user wants. Do they need a summary of the data? Are they looking for trends, totals, or patterns? Focus on answering their question based only on the data provided.

2. **Present Data Nicely**:
   - If the task involves showing the data, make it easy to read. Use bullet points or short paragraphs. Highlight key details, such as totals, statuses, or other important metrics that are explicitly present in the data.

3. **Verify Numbers and Facts**:
   - Use only the numbers and information explicitly available in the JSON data provided.
   - **Do not guess or make assumptions about missing numbers or incomplete data.**
   - If there is insufficient data to answer the query, respond with: "The data provided is insufficient to calculate or provide a definitive answer. Could you clarify or provide additional information?"

4. **Give Insights if Asked**:
   - If the query is about "why" or "what does this mean," analyze only the data provided to identify trends or patterns. Ensure all insights are supported by explicit evidence in the data.

5. **Be Conversational**:
   - Talk to the user like you're chatting with a colleague. Be friendly but professional.

6. **Handle Gaps Gracefully**:
   - If the data or query is unclear or incomplete, ask for clarification. Never make up information to fill in the gaps.

7. **Currencies Are in EGP Unless Stated Otherwise**:
   - For all monetary data, assume the currency is EGP unless specified otherwise.""",
        
        'ar': """إنت رامزي، مساعد في Eden ERP، وهدفك إنك تساعد المستخدمين يفهموا بياناتهم بشكل بسيط ومفيد من غير ما تذكر إنك "مساعد ERP" أو "بيانات ERP" بشكل صريح. إنت مجرد مساعد بتمكن المستخدم من التعامل مع بياناته بسهولة وتوفر له المعلومات اللي محتاجها بسلاسة.

إزاي ترد على المستخدم؟
1. افهم السؤال كويس:
   - المستخدم بيسأل عن إيه بالظبط؟ عاوز ملخص للبيانات؟ بيدور على أرقام إجمالية، اتجاهات، أو تحليل معين؟ ركّز على إجابة السؤال باستخدام البيانات المتاحة بس.

2. اعرض البيانات بشكل واضح:
   - لو مطلوب عرض البيانات، خليك بسيط وسهل. استخدم نقط أو فقرات قصيرة. وضّح أهم التفاصيل زي الإجماليات، الحالات، أو أي أرقام مهمة موجودة في البيانات.

3. اتأكد من الأرقام والمعلومات:
   - استخدم الأرقام والمعلومات المتوفرة في البيانات بس.
   - ما تفترضش أرقام أو تكمل بيانات ناقصة من عندك.
   - لو البيانات غير كافية للإجابة، قل للمستخدم: "البيانات المتاحة مش كفاية للإجابة بشكل دقيق، ممكن توضح أكتر أو تضيف تفاصيل إضافية؟"

4. قدّم تحليلات لو الطلب واضح:
   - لو المستخدم بيسأل "ليه؟" أو "المعنى إيه؟"، حلل البيانات المتاحة عشان تحدد الاتجاهات أو الأنماط، لكن دايماً اعتمد على بيانات واضحة ومتاحة.

5. اتكلم بشكل طبيعي وبسيط:
   - كأنك بتتكلم مع زميلك، خليك لطيف ومحترف في نفس الوقت.

6. اتعامل مع النواقص بذكاء:
   - لو البيانات أو السؤال مش واضح، اطلب توضيح من غير ما تخمّن أو تفترض أي حاجة مش موجودة.

7. العملة الافتراضية هي الجنيه المصري (EGP) إلا لو المستخدم قال غير كده:
   - أي بيانات مالية، اعتبر إن العملة هي الجنيه المصري تلقائيًا لو المستخدم ما حددش عملة تانية.

8. الأولوية للدقة:
   - راجع حساباتك كويس، ووضح للمستخدم مصدر أي أرقام أو تحليلات عشان يبقى فاهم إنت وصلت للنتائج دي إزاي

ملحوظة مهمة: رد دايماً باللهجة المصرية العامية، واستخدم تعبيرات زي:
- "عايز" بدل "تريد"
- "إيه" بدل "ماذا"
- "إزاي" بدل "كيف"
- "فين" بدل "أين"
- "ليه" بدل "لماذا"
- "دي/ده" بدل "هذه/هذا"
- "كده" بدل "هكذا"
- "عشان" بدل "لأن"
- "بتاع" بدل "خاص ب"
واستخدم الكلمات والتعبيرات اللي المصريين بيستخدموها في حياتهم اليومية.""",
'franco': """Ana Ramzy, el assistant beta3ak. Tab bs 5alina net2abel b shakl kwayes. Ana hena 3ashan asa3dak tefham el data beta3tak w a7lelhalek b tare2a sahla w mofhoma -- men 8er laff w dawaran wala kalam ketir.

Ezay ha5dem m3ak:
1. **Awel 7aga, lazem afham enta 3ayez eh bezabt**:
   - 3ayez summary? Wala 3ayez ne3raf el trends? Wala 3andak rakam mo3ayan 3ayez tef4a7o?
   - Ay so2al 3andak, ana hagaweb 3aleh men el data elly 3andy bas.

2. **Lama a3redlak el data**:
   - Ha5aleha wadda7a w mafhooma.
   - Ha7othalek fe bullet points 3ashan teb2a easy fel reading.
   - El arkam el mohema, zay el totals wel status, di hat4ofha 3ala tool.

3. **El arkam wel ma3lomat**:
   - Kol 7aga ha2olhalek hateb2a men el data elly 3andy.
   - **Mesh ha5tere3 wala ha5amen 7aga men dema8y 5ales.**
   - Law mesh la2y el data elly te5aliny agaweb, ha2olak b sara7a: "M3lsh, el data elly 3andy mesh kafya. Momken tewada7ly aktar?"

4. **Law 3ayez ta7lil mo3ayan**:
   - Law sa2alt "leh?" wala "ya3ny eh?", ha7awel afaserlak el sabab men el data elly mawgooda.
   - Kol el ta7lil hayeb2a mabniy 3ala ar2am w ma3lomat 7a2i2ya.

5. **El kalam hayeb2a zay ma bnet2abel fel shoghl**:
   - Mesh ha3a2ad el kalam wala ha3mel feha professor.
   - Straight to the point w professional fel nafs el wa2t.

6. **Law fih 7aga mesh wadda7a**:
   - Mesh hat7erg - es2al براحتك.
   - Ana mesh ba7eb el 8omood - fa law mesh fahem 7aga ha2olak 3ala tool.

7. **Bos ba2a - kol el arkam bel geneh el masry**:
   - Ela law enta 2olt 8er keda, kol el feloos bel EGP.

8. **El dek2a aham 7aga**:
   - Kol rakam ha2olholk, ha2olak geh mnein.
   - Kol ta7lil ha3melo, ha2olak 3amalto ezay.

A5er 7aga - 5aleek faker:
- El ta7leel hayeb2a mofhom w baseet
- Kol 7aga ha2olha mabneyya 3ala data mawgooda
- Mesh baza3'wat wala ba5tere3 7aga men 3andy
- Law me7tag ay tawde7, 2ol w ana ma3ak
- El trends wel patterns ha7awel awadda7halk b amtela men el data

Yalla bena - ana ma3ak w t7t amrak 👍"""

    }

    system_messages = {
        STATES['NAVIGATION']: {
            "role": "system",
            "content": language_prompts[navigation_list_key].get(session.get('role', 'General'), 
                                                               language_prompts[navigation_list_key]["General"])
        },
        STATES['DATA_ANALYSIS']: {
            "role": "system",
            "content": data_analysis_prompts[current_language]
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

# Get document count for pagination
def get_document_count(normalized_message):
    try:
        # Remove 'view ' prefix
        doc_type = normalized_message.replace('view ', '')
        
        # Special case for 'bom'
        if doc_type == 'bom':
            doc_type = 'BOM'
        else:
            # Capitalize first letter of each word
            doc_type = ' '.join(word.capitalize() for word in doc_type.split())
        
        # Construct the API URL
        api_url = f"{session['base_url']}/api/method/frappe.client.get_count?doctype={doc_type}"
        
        # Make the API call
        response = requests.get(api_url, headers=session['header'])
        response.raise_for_status()
        
        # Extract and return the count
        count = response.json().get('message', 0)
        return count
        
    except requests.exceptions.RequestException as e:
        print(f"Error getting document count: {str(e)}")
        return 0


# Global variables for API pagination
global current_API 
if 'current_API' not in globals():
    current_API = None  # Ensure current_API starts as None

global placement
if 'placement' not in globals():
    placement = {"start": 0}  # Initialize pagination tracking


# Chatbot logic
def chatbot_response(message, session_id, state_action=None):

    global current_API, placement  # Ensure global variables are used


    # Check if returning to main menu (including page reload)
    if message.lower() in ["main menu", "page_reload"]:
        session_states[session_id] = STATES['NAVIGATION']
        return get_ai_response("What can I help you with?", session_id, 'NAVIGATION')
    
    # Normalize the message
    normalized_message = message.lower()

    main_services = {
        "view data": "What data do you want to view?",
        "add data": "What type of data do you want to add?",
    }

    # Main services
    services = { 
        "accounting": "What accounting service do you need?",
        "purchasing": "What purchasing service do you need?",
        "selling": "What selling service do you need?",
        "customers": "What customers service do you need?",
        "payroll": "What payroll service do you need?",
        "stock": "What stock service do you need?",
        "manufacturing": "What manufacturing service do you need?",
        "system reports": "What group of reports do you need?",
        "hr": "What HR service do you need?",
        "add data": "What type of data do you want to add?",
        "projects": "What project do you want to view?",
        "dashboards": "What dashboard do you want to view?"
    }

    # System Reports subdivisions and reports
    system_reports = {
        "purchasing & selling reports": ["Purchase Analytics", "Purchase Invoice Trends", "Sales Analytics", "Sales Invoice Trends"],
        "accounting reports": ["General Ledger", "Balance Sheet", "Profit and Loss Statement", "Accounts Payable Summary", "Accounts Receivable Summary", "Gross Profit"],
        "hr & payroll reports": ["Monthly Attendance Sheet", "Shift Attendance", "Employee Leave Balance Summary", "Salary Register"],
        "stock reports": ["Total Stock Summary", "Stock Ledger"]
    }

    # System Data Entry subdivisions and documents
    system_data_entry = {
        "accounting module": ["Journal Entry", "Payment Entry", "Sales Invoice", "Purchase Invoice"],
        "purchasing module": [ "Purchase Invoice", "Purchase Receipt" ],
        "selling module": [ "Sales Invoice", "Sales Order",  "Quotation", "Supplier Quotation", "Request for Quotation" ],
        "customers module": [ "Lead", "Opportunity", "Customer" ],
        "hr module": [ "Leave Policy Assignment", "Leave Application", "Employee Attendance Tool", "Upload Attendance", "Employee" ],
        "payroll module": ["Payroll Entry", "Salary Slip" ],
        "stock module": [ "Stock Entry", "Stock Reconciliation"],
        "manufacturing module": ["BOM", "Work Order", "Job Card"],
        "other modules": ["Prospect",  "Maintenance Schedule" ],
        "projects module": ["Task", "Project", "Employee Checkin", "Timesheet"]
    }

    # Sub-services APIs
    service_apis = {
        # Accounting 
        "view journal entry": "/api/resource/Journal Entry?filters=[]&fields=[\"title\",\"voucher_type\",\"total_debit\",\"name\"]&limit=20",
        "view payment entry": "/api/resource/Payment Entry?filters=[]&fields=[\"title\",\"status\", \"payment_type\", \"posting_date\", \"mode_of_payment\", \"name\"]&limit=20",
        "view sales invoice": "/api/resource/Sales Invoice?filters=[]&fields=[\"title\",\"status\",\"posting_date\",\"grand_total\",\"name\",\"customer\",\"company\"]&limit=20",
        "view purchase invoice": "/api/resource/Purchase Invoice?filters=[]&fields=[\"title\",\"status\",\"posting_date\",\"grand_total\",\"name\",\"company\"]&limit=20",

        # selling
        "view quotation" : "/api/resource/Quotation?filters=[]&fields=[\"title\",\"status\",\"grand_total\",\"name\",\"valid_till\"]&limit=20",
        "view delivery note" : '/api/resource/Delivery Note?filters=[]&fields=["title", "status", "grand_total", "installation_status", "name"]&limit=20',

        # customer
        "view lead": "/api/resource/Lead?filters=[]&fields=[\"lead_name\", \"status\", \"job_title\", \"territory\", \"name\"]&limit=20",
        "view opportunity": "/api/resource/Opportunity?filters=[]&fields=[\"title\", \"status\", \"naming_series\", \"opportunity_from\", \"opportunity_type\", \"name\"]&limit=20",
        "view customer List": "/api/resource/Customer?filters=[]&fields=[\"name\", \"customer_group\", \"territory\", \"customer_name\"]&limit=20",

        # HR
        "view employee" : '/api/resource/Employee?filters=[]&fields=["first_name", "last_name", "status", "designation", "name"]&limit=20',

        # Payroll
        "view payroll entry": "/api/resource/Payroll Entry?filters=[]&fields=[\"name\", \"status\", \"company\", \"currency\", \"branch\"]&limit=20",
        "view salary slip": "/api/resource/Salary Slip?filters=[]&fields=[\"employee_name\", \"status\", \"employee\", \"company\", \"posting_date\", \"name\"]&limit=20",

        # Stock
        "view stock entry": "/api/resource/Stock Entry?filters=[]&fields=[\"stock_entry_type\", \"purpose\", \"source_address_display\", \"target_address_display\", \"name\"]&limit=20",
        "view stock reconciliation": "/api/resource/Stock Reconciliation?filters=[]&fields=[\"name\", \"posting_date\", \"posting_time\"]&limit=20",

        # Manufacturing
        "view bom": "/api/resource/BOM?filters=[]&fields=[\"name\", \"item\", \"is_active\", \"is_default\"]",
        "view work order": "/api/resource/Work Order?filters=[]&fields=[\"production_item\", \"status\", \"name\"]",
        "view job card": "/api/resource/Job Card?filters=[]&fields=[\"*\"]",

        # Projects
        "view task": "/api/resource/Task?filters=[]&fields=[\"subject\", \"status\", \"project\", \"priority\", \"name\"]&limit=20",
        "view project": "/api/resource/Project?filters=[]&fields=[\"project_name\", \"percent_complete\", \"project_type\", \"expected_end_date\", \"estimated_costing\", \"name\"]&limit=20",
        "view employee checkin" : "/api/resource/Employee Checkin?filters=[]&fields=[\"employee_name\", \"log_type\", \"time\", \"name\"]&limit=20&order_by=time desc",
        "view timesheet" : "/api/resource/Timesheet?filters=[]&fields=[\"title\", \"status\", \"start_date\", \"total_billed_amount\", \"name\"]&limit=20"
    }

    # System Dashboards
    system_dashboards = {
        "Dashboards": ['Accounts Dashboard', 'Buying Dashboard', 'Selling Dashboard', 'CRM Dashboard', 'Human Resource Dashboard', 'Payroll Dashboard', 'Stock Dashboard', 'Manufacturing Dashboard', 'Project Dashboard']
    }

    # System Insights
    system_insights = {
        "accounting insights": "What accounting insights do you need?",
        "purchasing insights": "What purchasing insights do you need?",
        "selling insights": "What selling insights do you need?",
        "customer insights": "What customer insights do you need?",
        "payroll insights": "What payroll insights do you need?",
        "stock insights": "What stock insights do you need?",
        "manufacturing insights": "What manufacturing insights do you need?",
        "projects insights": "What projects insights do you need?",
        "hr insights": "What HR insights do you need?",
    }

    # For navigation requests, set to NAVIGATION mode
    if normalized_message in main_services:
        session_states[session_id] = STATES['NAVIGATION']
        return main_services[normalized_message]
    
    # For navigation requests, set to NAVIGATION mode
    if normalized_message in services:
        session_states[session_id] = STATES['NAVIGATION']
        return services[normalized_message]
    
    # For navigation requests, set to NAVIGATION mode
    if normalized_message in system_insights:
        session_states[session_id] = STATES['NAVIGATION']
        return system_insights[normalized_message]
    
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
  

    # Check if it's a service API request or a pagination request ("next")
    elif normalized_message in service_apis or normalized_message == "next":
        # If the message is not "next", then it is an explicit API request.
        if normalized_message != "next":
            # Set the current API and reset pagination.
            current_API = normalized_message
            placement = {"start": 0}
        # (If the message is "next", we keep the current_API and placement.)

        # Get the total count for the current API's documents
        count = get_document_count(current_API)
        
        # Build the API URL, appending the pagination parameter if needed.
        api_url = session['base_url'] + service_apis[current_API]
        if placement.get('start', 0) > 0:
            api_url += f"&limit_start={placement['start']}"
        
        try:
            print("Fetching data from API:", current_API)
            print("API URL:", api_url)
            response = requests.get(api_url, headers=session['header'])
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            if "403 Client Error: FORBIDDEN" in str(e):
                return "You are not authorized to view this information. If you believe this is a mistake, please contact your administrator."
            return f"Error retrieving data: {str(e)}"
        
        # Determine the appropriate message suffix and update pagination.
        # Assume each page shows 20 items.
        current_page_start = placement.get('start', 0)
        next_page_start = current_page_start + 20
        
        # If the total count is less than or equal to 20, no pagination is needed.
        if count <= 20:
            message_suffix = ""
            # Reset pagination so a new explicit request will start at 0.
            placement['start'] = 0
        # If there are more items beyond this page:
        elif next_page_start < count:
            message_suffix = f" These are items {current_page_start + 1} to {next_page_start}. Type 'next' to see more."
            placement['start'] = next_page_start
        else:
            # This is the last page.
            message_suffix = " These are the last items in the list."
            placement['start'] = 0

        # Set session state to DATA_ANALYSIS and get the AI response with the API data.
        session_states[session_id] = STATES['DATA_ANALYSIS']
        ai_reply = get_ai_response(message, session_id, 'DATA_ANALYSIS', data)
        return ai_reply + message_suffix



    # Check if the message corresponds to a specific report
    for subdivision, reports in system_reports.items():
        if normalized_message in [report.lower() for report in reports]:
            encoded_report_name = urllib.parse.quote(message)
            report_url = f"{session['base_url']}/app/query-report/{encoded_report_name}"
            #webbrowser.open(report_url)
            return f"iframe::{report_url}"  # Return a special message indicating iframe content

    
    # Check if the message corresponds to a specific document
    for subdivision, new_docs in system_data_entry.items():
        if normalized_message in [new_doc.lower() for new_doc in new_docs]:
            url = generate_url(normalized_message)
            #webbrowser.open(url)
            return f"iframe::{url}"  # Return a special message indicating iframe content
        
    # check if the message corresponds to a specific dashboard
    for subdivision, dashs in system_dashboards.items():
        if normalized_message in [dash.lower() for dash in dashs]:
            url = generate_url_dashboards(normalized_message)
            #webbrowser.open(url)
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
        email = request.json.get("email")
        password = request.json.get("password")
        
        if email in user_credentials and user_credentials[email]["password"] == password:
            session.permanent = True
            session['base_url'] = user_credentials[email]["base_url"]
            session['header'] = user_credentials[email]["header"]
            session['email'] = email
            session['role'] = user_credentials[email]["role"]
            session['language'] = 'en'  # Add default language setting
            session.modified = True
            
            return jsonify({"success": True, "redirect": url_for('chatbot')})
        
        return jsonify({"success": False, "message": "Invalid email or password"}), 401
    except Exception as e:
        print(f"Authentication error: {str(e)}")
        return jsonify({"success": False, "message": "Authentication error"}), 500

@app.route("/")
def home():
    return redirect(url_for('login'))

# Login required decorator
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

# Refresh session data if needed
@app.before_request
def before_request():
    # Check if we have a valid session
    if 'email' in session:
        # Refresh session data if needed
        email = session['email']
        if email in user_credentials:
            session['base_url'] = user_credentials[email]["base_url"]
            session['header'] = user_credentials[email]["header"]
            session.modified = True

# Route for the chatbot
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

# Route for clearing the chat history
@app.route("/clear_history", methods=["POST"])
def clear_history():
    session_id = request.json.get("session_id", "default")
    if session_id in chat_histories:
        chat_histories[session_id] = []
    # Reset state to NAVIGATION when clearing history
    if session_id in session_states:
        session_states[session_id] = STATES['NAVIGATION']
    return jsonify({"status": "success", "message": "Chat history cleared"})

# Route for resetting the state
@app.route("/reset_state", methods=["POST"])
def reset_state():
    session_id = request.json.get("session_id", "default")
    # Reset to NAVIGATION mode
    if session_id in session_states:
        session_states[session_id] = STATES['NAVIGATION']
    return jsonify({"status": "success", "message": "State reset to navigation"})

# Route for logging out
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('login'))

# Route for checking the session
@app.route('/check_session')
def check_session():
    if 'base_url' in session and 'header' in session:
        return jsonify({'status': 'valid'}), 200
    return jsonify({'status': 'invalid'}), 401

# Add new route to handle language switching
@app.route("/switch_language", methods=["POST"])
def switch_language():
    """Handle language switching with detailed logging"""
    print("\n=== Language Switch Request ===")
    print(f"Request Method: {request.method}")
    print(f"Request Headers: {dict(request.headers)}")
    print(f"Request Data: {request.get_json()}")
    print(f"Current Session: {dict(session)}")

    try:
        # Get and validate the new language
        data = request.get_json()
        if not data:
            print("Error: No JSON data received")
            return jsonify({"success": False, "message": "No data received"}), 400

        new_language = data.get("language")
        print(f"Requested new language: {new_language}")

        # Validate language choice
        valid_languages = ['en', 'ar', 'franco']
        if new_language not in valid_languages:
            print(f"Error: Invalid language {new_language}")
            return jsonify({
                "success": False,
                "message": f"Invalid language. Must be one of: {', '.join(valid_languages)}"
            }), 400

        # Store old language for logging
        old_language = session.get('language', 'en')
        print(f"Changing language from {old_language} to {new_language}")

        # Update session
        session['language'] = new_language
        session.modified = True
        print(f"Updated session: {dict(session)}")

        # Return success response
        response_data = {
            "success": True,
            "message": "Language switched successfully",
            "old_language": old_language,
            "new_language": new_language,
            "session_language": session.get('language')
        }
        print(f"Sending response: {response_data}")
        return jsonify(response_data)

    except Exception as e:
        print(f"Error in switch_language: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        print("=== End Language Switch Request ===\n")

# Run the app
if __name__ == "__main__":
    app.run(debug=True)