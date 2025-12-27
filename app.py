from flask import Flask, render_template, request, jsonify, send_file
import requests
import json
from datetime import datetime
import sqlite3
import qrcode
import os
from weasyprint import HTML
import base64

DB_PATH = 'invoices.db'
QR_FOLDER = 'static/qrcodes'
os.makedirs(QR_FOLDER, exist_ok=True)
PDF_FOLDER = "static/pdfs"
os.makedirs(PDF_FOLDER, exist_ok=True)


app = Flask(__name__)

# Scenario configurations
SCENARIOS = {
    'SN001': {
        'name': 'Standard Rate - Registered Buyer (B2B)',
        'description': 'Sale to registered business at 18% standard rate',
        'buyer_type': 'Registered',
        'tax_rate': '18%',
        'sale_type': 'Goods at standard rate (default)',
        'info': {
            'title': 'Business-to-Business (B2B) Sale',
            'points': [
                'Tax Rate: Standard rate (18%)',
                'Buyer Type: Sales-tax registered',
                'Input Tax Credit: Buyer can claim credit when filing',
                'Use Case: Regular business sales of taxable goods'
            ]
        }
    },
    'SN002': {
        'name': 'Standard Rate - Unregistered Buyer (B2C)',
        'description': 'Sale to unregistered buyer/consumer at 18% standard rate',
        'buyer_type': 'Unregistered',
        'tax_rate': '18%',
        'sale_type': 'Goods at standard rate (default)',
        'info': {
            'title': 'Business-to-Consumer (B2C) Sale',
            'points': [
                'Tax Rate: Standard rate (18%)',
                'Buyer Type: Not sales-tax registered (end consumer)',
                'Input Tax Credit: Buyer CANNOT claim credit',
                'Use Case: Selling products to end consumers'
            ]
        }
    },
    'SN005': {
        'name': 'Reduced-Rate Sale',
        'description': 'Sale of goods at reduced tax rate (lower than standard 18%)',
        'buyer_type': 'Unregistered',
        'tax_rate': '1%',
        'sale_type': 'Goods at Reduced Rate',
        'info': {
            'title': 'Reduced-Rate Goods Sale',
            'points': [
                'Tax Rate: Reduced rate (1% or other lower rate, not standard 18%)',
                'Applicable when law sets a lower tax percentage',
                'Buyer Type: Unregistered',
                'Requires correct reduced tax rate in invoice',
                'SRO Schedule reference required'
            ]
        }
    },
    'SN006': {
        'name': 'Exempt Goods Sale',
        'description': 'Sale of goods that are exempt from Sales Tax',
        'buyer_type': 'Registered',
        'tax_rate': 'Exempt',
        'sale_type': 'Exempt goods',
        'info': {
            'title': 'Sales Tax Exempt Goods',
            'points': [
                'Tax Rate: Exempt (no sales tax charged)',
                'Buyer Type: Registered',
                'No normal sales tax is charged',
                'Invoice must be marked as exempt sale',
                'SRO Schedule reference required (e.g., 6th Schedule Table I)'
            ]
        }
    },
    'SN007': {
        'name': 'Zero-Rated Sale',
        'description': 'Sale of goods taxed at zero rate (exports & certain goods)',
        'buyer_type': 'Unregistered',
        'tax_rate': '0%',
        'sale_type': 'Goods at zero-rate',
        'info': {
            'title': 'Zero-Rated Goods Sale',
            'points': [
                'Tax Rate: Zero-rate (0% - tax applied but at zero)',
                'Buyer Type: Unregistered',
                'Buyers may still claim input tax credit',
                'Common for exports and internationally traded goods',
                'SRO number required (e.g., 327(I)/2008)'
            ]
        }
    },
    'SN008': {
        'name': 'Sale of 3rd Schedule Goods',
        'description': 'Goods listed in 3rd Schedule with special tax treatment',
        'buyer_type': 'Unregistered',
        'tax_rate': '18%',
        'sale_type': '3rd Schedule Goods',
        'info': {
            'title': '3rd Schedule Goods Sale',
            'points': [
                'Tax Rate: Standard 18% (or as per specific SRO)',
                'Goods listed in 3rd Schedule of Sales Tax Act',
                'Special tax treatment or specific pricing master rules',
                'Buyer Type: Unregistered',
                'Examples: daily-essential items, regulated products',
                'Fixed/Notified value may be required'
            ]
        }
    },
    'SN016': {
        'name': 'Processing/Conversion of Goods',
        'description': 'Processing or converting goods (toll manufacturing)',
        'buyer_type': 'Unregistered',
        'tax_rate': '5%',
        'sale_type': 'Processing/Conversion of Goods',
        'info': {
            'title': 'Processing/Conversion Service',
            'points': [
                'Tax Rate: 5%',
                'Activity: Processing or converting goods on behalf of someone',
                'Buyer Type: Unregistered',
                'Common in toll processing/manufacturing arrangements',
                'Buyer may not be typical reseller',
                'Service-based transaction'
            ]
        }
    },
    'SN017': {
        'name': 'Goods with FED in ST Mode',
        'description': 'Goods where FED is charged in Sales Tax mode',
        'buyer_type': 'Unregistered',
        'tax_rate': '8%',
        'sale_type': 'Goods (FED in ST Mode)',
        'info': {
            'title': 'FED in Sales Tax Mode',
            'points': [
                'Tax Rate: 8% (or as applicable)',
                'Federal Excise Duty (FED) applied in sales tax mode',
                'Buyer Type: Unregistered',
                'Requires correct FED fields in invoice',
                'Both sales tax and FED may apply',
                'Assign correct rates for both taxes'
            ]
        }
    },
    'SN024': {
        'name': 'Goods per SRO 297(I)/2023',
        'description': 'Goods with unique tax rules under SRO 297(I)/2023',
        'buyer_type': 'Unregistered',
        'tax_rate': '25%',
        'sale_type': 'Goods as per SRO.297(|)/2023',
        'info': {
            'title': 'SRO 297(I)/2023 Specific Goods',
            'points': [
                'Tax Rate: 25% (or as defined in SRO)',
                'Goods specifically defined in SRO 297(I)/2023',
                'Buyer Type: Unregistered',
                'Unique tax rules or fixed sales tax percentage',
                'May have mandated schedules or fixed notified values',
                'SRO Schedule and Item Serial No. required'
            ]
        }
    },
    'SN026': {
        'name': 'Retail Sale - Standard Rate (B2C)',
        'description': 'Retail sale to end consumer at standard 18% rate',
        'buyer_type': 'Unregistered',
        'tax_rate': '18%',
        'sale_type': 'Goods at standard rate (default)',
        'info': {
            'title': 'Retail B2C Sale - Standard Rate',
            'points': [
                'Tax Rate: Standard 18%',
                'Buyer Type: End consumer (unregistered)',
                'Retail business-to-consumer transaction',
                'Tax clearly applied at standard rate',
                'Typical retail store sale to individual customer'
            ]
        }
    },
    'SN027': {
        'name': 'Retail Sale - 3rd Schedule Goods',
        'description': 'Retail sale of 3rd Schedule goods to consumer',
        'buyer_type': 'Unregistered',
        'tax_rate': '18%',
        'sale_type': '3rd Schedule Goods',
        'info': {
            'title': 'Retail B2C Sale - 3rd Schedule Goods',
            'points': [
                'Tax Rate: 18% (or as per schedule)',
                'Buyer Type: End consumer (unregistered)',
                'Goods from 3rd Schedule (special tax rules)',
                'Specific pricing and SRO schedule requirements',
                'Regulated consumer products sold by retailers',
                'Fixed/Notified value may be required'
            ]
        }
    },
    'SN028': {
        'name': 'Retail Sale - Reduced Rate (B2C)',
        'description': 'Retail sale to consumer at reduced tax rate',
        'buyer_type': 'Unregistered',
        'tax_rate': '1%',
        'sale_type': 'Goods at Reduced Rate',
        'info': {
            'title': 'Retail B2C Sale - Reduced Rate',
            'points': [
                'Tax Rate: Reduced rate (1% or other lower rate)',
                'Buyer Type: End consumer (unregistered)',
                'Retail B2C transaction',
                'Reduced rate must be correctly applied',
                'SRO Schedule reference required',
                'Fixed/Notified value required'
            ]
        }
    }
}

