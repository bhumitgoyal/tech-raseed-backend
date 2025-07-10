# 📄 Receipt Processing & Chatbot API

A robust FastAPI backend for receipt processing, bill splitting, UPI payment link generation, and AI-powered chat/analysis. This backend powers workflows from image upload to Google Wallet pass generation, and supports advanced conversational queries.

---

## 🚀 Services Overview

- **pipeline_api.py** (Port 8001): Main receipt processing, bill splitting, UPI, and pass generation API.
- **new_chatbot.py** (Port 8000): AI-powered chatbot for receipt analysis, queries, and smart pass/list generation.
- **mcp_server.py** (Port 8002): Orchestrator that forwards queries to the chatbot and triggers pass generation if needed.

---

## 🏗️ Project Structure

```
backend-raseed/
├── pipeline_api.py         # Main API (image, extract, pass, split, UPI)
├── new_chatbot.py          # Chatbot backend (AI queries, lists, insights)
├── mcp_server.py           # Orchestrator (forwards to chatbot, triggers pass)
├── imageconvert.py         # Image to PDF conversion
├── dataextract.py          # Data extraction from PDF
├── pass_generation.py      # Google Wallet pass generation
├── pipeline_receipt.json   # Stored receipt data
├── temp_receipt.json       # Latest receipt data
├── processing_history.json # Processing step history
├── split_history.json      # Bill split history
└── ... (other files)
```

---

## 📊 Data Storage Structure

### 1. **pipeline_receipt.json** - Main Receipt Database

This file stores **all processed receipts** as a JSON array. Each receipt contains comprehensive data extracted by AI.

**Structure:**
```json
[
  {
    "store_name": "string",
    "store_address": "string",
    "store_phone": "string|null",
    "date": "YYYY-MM-DD",
    "time": "HH:MM",
    "bill_number": "string",
    "receipt_category": "string",
    "Summary": "string",
    "payment_method": "string",
    "currency": "string",
    "subtotal_amount": number,
    "tax_amount": "number|null",
    "tip_amount": "number|null",
    "total_amount": number,
    "items": [
      {
        "item_name": "string",
        "quantity": number,
        "unit_price": number,
        "total_price": number,
        "category": "string"
      }
    ],
    "tax_breakdown": [
      {
        "tax_name": "string",
        "tax_rate": "string",
        "tax_amount": "string"
      }
    ],
    "footer_notes": "string",
    "pdf_path": "string"
  }
]
```

**Example:**
```json
[
  {
    "store_name": "Bhargavi Auto Services",
    "store_address": "GP Delhi",
    "store_phone": null,
    "date": "2025-07-03",
    "time": "12:57",
    "bill_number": "002524",
    "receipt_category": "Transportation",
    "Summary": "This receipt from Bhargavi Auto Services in GP Delhi details the purchase of 22.8 liters of Diesel on July 3, 2025, at 12:57 PM. The unit price was ₹87.71, making the total amount ₹2000.00. Payment was processed via Mastercard.",
    "payment_method": "Mastercard (Card)",
    "currency": "₹",
    "subtotal_amount": 2000.0,
    "tax_amount": null,
    "tip_amount": null,
    "total_amount": 2000.0,
    "items": [
      {
        "item_name": "Diesel",
        "quantity": 22.8,
        "unit_price": 87.71,
        "total_price": 2000.0,
        "category": "Transportation"
      }
    ],
    "tax_breakdown": [],
    "footer_notes": "PIN Verified OK. Signature Not Required...",
    "pdf_path": "https://gofile.io/d/hwtUfe"
  }
]
```

**Key Points:**
- **Array Structure**: Always stored as a JSON array, even with single receipts
- **AI Extraction**: All data is extracted using Google Gemini AI from receipt images
- **Categories**: Predefined categories (Groceries, Food, Transportation, etc.)
- **PDF Links**: Original PDFs are uploaded to GoFile and linked via `pdf_path`
- **Currency**: Detected automatically from receipt (₹, $, €, etc.)

---

### 2. **temp_receipt.json** - Latest Receipt Cache

This file stores **only the most recently processed receipt** as a single JSON object (not an array).

**Structure:** Same as individual receipt in `pipeline_receipt.json`

