import os
import json
import base64
from pathlib import Path
import anthropic
from PIL import Image
import fitz  # PyMuPDF for PDF handling
import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom

class InvoiceExtractor:
    def __init__(self, api_key):
        """Initialize the invoice extractor with Anthropic API key."""
        self.client = anthropic.Anthropic(api_key=api_key)
        self.system_prompt = """You are an AI system designed to extract specific information from invoices and create a structured JSON output. Your task is to analyze the provided invoice and extract the following information:

<invoice_fields>
{{supplier_name}} description: Legal name of the company that issued the invoice. This legal name is usually but not always accompanied by a legal form (e.g. s.r.o., a.s. etc.). There could be Brand name of the company on the invoice therefore first look for company name accompanied by a legal form. If it is not a company but an individual person, the legal form is missing.
{{vat_number}} description: VAT number is a string beginning with 2 letters, usually CZ, and 8 digits for a company and 10 digits for an individual person.
{{invoice_number}} description: Invoice number is usually called "číslo faktury" or "doklad číslo". If you cannot find it, use the value of Variable symbol "variabilní symbol" as it is usually the invoice number as well. If the invoice number contains other characters than numbers, use only the string of numbers.
{{date_of_sale}} description: Date when the invoice was issued. Usually field with this date is named "Datum vystavení" or "Vystaveno". Use format dd.mm.yyyy even if there is a different format on the invoice.
{{due_date}} description: Date when the invoice is due for payment. Usually field with this date is named "Datum splatnosti". Use format dd.mm.yyyy even if there is a different format on the invoice.
{{duzp}} description: Date when is recognized VAT tax. Usually field with this date is named "Datum uskutečnění zdanitelného plnění" or some form abbreviated from this text or "DUZP" only. Use format dd.mm.yyyy even if there is a different format on the invoice.
{{amount_without_VAT_21}} description: Total amount where VAT rate 21% is applied. Use the value before VAT is applied. If on the invoice there is no amount related to VAT rate 21%, use value 0 for this field.
{{VAT_21}} description: Total amount of 21% VAT. Usually listed in the same line as total amount without 21% VAT in the table where the summary of VAT is shown. If there is no value, use 0 in this field. This field cannot be 0 if amount_without_VAT_21 is a number.
{{amount_without_VAT_12}} description: Total amount where VAT rate 12% is applied. Use the value before VAT is applied. If on the invoice there is no amount related to VAT rate 12%, use value 0 for this field.
{{VAT_12}} description: Total amount of 12% VAT. Usually listed in the same line as total amount without 12% VAT in the table where the summary of VAT is shown. If there is no value, use 0 in this field. This field cannot be 0 if amount_without_VAT_12 is a number.
{{total_amount_with_VAT}} description: Total amount on the issued invoice with VAT. Amount that the client paid or is going to pay.
</invoice_fields>

Instructions:
1. Carefully examine the invoice and extract the required information.
2. Format the information into a JSON structure.

After completing the extraction process, format the information exactly into the following JSON structure:

{
  "supplier_name": "",
  "vat_number": "",
  "invoice_number": "",
  "date_of_sale": "",
  "due_date": "",
  "duzp": "",
  "amount_without_VAT_21": "",
  "VAT_21": "",
  "amount_without_VAT_12": "",
  "VAT_12": "",
  "total_amount_with_VAT": "",
  "reliable_VAT_payer": ""
}

Provide only the JSON output without any additional description or explanation."""

    def encode_image(self, image_path):
        """Encode image to base64."""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def pdf_to_image(self, pdf_path):
        """Convert first page of PDF to image and return base64 encoded string."""
        doc = fitz.open(pdf_path)
        page = doc[0]  # Get first page
        
        # Convert page to image
        mat = fitz.Matrix(2, 2)  # Scale factor for better quality
        pix = page.get_pixmap(matrix=mat)
        img_data = pix.tobytes("png")
        
        # Save temporary image
        temp_image_path = "temp_invoice.png"
        with open(temp_image_path, "wb") as f:
            f.write(img_data)
        
        # Encode to base64
        encoded_image = self.encode_image(temp_image_path)
        
        # Clean up
        os.remove(temp_image_path)
        doc.close()
        
        return encoded_image

    def check_vat_reliability(self, vat_number):
        """Check VAT payer reliability using Czech Ministry of Finance web service."""
        if not vat_number or not isinstance(vat_number, str):
            return None
        
        # Clean VAT number - remove spaces and convert to uppercase
        vat_clean = vat_number.replace(" ", "").upper()
        
        # Check if it's a Czech VAT number (should start with CZ)
        if not vat_clean.startswith("CZ"):
            return None
        
        # Extract numeric part after CZ
        vat_numeric = vat_clean[2:]
        
        # Validate format (8 digits for companies, 9-10 digits for individuals)
        if not vat_numeric.isdigit() or len(vat_numeric) < 8 or len(vat_numeric) > 10:
            return None
        
        try:
            # Prepare SOAP request
            soap_body = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
    <soapenv:Body>
        <StatusNespolehlivyPlatceRequest xmlns="http://adis.mfcr.cz/rozhraniCRPDPH/">
            <dic>{vat_numeric}</dic>
        </StatusNespolehlivyPlatceRequest>
    </soapenv:Body>
