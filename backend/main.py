#!/usr/bin/env python3
"""
Consolidated TechTitan Backend API
Combines all functionality from:
- Chatbot Service (new_chatbot.py)
- Pipeline API (pipeline_api.py) 
- MCP Server (mcp_server.py)
- Bill Splitter (bill_splitter.py)

All endpoints now available on a single port (8000)
"""

import os
import sys
import json
import logging
import asyncio
import subprocess
import urllib.parse
import webbrowser
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List
from concurrent.futures import ThreadPoolExecutor
from dateutil.relativedelta import relativedelta

import requests
import jwt
from google.auth.transport.requests import Request
from google.oauth2 import service_account
import vertexai
from vertexai.generative_models import GenerativeModel

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Body
from pydantic import BaseModel
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import aiofiles
import uvicorn
from dotenv import load_dotenv
import tempfile

# Load .env from backend directory
load_dotenv(dotenv_path=Path(__file__).parent / '.env')

# --- Google Credentials Handling ---
# Write credentials from env to temp files if present
if os.getenv('GOOGLE_APPLICATION_CREDENTIALS_JSON'):
    cred_json = os.getenv('GOOGLE_APPLICATION_CREDENTIALS_JSON')
    temp_cred = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
    temp_cred.write(cred_json.encode())
    temp_cred.close()
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = temp_cred.name

if os.getenv('GOOGLE_APPLICATION_CREDENTIALS2_JSON'):
    cred2_json = os.getenv('GOOGLE_APPLICATION_CREDENTIALS2_JSON')
    temp_cred2 = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
    temp_cred2.write(cred2_json.encode())
    temp_cred2.close()
    os.environ['GOOGLE_APPLICATION_CREDENTIALS2'] = temp_cred2.name

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="TechTitan Consolidated Backend API",
    description="Complete backend service combining chatbot, receipt processing, bill splitting, and MCP functionality",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up Google credentials
# os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(Path(__file__).parent.parent / "backend-raseed" / "splendid-yeti-464913-j2-e4fcc70357d3.json")
# os.environ['GOOGLE_APPLICATION_CREDENTIALS2'] = str(Path(__file__).parent.parent / "backend-raseed" / "tempmail_service.json")

# Global variables
processing_state = {
    "current_image": None,
    "current_pdf": None,
    "current_receipt_data": None,
    "last_wallet_link": None,
    "processing_history": [],
    "bill_splits": []
}

# Available expense categories
EXPENSE_CATEGORIES = [
    "Groceries", "Food", "Transportation", "Travel", "Utilities",
    "Subscriptions", "Healthcare", "Shopping", "Entertainment",
    "Education", "Maintenance", "Financial", "Others"
]

# Supported image formats
SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}

# Pydantic Models
class ChatRequest(BaseModel):
    query: str
    user_id: Optional[str] = None
    language: Optional[str] = "en"

class ChatResponse(BaseModel):
    response: str
    categories_analyzed: List[str]
    receipts_count: int
    wallet_pass_link: Optional[str] = None
    pass_type: Optional[str] = None
    timestamp: str
    list_type: Optional[str] = None
    list_items: Optional[List[str]] = None

class BillSplitRequest(BaseModel):
    receipt_id: Optional[str] = None
    contacts: List[Dict[str, str]]
    upi_payee_vpa: str
    upi_payee_name: str

class ContactInfo(BaseModel):
    name: str
    phone: str
    email: str

class UPIShareRequest(BaseModel):
    contact: ContactInfo
    amount: float
    currency: str
    upi_link: str
    store_name: str
    method: str

class ShoppingPassRequest(BaseModel):
    items: List[str]
    recipe_name: str = "Shopping List"

class QueryRequest(BaseModel):
    query: str
    user_id: Optional[str] = None
    language: Optional[str] = "en"

class FinalResponse(BaseModel):
    chatbot_response: Dict[str, Any]
    pass_generation_result: Optional[Dict[str, Any]] = None

class ProcessingError(Exception):
    """Custom exception for processing errors."""
    pass

# Import all the service classes and functions
# Note: We'll need to adapt these to work within the consolidated app

