#!/usr/bin/env python3
"""
Demo MCP Tool Implementations
Contains the definitions and concrete implementations for all tools
available to the Generic MCP Server.
"""

import json
import logging
from typing import Dict, Any, List, Optional
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Base URLs for services
CHATBOT_BASE_URL = "http://localhost:8000"
PIPELINE_BASE_URL = "http://localhost:8001"

# MCP Tool Definitions
MCP_TOOLS = {
    "check_ingredient_availability": {
        "name": "check_ingredient_availability",
        "description": "Check if ingredients are available based on user's receipt history and spending patterns",
        "category": "shopping",
        "inputSchema": {
            "type": "object",
            "properties": {
                "recipe_name": {"type": "string", "description": "Name of the recipe/dish to make"},
                "ingredients": {"type": "array", "items": {"type": "string"}, "description": "List of ingredients needed for the recipe"},
                "user_id": {"type": "string", "description": "Optional user ID for personalized checking"}
            },
            "required": ["recipe_name", "ingredients"]
        }
    },
    "generate_shopping_pass": {
        "name": "generate_shopping_pass",
        "description": "Generate a Google Wallet pass for missing ingredients",
        "category": "shopping",
        "inputSchema": {
            "type": "object",
            "properties": {
                "missing_ingredients": {"type": "array", "items": {"type": "string"}, "description": "List of missing ingredients to purchase"},
                "recipe_name": {"type": "string", "description": "Name of the recipe these ingredients are for"},
                "user_id": {"type": "string", "description": "Optional user ID for personalized pass generation"}
            },
            "required": ["missing_ingredients", "recipe_name"]
        }
    },
    "analyze_spending_trends": {
        "name": "analyze_spending_trends",
        "description": "Analyze user's spending trends over time based on receipt data",
        "category": "finance",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Expense category to analyze (e.g., 'Groceries')"},
                "time_period": {"type": "string", "description": "Time period for analysis (e.g., 'last month')"},
                "user_id": {"type": "string", "description": "Optional user ID for personalized analysis"}
            },
            "required": []
        }
    },
    "extract_receipt_data": {
        "name": "extract_receipt_data",
        "description": "Extract structured data from a receipt image. This involves uploading an image.",
        "category": "document",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Local path to the receipt image file to upload"},
                "extract_level": {"type": "string", "description": "Level of detail for extraction ('basic', 'detailed')"}
            },
            "required": ["file_path"]
        }
    },
    "generate_travel_pass": {
        "name": "generate_travel_pass",
        "description": "Generate a Google Wallet pass for travel",
        "category": "travel",
        "inputSchema": {
            "type": "object",
            "properties": {
                "destination": {"type": "string", "description": "Travel destination"},
                "travel_date": {"type": "string", "description": "Date of travel"},
                "traveler_name": {"type": "string", "description": "Name of traveler"},
                "return_date": {"type": "string", "description": "Return date (optional)"}
            },
            "required": ["destination", "travel_date", "traveler_name"]
        }
    }
}


