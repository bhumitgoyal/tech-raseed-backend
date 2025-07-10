#!/usr/bin/env python3
"""
Receipt Processing Pipeline API with Bill Splitter Integration
FastAPI application that orchestrates the complete receipt processing workflow:
1. Image upload and conversion to PDF
2. Data extraction from PDF using AI
3. Google Wallet pass generation
4. Bill splitting with UPI payment links
"""

import os
import sys
from fastapi import FastAPI

import json
import logging
import asyncio
import subprocess
import urllib.parse
import webbrowser
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from pydantic import BaseModel
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import aiofiles
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Receipt Processing Pipeline with Bill Splitter",
    description="Complete receipt processing workflow: Upload → Extract → Generate Pass → Split Bills",
    version="1.1.0"
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

# Global variables to track processing state
processing_state = {
    "current_image": None,
    "current_pdf": None,
    "current_receipt_data": None,
    "last_wallet_link": None,
    "processing_history": [],
    "bill_splits": []
}

# Auto-load receipt data from temp_receipt.json if it exists (for recovery after restart)
temp_receipt_path = Path("temp_receipt.json")
if temp_receipt_path.exists():
    try:
        with open(temp_receipt_path, 'r', encoding='utf-8') as f:
            receipt_data = json.load(f)
        processing_state["current_receipt_data"] = receipt_data
        logger.info("✅ Loaded receipt data from temp_receipt.json on startup.")
    except Exception as e:
        logger.error(f"❌ Failed to load temp_receipt.json on startup: {e}")

# Supported image formats
SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}

class ProcessingError(Exception):
    """Custom exception for processing errors."""
    pass

class BillSplitRequest(BaseModel):
    receipt_id: Optional[str] = None  # Use current receipt if not provided
    contacts: List[Dict[str, str]]  # List of contacts with name, phone, email
    upi_payee_vpa: str  # UPI ID for collecting payments
    upi_payee_name: str  # Name for UPI payments

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
    method: str  # "whatsapp" or "sms"

class ShoppingPassRequest(BaseModel):
    items: List[str]
    recipe_name: str = "Shopping List"

class BillSplitter:
    """Bill splitting service integrated with the pipeline"""
    
    def __init__(self, receipt_file="pipeline_receipt.json"):
        self.receipt_file = receipt_file
        
        # Default UPI details (can be overridden)
        self.upi_details = {
            "payee_vpa": "9205704825@ptsbi",
            "payee_name": "Maisha",
        }
    
    def _load_receipts(self) -> List[Dict[str, Any]]:
        """Load receipts from the pipeline JSON file"""
        if not Path(self.receipt_file).exists():
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
        
        # Generate UPI deep link
        upi_link = (f"upi://pay?"
                   f"pa={urllib.parse.quote(self.upi_details['payee_vpa'])}&"
                   f"pn={urllib.parse.quote(self.upi_details['payee_name'])}&"
                   f"am={formatted_amount}&"
                   f"tr={urllib.parse.quote(transaction_ref)}&"
                   f"tn={urllib.parse.quote(transaction_note)}&"
                   f"cu=INR")
        
        return upi_link
    
    def update_upi_details(self, payee_vpa: str, payee_name: str):
        """Update UPI details for payment collection"""
        self.upi_details["payee_vpa"] = payee_vpa
        self.upi_details["payee_name"] = payee_name