@app.route('/')
def index():
    return render_template('index.html', scenarios=SCENARIOS)

@app.route('/form/<scenario_id>')
def form(scenario_id):
    if scenario_id not in SCENARIOS:
        return "Scenario not found", 404
    return render_template('form.html', scenario_id=scenario_id, scenario=SCENARIOS[scenario_id])

@app.route("/invoice/<invoice_id>")
def print_invoice(invoice_id):
    invoice = get_invoice_from_db(invoice_id)

    if not invoice:
        return "Invoice not found", 404

    return render_template(
        "invoice.html",
        invoice=invoice
    )

@app.route("/invoice/<invoice_id>/pdf")
def print_invoice_pdf(invoice_id):
    # Fetch invoice from DB
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM invoices WHERE invoice_number = ?", (invoice_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return "Invoice not found", 404

    invoice = {
        "invoice_number": row["invoice_number"],
        "scenario_id": row["scenario_id"],
        "created_at": row["created_at"],
        "payload": json.loads(row["payload"])
    }

    # QR code path
    qr_path = os.path.join(QR_FOLDER, f"{invoice_id}.png")
    if os.path.exists(qr_path):
        invoice["qr_code"] = qr_path
    else:
        invoice["qr_code"] = None

    # Render HTML to string
    html_out = render_template("invoice.html", invoice=invoice)

    # Generate PDF
    pdf_path = os.path.join(PDF_FOLDER, f"{invoice_id}.pdf")
    HTML(string=html_out, base_url=".").write_pdf(pdf_path)

    # Return PDF as download
    return send_file(pdf_path, as_attachment=True, download_name=f"Invoice_{invoice_id}.pdf")



