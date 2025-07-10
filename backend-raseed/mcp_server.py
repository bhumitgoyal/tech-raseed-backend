#!/usr/bin/env python3
"""
MCP Server - Simplified Workflow
This server now orchestrates a direct workflow:
1. Forwards a user's query to the Chatbot service.
2. Receives the chatbot's analysis, including any missing ingredients.
3. If ingredients are missing, it calls the Pipeline service to generate a shopping pass.
"""

import json
import logging
import asyncio
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

import requests
import uvicorn
from fastapi import FastAPI, HTTPException, Body, File, UploadFile, BackgroundTasks
from pydantic import BaseModel
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import aiofiles

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Simplified MCP Orchestrator",
    description="Orchestrates Chatbot analysis and direct pass generation.",
    version="4.0.0"
)

from fastapi.middleware.cors import CORSMiddleware

# Initialize FastAPI app
app = FastAPI(title="Enhanced Receipt Chatbot with Google Wallet", version="2.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or restrict to ["http://localhost:5173"] if desired
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Service URLs - Pipeline is no longer needed
CHATBOT_BASE_URL = "http://localhost:8000"

# Pydantic Models
class QueryRequest(BaseModel):
    query: str
    user_id: Optional[str] = None
    language: Optional[str] = "en"

class FinalResponse(BaseModel):
    chatbot_response: Dict[str, Any]
    pass_generation_result: Optional[Dict[str, Any]] = None

class MCPOrchestrator:
    """The main orchestration logic for the simplified MCP server."""

    def run_script(self, script_name: str, args: Optional[list] = None, timeout: int = 300) -> tuple[bool, str]:
        """
        Run a Python script with given arguments.
        """
        try:
            cmd = [sys.executable, script_name]
            if args:
                cmd.extend(args)
            logger.info(f"Running command: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=Path(__file__).parent
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

    async def process_query(self, query: str, user_id: Optional[str] = None, language: str = "en") -> Dict[str, Any]:
        """
        Processes a query by calling the chatbot and then potentially generating a pass locally.
        """
        # 1. Call the Chatbot
        logger.info(f"🗣️ Forwarding query to chatbot: '{query}'")
        try:
            chatbot_payload = {"query": query, "user_id": user_id, "language": language}
            response = requests.post(f"{CHATBOT_BASE_URL}/chat", json=chatbot_payload)
            response.raise_for_status()
            chatbot_data = response.json()
            logger.info(f"🤖 Chatbot replied: {chatbot_data.get('response')}")

        except requests.RequestException as e:
            logger.error(f"❌ Failed to connect to chatbot service: {e}")
            raise HTTPException(status_code=502, detail=f"Could not connect to the Chatbot service. Error: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse chatbot response: {e}")
            raise HTTPException(status_code=500, detail=f"Invalid response from Chatbot service. Error: {e}")

        # 2. Check for a generic list and generate a pass if needed
        final_response = {"chatbot_response": chatbot_data}
        list_items = chatbot_data.get("list_items")
        list_type = chatbot_data.get("list_type")

        if list_items and list_type:
            logger.info(f"📋 Found a '{list_type}' list with {len(list_items)} items. Generating pass locally...")
            try:
                pass_title = list_type.replace('_', ' ').title()
                
                temp_data = {
                    "pass_type": "list",
                    "list_type": list_type,
                    "title": pass_title,
                    "items": list_items,
                    "date": datetime.now().strftime("%Y-%m-%d")
                }
                
                temp_json_path = Path(f"temp_{list_type}_pass.json")
                with open(temp_json_path, 'w') as f:
                    json.dump(temp_data, f)

                success, output = self.run_script("pass_generation.py", ["--input", str(temp_json_path)])

                if not success:
                    raise Exception(f"Pass generation script failed: {output}")

                wallet_link = output.strip().split("\\n")[-1]
                if not wallet_link.startswith("https://pay.google.com"):
                    raise Exception("Script did not return a valid Google Wallet link.")
                
                pass_data = {"success": True, "wallet_link": wallet_link}
                logger.info(f"✅ Successfully generated {list_type} pass: {pass_data.get('wallet_link')}")
                final_response["pass_generation_result"] = pass_data

            except Exception as e:
                logger.error(f"❌ Failed to generate {list_type} pass locally: {e}")
                final_response["pass_generation_result"] = {"status": "error", "detail": str(e)}
        
        return final_response

# Initialize the orchestrator
orchestrator = MCPOrchestrator()

# --- API Endpoints ---

@app.get("/", summary="Root endpoint with server information")
async def root():
    return {
        "message": "Welcome to the Simplified MCP Orchestrator",
        "version": "3.0.0",
        "description": "This server forwards queries to the chatbot and may trigger pass generation."
    }

@app.post("/process", response_model=FinalResponse, summary="Process a natural language query")
async def process_query_endpoint(request: QueryRequest):
    """
    This is the main endpoint. It sends the query to the chatbot, and if the
    chatbot identifies missing ingredients, it triggers the pipeline to create a
    shopping pass.
    """
    try:
        result = await orchestrator.process_query(
            request.query, 
            request.user_id, 
            request.language or "en"
        )
        return FinalResponse(**result)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"An unexpected error occurred in /process: {e}")
        raise HTTPException(status_code=500, detail="An internal server error occurred.")

# --- Main Execution ---
if __name__ == "__main__":
    logger.info("🚀 Starting Simplified MCP Orchestrator on 0.0.0.0:8002")
    uvicorn.run(app, host="0.0.0.0", port=8002) 