def run_script(script_name: str, args: Optional[list] = None, timeout: int = 300) -> tuple[bool, str]:
    """
    Run a Python script with given arguments.
    
    Args:
        script_name: Name of the Python script to run
        args: List of arguments to pass to the script
        timeout: Timeout in seconds
        
    Returns:
        Tuple of (success, output/error_message)
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
            logger.error(f"❌ {script_name} failed with return code {result.returncode}")
            logger.error(f"Error output: {result.stderr}")
            return False, result.stderr
            
    except subprocess.TimeoutExpired:
        error_msg = f"Script {script_name} timed out after {timeout} seconds"
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Failed to run {script_name}: {str(e)}"
        logger.error(error_msg)
        return False, error_msg

def find_latest_file(pattern: str, directory: str = ".") -> Optional[str]:
    """Find the latest file matching a pattern."""
    try:
        files = list(Path(directory).glob(pattern))
        if not files:
            return None
        
        # Sort by modification time, newest first
        latest_file = max(files, key=lambda f: f.stat().st_mtime)
        return str(latest_file)
    except Exception as e:
        logger.error(f"Error finding latest file with pattern {pattern}: {e}")
        return None

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Receipt Processing Pipeline API with Bill Splitter",
        "version": "1.1.0",
        "endpoints": {
            "/upload": "Upload and convert image to PDF",
            "/extract": "Extract data from PDF using AI",
            "/passgen": "Generate Google Wallet pass",
            "/split-bill": "Split bill among contacts",
            "/generate-upi": "Generate UPI payment links",
            "/share-upi": "Share UPI payment via WhatsApp/SMS",
            "/split-history": "Get bill splitting history",
            "/status": "Get current processing status",
            "/history": "Get processing history",
            "/health": "Health check"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/status")
async def get_status():
    """Get current processing status."""
    return {
        "current_image": processing_state["current_image"],
        "current_pdf": processing_state["current_pdf"],
        "has_receipt_data": processing_state["current_receipt_data"] is not None,
        "last_wallet_link": processing_state["last_wallet_link"],
        "bill_splits_count": len(processing_state["bill_splits"]),
        "timestamp": datetime.now().isoformat()
    }

# File paths for persistent history
PROCESSING_HISTORY_FILE = Path("processing_history.json")
SPLIT_HISTORY_FILE = Path("split_history.json")

# Helper functions for persistence

def load_json_list(filepath):
    if not Path(filepath).exists():
        return []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        return [data]
    except Exception as e:
        logger.error(f"Error loading {filepath}: {e}")
        return []

def save_json_list(filepath, data):
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving {filepath}: {e}")

# On startup, load persistent histories
processing_state["processing_history"] = load_json_list(PROCESSING_HISTORY_FILE)
processing_state["bill_splits"] = load_json_list(SPLIT_HISTORY_FILE)

@app.get("/history")
async def get_history():
    """Get processing history from disk."""
    history = load_json_list(PROCESSING_HISTORY_FILE)
    return {
        "history": history,
        "count": len(history)
    }

@app.get("/split-history")
async def get_split_history():
    """Get bill splitting history from disk."""
    splits = load_json_list(SPLIT_HISTORY_FILE)
    return {
        "splits": splits,
        "count": len(splits)
    }

@app.get("/dashboard")
async def get_dashboard():
    """Get dashboard summary data for the frontend."""
    return {
        "receiptsCount": 5,
        "categories": ["Groceries", "Food", "Utilities"],
        "monthlySpend": 12345,
        "recentActivity": [
            {
                "id": 1,
                "store_name": "Supermart",
                "date": "2024-07-10",
                "total_amount": 1200,
                "category": "Groceries",
                "pdf_path": "receipt_1.pdf"
            },
            {
                "id": 2,
                "store_name": "Pizza Place",
                "date": "2024-07-09",
                "total_amount": 800,
                "category": "Food",
                "pdf_path": "receipt_2.pdf"
            }
        ]
    }

@app.post("/generate-shopping-pass")
async def generate_shopping_pass(request: ShoppingPassRequest):
    """
    Generates a Google Wallet pass directly from a list of shopping items.
    """
    if not request.items:
        raise HTTPException(status_code=400, detail="No items provided for the shopping list.")

    logger.info(f"Generating shopping pass for {len(request.items)} items for recipe: {request.recipe_name}")
    try:
        # Create temp data for pass generation
        temp_data = {
            "store_name": request.recipe_name,
            "shopping_items": request.items,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "pass_type": "shopping"
        }
        
        temp_json_path = Path("temp_shopping_list.json")
        with open(temp_json_path, 'w') as f:
            json.dump(temp_data, f)

        passgen_script = Path("pass_generation.py")
        if not passgen_script.exists():
            raise ProcessingError("pass_generation.py not found.")

        args = ["--input", str(temp_json_path)]
        success, output = run_script(str(passgen_script), args)

        if not success:
            raise ProcessingError(f"Pass generation script failed: {output}")

        # The script should output the URL of the pass
        wallet_link = output.strip().split("\n")[-1]
        
        if not wallet_link.startswith("https://pay.google.com"):
             raise ProcessingError("Script did not return a valid Google Wallet link.")

        return {"success": True, "wallet_link": wallet_link, "item_count": len(request.items)}

    except ProcessingError as e:
        logger.error(f"Failed to generate shopping pass: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"An unexpected error occurred in /generate-shopping-pass: {e}")
        raise HTTPException(status_code=500, detail="An internal server error occurred.")

@app.post("/upload")
async def upload_image(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    debug: bool = False
):
    """
    Upload an image file and convert it to PDF using imageconvert.py.
    """
    try:
        # Validate file format
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
            
        file_extension = Path(file.filename).suffix.lower()
        if file_extension not in SUPPORTED_FORMATS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format. Supported formats: {', '.join(SUPPORTED_FORMATS)}"
            )
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        input_filename = f"uploaded_image_{timestamp}{file_extension}"
        input_path = Path(input_filename)
        
        # Save uploaded file
        logger.info(f"Saving uploaded file: {input_filename}")
        async with aiofiles.open(input_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        # Check if imageconvert.py exists
        imageconvert_script = Path("imageconvert.py")
        if not imageconvert_script.exists():
            raise HTTPException(
                status_code=500,
                detail="imageconvert.py not found in the same directory"
            )
        
        # Run imageconvert.py
        args = ["--input", str(input_path)]
        if debug:
            args.append("--debug")
            
        success, output = run_script("imageconvert.py", args)
        
        if not success:
            raise ProcessingError(f"Image conversion failed: {output}")
        
        # Find generated PDF file
        pdf_pattern = f"receipt_*{timestamp}.pdf"
        pdf_file = find_latest_file(pdf_pattern)
        
        if not pdf_file:
            # Fallback: look for any recent PDF
            pdf_file = find_latest_file("receipt_*.pdf")
            
        if not pdf_file:
            raise ProcessingError("No PDF file was generated")
        
        # Update processing state
        processing_state["current_image"] = str(input_path)
        processing_state["current_pdf"] = pdf_file
        processing_state["processing_history"].append({
            "step": "upload",
            "timestamp": datetime.now().isoformat(),
            "input_file": str(input_path),
            "output_file": pdf_file,
            "success": True
        })
        save_json_list(PROCESSING_HISTORY_FILE, processing_state["processing_history"])
        
        # Clean up input file in background
        background_tasks.add_task(cleanup_file, input_path)
        
        logger.info(f"✅ Image upload and conversion completed successfully")
        
        return {
            "success": True,
            "message": "Image uploaded and converted to PDF successfully",
            "input_file": str(input_path),
            "output_pdf": pdf_file,
            "file_size": len(content),
            "timestamp": datetime.now().isoformat()
        }
        
    except ProcessingError as e:
        logger.error(f"Processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in upload: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/extract")
async def extract_data(pdf_file: Optional[str] = None):
    """
    Extract data from PDF using dataextract.py.
    """
    try:
        # Determine PDF file to process
        target_pdf = pdf_file or processing_state["current_pdf"]
        
        if not target_pdf:
            raise HTTPException(
                status_code=400,
                detail="No PDF file available. Please upload an image first."
            )
        
        pdf_path = Path(target_pdf)
        if not pdf_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"PDF file not found: {target_pdf}"
            )
        
        # Check if dataextract.py exists
        dataextract_script = Path("dataextract.py")
        if not dataextract_script.exists():
            raise HTTPException(
                status_code=500,
                detail="dataextract.py not found in the same directory"
            )
        
        # Run dataextract.py
        logger.info(f"Extracting data from PDF: {target_pdf}")
        success, output = run_script("dataextract.py", [str(pdf_path)])
        
        if not success:
            raise ProcessingError(f"Data extraction failed: {output}")
        
        # Load extracted data from temp_receipt.json
        temp_receipt_file = Path("temp_receipt.json")
        if not temp_receipt_file.exists():
            raise ProcessingError("No receipt data was generated")
        
        with open(temp_receipt_file, 'r', encoding='utf-8') as f:
            receipt_data = json.load(f)
        
        # Add unique ID and timestamp to receipt data
        receipt_data["receipt_id"] = f"receipt_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        receipt_data["processed_at"] = datetime.now().isoformat()
        
        # Update processing state
        processing_state["current_receipt_data"] = receipt_data
        processing_state["processing_history"].append({
            "step": "extract",
            "timestamp": datetime.now().isoformat(),
            "input_file": target_pdf,
            "success": True,
            "extracted_items": len(receipt_data.get('items', []))
        })
        save_json_list(PROCESSING_HISTORY_FILE, processing_state["processing_history"])
        
        logger.info(f"✅ Data extraction completed successfully")
        
        return {
            "success": True,
            "message": "Data extracted successfully",
            "pdf_file": target_pdf,
            "receipt_data": receipt_data,
            "timestamp": datetime.now().isoformat()
        }
        
    except ProcessingError as e:
        logger.error(f"Processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in extract: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/passgen")
async def generate_pass():
    """
    Generate Google Wallet pass using pass_generation.py.
    """
    try:
        # Check if receipt data is available
        if not processing_state["current_receipt_data"]:
            raise HTTPException(
                status_code=400,
                detail="No receipt data available. Please extract data first."
            )
        
        # Check if temp_receipt.json exists
        temp_receipt_file = Path("temp_receipt.json")
        if not temp_receipt_file.exists():
            raise HTTPException(
                status_code=400,
                detail="temp_receipt.json not found. Please extract data first."
            )
        
        # Check if pass_generation.py exists
        passgen_script = Path("pass_generation.py")
        if not passgen_script.exists():
            raise HTTPException(
                status_code=500,
                detail="pass_generation.py not found in the same directory"
            )
        
        # Run pass_generation.py
        logger.info("Generating Google Wallet pass...")
        success, output = run_script("pass_generation.py", timeout=60)
        
        if not success:
            raise ProcessingError(f"Pass generation failed: {output}")
        
        # Extract wallet link from output
        wallet_link = output.strip()
        if not wallet_link or not wallet_link.startswith("https://"):
            raise ProcessingError("Invalid wallet link generated")
        
        # Update processing state
        processing_state["last_wallet_link"] = wallet_link
        processing_state["processing_history"].append({
            "step": "passgen",
            "timestamp": datetime.now().isoformat(),
            "wallet_link": wallet_link,
            "success": True
        })
        save_json_list(PROCESSING_HISTORY_FILE, processing_state["processing_history"])
        
        logger.info(f"✅ Google Wallet pass generated successfully")
        
        return {
            "success": True,
            "message": "Google Wallet pass generated successfully",
            "wallet_link": wallet_link,
            "timestamp": datetime.now().isoformat()
        }
        
    except ProcessingError as e:
        logger.error(f"Processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in passgen: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/split-bill")
async def split_bill(request: BillSplitRequest):
    """
    Split bill among selected contacts and generate UPI payment links.
    """
    try:
        # Use current receipt data if no specific receipt_id provided
        receipt_data = processing_state["current_receipt_data"]
        
        if not receipt_data:
            raise HTTPException(
                status_code=400,
                detail="No receipt data available. Please process a receipt first."
            )
        
        if not request.contacts:
            raise HTTPException(
                status_code=400,
                detail="No contacts provided for bill splitting."
            )
        
        # Initialize bill splitter
        splitter = BillSplitter()
        
        # Update UPI details
        splitter.update_upi_details(request.upi_payee_vpa, request.upi_payee_name)
        
        # Calculate split
        split_result = splitter.calculate_split(receipt_data, request.contacts)
        
        if not split_result:
            raise ProcessingError("Unable to calculate bill split")
        
        # Generate UPI links for each contact
        upi_links = []
        for split in split_result["split_details"]["splits"]:
            upi_link = splitter.generate_upi_link(
                split["amount"], 
                split, 
                split_result["receipt_info"]
            )
            
            if upi_link:
                upi_links.append({
                    "contact": split,
                    "upi_link": upi_link,
                    "amount": split["amount"],
                    "currency": split["currency"]
                })
        
        # Add UPI links to split result
        split_result["upi_links"] = upi_links
        split_result["split_id"] = f"split_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Store in processing state
        processing_state["bill_splits"].append(split_result)
        save_json_list(SPLIT_HISTORY_FILE, processing_state["bill_splits"])
        processing_state["processing_history"].append({
            "step": "split_bill",
            "timestamp": datetime.now().isoformat(),
            "split_id": split_result["split_id"],
            "contacts_count": len(request.contacts),
            "success": True
        })
        save_json_list(PROCESSING_HISTORY_FILE, processing_state["processing_history"])
        
        logger.info(f"✅ Bill split calculated successfully for {len(request.contacts)} contacts")
        
        return {
            "success": True,
            "message": "Bill split calculated successfully",
            "split_data": split_result,
            "upi_links": upi_links,
            "timestamp": datetime.now().isoformat()
        }
        
    except ProcessingError as e:
        logger.error(f"Processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in split_bill: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/generate-upi")
async def generate_upi_links(
    receipt_id: Optional[str] = None,
    upi_payee_vpa: str = "9205704825@ptsbi",
    upi_payee_name: str = "Maisha"
):
    """
    Generate UPI payment links for the latest bill split.
    """
    try:
        if not processing_state["bill_splits"]:
            raise HTTPException(
                status_code=400,
                detail="No bill splits available. Please split a bill first."
            )
        
        # Use the latest split if no specific receipt_id provided
        latest_split = processing_state["bill_splits"][-1]
        
        # Initialize bill splitter
        splitter = BillSplitter()
        splitter.update_upi_details(upi_payee_vpa, upi_payee_name)
        
        # Generate UPI links
        upi_links = []
        for split in latest_split["split_details"]["splits"]:
            upi_link = splitter.generate_upi_link(
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
        
        logger.info(f"✅ Generated {len(upi_links)} UPI payment links")
        
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
        upload_result = await upload_image(background_tasks, file, debug)
        
        if not upload_result["success"]:
            raise ProcessingError("Upload step failed")
        
        # Step 2: Extract data
        extract_result = await extract_data()
        
        if not extract_result["success"]:
            raise ProcessingError("Extract step failed")
        
        # Step 3: Generate pass
        pass_result = await generate_pass()
        
        if not pass_result["success"]:
            raise ProcessingError("Pass generation step failed")
        
        logger.info("✅ Complete pipeline processing finished successfully")
        
        return {
            "success": True,
            "message": "Complete processing pipeline executed successfully",
            "steps": {
                "upload": upload_result,
                "extract": extract_result,
                "passgen": pass_result
            },
            "wallet_link": pass_result["wallet_link"],
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Complete processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def cleanup_file(file_path: Path):
    """Clean up temporary files."""
    try:
        if file_path.exists():
            file_path.unlink()
            logger.info(f"🗑️ Cleaned up temporary file: {file_path}")
    except Exception as e:
        logger.warning(f"Failed to clean up file {file_path}: {e}")

@app.get("/download/{filename}")
async def download_file(filename: str):
    """Download generated files."""
    try:
        file_path = Path(filename)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type='application/octet-stream'
        )
    except Exception as e:
        logger.error(f"Download error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/receipts/all")
async def get_all_receipts():
    """Return all receipts from pipeline_receipt.json as a JSON array."""
    try:
        receipt_file = Path("pipeline_receipt.json")
        if not receipt_file.exists():
            return {"receipts": []}
        with open(receipt_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, list):
            data = [data]
        return {"receipts": data}
    except Exception as e:
        logger.error(f"Error loading receipts for /receipts/all: {e}")
        return {"receipts": []}

# Expense categories (should match chatbots)
EXPENSE_CATEGORIES = [
    "Groceries", "Food", "Transportation", "Travel", "Utilities",
    "Subscriptions", "Healthcare", "Shopping", "Entertainment",
    "Education", "Maintenance", "Financial", "Others"
]

@app.get("/categories")
async def get_categories():
    """Get available expense categories (robust)."""
    try:
        # In future, could load from config or file
        if not EXPENSE_CATEGORIES or not isinstance(EXPENSE_CATEGORIES, list):
            raise ValueError("Categories list missing or invalid")
        return {"categories": EXPENSE_CATEGORIES}
    except Exception as e:
        logger.error(f"Error in /categories: {e}")
        # Fallback default
        return {"categories": ["Groceries", "Food", "Transportation", "Others"]}

@app.post("/reload")
async def reload_receipt_data():
    """
    Reload receipt data from temp_receipt.json into processing_state for manual recovery.
    """
    temp_receipt_path = Path("temp_receipt.json")
    if not temp_receipt_path.exists():
        return {"success": False, "message": "temp_receipt.json not found."}
    try:
        with open(temp_receipt_path, 'r', encoding='utf-8') as f:
            receipt_data = json.load(f)
        processing_state["current_receipt_data"] = receipt_data
        logger.info("✅ Reloaded receipt data from temp_receipt.json via /reload endpoint.")
        return {"success": True, "message": "Receipt data reloaded from temp_receipt.json."}
    except Exception as e:
        logger.error(f"❌ Failed to reload temp_receipt.json via /reload: {e}")
        return {"success": False, "message": f"Failed to reload: {e}"}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Receipt Processing Pipeline API")
    parser.add_argument('--host', type=str, default="0.0.0.0", help='Host to bind')
    parser.add_argument('--port', type=int, default=8001, help='Port to bind (default: 8001)')
    parser.add_argument('--reload', action='store_true', help='Enable auto-reload')
    args = parser.parse_args()
    logger.info(f"🚀 Starting Receipt Processing Pipeline API on {args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, reload=args.reload)