# ----------------- SUBMIT ROUTE -----------------
@app.route('/submit/<scenario_id>', methods=['POST'])
def submit(scenario_id):
    payload = None  # Ensure payload exists in exception handling
    try:
        form_data = request.form.to_dict()
        api_url = form_data.get('api_url')
        bearer_token = form_data.get('bearer_token')

        # Map scenarios to payload builders
        payload_builders = {
            'SN001': build_sn001_payload,
            'SN002': build_sn002_payload,
            'SN005': build_sn005_payload,
            'SN006': build_sn006_payload,
            'SN007': build_sn007_payload,
            'SN008': build_sn008_payload,
            'SN016': build_sn016_payload,
            'SN017': build_sn017_payload,
            'SN024': build_sn024_payload,
            'SN026': build_sn026_payload,
            'SN027': build_sn027_payload,
            'SN028': build_sn028_payload,
        }

        if scenario_id not in payload_builders:
            return jsonify({'error': f'Scenario {scenario_id} not implemented yet'}), 400

        # Build JSON payload
        payload = payload_builders[scenario_id](form_data)

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {bearer_token}'
        }

        # Send request to API
        response = requests.post(api_url, json=payload, headers=headers)

        # Safe JSON parsing
        try:
            response_data = response.json()
        except ValueError:
            response_data = {'raw_response': response.text}

        result = {
            'status_code': response.status_code,
            'success': False,
            'request_payload': payload,
            'response_data': response_data,
            'response_headers': dict(response.headers)
        }

        # Save invoice and generate QR code if invoiceNumber exists
        invoice_number = None
        if response.status_code == 200 and isinstance(response_data, dict):
            invoice_number = response_data.get('invoiceNumber')

            if invoice_number:
                result['success'] = True
                # Connect to DB and create table if not exists
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS invoices (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        invoice_number TEXT UNIQUE,
                        scenario_id TEXT,
                        payload TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute(
                    "INSERT OR IGNORE INTO invoices (invoice_number, scenario_id, payload) VALUES (?, ?, ?)",
                    (invoice_number, scenario_id, json.dumps(payload))
                )
                conn.commit()
                conn.close()

                import time

                # ... inside submit function ...

                # 1. Setup STRICT Version 2
                qr = qrcode.QRCode(
                    version=2, 
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=3,
                    border=4,
                )
                
                # 2. Add Data
                qr.add_data(invoice_number) 

                # 3. Force Build
                qr.make(fit=False)

                # --- THE TRUTH CHECK ---
                matrix = qr.get_matrix()
                width = len(matrix)
                print(f"DEBUG: QR Version reported: {qr.version}")
                print(f"DEBUG: Actual Grid Width: {width} squares")
                
                if width == 21:
                    print("RESULT: This is VERSION 1 (Incorrect)")
                elif width == 25:
                    print("RESULT: This is VERSION 2 (Correct!)")
                # -----------------------

                qr_img = qr.make_image(fill_color="black", back_color="white")
                
                # 4. SAVE WITH TIMESTAMP (Bypasses Cache)
                timestamp = int(time.time())
                unique_filename = f"{invoice_number}.png"
                qr_path = os.path.join(QR_FOLDER, unique_filename)
                qr_img.save(qr_path)
                
                print(f"SAVED TO: {qr_path}")
                # Add QR path for rendering
                result['qr_code'] = f'/static/qrcodes/{invoice_number}.png'

        return render_template(
    'result.html',
    result=result,
    invoice_id=invoice_number
)


    except requests.exceptions.RequestException as e:
        return render_template('result.html', result={
            'success': False,
            'error': str(e),
            'request_payload': payload
        })
    except Exception as e:
        return render_template('result.html', result={
            'success': False,
            'error': f'Application error: {str(e)}',
            'request_payload': payload
        })


# ---------------- HELPER FUNCTIONS -----------------
def get_invoice_from_db(invoice_number):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM invoices WHERE invoice_number = ?",
        (invoice_number,)
    )

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "invoice_number": row["invoice_number"],
        "scenario_id": row["scenario_id"],
        "payload": json.loads(row["payload"]),
        "created_at": row["created_at"]
    }

