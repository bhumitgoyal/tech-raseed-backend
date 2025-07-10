#!/usr/bin/env python3
"""
Receipt Parser using Google Cloud Vertex AI Gemini
Extracts structured information from receipt PDFs using multimodal AI.
"""

import sys
import requests

import json
import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from dotenv import load_dotenv
import tempfile

# Load .env from backend directory
load_dotenv(dotenv_path=Path(__file__).parent.parent / 'backend' / '.env')

# --- Google Credentials Handling ---
if os.getenv('GOOGLE_APPLICATION_CREDENTIALS_JSON'):
    cred_json = os.getenv('GOOGLE_APPLICATION_CREDENTIALS_JSON')
    temp_cred = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
    temp_cred.write(cred_json.encode())
    temp_cred.close()
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = temp_cred.name

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Vertex AI configuration
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "default-project-id")  # Updated to match service account
LOCATION = "us-central1"  # Replace with your preferred location
MODEL_NAME = "gemini-2.5-flash"  # or "gemini-1.5-pro"

# Set credentials to the current service account file
# os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(Path(__file__).parent / "splendid-yeti-464913-j2-e4fcc70357d3.json")

class ReceiptParser:
    def upload_to_gofile(self, pdf_path: str) -> Optional[str]:
        """
        Upload the PDF to GoFile and return the download URL.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Download URL or None if failed
        """
        try:
            logger.info(f"Uploading PDF to GoFile: {pdf_path}")
            with open(pdf_path, "rb") as f:
                res = requests.post(
                    "https://store1.gofile.io/uploadFile",
                    files={"file": f},
                    timeout=30
                )
            res.raise_for_status()
            data = res.json()
            if data.get("status") != "ok":
                logger.error(f"GoFile upload failed: {data}")
                return None
            url = data["data"]["downloadPage"]
            logger.info(f"Uploaded PDF to GoFile: {url}")
            return url
        except Exception as e:
            logger.error(f"Failed to upload PDF to GoFile: {str(e)}")
            return None
    """Receipt parser using Vertex AI Gemini multimodal model."""
    
    def __init__(self, project_id: str, location: str, model_name: str = "gemini-1.5-flash"):
        """
        Initialize the receipt parser.
        
        Args:
            project_id: Google Cloud project ID
            location: Vertex AI location (e.g., 'us-central1')
            model_name: Gemini model name
        """
        self.project_id = project_id
        self.location = location
        self.model_name = model_name
        
        # Initialize Vertex AI with authentication
        try:
            vertexai.init(project=project_id, location=location)
            self.model = GenerativeModel(model_name)
            logger.info(f"Successfully initialized Vertex AI with model: {model_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Vertex AI: {str(e)}")
            raise
        
        # Receipt parsing prompt
        self.prompt = """You are an expert receipt parser. Extract structured information from the receipt image and output it as valid JSON.

IMPORTANT: Output ONLY valid JSON without any markdown formatting, quotes, or additional text. The response must be parseable by JSON.parse().

Extract information following this exact schema:
{
    "store_name": "string",
    "store_address": "string",
    "store_phone": "string or null",
    "date": "YYYY-MM-DD",
    "time": "HH:MM",
    "bill_number": "string",
    "receipt_category": "string",
    "Summary": "string (max 150 words, no quotes)",
    "payment_method": "string",
    "currency": "string",
    "subtotal_amount": "number",
    "tax_amount": "number or null",
    "tip_amount": "number or null", 
    "total_amount": "number",
    "items": [
        {
            "item_name": "string",
            "quantity": "number",
            "unit_price": "number",
            "total_price": "number",
            "category": "string"
        }
    ],
    "tax_breakdown": [
        {
            "tax_name": "string",
            "tax_rate": "string",
            "tax_amount": "number"
        }
    ],
    "footer_notes": "string"
}

Categories: Groceries, Food, Transportation, Travel, Utilities, Subscriptions, Healthcare, Shopping, Entertainment, Education, Maintenance, Financial, Others.

Rules:
1. Use numbers for amounts (not strings)
2. Keep Summary under 150 words and avoid quotes
3. Translate non-English text to English
4. Use null for missing values
5. Output ONLY the JSON object, no other text"""

    def load_pdf_bytes(self, pdf_path: str) -> Optional[bytes]:
        """
        Load PDF file as bytes.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            PDF bytes or None if loading fails
        """
        try:
            logger.info(f"Loading PDF file: {pdf_path}")
            
            with open(pdf_path, 'rb') as f:
                pdf_bytes = f.read()
            
            logger.info(f"Successfully loaded PDF ({len(pdf_bytes)} bytes)")
            return pdf_bytes
            
        except Exception as e:
            logger.error(f"Error loading PDF file: {str(e)}")
            return None

    def parse_receipt(self, pdf_path: str) -> Optional[Dict[str, Any]]:
        """
        Parse receipt from PDF using Gemini multimodal model.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Parsed receipt data as dictionary or None if parsing fails
        """
        try:
            # Load PDF as bytes
            pdf_bytes = self.load_pdf_bytes(pdf_path)
            if not pdf_bytes:
                logger.error("Failed to load PDF bytes")
                return None
                
            logger.info("Sending PDF to Gemini for parsing...")
            
            # Create PDF part for Gemini
            pdf_part = Part.from_data(pdf_bytes, mime_type="application/pdf")
            
            # Generate content with Gemini
            response = self.model.generate_content([self.prompt, pdf_part])
            
            if not response.text:
                logger.error("No response from Gemini")
                return None
                
            logger.info("Received response from Gemini")
            logger.info(f"Raw response: {response.text[:500]}...")  # Log first 500 chars
            
            # Parse JSON response
            try:
                # Clean the response text (remove any markdown formatting)
                response_text = response.text.strip()
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                response_text = response_text.strip()
                
                # Try to parse the JSON
                parsed_data = json.loads(response_text)
                logger.info("Successfully parsed JSON response")
                logger.info(f"Parsed data keys: {list(parsed_data.keys())}")
                return parsed_data
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {str(e)}")
                logger.error(f"Response text: {response.text}")
                
                # Try to fix common JSON issues
                try:
                    # Remove any trailing incomplete content
                    if response_text.count('{') > response_text.count('}'):
                        # Find the last complete object
                        last_brace = response_text.rfind('}')
                        if last_brace > 0:
                            response_text = response_text[:last_brace + 1]
                    
                    # Try to escape quotes in the Summary field if it exists
                    if '"Summary":"' in response_text:
                        # Find the Summary field and escape quotes within it
                        summary_start = response_text.find('"Summary":"') + 11
                        summary_end = response_text.find('","', summary_start)
                        if summary_end == -1:
                            summary_end = response_text.find('"}', summary_start)
                        
                        if summary_end > summary_start:
                            summary_content = response_text[summary_start:summary_end]
                            # Escape quotes in summary
                            summary_content = summary_content.replace('"', '\\"')
                            response_text = response_text[:summary_start] + summary_content + response_text[summary_end:]
                    
                    # Try parsing again
                    parsed_data = json.loads(response_text)
                    logger.info("Successfully parsed JSON response after fixing")
                    logger.info(f"Parsed data keys: {list(parsed_data.keys())}")
                    return parsed_data
                    
                except json.JSONDecodeError as e2:
                    logger.error(f"Failed to parse JSON even after fixing: {str(e2)}")
                    logger.error(f"Fixed response text: {response_text}")
                    return None
                
        except Exception as e:
            logger.error(f"Error parsing receipt: {str(e)}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return None

    def save_result(self, data: Dict[str, Any], pdf_path: str, output_path: str = "pipeline_receipt.json"):
        """
        Append parsed receipt data to JSON file (as a list), and include original PDF path.
        Also save the latest receipt data alone in temp_receipt.json.
        
        Args:
            data: Parsed receipt data
            pdf_path: Path to the original PDF file
            output_path: Output file path
        """
        try:
            logger.info(f"Attempting to save result to: {output_path}")
            
            # Add PDF path to data
            
            gofile_url = self.upload_to_gofile(pdf_path)
            if gofile_url:
                data["pdf_path"] = gofile_url
                logger.info(f"Replaced local PDF path with GoFile URL: {gofile_url}")
            else:
                data["pdf_path"] = str(Path(pdf_path).resolve())
                logger.warning(f"Failed to upload to GoFile, using local path: {data['pdf_path']}")
            
            # Check if file already exists and load existing data
            receipts = []
            output_file = Path(output_path)
            
            if output_file.exists():
                logger.info(f"Found existing file: {output_path}")
                with open(output_path, 'r', encoding='utf-8') as f:
                    try:
                        receipts = json.load(f)
                        if not isinstance(receipts, list):
                            logger.warning(f"{output_path} does not contain a list. Overwriting.")
                            receipts = []
                        else:
                            logger.info(f"Loaded {len(receipts)} existing receipts")
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse {output_path}. Starting fresh.")
                        receipts = []
            else:
                logger.info(f"Creating new file: {output_path}")
            
            receipts.append(data)
            logger.info(f"Total receipts to save: {len(receipts)}")

            # Write updated list back
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(receipts, f, separators=(',', ':'), ensure_ascii=False, indent=2)

            # Also save latest receipt only to temp_receipt.json
            temp_path = Path("temp_receipt.json")
            with open(temp_path, 'w', encoding='utf-8') as temp_f:
                json.dump(data, temp_f, separators=(',', ':'), ensure_ascii=False, indent=2)
            logger.info(f"Successfully saved latest receipt to: {temp_path.resolve()}")

            # Verify file was created
            if output_file.exists():
                file_size = output_file.stat().st_size
                logger.info(f"Successfully saved result to: {output_path} (size: {file_size} bytes)")
            else:
                logger.error(f"File was not created: {output_path}")
                
        except Exception as e:
            logger.error(f"Error saving result: {str(e)}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")


def main():
    """Main function to run the receipt parser."""
    
    # Handle both direct argument and --input flag
    pdf_path = None
    
    if len(sys.argv) == 2:
        if sys.argv[1] in ["--help", "-h", "help"]:
            print("Usage: python dataextract.py <path_to_receipt.pdf>")
            print("   or: python dataextract.py --input <path_to_receipt.pdf>")
            print("\nThis script extracts structured data from receipt PDFs using Google Vertex AI Gemini.")
            sys.exit(0)
        # Direct argument: python dataextract.py file.pdf
        pdf_path = sys.argv[1]
    elif len(sys.argv) == 3 and sys.argv[1] == "--input":
        # Flag format: python dataextract.py --input file.pdf
        pdf_path = sys.argv[2]
    else:
        print("Usage: python dataextract.py <path_to_receipt.pdf>")
        print("   or: python dataextract.py --input <path_to_receipt.pdf>")
        sys.exit(1)
    
    # Validate input file
    if not Path(pdf_path).exists():
        logger.error(f"PDF file not found: {pdf_path}")
        sys.exit(1)
    
    if not pdf_path.lower().endswith('.pdf'):
        logger.error(f"Input file must be a PDF: {pdf_path}")
        sys.exit(1)
    
    # Check if project ID is set
    if PROJECT_ID == "your-project-id":
        logger.error("Please set your Google Cloud PROJECT_ID in the script")
        print("\n📋 Setup Instructions:")
        print("1. Replace 'your-project-id' with your actual Google Cloud project ID")
        print("2. Ensure you have Vertex AI API enabled in your project")
        print("3. Choose one authentication method:")
        print("   Method 1 (Recommended): Service Account Key")
        print("   - Create a service account in Google Cloud Console")
        print("   - Download the JSON key file")
        print("   - Set environment variable: export GOOGLE_APPLICATION_CREDENTIALS='/path/to/key.json'")
        print("   Method 2 (Development): gcloud CLI")
        print("   - Run: gcloud auth application-default login")
        print("   - Follow the browser authentication flow")
        print("   Method 3 (Direct): Set SERVICE_ACCOUNT_KEY_PATH in script")
        print("   - Uncomment and set the SERVICE_ACCOUNT_KEY_PATH variable")
        sys.exit(1)
    
    try:
        # Initialize parser
        logger.info("Initializing receipt parser...")
        parser = ReceiptParser(PROJECT_ID, LOCATION, MODEL_NAME)
        
        # Parse receipt
        logger.info(f"Processing receipt: {pdf_path}")
        result = parser.parse_receipt(pdf_path)
        
        if result:
            logger.info("Receipt parsing successful, attempting to save...")
            # Save result (include PDF path)
            parser.save_result(result, pdf_path)
            print("✅ Receipt parsed successfully!")
            print(f"✅ Output saved to: pipeline_receipt.json")
            
            # Verify file exists
            if Path("pipeline_receipt.json").exists():
                print(f"✅ File confirmed to exist at: {Path('pipeline_receipt.json').resolve()}")
            else:
                print("❌ Warning: File was not created!")
            
            # Print summary
            if 'Summary' in result and result['Summary']:
                print(f"\n📋 Summary: {result['Summary']}")
            
            if 'total_amount' in result and result['total_amount']:
                currency = result.get('currency', '')
                print(f"💰 Total: {currency}{result['total_amount']}")
                
        else:
            logger.error("Failed to parse receipt - no result returned")
            print("❌ Receipt parsing failed!")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    main()
