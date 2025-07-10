#!/usr/bin/env python3
"""
Google Wallet Pass Generator for Single Receipt
Creates digital wallet pass from a single receipt in temp_receipt.json
"""

import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import jwt
import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from dotenv import load_dotenv
import tempfile

# Load .env from backend directory
load_dotenv(dotenv_path=Path(__file__).parent.parent / 'backend' / '.env')

# --- Google Credentials Handling ---
if os.getenv('GOOGLE_APPLICATION_CREDENTIALS2_JSON'):
    cred2_json = os.getenv('GOOGLE_APPLICATION_CREDENTIALS2_JSON')
    temp_cred2 = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
    temp_cred2.write(cred2_json.encode())
    temp_cred2.close()
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = temp_cred2.name

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set credentials to the current service account file
# os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(Path(__file__).parent / "tempmail_service.json") # This line is removed

class WalletPassGenerator:
    """Generate Google Wallet passes from receipt data."""
    
    def __init__(self, service_account_file: Optional[str] = None):
        """Initialize the wallet pass generator."""
        self.service_account_file = service_account_file or os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        if not self.service_account_file:
            raise ValueError("Service account file path is required")
            
        self.issuer_id = "3388000000022948485"# Your Google Pay issuer ID
        self.base_url = "https://walletobjects.googleapis.com/walletobjects/v1"  
        self.credentials: Optional[service_account.Credentials] = None
        self.access_token: Optional[str] = None
        
        # Load service account credentials
        self._load_credentials()
        
    def _load_credentials(self):
        """Load and validate service account credentials."""
        try:
            if not self.service_account_file or not Path(self.service_account_file).exists():
                raise FileNotFoundError(f"Service account file not found: {self.service_account_file}")
                
            self.credentials = service_account.Credentials.from_service_account_file(
                self.service_account_file,
                scopes=['https://www.googleapis.com/auth/wallet_object.issuer']
            )
            logger.info("✅ Service account credentials loaded successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to load credentials: {e}")
            raise

    def _get_access_token(self) -> str:
        """Get access token for Google Wallet API."""
        try:
            if not self.credentials:
                raise ValueError("Credentials not loaded")
                
            if not self.credentials.valid:
                self.credentials.refresh(Request())
            
            token = self.credentials.token
            if not token:
                raise ValueError("Failed to obtain access token")
                
            self.access_token = token
            logger.info("✅ Access token obtained")
            return token
            
        except Exception as e:
            logger.error(f"❌ Failed to get access token: {e}")
            raise

    def _make_api_request(self, method: str, url: str, data: Optional[dict] = None) -> dict:
        """Make authenticated API request to Google Wallet."""
        try:
            headers = {
                'Authorization': f'Bearer {self._get_access_token()}',
                'Content-Type': 'application/json'
            }
            
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=headers, json=data)
            elif method.upper() == 'PUT':
                response = requests.put(url, headers=headers, json=data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json() if response.content else {}
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ API request failed: {e}")
            if e.response.content:
                logger.error(f"Response: {e.response.content.decode()}")
            raise
        except Exception as e:
            logger.error(f"❌ Request error: {e}")
            raise

    def create_generic_class(self, class_id: str, category: str) -> dict:
        """Create a generic pass class for receipts."""
        try:
            # Create the generic class
            generic_class = {
                "id": f"{self.issuer_id}.{class_id}",
                "classTemplateInfo": {
                    "cardTemplateOverride": {
                        "cardRowTemplateInfos": [
                            {
                                "twoItems": {
                                    "startItem": {
                                        "firstValue": {
                                            "fields": [
                                                {
                                                    "fieldPath": "object.textModulesData['total']"
                                                }
                                            ]
                                        }
                                    },
                                    "endItem": {
                                        "firstValue": {
                                            "fields": [
                                                {
                                                    "fieldPath": "object.textModulesData['date']"
                                                }
                                            ]
                                        }
                                    }
                                }
                            }
                        ]
                    }
                }
            }
            
            # Try to create the class
            url = f"{self.base_url}/genericClass"
            response = self._make_api_request('POST', url, generic_class)
            logger.info(f"✅ Generic class created: {class_id}")
            return response
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 409:
                logger.info(f"ℹ️  Class already exists: {class_id}")
                return {"id": f"{self.issuer_id}.{class_id}"}
            else:
                raise
        except Exception as e:
            logger.error(f"❌ Failed to create generic class: {e}")
            raise

    def create_list_pass_object(self, pass_data: dict) -> dict:
        """Create a generic pass object for any type of list."""
        try:
            list_type = pass_data.get("list_type", "Generic")
            list_items = pass_data.get("items", [])
            pass_title = pass_data.get("title", f"{list_type.capitalize()} List")

            class_id = f"{list_type.lower().replace(' ', '_')}_class_{uuid.uuid4().hex}"
            object_id = f"{list_type.lower().replace(' ', '_')}_{uuid.uuid4().hex[:8]}"

            # Ensure the generic class exists
            self.create_generic_class(class_id, pass_title)

            items_text = "\\n".join([f"• {item}" for item in list_items])

            text_fields = [
                {
                    "header": f"{pass_title} Items",
                    "body": items_text,
                    "id": "items"
                }
            ]

            generic_object = {
                "id": f"{self.issuer_id}.{object_id}",
                "classId": f"{self.issuer_id}.{class_id}",
                "state": "ACTIVE",
                "header": {
                    "defaultValue": {
                        "language": "en-US",
                        "value": pass_title
                    }
                },
                "subheader": {
                    "defaultValue": {
                        "language": "en-US",
                        "value": f"{len(list_items)} items"
                    }
                },
                "cardTitle": {
                    "defaultValue": {
                        "language": "en-US",
                        "value": pass_title
                    }
                },
                "textModulesData": text_fields,
                "barcode": {
                    "type": "QR_CODE",
                    "value": json.dumps({"object_id": object_id, "type": list_type}),
                    "alternateText": object_id
                }
            }
            
            url = f"{self.base_url}/genericObject"
            response = self._make_api_request('POST', url, generic_object)
            logger.info(f"✅ {list_type} pass object created: {object_id}")
            return response

        except Exception as e:
            logger.error(f"❌ Failed to create list pass object: {e}")
            raise

    def create_generic_object(self, receipt_data: dict) -> dict:
        """Create a generic pass object from receipt data."""
        try:
            # Generate unique IDs
            class_id = f"receipt_{receipt_data['receipt_category'].lower().replace(' ', '_')}_class"
            object_id = f"receipt_{uuid.uuid4().hex[:8]}"
            
            # Create class if it doesn't exist
            self.create_generic_class(class_id, receipt_data['receipt_category'])
            
            # Format currency and amount
            total_amount = receipt_data.get('total_amount', 0)
            currency = receipt_data.get('currency', '$')
            
            # Create text fields for receipt details
            text_fields = [
                {
                    "header": "Total Amount",
                    "body": f"{currency}{total_amount}",
                    "id": "total"
                },
                {
                    "header": "Date",
                    "body": receipt_data.get('date', 'Unknown Date'),
                    "id": "date"
                },
                {
                    "header": "Category",
                    "body": receipt_data.get('receipt_category', 'General'),
                    "id": "category"
                },
                {
                    "header": "Payment Method",
                    "body": receipt_data.get('payment_method', 'Unknown'),
                    "id": "payment"
                }
            ]
            
            # Create the generic object
            generic_object = {
                "id": f"{self.issuer_id}.{object_id}",
                "classId": f"{self.issuer_id}.{class_id}",
                "state": "ACTIVE",
                "header": {
                    "defaultValue": {
                        "language": "en-US",
                        "value": f"{receipt_data['store_name']} Receipt"
                    }
                },
                "subheader": {
                    "defaultValue": {
                        "language": "en-US",
                        "value": f"{receipt_data['receipt_category']} • {receipt_data.get('date', 'Unknown Date')}"
                    }
                },
                "cardTitle": {
                    "defaultValue": {
                        "language": "en-US",
                        "value": f"{currency}{total_amount}"
                    }
                },
                "textModulesData": text_fields,
                "linksModuleData": {
                    "uris": [
                        {
                            "uri": "https://example.com/receipt",
                            "description": "View Full Receipt"
                        }
                    ]
                },
                "imageModulesData": [],
                "barcode": {
                    "type": "QR_CODE",
                    "value": json.dumps({
                        "store": receipt_data.get('store_name', ''),
                        "date": receipt_data.get('date', ''),
                        "total": f"{currency}{total_amount}",
                        "bill_number": receipt_data.get('bill_number', ''),
                        "object_id": object_id
                    }),
                    "alternateText": object_id
                }
            }
            
            # Create the object
            url = f"{self.base_url}/genericObject"
            response = self._make_api_request('POST', url, generic_object)
            logger.info(f"✅ Generic object created: {object_id}")
            return response
            
        except Exception as e:
            logger.error(f"❌ Failed to create generic object: {e}")
            raise

    def create_jwt_token(self, object_id: str) -> str:
        """Create JWT token for wallet pass."""
        try:
            if not self.service_account_file:
                raise ValueError("Service account file path is required")    
                
            # Load service account key
            with open(self.service_account_file, 'r') as f:
                service_account_info = json.load(f)
            
            # Create JWT payload
            payload = {
                "iss": service_account_info['client_email'],
                "aud": "google",
                "typ": "savetowallet",
                "iat": datetime.now().timestamp(),
                "payload": {
                    "genericObjects": [
                        {
                            "id": object_id
                        }
                    ]
                }
            }
            
            # Sign the JWT
            token = jwt.encode(
                payload,
                service_account_info['private_key'],
                algorithm='RS256'
            )
            
            logger.info(f"✅ JWT token created for object: {object_id}")
            return token

        except Exception as e:
            logger.error(f"❌ Failed to create JWT token: {e}")
            raise

    def generate_wallet_link(self, object_id: str) -> str:
        """Generate a 'Save to Google Wallet' link."""
        try:
            jwt_token = self.create_jwt_token(object_id)
            wallet_link = f"https://pay.google.com/gp/v/save/{jwt_token}"
            logger.info(f"✅ Wallet link generated: {wallet_link}")
            return wallet_link
            
        except Exception as e:
            logger.error(f"❌ Failed to generate wallet link: {e}")
            raise

    def process_single_receipt(self, receipt_file: str = "temp_receipt.json") -> str:
        """Process a single receipt and return the wallet pass link."""
        try:
            # Load receipt data
            with open(receipt_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle both single object and array with one object
            if isinstance(data, list):
                if len(data) == 0:
                    raise ValueError("Receipt file is empty")
                data = data[0]
            
            logger.info(f"🔄 Processing receipt: {data.get('store_name', 'Unknown Store')}")
            
            # For a shopping pass, we use a different creation method
            if data.get("pass_type") == "list":
                logger.info("Processing as a generic list pass.")
                created_object = self.create_list_pass_object(data)
            else:
                logger.info("Processing as a standard receipt pass.")
                created_object = self.create_generic_object(data)

            if not created_object or 'id' not in created_object:
                raise ValueError("Failed to create pass object")

            object_id = created_object['id']
            
            # Generate wallet link
            wallet_link = self.generate_wallet_link(object_id)
            
            logger.info(f"✅ Receipt processed successfully")
            return wallet_link
            
        except Exception as e:
            logger.error(f"❌ Failed to process receipt: {e}")
            raise

def main():
    """Main function to be called from the command line."""
    import argparse
    parser = argparse.ArgumentParser(description="Generate a Google Wallet pass from a JSON file.")
    parser.add_argument(
        "--input",
        default="temp_receipt.json",
        help="Path to the input JSON file containing receipt or shopping list data."
    )
    args = parser.parse_args()
    
    try:
        logger.info(f"🚀 Starting Google Wallet Pass Generator for file: {args.input}")
        generator = WalletPassGenerator()
        
        # Process the file specified by the --input argument
        wallet_link = generator.process_single_receipt(receipt_file=args.input)
        
        # The script's primary output should be ONLY the wallet link
        print(wallet_link)
        
    except Exception as e:
        # Log the full error to the console/log file for debugging
        logger.error(f"❌ Script failed to generate pass for {args.input}: {e}", exc_info=True)
        # Exit with a non-zero status code to indicate failure to the calling process
        exit(1)

if __name__ == "__main__":
    main()