def safe_float(value):
    """Convert to float safely, return 0 if invalid"""
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0

def safe_float_or_empty(value):
    """Convert to float if valid, otherwise return empty string for API compatibility"""
    if value is None or str(value).strip() == "":
        return ""
    try:
        return float(value)
    except (ValueError, TypeError):
        return ""

def parse_items(form_data):
    """Parse items from form data safely"""
    items = []
    index = 0
    while f'item_{index}_hsCode' in form_data:
        item = {
            'hsCode': form_data.get(f'item_{index}_hsCode', ''),
            'productDescription': form_data.get(f'item_{index}_productDescription', ''),
            'rate': form_data.get(f'item_{index}_rate', '18%'),
            'uoM': form_data.get(f'item_{index}_uoM', ''),
            'quantity': safe_float(form_data.get(f'item_{index}_quantity')),
            'totalValues': safe_float(form_data.get(f'item_{index}_totalValues')),
            'valueSalesExcludingST': safe_float(form_data.get(f'item_{index}_valueSalesExcludingST')),
            'fixedNotifiedValueOrRetailPrice': safe_float(form_data.get(f'item_{index}_fixedNotifiedValueOrRetailPrice')),
            'salesTaxApplicable': safe_float(form_data.get(f'item_{index}_salesTaxApplicable')),
            'salesTaxWithheldAtSource': safe_float(form_data.get(f'item_{index}_salesTaxWithheldAtSource')),
            # 'extraTax': safe_float(form_data.get(f'item_{index}_extraTax')),
            'extraTax': safe_float_or_empty(form_data.get(f'item_{index}_extraTax')),
            'furtherTax': safe_float(form_data.get(f'item_{index}_furtherTax')),
            'sroScheduleNo': form_data.get(f'item_{index}_sroScheduleNo', ''),
            'fedPayable': safe_float(form_data.get(f'item_{index}_fedPayable')),
            'discount': safe_float(form_data.get(f'item_{index}_discount')),
            'saleType': form_data.get(f'item_{index}_saleType', 'Goods at standard rate (default)'),
            'sroItemSerialNo': form_data.get(f'item_{index}_sroItemSerialNo', '')
        }
        items.append(item)
        index += 1
    return items