class EnhancedWalletPassGenerator:
    """Enhanced Google Wallet pass generator with intelligent pass creation"""
    
    def __init__(self, service_account_file: Optional[str] = None):
        """Initialize the wallet pass generator."""
        self.service_account_file = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS2')
        if not self.service_account_file:
            raise ValueError("Service account file path is required")
            
        self.issuer_id = "3388000000022948485"
        self.base_url = "https://walletobjects.googleapis.com/walletobjects/v1"
        self.credentials: Optional[service_account.Credentials] = None
        self.access_token: Optional[str] = None
        
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

    def create_shopping_list_pass(self, shopping_items: List[str], title: str = "Shopping List") -> str:
        """Create a shopping list pass for Google Wallet."""
        try:
            class_id = "shopping_list_class"
            object_id = f"shopping_list_{uuid.uuid4().hex[:8]}"
            
            # Create class if it doesn't exist
            self._create_generic_class(class_id, "Shopping List")
            
            # Format shopping items
            items_text = "\n".join([f"• {item}" for item in shopping_items])
            
            # Create text fields
            text_fields = [
                {
                    "header": "Items Needed",
                    "body": items_text,
                    "id": "items"
                },
                {
                    "header": "Created",
                    "body": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "id": "created"
                },
                {
                    "header": "Total Items",
                    "body": str(len(shopping_items)),
                    "id": "count"
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
                        "value": title
                    }
                },
                "subheader": {
                    "defaultValue": {
                        "language": "en-US",
                        "value": f"{len(shopping_items)} items • {datetime.now().strftime('%Y-%m-%d')}"
                    }
                },
                "textModulesData": [
                    {
                        "header": "Items Needed",
                        "body": items_text,
                        "id": "items"
                    },
                    {
                        "header": "Created",
                        "body": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "id": "created"
                    },
                    {
                        "header": "Total Items",
                        "body": str(len(shopping_items)),
                        "id": "count"
                    }
                ]
            }
            
            # Create the object
            url = f"{self.base_url}/genericObject"
            self._make_api_request("POST", url, generic_object)
            
            # Generate wallet link
            wallet_link = self._generate_wallet_link(object_id)
            logger.info(f"✅ Shopping list pass created: {wallet_link}")
            
            return wallet_link
            
        except Exception as e:
            logger.error(f"❌ Failed to create shopping list pass: {e}")
            raise

    def _create_generic_class(self, class_id: str, category: str) -> dict:
        """Create a generic class for Google Wallet."""
        try:
            class_data = {
                "id": f"{self.issuer_id}.{class_id}",
                "issuerName": "TechTitan",
                "reviewStatus": "UNDER_REVIEW",
                "allowMultipleUsersPerObject": True,
                "genericType": "GENERIC_TYPE_UNSPECIFIED",
                "hexBackgroundColor": "#4285f4",
                "logo": {
                    "sourceUri": {
                        "uri": "https://developers.google.com/identity/images/g-logo.png"
                    }
                },
                "cardTemplateOverride": {
                    "cardRowTemplateInfos": [
                        {
                            "twoItems": {
                                "startItem": {
                                    "firstValue": {
                                        "fields": [
                                            {
                                                "fieldName": {
                                                    "defaultValue": {
                                                        "language": "en-US",
                                                        "value": "Items"
                                                    }
                                                }
                                            }
                                        ]
                                    }
                                },
                                "endItem": {
                                    "firstValue": {
                                        "fields": [
                                            {
                                                "fieldName": {
                                                    "defaultValue": {
                                                        "language": "en-US",
                                                        "value": "Count"
                                                    }
                                                }
                                            }
                                        ]
                                    }
                                }
                            }
                        }
                    ]
                }
            }
            
            url = f"{self.base_url}/genericClass"
            return self._make_api_request("POST", url, class_data)
            
        except Exception as e:
            logger.error(f"❌ Failed to create generic class: {e}")
            raise

    def _generate_wallet_link(self, object_id: str) -> str:
        """Generate a Google Wallet link for the object."""
        try:
            jwt_token = self._create_jwt_token(object_id)
            return f"https://pay.google.com/gp/v/save/{jwt_token}"
        except Exception as e:
            logger.error(f"❌ Failed to generate wallet link: {e}")
            raise

    def _create_jwt_token(self, object_id: str) -> str:
        """Create JWT token for Google Wallet."""
        try:
            payload = {
                "iss": {
                    "email": self.credentials.service_account_email,
                    "signingAlgorithm": "RS256"
                },
                "aud": "google",
                "origins": ["www.example.com"],
                "typ": "savetowallet",
                "payload": {
                    "genericObjects": [
                        {
                            "id": f"{self.issuer_id}.{object_id}"
                        }
                    ]
                }
            }
            
            return jwt.encode(payload, self.credentials.signer, algorithm="RS256")
            
        except Exception as e:
            logger.error(f"❌ Failed to create JWT token: {e}")
            raise