class DemoMCPToolKit:
    """A collection of implemented MCP tools for demonstration."""

    async def check_ingredient_availability(self, recipe_name: str, ingredients: Optional[List[str]] = None, user_id: Optional[str] = None) -> Dict[str, Any]:
        logger.info(f"Checking availability for recipe '{recipe_name}'")
        try:
            # Step 1: If no ingredients are provided, ask the chatbot for a typical list.
            if not ingredients:
                logger.info(f"No ingredients provided for '{recipe_name}'. Asking chatbot for a list.")
                recipe_query = f"What are the typical ingredients needed to make a {recipe_name}?"
                response = requests.post(f"{CHATBOT_BASE_URL}/chat", json={"query": recipe_query, "language": "en"})
                response.raise_for_status()
                recipe_response = response.json()["response"]
                # This is a simple parse; a real system might use a more structured LLM output.
                ingredients = [line.strip().replace("•", "").strip() for line in recipe_response.split('\\n') if line.strip()]

            if not ingredients:
                return {"status": "error", "message": f"Could not determine ingredients for {recipe_name}."}

            # Step 2: Check against purchase history.
            chat_query = f"Based on my past receipts, do I have these ingredients for {recipe_name}: {', '.join(ingredients)}?"
            response = requests.post(
                f"{CHATBOT_BASE_URL}/chat",
                json={"query": chat_query, "user_id": user_id, "language": "en"}
            )
            response.raise_for_status()
            chat_response = response.json()

            text_response = chat_response.get("response", "").lower()
            available = [ing for ing in ingredients if ing.lower() in text_response]
            missing = [ing for ing in ingredients if ing.lower() not in text_response]

            # Construct a helpful message, suggesting a follow-up action if needed.
            if missing:
                message = (
                    f"You have {len(available)} of the {len(ingredients)} ingredients for {recipe_name}. "
                    f"You are missing: {', '.join(missing)}. "
                    "You can ask me to 'generate a shopping pass' to get these."
                )
            else:
                message = f"Success! You have all the required ingredients for {recipe_name}."

            return {
                "status": "success",
                "recipe": recipe_name,
                "assumed_ingredients": ingredients,
                "available_ingredients": available,
                "missing_ingredients": missing,
                "message": message
            }
        except Exception as e:
            logger.error(f"Error checking ingredient availability: {e}")
            return {"status": "error", "message": str(e)}

    async def generate_shopping_pass(self, missing_ingredients: List[str], recipe_name: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        logger.info(f"Generating shopping pass for missing ingredients for recipe '{recipe_name}'")
        try:
            # This tool now directly calls the chatbot's pass generation capability
            chat_query = f"Generate a shopping list pass for these missing items for my {recipe_name} recipe: {', '.join(missing_ingredients)}"
            response = requests.post(
                f"{CHATBOT_BASE_URL}/chat",
                json={"query": chat_query, "user_id": user_id, "language": "en"}
            )
            response.raise_for_status()
            chat_response = response.json()
            wallet_link = chat_response.get("wallet_pass_link")

            if not wallet_link:
                return {"status": "error", "message": "Chatbot failed to generate a wallet pass."}

            return {
                "status": "success",
                "wallet_link": wallet_link,
                "message": "Successfully generated a Google Wallet pass for your shopping list."
            }
        except Exception as e:
            logger.error(f"Error generating shopping pass: {e}")
            return {"status": "error", "message": str(e)}

    async def analyze_spending_trends(self, time_period: str = "last month", category: Optional[str] = None, user_id: Optional[str] = None) -> Dict[str, Any]:
        logger.info(f"Analyzing spending trends for category '{category}' over '{time_period}'")
        try:
            # This tool asks the chatbot to perform the analysis
            if category:
                chat_query = f"Analyze my spending trends for {category} from {time_period}."
            else:
                chat_query = f"Analyze my overall spending trends from {time_period}."

            response = requests.post(
                f"{CHATBOT_BASE_URL}/chat",
                json={"query": chat_query, "user_id": user_id, "language": "en"}
            )
            response.raise_for_status()
            chat_response = response.json()

            return {
                "status": "success",
                "analysis": chat_response.get("response"),
                "message": "Spending trend analysis complete."
            }
        except Exception as e:
            logger.error(f"Error analyzing spending trends: {e}")
            return {"status": "error", "message": str(e)}

    async def extract_receipt_data(self, file_path: str, extract_level: str = "detailed") -> Dict[str, Any]:
        logger.info(f"Extracting data from receipt image at '{file_path}'")
        try:
            # Step 1: Upload the image to the pipeline service
            with open(file_path, "rb") as f:
                upload_response = requests.post(
                    f"{PIPELINE_BASE_URL}/upload",
                    files={"file": (file_path, f, "image/jpeg")}
                )
            upload_response.raise_for_status()
            upload_data = upload_response.json()
            
            if not upload_data.get("success"):
                return {"status": "error", "message": f"Upload failed: {upload_data.get('detail')}"}

            # Step 2: Trigger extraction on the pipeline service
            extract_response = requests.post(f"{PIPELINE_BASE_URL}/extract")
            extract_response.raise_for_status()
            extract_data = extract_response.json()

            if not extract_data.get("success"):
                return {"status": "error", "message": f"Extraction failed: {extract_data.get('detail')}"}

            return {
                "status": "success",
                "extracted_data": extract_data.get("receipt_data"),
                "message": "Receipt data extracted successfully via pipeline."
            }
        except Exception as e:
            logger.error(f"Error extracting receipt data: {e}")
            return {"status": "error", "message": str(e)}

    async def generate_travel_pass(self, destination: str, travel_date: str, traveler_name: str, return_date: Optional[str] = None) -> Dict[str, Any]:
        logger.info(f"Generating travel pass for {traveler_name} to {destination}")
        try:
            # This tool is more complex and still relies on the chatbot's NLU for pass generation
            # In a real system, this might call a dedicated travel service API
            return_info = f" with a return date of {return_date}" if return_date else ""
            chat_query = f"Generate a travel pass for {traveler_name} going to {destination} on {travel_date}{return_info}."
            
            response = requests.post(
                f"{CHATBOT_BASE_URL}/chat",
                json={"query": chat_query, "language": "en"}
            )
            response.raise_for_status()
            chat_response = response.json()
            wallet_link = chat_response.get("wallet_pass_link")

            if not wallet_link:
                return {"status": "error", "message": "Chatbot failed to generate a travel wallet pass."}

            return {
                "status": "success",
                "wallet_link": wallet_link,
                "message": f"Successfully generated a travel pass to {destination}."
            }
        except Exception as e:
            logger.error(f"Error generating travel pass: {e}")
            return {"status": "error", "message": str(e)} 