import os
import json
import base64
from pathlib import Path
from groq import Groq
from PIL import Image
import fitz  # PyMuPDF for PDF handling
import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom

# Load environment variables from .env file if it exists
def load_env_file():
    env_file = Path('.env')
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                if line.startswith("GROQ_API_KEY="):
                    key = line.strip().split("=", 1)[1]
                    os.environ["GROQ_API_KEY"] = key
                    return
    # If no .env file, check if it's already in environment
    if not os.environ.get("GROQ_API_KEY"):
        print("Warning: GROQ_API_KEY not found in .env file or environment variables")

# Load .env file at import time
load_env_file()

class InvoiceExtractor:
    def __init__(self, api_key=None):
        """Initialize the invoice extractor with Groq API key."""
        if api_key is None:
            api_key = os.environ.get("GROQ_API_KEY")
            if not api_key:
                raise ValueError("GROQ_API_KEY environment variable not set")
        
        self.client = Groq(api_key=api_key)
        self.model = "meta-llama/llama-4-maverick-17b-128e-instruct"
        self.system_prompt = """You are an AI system designed to extract specific information from invoices and create a structured JSON output. Your task is to analyze the provided invoice and extract the following information:

<invoice_fields>
{{supplier_name}} description: Extract the legal name of the entity that issued the invoice. Follow this priority order: 1) Primary: Look for the company name that includes a legal entity designation (e.g., s.r.o., a.s., spol. s r.o., LLC, Inc., Corp., Ltd., GmbH, SA, etc.). This is typically the official legal name and should always be prioritized over brand names or trade names. 2) Secondary: If no legal entity designation is present, look for the name that appears in the official invoice header, sender address, or tax/registration number section. 3) Individual persons: If the invoice is issued by an individual (no legal entity designation present), extract the full personal name. Prioritize legal names over brand names, even if the brand name is more prominently displayed.

{{vat_number}} description: VAT number is a string beginning with 2 letters, usually CZ, followed by 8 or 9 digits for a company and 10 digits for an individual person. IMPORTANT: If you see a string starting with "C" followed by what appears to be a digit "2", interpret this as "CZ" - the second character should always be the letter "Z" when the first character is "C". This field is mandatory - every invoice must have a VAT number. Look carefully in the header, footer, or company details section if not immediately visible.

{{invoice_number}} description: Invoice number is the unique identifier of this specific invoice document. Look for fields labeled "číslo faktury", "daňový doklad číslo", or "doklad číslo". AVOID extracting "číslo plátce" (payers number), "klientské číslo" (client number), "zákaznické číslo" (customer number), or "číslo objednávky" (order numbers). This field is mandatory - every invoice must have an invoice number. The invoice number is typically displayed prominently near the top of the invoice and is the number that identifies this particular billing document. If you cannot find a clearly labeled invoice number, use the "variabilní symbol" (variable symbol) value as it often serves as the invoice number. Extract only numeric characters from this field, removing any letters or special characters.

{{date_of_sale}} description: Date when the invoice was issued. Usually field with this date is named "Datum vystavení" or "Vystaveno". Use format dd.mm.yyyy even if there is a different format on the invoice.

{{due_date}} description: Date when the invoice is due for payment. Usually field with this date is named "Datum splatnosti". If you can not find this date, use same date as date of sale. Use format dd.mm.yyyy even if there is a different format on the invoice.

{{duzp}} description: Date when is recognized VAT tax. Usually field with this date is named "Datum uskutečnění zdanitelného plnění" or some form abbreviated from this text or "DUZP" only. This field must be always filled. If you can not find this date, use same date as date of sale. Use format dd.mm.yyyy even if there is a different format on the invoice.

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
        """Convert first page of PDF to image and return base64 encoded string with enhanced quality."""
        doc = fitz.open(pdf_path)
        page = doc[0]  # Get first page
        
        mat = fitz.Matrix(3, 3)  # Scale factor for better OCR quality
        pix = page.get_pixmap(matrix=mat)
        
        # Convert to PIL Image for processing
        img_data = pix.tobytes("png")
        from io import BytesIO
        img = Image.open(BytesIO(img_data))
        
        # Enhance image for better OCR
        img = self.enhance_image_for_ocr(img)
        
        # Save processed image
        temp_image_path = "temp_invoice_enhanced.png"
        img.save(temp_image_path, "PNG", quality=100, optimize=False)
        
        # Encode to base64
        encoded_image = self.encode_image(temp_image_path)
        
        # Clean up
        os.remove(temp_image_path)
        doc.close()
        
        return encoded_image

    def enhance_image_for_ocr(self, img):
        """Enhance image quality for better OCR recognition."""
        from PIL import ImageEnhance, ImageFilter
        
        # Convert to RGB if not already
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # 1. Increase contrast
        contrast_enhancer = ImageEnhance.Contrast(img)
        img = contrast_enhancer.enhance(1.3)  # Increase contrast by 30%
        
        # 2. Increase sharpness
        sharpness_enhancer = ImageEnhance.Sharpness(img)
        img = sharpness_enhancer.enhance(1.2)  # Increase sharpness by 20%
        
        # 3. Slight brightness adjustment (optional)
        brightness_enhancer = ImageEnhance.Brightness(img)
        img = brightness_enhancer.enhance(1.1)  # Slightly brighter
        
        # 4. Apply unsharp mask filter for better edge definition
        img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=150, threshold=3))
        
        return img

    def enhance_existing_image(self, image_path):
        """Enhance existing image files for better OCR."""
        try:
            img = Image.open(image_path)
            enhanced_img = self.enhance_image_for_ocr(img)
            
            # Save enhanced version temporarily
            temp_path = f"temp_enhanced_{Path(image_path).name}"
            enhanced_img.save(temp_path, quality=100, optimize=False)
            
            return temp_path
        except Exception as e:
            print(f"Error enhancing image {image_path}: {e}")
            return image_path  # Return original if enhancement fails

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
                    # Look for VAT payer records - correct element name
                    platce_elements = root.findall('.//ns:statusPlatceDPH', namespaces)
                    
                    # Check if we found any records at all
                    if not platce_elements:
                        print(f"VAT number {vat_number} not found in registry")
                        return False  # VAT number doesn't exist = not reliable
                    
                    # Look for our specific VAT number
                    for platce in platce_elements:
                        # DIC is an attribute, not a nested element
                        dic_value = platce.get('dic', '')
                        nespolehlivy_value = platce.get('nespolehlivyPlatce', '')
                        
                        if dic_value == vat_number:
                            # Interpret the nespolehlivyPlatce value
                            # Based on Czech VAT service documentation:
                            # - "NENALEZEN" = Not found (invalid VAT number)
                            # - "ANO" = Yes, unreliable
                            # - "NE" = No, reliable (not unreliable)
                            # - Empty or other = Usually means reliable
                            
                            if nespolehlivy_value == "NENALEZEN":
                                print(f"VAT number {vat_number} not found in registry")
                                return False
                            elif nespolehlivy_value == "ANO":
                                print(f"VAT payer {vat_number} is unreliable")
                                return False
                            elif nespolehlivy_value == "NE" or nespolehlivy_value == "":
                                print(f"VAT payer {vat_number} is reliable")
                                return True
                            else:
                                print(f"Unknown VAT status '{nespolehlivy_value}' for {vat_number}, assuming reliable")
                                return True
                    
                    # If records exist but our VAT number wasn't found
                    print(f"VAT number {vat_number} not found in returned records")
                    return False  # VAT number doesn't exist = not reliable
                    
                else:
                    print(f"VAT service returned error status code: {status_code}")
                    return None  # Service error, can't determine
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
            # Enhance existing image
            enhanced_image_path = self.enhance_existing_image(file_path)
            encoded_image = self.encode_image(enhanced_image_path)
            
            # Clean up enhanced image if it was created
            if enhanced_image_path != file_path:
                os.remove(enhanced_image_path)
            
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
            # Prepare image data for Groq API
            image_data_url = f"data:{media_type};base64,{encoded_image}"
            
            # Call Groq API
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self.system_prompt
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Please extract the invoice data and return it in the specified JSON format."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_data_url
                                }
                            }
                        ]
                    }
                ],
                temperature=0.0,
                max_tokens=300,
                top_p=0.95,
                stream=False,
                response_format={"type": "json_object"},
                stop=None,
            )
            
            # Extract JSON from response
            response_text = completion.choices[0].message.content.strip()
            
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
    try:
        # Initialize extractor (will use GROQ_API_KEY environment variable)
        extractor = InvoiceExtractor()
        
        # Process all invoices in current directory
        extractor.process_all_invoices()
        
    except ValueError as e:
        print(f"Configuration error: {e}")
        print("Please make sure GROQ_API_KEY environment variable is set.")
        return
    except Exception as e:
        print(f"Unexpected error: {e}")
        return

if __name__ == "__main__":
    # Install required packages if not already installed
    try:
        from groq import Groq
        import fitz
        from PIL import Image, ImageEnhance, ImageFilter
        import requests
        import xml.etree.ElementTree as ET
    except ImportError as e:
        print("Missing required packages. Please install them using:")
        print("pip install groq PyMuPDF Pillow requests")
        exit(1)
    
    main()