class EnhancedReceiptAnalysisService:
    """Enhanced receipt analysis service with AI integration"""
    
    def __init__(self):
        """Initialize the receipt analysis service."""
        self.receipts_file = Path(__file__).parent.parent / "backend-raseed" / "pipeline_receipt.json"
        self.vertex_project = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "default-project-id")
        self.vertex_location = "us-central1"
        
        # Initialize Vertex AI
        vertexai.init(project=self.vertex_project, location=self.vertex_location)
        self.model = GenerativeModel("gemini-2.5-flash")  # Updated to match your working version
        
    def _load_receipt_data(self) -> List[Dict[str, Any]]:
        """Load receipt data from the pipeline JSON file."""
        if not self.receipts_file.exists():
            return []
        
        try:
            with open(self.receipts_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, list):
                return data
            else:
                return [data]
                
        except Exception as e:
            logger.error(f"Error loading receipt data: {e}")
            return []
    
    def _build_context(self) -> str:
        """Build context from receipt data for AI analysis."""
        receipts = self._load_receipt_data()
        if not receipts:
            return "No receipt data available."
        
        context_parts = []
        for i, receipt in enumerate(receipts[-5:], 1):  # Last 5 receipts
            store = receipt.get('store_name', 'Unknown Store')
            total = receipt.get('total_amount', '0')
            currency = receipt.get('currency', '')
            category = receipt.get('receipt_category', 'Unknown')
            date = receipt.get('date', 'Unknown Date')
            
            context_parts.append(f"Receipt {i}: {store} - {currency}{total} ({category}) on {date}")
        
        return "\n".join(context_parts)

    async def analyze_query_intent(self, query: str, language: str = "en") -> Dict[str, Any]:
        """Analyze the intent of a user query using new_chatbot.py logic."""
        prompt = f"""
        You are an expert at analyzing user queries for a receipt management system.
        Your goal is to classify the user's intent and extract key information.

        You must classify the user's query into one of these intents:
        - 'list_generation': For any query that asks for a list of items. This includes shopping lists, ingredients, packing lists, to-do lists, etc.
        - 'financial_analysis': For queries asking for spending trends, summaries, or financial analysis.
        - 'general_conversation': For all other questions, greetings, or conversational chat.

        If the intent is 'list_generation', you MUST also identify the 'list_type'.
        The 'list_type' should be a short, descriptive snake_case string (e.g., 'grocery_shopping', 'biryani_ingredients', 'vacation_packing').

        Analyze the following user query and return ONLY a single, valid JSON object with the keys \"intent\" and, if applicable, \"list_type\".

        User Query: \"{query}\"
        """
        try:
            response = self.model.generate_content(prompt)
            cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
            return json.loads(cleaned_response)
        except Exception as e:
            logger.error(f"Error analyzing query intent: {e}")
            return {"intent": "general_conversation"}

    async def generate_list_items(self, query: str, context: str, list_type: str, language: str = "en") -> Dict[str, Any]:
        """Generate a list of items based on the user's query, context, and a specified list type."""
        list_title = list_type.replace('_', ' ').title()
        prompt = f"""
        You are a helpful assistant. The user wants a list for '{list_title}'.
        Based on their query and purchase history (if relevant), generate a helpful response and a comma-separated list of items.

        User Query: "{query}"
        Purchase Context: {context}
        Respond in: {language}

        Return a JSON object with two keys:
        1. "response_text": A conversational and helpful response for the user.
        2. "list_items": A comma-separated string of relevant items for the '{list_title}' list.
        """
        try:
            response = self.model.generate_content(prompt)
            cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
            result = json.loads(cleaned_response)
            list_items_str = result.get("list_items", "")
        except Exception as e:
            logger.error(f"Error generating list items: {e}")
            return {
                "response_text": f"I had trouble creating the '{list_title}' list, but I can still help. What kind of items are you looking for?",
                "list_items": []
            }
        list_items = [item.strip() for item in list_items_str.split(',') if item.strip()] if list_items_str else []
        return {
            "response_text": result.get("response_text", f"Here is the {list_title} list you requested."),
            "list_items": list_items
        }

    async def generate_financial_insights(self, query: str, context: str, language: str = "en") -> Dict[str, Any]:
        """Generate financial insights from receipt data."""
        prompt = f"""
        You are an expert financial assistant. Analyze the following receipt data and answer the user's analytics question as clearly and concisely as possible.
        
        Receipts:
        {context}
        
        User Query:
        {query}
        
        Instructions:
        - If the query asks for a total, sum up the relevant amounts and state the total clearly (e.g., 'Your total spend on groceries is ₹12,000.').
        - If the query asks for an average, calculate the average and state it clearly (e.g., 'Your average spend on transportation is ₹1,500.').
        - If the query asks for a month, category, trend, or summary, provide a direct, data-driven answer.
        - If the data is insufficient, say so politely but do not apologize.
        - Always return a clear, actionable insight or summary, with numbers if possible.
        - Respond in the user's language if specified.
        
        Return only the answer, no extra commentary.
        """
        try:
            response = self.model.generate_content(prompt)
            return {"insights": response.text.strip()}
        except Exception as e:
            logger.error(f"Error generating financial insights: {e}")
            return {"insights": "Unable to generate insights at this time."}

    async def generate_response(self, query: str, context: str, language: str = "en") -> str:
        """Generate a natural language response."""
        prompt = f"""
        Based on this query: "{query}"
        And this receipt context: {context}
        
        Provide a helpful, conversational response.
        """
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "I'm here to help with your receipts and shopping needs!"

    async def process_enhanced_chat_query(self, query: str, language: str = "en") -> Dict[str, Any]:
        """Process an enhanced chat query with AI analysis using new_chatbot.py logic."""
        try:
            # Analyze intent
            intent_result = await self.analyze_query_intent(query, language)
            intent = intent_result.get("intent")
            list_type = intent_result.get("list_type")
            
            # Build context
            context = self._build_context()

            # Default response values
            response_text = ""
            wallet_pass_link = None
            pass_type = None
            final_list_items = None
            final_list_type = None

            if intent == "list_generation" and list_type:
                # Generate a specific list (e.g., biryani_ingredients)
                list_result = await self.generate_list_items(query, context, list_type, language)
                response_text = list_result.get("response_text")
                final_list_items = list_result.get("list_items")
                final_list_type = list_type
                pass_type = "list"
            elif intent == "financial_analysis":
                insights = await self.generate_financial_insights(query, context, language)
                response_text = insights.get("insights", "I could not generate a financial summary for your query.")
                pass_type = None
            else:
                response_text = await self.generate_response(query, context, language)

            return {
                "response": response_text,
                "categories_analyzed": [],
                "receipts_count": len(self._load_receipt_data()),
                "wallet_pass_link": wallet_pass_link,
                "pass_type": pass_type,
                "timestamp": datetime.now().isoformat(),
                "list_type": final_list_type,
                "list_items": final_list_items,
            }
        except Exception as e:
            logger.error(f"Error processing enhanced chat query: {e}")
            return {
                "response": "I'm having trouble processing your request right now. Please try again.",
                "categories_analyzed": [],
                "receipts_count": 0,
                "wallet_pass_link": None,
                "pass_type": None,
                "timestamp": datetime.now().isoformat(),
                "list_type": None,
                "list_items": None
            }