# import base64
# import os

# Helper function to encode image
def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode('utf-8')
    except FileNotFoundError:
        print(f"Error: Image not found at {image_path}")
        return None

    logo_path = os.path.join('static', 'images', 'fbr_logo.jpg') 

# 2. Convert to Base64
    fbr_logo_data = get_base64_image(logo_path)

    return render_template("invoice.html", 
                       invoice=invoice_data,
                       fbr_invoice_number=fbr_invoice_number,
                       fbr_logo_data=fbr_logo_data,  # <--- Pass this
                       qr_code=qr_code_path)

def build_sn001_payload(form_data):
    """Build JSON payload for SN001 scenario"""
    items = parse_items(form_data)
    
    payload = {
        'invoiceType': form_data.get('invoiceType', 'Sale Invoice'),
        'invoiceDate': form_data.get('invoiceDate', datetime.now().strftime('%Y-%m-%d')),
        'sellerBusinessName': form_data.get('sellerBusinessName', ''),
        'sellerProvince': form_data.get('sellerProvince', ''),
        'sellerNTNCNIC': form_data.get('sellerNTNCNIC', ''),
        'sellerAddress': form_data.get('sellerAddress', ''),
        'buyerNTNCNIC': form_data.get('buyerNTNCNIC', ''),
        'buyerBusinessName': form_data.get('buyerBusinessName', ''),
        'buyerProvince': form_data.get('buyerProvince', ''),
        'buyerAddress': form_data.get('buyerAddress', ''),
        'invoiceRefNo': form_data.get('invoiceRefNo', ''),
        'scenarioId': 'SN001',
        # 'buyerRegistrationType': 'Registered',
        "buyerRegistrationType": form_data["buyerType"],
        'items': items
    }
    
    return payload

def build_sn002_payload(form_data):
    """Build JSON payload for SN002 scenario"""
    items = parse_items(form_data)
    
    payload = {
        'invoiceType': form_data.get('invoiceType', 'Sale Invoice'),
        'invoiceDate': form_data.get('invoiceDate', datetime.now().strftime('%Y-%m-%d')),
        'sellerBusinessName': form_data.get('sellerBusinessName', ''),
        'sellerProvince': form_data.get('sellerProvince', ''),
        'sellerNTNCNIC': form_data.get('sellerNTNCNIC', ''),
        'sellerAddress': form_data.get('sellerAddress', ''),
        'buyerNTNCNIC': form_data.get('buyerNTNCNIC', ''),
        'buyerBusinessName': form_data.get('buyerBusinessName', ''),
        'buyerProvince': form_data.get('buyerProvince', ''),
        'buyerAddress': form_data.get('buyerAddress', ''),
        'invoiceRefNo': form_data.get('invoiceRefNo', ''),
        'scenarioId': 'SN002',
        # 'buyerRegistrationType': 'Unregistered',
        "buyerRegistrationType": form_data["buyerType"],
        'items': items
    }
    
    return payload