**Example:**
```json
{
  "store_name": "Bhargavi Auto Services",
  "store_address": "DELHI",
  "store_phone": null,
  "date": "2025-07-03",
  "time": "12:57",
  "bill_number": "002524",
  "receipt_category": "Transportation",
  "Summary": "This receipt is for a fuel purchase from Bhargavi Auto Services in Delhi on July 3, 2025. The transaction, paid via MasterCard, totaled ₹2000.00 for 22.8 liters of Diesel at ₹87.71 per liter.",
  "payment_method": "Mastercard",
  "currency": "₹",
  "subtotal_amount": 2000.0,
  "tax_amount": null,
  "tip_amount": null,
  "total_amount": 2000.0,
  "items": [
    {
      "item_name": "Diesel",
      "quantity": 22.8,
      "unit_price": 87.71,
      "total_price": 2000.0,
      "category": "Transportation"
    }
  ],
  "tax_breakdown": [],
  "footer_notes": "PIN VERIFIED OK\nSIGNATURE NOT REQUIRED...",
  "pdf_path": "https://gofile.io/d/ctqSZG"
}
```

**Key Points:**
- **Single Object**: Contains only the latest receipt (not an array)
- **Auto-Updated**: Overwritten with each new receipt processing
- **Recovery**: Used for system recovery after restarts
- **API State**: Reflects the current `processing_state["current_receipt_data"]`

---

### 3. **processing_history.json** - Processing Step Log

This file tracks **all processing steps** performed by the system as a JSON array.

**Structure:**
```json
[
  {
    "step": "string",
    "timestamp": "ISO-8601",
    "input_file": "string",
    "output_file": "string|null",
    "success": boolean,
    "extracted_items": number|null,
    "wallet_link": "string|null",
    "split_id": "string|null",
    "contacts_count": number|null
  }
]
```

**Example:**
```json
[
  {
    "step": "upload",
    "timestamp": "2025-07-09T21:43:42.306252",
    "input_file": "uploaded_image_20250709_214329.jpg",
    "output_file": "receipt_20250709_214339.pdf",
    "success": true
  },
  {
    "step": "extract",
    "timestamp": "2025-07-09T21:44:36.174118",
    "input_file": "receipt_20250709_214339.pdf",
    "success": true,
    "extracted_items": 1
  },
  {
    "step": "passgen",
    "timestamp": "2025-07-09T21:46:30.273834",
    "wallet_link": "https://pay.google.com/gp/v/save/eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
    "success": true
  },
  {
    "step": "split_bill",
    "timestamp": "2025-07-09T21:50:15.123456",
    "split_id": "split_20250709_215015",
    "contacts_count": 3,
    "success": true
  }
]
```

**Step Types:**
- `upload`: Image upload and PDF conversion
- `extract`: Data extraction from PDF
- `passgen`: Google Wallet pass generation
- `split_bill`: Bill splitting operations

---

### 4. **split_history.json** - Bill Split Records

This file stores **all bill splits** performed by the system as a JSON array.

**Structure:**
```json
[
  {
    "receipt_info": {
      "store_name": "string",
      "date": "string",
      "total_amount": number,
      "currency": "string",
      "category": "string"
    },
    "split_details": {
      "total_people": number,
      "amount_per_person": number,
      "splits": [
        {
          "name": "string",
          "phone": "string",
          "email": "string",
          "amount": number,
          "currency": "string"
        }
      ]
    },
    "upi_links": [
      {
        "contact": { ... },
        "upi_link": "upi://pay?...",
        "amount": number,
        "currency": "string"
      }
    ],
    "split_id": "string",
    "timestamp": "ISO-8601"
  }
]
```

**Example:**
```json
[
  {
    "receipt_info": {
      "store_name": "Supermart",
      "date": "2025-07-03",
      "total_amount": 1500.0,
      "currency": "₹",
      "category": "Groceries"
    },
    "split_details": {
      "total_people": 3,
      "amount_per_person": 500.0,
      "splits": [
        {
          "name": "Alice",
          "phone": "+919876543210",
          "email": "alice@email.com",
          "amount": 500.0,
          "currency": "₹"
        },
        {
          "name": "Bob",
          "phone": "+919876543211",
          "email": "bob@email.com",
          "amount": 500.0,
          "currency": "₹"
        },
        {
          "name": "Charlie",
          "phone": "+919876543212",
          "email": "charlie@email.com",
          "amount": 500.0,
          "currency": "₹"
        }
      ]
    },
    "upi_links": [
      {
        "contact": { "name": "Alice", ... },
        "upi_link": "upi://pay?pa=9205704825@ptsbi&pn=Maisha&am=500.00&tr=BILLSPLIT_20250709_215015_Alice&tn=Bill split - Supermart&cu=INR",
        "amount": 500.0,
        "currency": "₹"
      }
    ],
    "split_id": "split_20250709_215015",
    "timestamp": "2025-07-09T21:50:15.123456"
  }
]
```

**Key Points:**
- **Split Calculation**: Amounts are evenly divided with rounding handled
- **UPI Links**: Deep links for instant payment via UPI apps
- **Unique IDs**: Each split gets a timestamp-based unique ID
- **Contact Info**: Full contact details for each person in the split

