from flask import Flask, render_template, request, jsonify
import requests
import json
import webbrowser
import urllib.parse

#####################
# Backend API details for additional data fetching
base_url = "http://system.edenmea.com"
header = {
    "Authorization": "token 92420cab12d4143:54f1bb6f943e856"
}
#####################
app = Flask(__name__)

# Chatbot logic
def chatbot_response(message):
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
            return f"iframe::{report_url}"  # Return a special message indicating iframe content

    # Check if the message corresponds to a sub-service
    if normalized_message in service_apis:
        # Make the API call
        api_url = base_url + service_apis[normalized_message]
        try:
            response = requests.get(api_url, headers=header)
            response.raise_for_status()  # Raise an error for bad responses
            data = response.json()

            # Format the response data
            if "data" in data and len(data["data"]) > 0:
                formatted_data = "\n".join([
                    json.dumps(entry, indent=2) for entry in data["data"]
                ])
                return f"Here are the results for {message.title()}:\n{formatted_data}"
            else:
                return f"No results found for {message.title()}."
        except requests.exceptions.RequestException as e:
            return f"Error retrieving data for {message.title()}: {str(e)}"

    # Default response for unrecognized input
    return "I'm not sure how to help with that. Please choose a valid option."

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/get_response", methods=["POST"])
def get_response():
    user_message = request.json.get("message")
    response = chatbot_response(user_message)
    return jsonify({"response": response})

if __name__ == "__main__":
    app.run(debug=True)