def build_sn005_payload(form_data):
    """Build JSON payload for SN005 scenario"""
    items = parse_items(form_data)
    
    payload = {
        'invoiceType': form_data.get('invoiceType', 'Sale Invoice'),
        'invoiceDate': form_data.get('invoiceDate', datetime.now().strftime('%Y-%m-%d')),
        'sellerNTNCNIC': form_data.get('sellerNTNCNIC', ''),
        'sellerBusinessName': form_data.get('sellerBusinessName', ''),
        'sellerAddress': form_data.get('sellerAddress', ''),
        'sellerProvince': form_data.get('sellerProvince', ''),
        'buyerNTNCNIC': form_data.get('buyerNTNCNIC', ''),
        'buyerBusinessName': form_data.get('buyerBusinessName', ''),
        'buyerProvince': form_data.get('buyerProvince', ''),
        'buyerAddress': form_data.get('buyerAddress', ''),
        'invoiceRefNo': form_data.get('invoiceRefNo', ''),
        'scenarioId': 'SN005',
        # 'buyerRegistrationType': form_data.get('buyerRegistrationType', 'Unregistered'),
        "buyerRegistrationType": form_data["buyerType"],
        'items': items
    }
    
    return payload

def build_sn006_payload(form_data):
    """Build JSON payload for SN006 scenario"""
    items = parse_items(form_data)
    
    payload = {
        'invoiceType': form_data.get('invoiceType', 'Sale Invoice'),
        'invoiceDate': form_data.get('invoiceDate', datetime.now().strftime('%Y-%m-%d')),
        'sellerBusinessName': form_data.get('sellerBusinessName', ''),
        'sellerNTNCNIC': form_data.get('sellerNTNCNIC', ''),
        'sellerProvince': form_data.get('sellerProvince', ''),
        'sellerAddress': form_data.get('sellerAddress', ''),
        'buyerNTNCNIC': form_data.get('buyerNTNCNIC', ''),
        'buyerBusinessName': form_data.get('buyerBusinessName', ''),
        'buyerProvince': form_data.get('buyerProvince', ''),
        'buyerAddress': form_data.get('buyerAddress', ''),
        'invoiceRefNo': form_data.get('invoiceRefNo', ''),
        'scenarioId': 'SN006',
        # 'buyerRegistrationType': form_data.get('buyerRegistrationType', 'Registered'),
        "buyerRegistrationType": form_data["buyerType"],
        'items': items
    }
    
    return payload

def build_sn007_payload(form_data):
    """Build JSON payload for SN007 scenario"""
    items = parse_items(form_data)
    
    payload = {
        'invoiceType': form_data.get('invoiceType', 'Sale Invoice'),
        'invoiceDate': form_data.get('invoiceDate', datetime.now().strftime('%Y-%m-%d')),
        'sellerBusinessName': form_data.get('sellerBusinessName', ''),
        'sellerNTNCNIC': form_data.get('sellerNTNCNIC', ''),
        'sellerProvince': form_data.get('sellerProvince', ''),
        'buyerNTNCNIC': form_data.get('buyerNTNCNIC', ''),
        'buyerBusinessName': form_data.get('buyerBusinessName', ''),
        'buyerProvince': form_data.get('buyerProvince', ''),
        'buyerAddress': form_data.get('buyerAddress', ''),
        'sellerAddress': form_data.get('sellerAddress', ''),
        'scenarioId': 'SN007',
        # 'buyerRegistrationType': form_data.get('buyerRegistrationType', 'Unregistered'),
        "buyerRegistrationType": form_data["buyerType"],
        'invoiceRefNo': form_data.get('invoiceRefNo', '0'),
        'items': items
    }
    
    return payload

def build_sn008_payload(form_data):
    """Build JSON payload for SN008 scenario"""
    items = parse_items(form_data)
    
    payload = {
        'invoiceType': form_data.get('invoiceType', 'Sale Invoice'),
        'invoiceDate': form_data.get('invoiceDate', datetime.now().strftime('%Y-%m-%d')),
        'sellerNTNCNIC': form_data.get('sellerNTNCNIC', ''),
        'sellerBusinessName': form_data.get('sellerBusinessName', ''),
        'sellerProvince': form_data.get('sellerProvince', ''),
        'buyerNTNCNIC': form_data.get('buyerNTNCNIC', ''),
        'buyerBusinessName': form_data.get('buyerBusinessName', ''),
        'buyerProvince': form_data.get('buyerProvince', ''),
        'buyerAddress': form_data.get('buyerAddress', ''),
        'sellerAddress': form_data.get('sellerAddress', ''),
        'invoiceRefNo': form_data.get('invoiceRefNo', '0'),
        'scenarioId': 'SN008',
        # 'buyerRegistrationType': form_data.get('buyerRegistrationType', 'Unregistered'),
        "buyerRegistrationType": form_data["buyerType"],
        'items': items
    }
    
    return payload