class BillSplitterService:
    """Bill splitting service integrated with the consolidated API"""
    
    def __init__(self, receipt_file="pipeline_receipt.json"):
        self.receipt_file = Path(__file__).parent.parent / "backend-raseed" / receipt_file
        
        # Default UPI details (can be overridden)
        self.upi_details = {
            "payee_vpa": "9205704825@ptsbi",
            "payee_name": "Maisha",
        }
    
    def _load_receipts(self) -> List[Dict[str, Any]]:
        """Load receipts from the pipeline JSON file"""
        if not self.receipt_file.exists():
            return []
        
        try:
            with open(self.receipt_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, list):
                return data
            else:
                return [data]
                
        except Exception as e:
            logger.error(f"Error loading receipts: {e}")
            return []
    
    def calculate_split(self, receipt: Dict[str, Any], contacts: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Calculate bill split among selected contacts"""
        total_amount = float(receipt.get('total_amount', 0))
        currency = receipt.get('currency', '')
        num_people = len(contacts)
        
        if total_amount <= 0 or num_people <= 0:
            return None
        
        # Calculate split amounts
        amount_per_person = total_amount / num_people
        
        # Handle rounding (last person pays the difference)
        rounded_amounts = [round(amount_per_person, 2)] * (num_people - 1)
        last_amount = round(total_amount - sum(rounded_amounts), 2)
        rounded_amounts.append(last_amount)
        
        # Create split summary
        split_data = {
            "receipt_info": {
                "store_name": receipt.get('store_name', 'Unknown Store'),
                "date": receipt.get('date', 'Unknown Date'),
                "total_amount": total_amount,
                "currency": currency,
                "category": receipt.get('receipt_category', 'Unknown')
            },
            "split_details": {
                "total_people": num_people,
                "amount_per_person": amount_per_person,
                "splits": []
            },
            "timestamp": datetime.now().isoformat()
        }
        
        # Assign amounts to contacts
        for i, contact in enumerate(contacts):
            split_data["split_details"]["splits"].append({
                "name": contact.get("name", "Unknown"),
                "phone": contact.get("phone", ""),
                "email": contact.get("email", ""),
                "amount": rounded_amounts[i],
                "currency": currency
            })
        
        return split_data
    
    def generate_upi_link(self, amount: float, contact: Dict[str, Any], receipt_info: Dict[str, Any]) -> str:
        """Generate UPI payment link for a specific amount and contact"""
        if not self.upi_details["payee_vpa"] or not self.upi_details["payee_name"]:
            return ""
        
        # Generate transaction reference
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        transaction_ref = f"BILLSPLIT_{timestamp}_{contact['name'].replace(' ', '')}"
        
        # Transaction note
        store_name = receipt_info.get('store_name', 'Unknown Store')
        transaction_note = f"Bill split - {store_name}"
        
        # Format amount to 2 decimal places
        formatted_amount = f"{amount:.2f}"
        
        # Build UPI URL
        upi_params = {
            'pa': self.upi_details["payee_vpa"],
            'pn': self.upi_details["payee_name"],
            'tn': transaction_note,
            'am': formatted_amount,
            'tr': transaction_ref,
            'cu': 'INR'
        }
        
        upi_url = f"upi://pay?{urllib.parse.urlencode(upi_params)}"
        return upi_url

# Initialize services
wallet_generator = EnhancedWalletPassGenerator()
receipt_analyzer = EnhancedReceiptAnalysisService()
bill_splitter = BillSplitterService()

# Utility functions
def run_script(script_name: str, args: Optional[list] = None, timeout: int = 300) -> tuple[bool, str]:
    """Run a Python script with given arguments."""
    try:
        script_path = Path(__file__).parent.parent / "backend-raseed" / script_name
        cmd = [sys.executable, str(script_path)]
        if args:
            cmd.extend(args)
        logger.info(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=Path(__file__).parent.parent / "backend-raseed"
        )
        if result.returncode == 0:
            logger.info(f"✅ {script_name} completed successfully")
            return True, result.stdout
        else:
            logger.error(f"❌ {script_name} failed: {result.stderr}")
            return False, result.stderr
    except Exception as e:
        error_msg = f"Failed to run {script_name}: {e}"
        logger.error(error_msg)
        return False, error_msg

def find_latest_file(pattern: str, directory: str = ".") -> Optional[str]:
    """Find the latest file matching a pattern."""
    try:
        files = list(Path(directory).glob(pattern))
        if not files:
            return None
        return str(max(files, key=lambda x: x.stat().st_mtime))
    except Exception as e:
        logger.error(f"Error finding latest file: {e}")
        return None

# API Endpoints

@app.get("/")
async def root():
    """Root endpoint with server information."""
    return {
        "message": "Welcome to TechTitan Consolidated Backend API",
        "version": "1.0.0",
        "description": "Complete backend service combining all functionality",
        "endpoints": {
            "chat": "/chat - Enhanced chatbot with AI analysis",
            "upload": "/upload - Upload and process receipt images",
            "extract": "/extract - Extract data from PDFs",
            "passgen": "/passgen - Generate Google Wallet passes",
            "process-complete": "/process-complete - Complete pipeline: Upload → Extract → Generate Pass",
            "split-bill": "/split-bill - Split bills among contacts",
            "share-upi": "/share-upi - Share UPI payment links via WhatsApp/SMS",
            "process": "/process - MCP-style query processing",
            "generate-shopping-pass": "/generate-shopping-pass - Generate shopping list passes",
            "receipts": "/receipts/all - Get all processed receipts",
            "categories": "/categories - Get expense categories",
            "split-history": "/split-history - Get bill split history",
            "health": "/health - Health check",
            "status": "/status - System status",
            "monthlyexpenditure": "/monthlyexpenditure - Get total expenditure for the last month"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "wallet_generator": "initialized",
            "receipt_analyzer": "initialized",
            "bill_splitter": "initialized"
        }
    }

@app.get("/status")
async def get_status():
    """Get system status and processing state."""
    receipts = bill_splitter._load_receipts()
    return {
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "processing_state": processing_state,
        "receipts_count": len(receipts),
        "recent_receipts": receipts[-3:] if receipts else [],
        "categories": EXPENSE_CATEGORIES
    }

@app.post("/chat", response_model=ChatResponse)
async def enhanced_chat_endpoint(request: ChatRequest):
    """Enhanced chatbot endpoint with AI analysis."""
    try:
        result = await receipt_analyzer.process_enhanced_chat_query(
            request.query, 
            request.language or "en"
        )
        
        # Generate wallet pass if list items are present using pass_generation.py
        wallet_pass_link = None
        if result.get("list_items"):
            try:
                # Prepare temp JSON file for pass_generation.py
                temp_pass_data = {
                    "items": result["list_items"],
                    "list_type": result.get("list_type", "shopping"),
                    "title": result.get("list_type", "shopping").replace('_', ' ').title(),
                    "pass_type": "list"
                }
                temp_path = Path(__file__).parent.parent / "backend-raseed" / "temp_receipt.json"
                with open(temp_path, "w", encoding="utf-8") as f:
                    json.dump(temp_pass_data, f, ensure_ascii=False)
                # Call pass_generation.py as subprocess
                success, output = run_script("pass_generation.py", ["--input", str(temp_path)])
                if success:
                    for line in output.strip().split('\n'):
                        if line.startswith('https://pay.google.com'):
                            wallet_pass_link = line.strip()
                            break
                else:
                    logger.error(f"Pass generation script failed: {output}")
                result["wallet_pass_link"] = wallet_pass_link
            except Exception as e:
                logger.error(f"Failed to generate wallet pass: {e}")
        
        return ChatResponse(**result)
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/process", response_model=FinalResponse)
async def process_query_endpoint(request: QueryRequest):
    """MCP-style query processing endpoint."""
    try:
        # Process query through the enhanced chatbot
        chatbot_result = await receipt_analyzer.process_enhanced_chat_query(
            request.query, 
            request.language or "en"
        )
        
        final_response = {"chatbot_response": chatbot_result}
        
        # Generate pass if list items are present using pass_generation.py
        if chatbot_result.get("list_items"):
            try:
                temp_pass_data = {
                    "items": chatbot_result["list_items"],
                    "list_type": chatbot_result.get("list_type", "shopping"),
                    "title": chatbot_result.get("list_type", "shopping").replace('_', ' ').title(),
                    "pass_type": "list"
                }
                temp_path = Path(__file__).parent.parent / "backend-raseed" / "temp_receipt.json"
                with open(temp_path, "w", encoding="utf-8") as f:
                    json.dump(temp_pass_data, f, ensure_ascii=False)
                success, output = run_script("pass_generation.py", ["--input", str(temp_path)])
                wallet_link = None
                if success:
                    for line in output.strip().split('\n'):
                        if line.startswith('https://pay.google.com'):
                            wallet_link = line.strip()
                            break
                    final_response["pass_generation_result"] = {
                        "success": True, 
                        "wallet_link": wallet_link
                    }
                else:
                    logger.error(f"Pass generation script failed: {output}")
                    final_response["pass_generation_result"] = {
                        "status": "error", 
                        "detail": str(output)
                    }
            except Exception as e:
                logger.error(f"Failed to generate pass: {e}")
                final_response["pass_generation_result"] = {
                    "status": "error", 
                    "detail": str(e)
                }
        
        return FinalResponse(**final_response)
        
    except Exception as e:
        logger.error(f"Error in process endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload")
async def upload_image(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    debug: bool = False
):
    """Upload and process receipt image."""
    try:
        # Validate file type
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in SUPPORTED_FORMATS:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file format. Supported: {', '.join(SUPPORTED_FORMATS)}"
            )
        
        # Save uploaded file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"uploaded_image_{timestamp}{file_ext}"
        file_path = Path(__file__).parent.parent / "backend-raseed" / filename
        
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        processing_state["current_image"] = str(file_path)
        
        # Convert image to PDF using the existing script
        success, output = run_script("imageconvert.py", ["--input", str(file_path)])
        
        if not success:
            raise HTTPException(status_code=500, detail=f"Image conversion failed: {output}")
        
        # Find the generated PDF
        pdf_file = find_latest_file("receipt_*.pdf", str(Path(__file__).parent.parent / "backend-raseed"))
        if not pdf_file:
            raise HTTPException(status_code=500, detail="PDF generation failed")
        
        processing_state["current_pdf"] = pdf_file
        
        # Extract data from PDF
        success, output = run_script("dataextract.py", ["--input", pdf_file])
        
        if not success:
            raise HTTPException(status_code=500, detail=f"Data extraction failed: {output}")
        
        # Load extracted data
        receipt_file = find_latest_file("pipeline_receipt.json", str(Path(__file__).parent.parent / "backend-raseed"))
        if receipt_file:
            with open(receipt_file, 'r') as f:
                receipt_data = json.load(f)
            processing_state["current_receipt_data"] = receipt_data
        
        return {
            "message": "Image uploaded and processed successfully",
            "image_file": filename,
            "pdf_file": Path(pdf_file).name,
            "receipt_data": processing_state["current_receipt_data"]
        }
        
    except Exception as e:
        logger.error(f"Error in upload endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/extract")
async def extract_data(pdf_file: Optional[str] = None):
    """Extract data from PDF file."""
    try:
        if not pdf_file:
            pdf_file = processing_state.get("current_pdf")
            if not pdf_file:
                raise HTTPException(status_code=400, detail="No PDF file available")
        
        success, output = run_script("dataextract.py", ["--input", pdf_file])
        
        if not success:
            raise HTTPException(status_code=500, detail=f"Data extraction failed: {output}")
        
        # Load extracted data
        receipt_file = find_latest_file("pipeline_receipt.json", str(Path(__file__).parent.parent / "backend-raseed"))
        if receipt_file:
            with open(receipt_file, 'r') as f:
                receipt_data = json.load(f)
            # receipt_data is a list, get the latest receipt
            if isinstance(receipt_data, list) and receipt_data:
                processing_state["current_receipt_data"] = receipt_data[-1]  # Get the latest receipt
            else:
                processing_state["current_receipt_data"] = receipt_data
        
        return {
            "message": "Data extraction completed",
            "receipt_data": processing_state["current_receipt_data"]
        }
        
    except Exception as e:
        logger.error(f"Error in extract endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/passgen")
async def generate_pass():
    """Generate Google Wallet pass from current receipt data."""
    try:
        if not processing_state["current_receipt_data"]:
            raise HTTPException(status_code=400, detail="No receipt data available")
        
        # Use the existing pass generation script
        success, output = run_script("pass_generation.py")
        
        if not success:
            raise HTTPException(status_code=500, detail=f"Pass generation failed: {output}")
        
        # Extract wallet link from output
        lines = output.strip().split('\n')
        wallet_link = None
        for line in lines:
            if line.startswith('https://pay.google.com'):
                wallet_link = line.strip()
                break
        
        if not wallet_link:
            raise HTTPException(status_code=500, detail="No wallet link generated")
        
        processing_state["last_wallet_link"] = wallet_link
        
        return {
            "message": "Google Wallet pass generated successfully",
            "wallet_link": wallet_link
        }
        
    except Exception as e:
        logger.error(f"Error in passgen endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/split-bill")
async def split_bill(request: BillSplitRequest):
    """Split bill among selected contacts."""
    try:
        # Get receipt data
        if request.receipt_id:
            # Find specific receipt by ID
            receipts = bill_splitter._load_receipts()
            receipt = next((r for r in receipts if r.get('id') == request.receipt_id), None)
            if not receipt:
                raise HTTPException(status_code=404, detail="Receipt not found")
        else:
            # Use current receipt data
            if not processing_state["current_receipt_data"]:
                raise HTTPException(status_code=400, detail="No receipt data available")
            receipt = processing_state["current_receipt_data"]
        
        # Update UPI details if provided
        if request.upi_payee_vpa and request.upi_payee_name:
            bill_splitter.upi_details = {
                "payee_vpa": request.upi_payee_vpa,
                "payee_name": request.upi_payee_name
            }
        
        # Calculate split
        split_data = bill_splitter.calculate_split(receipt, request.contacts)
        
        if not split_data:
            raise HTTPException(status_code=400, detail="Invalid split calculation")
        
        # Generate UPI links for each contact
        upi_links = []
        for split in split_data["split_details"]["splits"]:
            contact = {
                "name": split["name"],
                "phone": split["phone"],
                "email": split["email"]
            }
            upi_link = bill_splitter.generate_upi_link(
                split["amount"], 
                contact, 
                split_data["receipt_info"]
            )
            upi_links.append({
                "contact": contact,
                "amount": split["amount"],
                "currency": split["currency"],
                "upi_link": upi_link
            })
        
        # Save split record
        split_data["upi_links"] = upi_links
        processing_state["bill_splits"].append(split_data)
        
        return {
            "success": True,
            "message": "Bill split calculated successfully",
            "split_data": split_data,
            "upi_links": upi_links
        }
        
    except Exception as e:
        logger.error(f"Error in split-bill endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/process-complete")
async def process_complete(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    debug: bool = False
):
    """
    Complete pipeline: Upload → Extract → Generate Pass in one call.
    
    Args:
        file: Image file to upload
        debug: Enable debug mode
        
    Returns:
        Complete processing result with wallet link
    """
    try:
        # Step 1: Upload and convert
        logger.info("🔄 Starting complete pipeline processing...")
        
        # Validate file type
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in SUPPORTED_FORMATS:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file format. Supported: {', '.join(SUPPORTED_FORMATS)}"
            )
        
        # Save uploaded file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"uploaded_image_{timestamp}{file_ext}"
        file_path = Path(__file__).parent.parent / "backend-raseed" / filename
        
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        processing_state["current_image"] = str(file_path)
        
        # Convert image to PDF using the existing script
        success, output = run_script("imageconvert.py", ["--input", str(file_path)])
        
        if not success:
            raise HTTPException(status_code=500, detail=f"Image conversion failed: {output}")
        
        # Find the generated PDF
        pdf_file = find_latest_file("receipt_*.pdf", str(Path(__file__).parent.parent / "backend-raseed"))
        if not pdf_file:
            raise HTTPException(status_code=500, detail="PDF generation failed")
        
        processing_state["current_pdf"] = pdf_file
        
        # Step 2: Extract data from PDF
        success, output = run_script("dataextract.py", ["--input", pdf_file])
        
        if not success:
            raise HTTPException(status_code=500, detail=f"Data extraction failed: {output}")
        
        # Load extracted data
        receipt_file = find_latest_file("pipeline_receipt.json", str(Path(__file__).parent.parent / "backend-raseed"))
        if receipt_file:
            with open(receipt_file, 'r') as f:
                receipt_data = json.load(f)
            # receipt_data is a list, get the latest receipt
            if isinstance(receipt_data, list) and receipt_data:
                processing_state["current_receipt_data"] = receipt_data[-1]  # Get the latest receipt
            else:
                processing_state["current_receipt_data"] = receipt_data
        
        # Step 3: Generate pass
        if not processing_state["current_receipt_data"]:
            raise HTTPException(status_code=400, detail="No receipt data available for pass generation")
        
        # Use the existing pass generation script
        success, output = run_script("pass_generation.py")
        
        if not success:
            raise HTTPException(status_code=500, detail=f"Pass generation failed: {output}")
        
        # Extract wallet link from output
        lines = output.strip().split('\n')
        wallet_link = None
        for line in lines:
            if line.startswith('https://pay.google.com'):
                wallet_link = line.strip()
                break
        
        if not wallet_link:
            raise HTTPException(status_code=500, detail="No wallet link generated")
        
        processing_state["last_wallet_link"] = wallet_link
        
        logger.info("✅ Complete pipeline processing finished successfully")
        
        return {
            "success": True,
            "message": "Complete processing pipeline executed successfully",
            "steps": {
                "upload": {
                    "success": True,
                    "image_file": filename,
                    "pdf_file": Path(pdf_file).name
                },
                "extract": {
                    "success": True,
                    "receipt_data": processing_state["current_receipt_data"]
                },
                "passgen": {
                    "success": True,
                    "wallet_link": wallet_link
                }
            },
            "wallet_link": wallet_link,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Complete processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate-shopping-pass")
async def generate_shopping_pass(request: ShoppingPassRequest):
    """Generate shopping list pass for Google Wallet."""
    try:
        wallet_link = wallet_generator.create_shopping_list_pass(
            request.items,
            request.recipe_name
        )
        
        return {
            "message": "Shopping list pass generated successfully",
            "wallet_link": wallet_link,
            "items": request.items,
            "title": request.recipe_name
        }
        
    except Exception as e:
        logger.error(f"Error in generate-shopping-pass endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/receipts/all")
async def get_all_receipts():
    """Get all processed receipts."""
    try:
        receipts = bill_splitter._load_receipts()
        return {
            "receipts": receipts,
            "count": len(receipts)
        }
    except Exception as e:
        logger.error(f"Error getting receipts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/receipts/count")
async def get_receipts_count():
    """Get the count of processed receipts."""
    try:
        receipts = bill_splitter._load_receipts()
        return {"count": len(receipts)}
    except Exception as e:
        logger.error(f"Error getting receipt count: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/receipts/category/{category_name}")
async def get_receipts_by_category(category_name: str):
    """Get all receipts for a specific category (case-insensitive)."""
    try:
        receipts = bill_splitter._load_receipts()
        filtered = [r for r in receipts if r.get("receipt_category", "").lower() == category_name.lower()]
        return {"receipts": filtered, "count": len(filtered)}
    except Exception as e:
        logger.error(f"Error getting receipts by category: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/receipts/percentage")
async def get_receipt_category_percentages():
    """Get percentage breakdown of expenses by category."""
    try:
        receipts = bill_splitter._load_receipts()
        if not receipts:
            return {"categories": [], "total": 0}
        # Sum total per category
        category_totals = {}
        total_spend = 0.0
        for r in receipts:
            cat = r.get("receipt_category", "Unknown")
            amt = float(r.get("total_amount", 0))
            category_totals[cat] = category_totals.get(cat, 0.0) + amt
            total_spend += amt
        # Calculate percentages
        result = []
        for cat, amt in category_totals.items():
            pct = (amt / total_spend * 100) if total_spend > 0 else 0
            result.append({"category": cat, "amount": round(amt, 2), "percentage": round(pct, 2)})
        # Sort by amount descending
        result.sort(key=lambda x: x["amount"], reverse=True)
        return {"categories": result, "total": round(total_spend, 2)}
    except Exception as e:
        logger.error(f"Error calculating category percentages: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/history")
async def get_processing_history():
    """Get processing history."""
    try:
        history_file = Path(__file__).parent.parent / "backend-raseed" / "processing_history.json"
        if not history_file.exists():
            return {"history": []}
            
        with open(history_file, 'r', encoding='utf-8') as f:
            history = json.load(f)
            
        return {"history": history}
        
    except Exception as e:
        logger.error(f"Error getting processing history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/categories")
async def get_categories():
    """Get available expense categories."""
    return {
        "categories": EXPENSE_CATEGORIES
    }

@app.post("/share-upi")
async def share_upi_payment(request: UPIShareRequest):
    """
    Generate shareable message for UPI payment (returns URLs for WhatsApp/SMS).
    Note: Actual sending of WhatsApp/SMS is not implemented server-side.
    """
    try:
        contact = request.contact
        if request.method == "whatsapp":
            # Only generate WhatsApp URL, do not send
            phone = contact.phone.replace('+', '').replace('-', '').replace(' ', '')
            message = (f"Hi {contact.name}! 👋\n\n"
                      f"Here's your share from our bill at {request.store_name}:\n"
                      f"💰 Amount: {request.currency}{request.amount:.2f}\n\n"
                      f"💳 *Pay via UPI:*\n"
                      f"{request.upi_link}\n\n"
                      f"📱 *How to pay:*\n"
                      f"1. Tap the link above OR\n"
                      f"2. Copy the link and open any UPI app\n"
                      f"3. The payment details will auto-fill\n\n"
                      f"Thanks! 😊\n\n"
                      f"🧾 _Sent via Receipt Processing System_")
            whatsapp_url = f"https://wa.me/{phone}?text={urllib.parse.quote(message)}"
            return {
                "success": True,
                "method": "whatsapp",
                "share_url": whatsapp_url,
                "message": message,
                "contact": contact.name,
                "note": "This only generates a WhatsApp share URL. Actual sending is not implemented server-side."
            }
        elif request.method == "sms":
            # Only generate SMS URL, do not send
            message = (f"Hi {contact.name}! Your share from {request.store_name}: "
                      f"{request.currency}{request.amount:.2f}. "
                      f"Pay via UPI: {request.upi_link}")
            sms_url = f"sms:{contact.phone}?body={urllib.parse.quote(message)}"
            return {
                "success": True,
                "method": "sms",
                "share_url": sms_url,
                "message": message,
                "contact": contact.name,
                "note": "This only generates an SMS share URL. Actual sending is not implemented server-side."
            }
        else:
            return {
                "success": False,
                "error": "Invalid method. Only 'whatsapp' and 'sms' are supported.",
                "note": "No real WhatsApp/SMS sending is implemented. Only share URLs are generated."
            }
    except Exception as e:
        logger.error(f"Unexpected error in share_upi: {e}")
        return {
            "success": False,
            "error": f"Internal server error: {str(e)}",
            "note": "No real WhatsApp/SMS sending is implemented. Only share URLs are generated."
        }

@app.get("/split-history")
async def get_split_history():
    """Get bill split history."""
    return {
        "splits": processing_state["bill_splits"]
    }

@app.post("/generate-upi")
async def generate_upi_links(
    upi_payee_vpa: str = '',
    upi_payee_name: str = '',
    receipt_id: str = None
):
    """Generate UPI payment links for the latest bill split."""
    try:
        if not processing_state["bill_splits"]:
            raise HTTPException(
                status_code=400,
                detail="No bill splits available. Please split a bill first."
            )

        # Use the latest split if no specific receipt_id provided
        latest_split = processing_state["bill_splits"][-1]

        # Update UPI details if provided
        if upi_payee_vpa and upi_payee_name:
            bill_splitter.upi_details = {
                "payee_vpa": upi_payee_vpa,
                "payee_name": upi_payee_name
            }

        # Generate UPI links
        upi_links = []
        for split in latest_split["split_details"]["splits"]:
            upi_link = bill_splitter.generate_upi_link(
                split["amount"],
                split,
                latest_split["receipt_info"]
            )
            if upi_link:
                upi_links.append({
                    "contact": split,
                    "upi_link": upi_link,
                    "amount": split["amount"],
                    "currency": split["currency"]
                })

        return {
            "success": True,
            "message": f"Generated {len(upi_links)} UPI payment links",
            "upi_links": upi_links,
            "split_id": latest_split.get("split_id", "unknown"),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Unexpected error in generate_upi: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/monthlyexpenditure")
async def get_monthly_expenditure():
    """Calculate and return the total expenditure for the last month."""
    try:
        # Load all receipts
        receipts = bill_splitter._load_receipts()
        if not receipts:
            return {"monthly_expenditure": 0, "currency": "INR", "count": 0}

        # Calculate date range: from (today - 1 month) to today
        today = datetime.now()
        one_month_ago = today - relativedelta(months=1)

        # Sum up total_amount for receipts in the last month
        total = 0.0
        currency = None
        count = 0
        for receipt in receipts:
            try:
                date_str = receipt.get('date')
                if not date_str:
                    continue
                # Try parsing date in common formats
                for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"):
                    try:
                        receipt_date = datetime.strptime(date_str, fmt)
                        break
                    except Exception:
                        receipt_date = None
                else:
                    receipt_date = None
                if not receipt_date:
                    continue
                if one_month_ago <= receipt_date <= today:
                    amt = float(receipt.get('total_amount', 0))
                    total += amt
                    currency = receipt.get('currency', currency)
                    count += 1
            except Exception:
                continue
        return {"monthly_expenditure": round(total, 2), "currency": currency or "INR", "count": count}
    except Exception as e:
        logger.error(f"Error calculating monthly expenditure: {e}")
        return {"monthly_expenditure": 0, "currency": "INR", "count": 0, "error": str(e)}

@app.post("/analytics")
async def analytics_endpoint(request: ChatRequest):
    """Return financial analytics or insights based on receipts and user query. be conscise and to the point"""
    try:
        # Build context from receipts
        context = receipt_analyzer._build_context()
        # Use the user's query and language (default to 'en')
        result = await receipt_analyzer.generate_financial_insights(
            request.query, context, request.language or "en"
        )
        return result
    except Exception as e:
        logger.error(f"Error in analytics endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    logger.info("🚀 Starting TechTitan Consolidated Backend API on port 8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True) 