---

## 🧩 API Endpoints

### 1. **pipeline_api.py** (Port 8001)

#### **Root & Health**

- `GET /`  
  Returns API info and all available endpoints.

- `GET /health`  
  Health check.  
  **Response:**  
  ```json
  { "status": "healthy", "timestamp": "..." }
  ```

---

#### **Image & Receipt Processing**

- `POST /upload`  
  Upload an image (jpg/png/bmp/tiff) and convert to PDF.  
  **Request:**  
  - `file`: Image file (multipart/form-data)
  - `debug`: (optional, boolean)  
  **Response:**  
  ```json
  {
    "success": true,
    "message": "...",
    "input_file": "...",
    "output_pdf": "...",
    "file_size": 12345,
    "timestamp": "..."
  }
  ```

- `POST /extract`  
  Extract structured data from the latest PDF.  
  **Response:**  
  ```json
  {
    "success": true,
    "message": "...",
    "pdf_file": "...",
    "receipt_data": { ... },
    "timestamp": "..."
  }
  ```

- `POST /passgen`  
  Generate a Google Wallet pass from the extracted receipt data.  
  **Response:**  
  ```json
  {
    "success": true,
    "message": "...",
    "wallet_link": "https://pay.google.com/gp/v/save/...",
    "timestamp": "..."
  }
  ```

- `POST /process-complete`  
  Run the full pipeline (upload → extract → pass) in one call.  
  **Request:** Same as `/upload`  
  **Response:**  
  ```json
  {
    "success": true,
    "message": "...",
    "wallet_link": "...",
    "timestamp": "...",
    "steps": {
      "upload": {...},
      "extract": {...},
      "passgen": {...}
    }
  }
  ```

---

#### **Bill Splitting & UPI**

- `POST /split-bill`  
  Split the current receipt among contacts and generate UPI links.  
  **Request (JSON):**
  ```json
  {
    "receipt_id": "optional",  // Use current if omitted
    "contacts": [
      { "name": "Alice", "phone": "123...", "email": "alice@email.com" },
      { "name": "Bob", "phone": "456...", "email": "bob@email.com" }
    ],
    "upi_payee_vpa": "yourupi@bank",
    "upi_payee_name": "Your Name"
  }
  ```
  **Response:**
  ```json
  {
    "success": true,
    "message": "...",
    "split_data": {
      "receipt_info": { ... },
      "split_details": {
        "total_people": 2,
        "amount_per_person": 500.0,
        "splits": [
          { "name": "Alice", "phone": "...", "email": "...", "amount": 500.0, "currency": "INR" },
          { "name": "Bob", ... }
        ]
      },
      "upi_links": [
        { "contact": { ... }, "upi_link": "upi://pay?...&am=500.00...", "amount": 500.0, "currency": "INR" }
      ],
      "split_id": "split_YYYYMMDD_HHMMSS",
      "timestamp": "..."
    },
    "upi_links": [ ... ],  // same as above
    "timestamp": "..."
  }
  ```

- `POST /generate-upi`  
  Generate UPI links for the latest bill split.  
  **Request (form or query):**
    - `receipt_id` (optional)
    - `upi_payee_vpa` (default: "9205704825@ptsbi")
    - `upi_payee_name` (default: "Maisha")
  **Response:**  
  ```json
  {
    "success": true,
    "message": "...",
    "upi_links": [
      { "contact": { ... }, "upi_link": "upi://pay?...&am=500.00...", "amount": 500.0, "currency": "INR" }
    ],
    "split_id": "...",
    "timestamp": "..."
  }
  ```

- `POST /share-upi`  
  Generate a WhatsApp/SMS share URL for a UPI payment.  
  **Request (JSON):**
  ```json
  {
    "contact": { "name": "Alice", "phone": "123...", "email": "alice@email.com" },
    "amount": 500.0,
    "currency": "INR",
    "upi_link": "upi://pay?...",
    "store_name": "Supermart",
    "method": "whatsapp"  // or "sms"
  }
  ```
  **Response:**  
  ```json
  {
    "success": true,
    "method": "whatsapp",
    "share_url": "https://wa.me/123...?text=...",
    "message": "...",  // Pre-filled message
    "contact": "Alice",
    "note": "This only generates a WhatsApp share URL. Actual sending is not implemented server-side."
  }
  ```
  *(For SMS, `share_url` will be an `sms:` link.)*

---

#### **History, Status, and Files**

- `GET /status`  
  Get current processing state.

- `GET /history`  
  Get all processing steps performed.

- `GET /split-history`  
  Get all bill splits performed.

- `GET /dashboard`  
  Get summary data for dashboard (receipts count, categories, monthly spend, recent activity).