</soapenv:Envelope>"""
            
            # Set headers
            headers = {
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': 'http://adis.mfcr.cz/rozhraniCRPDPH/getStatusNespolehlivyPlatce'
            }
            
            # Make SOAP request
            url = "https://adisrws.mfcr.cz/adistc/axis2/services/rozhraniCRPDPH.rozhraniCRPDPHSOAP"
            
            response = requests.post(url, data=soap_body, headers=headers, timeout=10)
            
            if response.status_code == 200:
                return self.parse_vat_response(response.text, vat_numeric)
            else:
                print(f"VAT service error: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            print(f"Error checking VAT reliability: {e}")
            return None

    def parse_vat_response(self, xml_response, vat_number):
        """Parse SOAP response from VAT reliability service."""
        try:
            # Parse XML response
            root = ET.fromstring(xml_response)
            
            # Define namespaces
            namespaces = {
                'soap': 'http://schemas.xmlsoap.org/soap/envelope/',
                'ns': 'http://adis.mfcr.cz/rozhraniCRPDPH/'
            }
            
            # Look for response status
            status_elem = root.find('.//ns:status', namespaces)
            if status_elem is not None:
                status_code = status_elem.get('statusCode', '')
                if status_code == '0':  # Success
                    # Look for VAT payer records
                    platce_elements = root.findall('.//ns:StatusNespolehlivyPlatce', namespaces)
                    
                    for platce in platce_elements:
                        dic = platce.find('.//ns:dic', namespaces)
                        if dic is not None and dic.text == vat_number:
                            # Check reliability status
                            nespolehlivy = platce.find('.//ns:nespolehlivy', namespaces)
                            if nespolehlivy is not None:
                                # If nespolehlivy is true, the payer is unreliable
                                is_unreliable = nespolehlivy.text.lower() == 'true'
                                return not is_unreliable  # Return True if reliable
                    
                    # If no specific record found but status is OK, assume reliable
                    return True
                else:
                    print(f"VAT service returned status code: {status_code}")
                    return None
            else:
                print("Could not find status in VAT service response")
                return None
                
        except ET.ParseError as e:
            print(f"Error parsing VAT service XML response: {e}")
            return None
        except Exception as e:
            print(f"Error processing VAT service response: {e}")
            return None

    def get_supported_files(self, folder_path="."):
        """Get list of supported invoice files (PDF and images) in the folder."""
        supported_extensions = ['.pdf', '.png', '.jpg', '.jpeg', '.gif', '.webp']
        folder = Path(folder_path)
        
        files = []
        for ext in supported_extensions:
            files.extend(folder.glob(f"*{ext}"))
            files.extend(folder.glob(f"*{ext.upper()}"))
        
        return files

    def process_invoice(self, file_path):
        """Process a single invoice file and extract data."""
        print(f"Processing: {file_path}")
        
        file_extension = Path(file_path).suffix.lower()
        
        # Handle PDF files
        if file_extension == '.pdf':
            encoded_image = self.pdf_to_image(file_path)
            media_type = "image/png"
        # Handle image files
        else:
            encoded_image = self.encode_image(file_path)
            if file_extension in ['.jpg', '.jpeg']:
                media_type = "image/jpeg"
            elif file_extension == '.png':
                media_type = "image/png"
            elif file_extension == '.gif':
                media_type = "image/gif"
            elif file_extension == '.webp':
                media_type = "image/webp"
            else:
                media_type = "image/png"  # Default

        try:
            # Call Anthropic API
            message = self.client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=500,
                temperature=0.2,
                system=self.system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": encoded_image
                                }
                            },
                            {
                                "type": "text",
                                "text": "Please extract the invoice data and return it in the specified JSON format."
                            }
                        ]
                    }
                ]
            )
            
            # Extract JSON from response
            response_text = message.content[0].text.strip()
            
            # Clean up response to extract JSON
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            
            response_text = response_text.strip()
            
            # Parse JSON
            try:
                extracted_data = json.loads(response_text)
                
                # Check VAT reliability if VAT number is present
                if 'vat_number' in extracted_data and extracted_data['vat_number']:
                    print(f"Checking VAT reliability for: {extracted_data['vat_number']}")
                    vat_reliability = self.check_vat_reliability(extracted_data['vat_number'])
                    
                    if vat_reliability is not None:
                        extracted_data['reliable_VAT_payer'] = vat_reliability
                        print(f"VAT reliability check result: {'Reliable' if vat_reliability else 'Unreliable'}")
                    else:
                        extracted_data['reliable_VAT_payer'] = "Unable to verify"
                        print("VAT reliability could not be determined")
                else:
                    extracted_data['reliable_VAT_payer'] = "No VAT number found"
                    print("No VAT number found for reliability check")
                
                return extracted_data
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON response: {e}")
                print(f"Response text: {response_text}")
                return None
                
        except Exception as e:
            print(f"Error processing invoice: {e}")
            return None

    def save_results(self, data, original_filename):
        """Save extracted data to JSON file."""
        output_filename = f"{Path(original_filename).stem}_extracted.json"
        
        with open(output_filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"Results saved to: {output_filename}")

    def process_all_invoices(self, folder_path="."):
        """Process all invoice files in the specified folder."""
        files = self.get_supported_files(folder_path)
        
        if not files:
            print("No supported invoice files found in the current directory.")
            print("Supported formats: PDF, PNG, JPG, JPEG, GIF, WEBP")
            return
        
        print(f"Found {len(files)} invoice file(s) to process:")
        for file in files:
            print(f"  - {file}")
        
        for file_path in files:
            extracted_data = self.process_invoice(file_path)
            
            if extracted_data:
                self.save_results(extracted_data, file_path.name)
                print(f"Successfully processed: {file_path.name}")
            else:
                print(f"Failed to process: {file_path.name}")
            
            print("-" * 50)

def main():
    # Replace with your actual Anthropic API key
    API_KEY = "YOUR_API_KEY_HERE"
    
    # Initialize extractor
    extractor = InvoiceExtractor(API_KEY)
    
    # Process all invoices in current directory
    extractor.process_all_invoices()

if __name__ == "__main__":
    # Install required packages if not already installed
    try:
        import anthropic
        import fitz
        from PIL import Image
        import requests
        import xml.etree.ElementTree as ET
    except ImportError as e:
        print("Missing required packages. Please install them using:")
        print("pip install anthropic PyMuPDF Pillow requests")
        exit(1)
    
    main()