def build_sn016_payload(form_data):
    """Build JSON payload for SN016 scenario"""
    items = parse_items(form_data)
    
    payload = {
        'invoiceType': form_data.get('invoiceType', 'Sale Invoice'),
        'invoiceDate': form_data.get('invoiceDate', datetime.now().strftime('%Y-%m-%d')),
        'sellerNTNCNIC': form_data.get('sellerNTNCNIC', ''),
        'sellerBusinessName': form_data.get('sellerBusinessName', ''),
        'sellerProvince': form_data.get('sellerProvince', ''),
        'sellerAddress': form_data.get('sellerAddress', ''),
        'buyerNTNCNIC': form_data.get('buyerNTNCNIC', ''),
        'buyerBusinessName': form_data.get('buyerBusinessName', ''),
        'buyerProvince': form_data.get('buyerProvince', ''),
        'buyerAddress': form_data.get('buyerAddress', ''),
        'invoiceRefNo': form_data.get('invoiceRefNo', ''),
        'scenarioId': 'SN016',
        # 'buyerRegistrationType': form_data.get('buyerRegistrationType', 'Unregistered'),
        "buyerRegistrationType": form_data["buyerType"],
        'items': items
    }
    
    return payload

def build_sn017_payload(form_data):
    """Build JSON payload for SN017 scenario"""
    items = parse_items(form_data)
    
    payload = {
        'invoiceType': form_data.get('invoiceType', 'Sale Invoice'),
        'invoiceDate': form_data.get('invoiceDate', datetime.now().strftime('%Y-%m-%d')),
        'sellerNTNCNIC': form_data.get('sellerNTNCNIC', ''),
        'sellerBusinessName': form_data.get('sellerBusinessName', ''),
        'sellerProvince': form_data.get('sellerProvince', ''),
        'sellerAddress': form_data.get('sellerAddress', ''),
        'buyerNTNCNIC': form_data.get('buyerNTNCNIC', ''),
        'buyerBusinessName': form_data.get('buyerBusinessName', ''),
        'buyerProvince': form_data.get('buyerProvince', ''),
        'buyerAddress': form_data.get('buyerAddress', ''),
        'invoiceRefNo': form_data.get('invoiceRefNo', ''),
        'scenarioId': 'SN017',
        # 'buyerRegistrationType': form_data.get('buyerRegistrationType', 'Unregistered'),
        "buyerRegistrationType": form_data["buyerType"],
        'items': items
    }
    
    return payload

def build_sn024_payload(form_data):
    """Build JSON payload for SN024 scenario"""
    items = parse_items(form_data)
    
    payload = {
        'invoiceType': form_data.get('invoiceType', 'Sale Invoice'),
        'invoiceDate': form_data.get('invoiceDate', datetime.now().strftime('%Y-%m-%d')),
        'sellerNTNCNIC': form_data.get('sellerNTNCNIC', ''),
        'sellerBusinessName': form_data.get('sellerBusinessName', ''),
        'sellerProvince': form_data.get('sellerProvince', ''),
        'sellerAddress': form_data.get('sellerAddress', ''),
        'buyerNTNCNIC': form_data.get('buyerNTNCNIC', ''),
        'buyerBusinessName': form_data.get('buyerBusinessName', ''),
        'buyerProvince': form_data.get('buyerProvince', ''),
        'buyerAddress': form_data.get('buyerAddress', ''),
        # 'buyerRegistrationType': form_data.get('buyerRegistrationType', 'Unregistered'),
        "buyerRegistrationType": form_data["buyerType"],
        'scenarioId': 'SN024',
        'invoiceRefNo': form_data.get('invoiceRefNo', ''),
        'items': items
    }
    
    return payload