- `GET /download/{filename}`  
  Download any generated file (PDF, JSON, etc).

- `GET /categories`  
  List all supported expense categories.

---

#### **Shopping List Pass**

- `POST /generate-shopping-pass`  
  Generate a Google Wallet pass from a list of shopping items.  
  **Request (JSON):**
  ```json
  {
    "items": ["Milk", "Eggs", "Bread"],
    "recipe_name": "Groceries"
  }
  ```
  **Response:**  
  ```json
  {
    "success": true,
    "wallet_link": "https://pay.google.com/gp/v/save/...",
    "item_count": 3
  }
  ```

---

### 2. **new_chatbot.py** (Port 8000)

#### **Chatbot Endpoints**

- `POST /chat`  
  Ask a question about your receipts, get lists, or request insights.  
  **Request (JSON):**
  ```json
  {
    "query": "How much did I spend on groceries?",
    "user_id": "optional",
    "language": "en"
  }
  ```
  **Response:**
  ```json
  {
    "response": "Groceries: ₹1200.0 | Food: ₹800.0",
    "categories_analyzed": [],
    "receipts_count": 12,
    "wallet_pass_link": null,
    "pass_type": null,
    "timestamp": "...",
    "list_type": null,
    "list_items": null
  }
  ```
  - If the query is for a list (e.g., "What do I need for pizza?"), `list_type` and `list_items` will be filled, and a pass may be generated.

- `POST /reload`  
  Reload receipt data from file.

- `GET /health`  
  Health check.

- `GET /categories`  
  List all supported expense categories.

- `GET /receipts/count`  
  Get the number of loaded receipts.

---

### 3. **mcp_server.py** (Port 8002)

#### **Orchestrator Endpoints**

- `GET /`  
  Root info.

- `POST /process`  
  Forward a natural language query to the chatbot, and if a list is generated, trigger pass creation.  
  **Request (JSON):**
  ```json
  {
    "query": "What do I need for pizza?",
    "user_id": "optional",
    "language": "en"
  }
  ```
  **Response:**
  ```json
  {
    "chatbot_response": { ... },  // Same as /chat
    "pass_generation_result": {
      "success": true,
      "wallet_link": "https://pay.google.com/gp/v/save/..."
    }
  }
  ```
  - If no list is generated, `pass_generation_result` may be null.

---

## 📝 Input & Output Schemas

### **BillSplitRequest**
```json
{
  "receipt_id": "optional",
  "contacts": [
    { "name": "string", "phone": "string", "email": "string" }
  ],
  "upi_payee_vpa": "string",
  "upi_payee_name": "string"
}
```

### **UPIShareRequest**
```json
{
  "contact": { "name": "string", "phone": "string", "email": "string" },
  "amount": 123.45,
  "currency": "INR",
  "upi_link": "upi://pay?...",
  "store_name": "string",
  "method": "whatsapp" // or "sms"
}
```

### **ChatRequest**
```json
{
  "query": "string",
  "user_id": "optional",
  "language": "en"
}
```

### **ChatResponse**
```json
{
  "response": "string",
  "categories_analyzed": [],
  "receipts_count": 0,
  "wallet_pass_link": "string|null",
  "pass_type": "string|null",
  "timestamp": "string",
  "list_type": "string|null",
  "list_items": ["string", ...] // or null
}
```

---

## 💡 Usage Tips

- Always call `/upload` → `/extract` → `/passgen` in sequence, or use `/process-complete`.
- Use `/split-bill` after extracting receipt data to split among contacts.
- Use `/generate-upi` to regenerate UPI links for the latest split.
- Use `/share-upi` to generate WhatsApp/SMS share URLs for UPI payments.
- Use `/chat` for AI-powered queries, list generation, and insights.
- Use `/process` (orchestrator) for a one-stop conversational workflow.

---

## 🛠️ Example Frontend Flows

1. **Upload & Process Receipt**
   - POST `/upload` (image) → POST `/extract` → POST `/passgen`

2. **Split Bill & Share**
   - POST `/split-bill` (with contacts, UPI info)
   - POST `/share-upi` (for each contact, to get WhatsApp/SMS link)

3. **Conversational Query**
   - POST `/chat` (ask for spending, lists, etc.)

4. **Orchestrated Flow**
   - POST `/process` (let backend handle chat + pass generation)

---

## 📚 Further Reference

- All endpoints have OpenAPI docs at `/docs` (for each service).
- All request/response schemas are Pydantic models, ensuring strict validation.
- For any file download, use `/download/{filename}`.

---

**This README is auto-generated from the codebase and covers every endpoint, input, output, and data storage structure for seamless frontend integration.** If you need more details on any endpoint or want example payloads, just ask! 