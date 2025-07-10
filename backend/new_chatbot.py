"""
Enhanced Receipt Chatbot with Google Wallet Integration
Supports local language queries, spending analysis, and intelligent pass generation
"""

import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List
import jwt
import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import vertexai
from vertexai.generative_models import GenerativeModel
import uvicorn

from fastapi.middleware.cors import CORSMiddleware

# Initialize FastAPI app
app = FastAPI(title="Enhanced Receipt Chatbot with Google Wallet", version="2.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set credentials
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(Path(__file__).parent / "splendid-yeti-464913-j2-e4fcc70357d3.json")

# Initialize FastAPI app
# app = FastAPI(title="Enhanced Receipt Chatbot with Google Wallet", version="2.0.0") # This line is removed as per the edit hint.

# Available expense categories
EXPENSE_CATEGORIES = [
    "Groceries", "Food", "Transportation", "Travel", "Utilities",
    "Subscriptions", "Healthcare", "Shopping", "Entertainment",
    "Education", "Maintenance", "Financial", "Others"
]

# Pydantic models
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

os.environ['GOOGLE_APPLICATION_CREDENTIALS2'] = str(Path(__file__).parent / "tempmail_service.json")

class EnhancedWalletPassGenerator:
    """Enhanced Google Wallet pass generator with intelligent pass creation"""
    
    def __init__(self, service_account_file: Optional[str] = None):
        """Initialize the wallet pass generator."""
        self.service_account_file =os.environ.get('GOOGLE_APPLICATION_CREDENTIALS2')
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
                "cardTitle": {
                    "defaultValue": {
                        "language": "en-US",
                        "value": f"🛒 {len(shopping_items)} Items"
                    }
                },
                "textModulesData": text_fields,
                "barcode": {
                    "type": "QR_CODE",
                    "value": json.dumps({
                        "type": "shopping_list",
                        "items": shopping_items,
                        "created": datetime.now().isoformat(),
                        "object_id": object_id
                    }),
                    "alternateText": object_id
                }
            }
            
            # Create the object
            url = f"{self.base_url}/genericObject"
            response = self._make_api_request('POST', url, generic_object)
            logger.info(f"✅ Shopping list pass created: {object_id}")
            
            return self._generate_wallet_link(f"{self.issuer_id}.{object_id}")
            
        except Exception as e:
            logger.error(f"❌ Failed to create shopping list pass: {e}")
            raise

    def create_financial_insights_pass(self, insights: Dict[str, Any]) -> str:
        """Create a financial insights pass for Google Wallet."""
        try:
            class_id = "financial_insights_class"
            object_id = f"insights_{uuid.uuid4().hex[:8]}"
            
            # Create class if it doesn't exist
            self._create_generic_class(class_id, "Financial Insights")
            
            # Format insights
            main_insight = insights.get('main_insight', 'No insights available')
            spending_trend = insights.get('spending_trend', 'Stable')
            top_category = insights.get('top_category', 'Unknown')
            savings_tip = insights.get('savings_tip', 'Track your expenses regularly')
            
            # Create text fields
            text_fields = [
                {
                    "header": "Key Insight",
                    "body": main_insight,
                    "id": "insight"
                },
                {
                    "header": "Spending Trend",
                    "body": f"📈 {spending_trend}",
                    "id": "trend"
                },
                {
                    "header": "Top Category",
                    "body": f"🏆 {top_category}",
                    "id": "category"
                },
                {
                    "header": "Savings Tip",
                    "body": f"💡 {savings_tip}",
                    "id": "tip"
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
                        "value": "💰 Financial Insights"
                    }
                },
                "subheader": {
                    "defaultValue": {
                        "language": "en-US",
                        "value": f"Spending Analysis • {datetime.now().strftime('%Y-%m-%d')}"
                    }
                },
                "cardTitle": {
                    "defaultValue": {
                        "language": "en-US",
                        "value": f"Trend: {spending_trend}"
                    }
                },
                "textModulesData": text_fields,
                "barcode": {
                    "type": "QR_CODE",
                    "value": json.dumps({
                        "type": "financial_insights",
                        "main_insight": main_insight,
                        "top_category": top_category,
                        "object_id": object_id
                    }),
                    "alternateText": object_id
                }
            }
            
            # Create the object
            url = f"{self.base_url}/genericObject"
            response = self._make_api_request('POST', url, generic_object)
            logger.info(f"✅ Financial insights pass created: {object_id}")
            
            return self._generate_wallet_link(f"{self.issuer_id}.{object_id}")
            
        except Exception as e:
            logger.error(f"❌ Failed to create financial insights pass: {e}")
            raise

    def _create_generic_class(self, class_id: str, category: str) -> dict:
        """Create a generic pass class."""
        try:
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
                                                    "fieldPath": "object.textModulesData['insight']"
                                                }
                                            ]
                                        }
                                    },
                                    "endItem": {
                                        "firstValue": {
                                            "fields": [
                                                {
                                                    "fieldPath": "object.textModulesData['created']"
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

    def _generate_wallet_link(self, object_id: str) -> str:
        """Generate a 'Save to Google Wallet' link."""
        try:
            jwt_token = self._create_jwt_token(object_id)
            wallet_link = f"https://pay.google.com/gp/v/save/{jwt_token}"
            logger.info(f"✅ Wallet link generated: {wallet_link}")
            return wallet_link
            
        except Exception as e:
            logger.error(f"❌ Failed to generate wallet link: {e}")
            raise

    def _create_jwt_token(self, object_id: str) -> str:
        """Create JWT token for wallet pass."""
        try:
            if not self.service_account_file:
                raise ValueError("Service account file not found.")

            with open(self.service_account_file, 'r') as f:
                service_account_info = json.load(f)
            
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
            
            token = jwt.encode(
                payload,
                service_account_info['private_key'],
                algorithm='RS256'
            )
            
            return token

        except Exception as e:
            logger.error(f"❌ Failed to create JWT token: {e}")
            raise

class EnhancedReceiptAnalysisService:
    """Enhanced service class with local language support and intelligent pass generation"""

    def __init__(self):
        vertexai.init(
            project=os.getenv("GOOGLE_CLOUD_PROJECT", "splendid-yeti-464913-j2"),
            location=os.getenv("GOOGLE_CLOUD_REGION", "us-central1")
        )
        self.gemini = GenerativeModel("gemini-2.5-flash")
        self.receipt_data = self._load_receipt_data()
        self.wallet_generator = EnhancedWalletPassGenerator()

    def _load_receipt_data(self) -> List[Dict[str, Any]]:
        """Load receipt data from pipeline_receipt.json"""
        try:
            with open("pipeline_receipt.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                raise ValueError("pipeline_receipt.json must contain a JSON array of receipts.")
            logger.info(f"Loaded {len(data)} receipts from pipeline_receipt.json.")
            return data
        except Exception as e:
            logger.error(f"Failed to load pipeline_receipt.json: {e}")
            return []

    def _build_context(self) -> str:
        """Builds context string from receipt data"""
        if not self.receipt_data:
            return "No receipts found."

        summaries = []
        for idx, receipt in enumerate(self.receipt_data, start=1):
            store = receipt.get('store_name', 'Unknown Store')
            category = receipt.get('receipt_category', 'Unknown Category')
            total = receipt.get('total_amount', '0')
            currency = receipt.get('currency', '')
            date = receipt.get('date', 'Unknown Date')
            
            context_line = f"{idx}. {store} ({category}) - {currency}{total} on {date}"
            if receipt.get('Summary'):
                context_line += f" - {receipt['Summary']}"
            summaries.append(context_line)

        return "\n".join(summaries)

    async def analyze_query_intent(self, query: str, language: str = "en") -> Dict[str, Any]:
        prompt = f"""
        You are an expert at analyzing user queries for a receipt management system.
        Your goal is to classify the user's intent and extract key information.

        You must classify the user's query into one of these intents:
        - 'list_generation': For any query that asks for a list of items. This includes shopping lists, ingredients, packing lists, to-do lists, etc.
        - 'financial_analysis': For queries asking for spending trends, summaries, or financial analysis.
        - 'general_conversation': For all other questions, greetings, or conversational chat.

        If the intent is 'list_generation', you MUST also identify the 'list_type'.
        The 'list_type' should be a short, descriptive snake_case string (e.g., 'grocery_shopping', 'laundry_supplies', 'vacation_packing').

        Analyze the following user query and return ONLY a single, valid JSON object with the keys "intent" and, if applicable, "list_type".

        User Query: "{query}"
        
        Example Responses:
        - Query: "Can I make pizza?" -> {{"intent": "list_generation", "list_type": "pizza_ingredients"}}
        - Query: "I need to do my laundry." -> {{"intent": "list_generation", "list_type": "laundry_supplies"}}
        - Query: "What did I spend the most on last month?" -> {{"intent": "financial_analysis"}}
        - Query: "Hello, how are you?" -> {{"intent": "general_conversation"}}
        """
        model = GenerativeModel("gemini-2.5-flash")
        response = await model.generate_content_async(prompt)

        try:
            cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
            return json.loads(cleaned_response)
        except (json.JSONDecodeError, AttributeError) as e:
            logger.error(f"Could not parse intent from model. Defaulting to general_conversation. Error: {e}")
            return {"intent": "general_conversation"}

    async def generate_list_items(self, query: str, context: str, list_type: str, language: str = "en") -> Dict[str, Any]:
        """Generates a list of items based on the user's query, context, and a specified list type."""
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
        
        model = GenerativeModel("gemini-2.5-flash")
        response = await model.generate_content_async(prompt)
        
        try:
            cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
            result = json.loads(cleaned_response)
            list_items_str = result.get("list_items", "")
        except (json.JSONDecodeError, AttributeError):
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
        """Generates specific financial insights based on the user's query."""
        prompt = f"""
        You are a financial analyst chatbot. Your task is to answer the user's specific financial question based on the provided receipt data.
        Be concise and direct.

        **Receipt Data:**
        {context}

        **User's Query (in {language}):** "{query}"

        **Instructions:**
        1.  Analyze the user's query to understand exactly what they are asking for (e.g., total spending, spending by category, spending in a specific time frame like "last week").
        2.  Filter the receipt data to match the user's query. Pay close attention to dates.
        3.  Perform the necessary calculations (e.g., sum, average).
        4.  Generate a concise, direct answer. For example: "Last week, you spent a total of $123.45 on Groceries and Transportation."
        5.  If the data is insufficient to answer the question, state that clearly and explain what's missing (e.g., "I don't have any receipts from last week to calculate your spending.").

        **Your Response:**
        Generate a JSON object with a single key, "summary", containing the direct and concise answer.
        """

        model = GenerativeModel("gemini-2.5-flash")
        response = await model.generate_content_async(prompt)
        
        try:
            cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
            result = json.loads(cleaned_response)
            return result
        except (json.JSONDecodeError, AttributeError) as e:
            logger.error(f"Financial insights generation error: {e}")
            return {
                "summary": "I had trouble analyzing your spending. Please try asking in a different way."
            }

    async def generate_response(self, query: str, context: str, language: str = "en") -> str:
        """Generate natural language response"""
        prompt = f"""You are a helpful personal finance assistant. Respond to the user's query about their receipts and expenses.

User Query: "{query}"
Language: {language}

Receipt Data:
{context}

Instructions:
- Be conversational and helpful
- Provide specific information from the data
- Use the user's preferred language ({language})
- Be concise but informative
- Include relevant details like amounts, dates, and categories

Respond naturally as if you're a helpful assistant."""

        try:
            response = await self.gemini.generate_content_async(prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Response generation error: {e}")
            return "I encountered an error while processing your request. Please try again."

    async def process_enhanced_chat_query(self, query: str, language: str = "en") -> Dict[str, Any]:
        """Main method to process enhanced chat queries with wallet pass generation"""
        try:
            # Analyze intent
            logger.info("Analysing query intent...")
            intent_result = await self.analyze_query_intent(query, language)
            intent = intent_result.get("intent")
            list_type = intent_result.get("list_type")
            logger.info(f"Intent identified: {intent}, List Type: {list_type}")

            # Build context from receipt data
            context = self._build_context()

            # Default response values
            response_text = ""
            wallet_pass_link = None
            pass_type = None
            final_list_items = None
            final_list_type = None

            if intent == "list_generation" and list_type:
                logger.info(f"Generating a '{list_type}' list...")
                list_result = await self.generate_list_items(query, context, list_type, language)
                response_text = list_result.get("response_text")
                final_list_items = list_result.get("list_items")
                final_list_type = list_type
                pass_type = "list"
            
            elif intent == "financial_analysis":
                logger.info("Generating financial insights...")
                insights = await self.generate_financial_insights(query, context, language)
                response_text = insights.get("summary", "I could not generate a financial summary for your query.")
                pass_type = None # No pass is generated for direct financial questions

            else:
                response_text = await self.generate_response(query, context, language)
                
            return {
                "response": response_text,
                "categories_analyzed": [],
                "receipts_count": len(self.receipt_data),
                "wallet_pass_link": wallet_pass_link,
                "pass_type": pass_type,
                "timestamp": datetime.now().isoformat(),
                "list_type": final_list_type,
                "list_items": final_list_items,
            }

        except Exception as e:
            logger.error(f"Enhanced chat processing error: {e}")
            return {
                "response": "I encountered an error while processing your request. Please try again.",
                "categories_analyzed": [],
                "receipts_count": 0,
                "wallet_pass_link": None,
                "pass_type": None,
                "timestamp": datetime.now().isoformat(),
                "list_type": None,
                "list_items": None
            }

# Initialize the enhanced service
enhanced_service = EnhancedReceiptAnalysisService()

@app.post("/chat", response_model=ChatResponse)
async def enhanced_chat_endpoint(request: ChatRequest):
    """
    Enhanced chat endpoint that provides intelligent analysis and pass generation.
    """
    try:
        service = EnhancedReceiptAnalysisService()
        result = await service.process_enhanced_chat_query(request.query, request.language or "en")
        
        # Create the response model from the result dictionary
        response = ChatResponse(**result)
        return response

    except Exception as e:
        logger.error(f"❌ Failed to process chat request: {e}", exc_info=True)

@app.post("/reload")
async def reload_receipts():
    """Reload receipt data from file"""
    count = enhanced_service._load_receipt_data()
    enhanced_service.receipt_data = count
    return {"message": f"Reloaded {len(count)} receipts", "timestamp": datetime.now().isoformat()}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/categories")
async def get_categories():
    """Get available expense categories"""
    return {"categories": EXPENSE_CATEGORIES}

@app.get("/receipts/count")
async def get_receipts_count():
    """Get current number of receipts"""
    return {"count": len(enhanced_service.receipt_data), "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