def build_sn026_payload(form_data):
    """Build JSON payload for SN026 scenario"""
    items = parse_items(form_data)
    
    payload = {
        'invoiceType': form_data.get('invoiceType', 'Sale Invoice'),
        'invoiceDate': form_data.get('invoiceDate', datetime.now().strftime('%Y-%m-%d')),
        'sellerNTNCNIC': form_data.get('sellerNTNCNIC', ''),
        'sellerBusinessName': form_data.get('sellerBusinessName', ''),
        'sellerProvince': form_data.get('sellerProvince', ''),
        'sellerAddress': form_data.get('sellerAddress', ''),
        'buyerNTNCNIC': form_data.get('buyerNTNCNIC', ''),
        'buyerBusinessName': form_data.get('buyerBusinessName', ''),
        'buyerProvince': form_data.get('buyerProvince', ''),
        'buyerAddress': form_data.get('buyerAddress', ''),
        # 'buyerRegistrationType': form_data.get('buyerRegistrationType', 'Unregistered'),
        "buyerRegistrationType": form_data["buyerType"],
        'scenarioId': 'SN026',
        'invoiceRefNo': form_data.get('invoiceRefNo', ''),
        'items': items
    }
    
    return payload

def build_sn027_payload(form_data):
    """Build JSON payload for SN027 scenario"""
    items = parse_items(form_data)
    
    payload = {
        'invoiceType': form_data.get('invoiceType', 'Sale Invoice'),
        'invoiceDate': form_data.get('invoiceDate', datetime.now().strftime('%Y-%m-%d')),
        'sellerNTNCNIC': form_data.get('sellerNTNCNIC', ''),
        'sellerBusinessName': form_data.get('sellerBusinessName', ''),
        'sellerProvince': form_data.get('sellerProvince', ''),
        'sellerAddress': form_data.get('sellerAddress', ''),
        'buyerNTNCNIC': form_data.get('buyerNTNCNIC', ''),
        'buyerBusinessName': form_data.get('buyerBusinessName', ''),
        'buyerProvince': form_data.get('buyerProvince', ''),
        'buyerAddress': form_data.get('buyerAddress', ''),
        # 'buyerRegistrationType': form_data.get('buyerRegistrationType', 'Unregistered'),
        "buyerRegistrationType": form_data["buyerType"],
        'invoiceRefNo': form_data.get('invoiceRefNo', ''),
        'scenarioId': 'SN027',
        'items': items
    }
    
    return payload

def build_sn028_payload(form_data):
    """Build JSON payload for SN028 scenario"""
    items = parse_items(form_data)
    
    payload = {
        'invoiceType': form_data.get('invoiceType', 'Sale Invoice'),
        'invoiceDate': form_data.get('invoiceDate', datetime.now().strftime('%Y-%m-%d')),
        'sellerNTNCNIC': form_data.get('sellerNTNCNIC', ''),
        'sellerBusinessName': form_data.get('sellerBusinessName', ''),
        'sellerProvince': form_data.get('sellerProvince', ''),
        'sellerAddress': form_data.get('sellerAddress', ''),
        'buyerNTNCNIC': form_data.get('buyerNTNCNIC', ''),
        'buyerBusinessName': form_data.get('buyerBusinessName', ''),
        'buyerProvince': form_data.get('buyerProvince', ''),
        'buyerAddress': form_data.get('buyerAddress', ''),
        'invoiceRefNo': form_data.get('invoiceRefNo', ''),
        # 'buyerRegistrationType': form_data.get('buyerRegistrationType', 'Unregistered'),
        "buyerRegistrationType": form_data["buyerType"],
        'scenarioId': 'SN028',
        'items': items
    }
    
    return payload

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)