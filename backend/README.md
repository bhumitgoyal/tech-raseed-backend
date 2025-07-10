# TechTitan Consolidated Backend

This is a consolidated FastAPI backend that combines all functionality from the original three separate services into a single application running on port 8000.

## What's Included

The consolidated backend includes all functionality from:

1. **Chatbot Service** (`new_chatbot.py`) - AI-powered chat with receipt analysis
2. **Pipeline API** (`pipeline_api.py`) - Receipt processing and data extraction
3. **MCP Server** (`mcp_server.py`) - Query processing and orchestration
4. **Bill Splitter** (`bill_splitter.py`) - Bill splitting with UPI payment links

## Features

- **Single Port**: All services run on port 8000
- **Unified API**: All endpoints available through one API
- **AI Integration**: Google Vertex AI for intelligent responses
- **Receipt Processing**: Image upload, PDF conversion, data extraction
- **Google Wallet**: Pass generation for shopping lists and receipts
- **Bill Splitting**: Split bills among contacts with UPI payment links
- **Real-time Processing**: Background task processing for file operations

## Setup

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Verify Credentials

Ensure these files exist in the `backend-raseed` directory:
- `splendid-yeti-464913-j2-e4fcc70357d3.json` (Google Cloud credentials)
- `tempmail_service.json` (Google Wallet service account)

### 3. Start the Server

```bash
# Option 1: Using the startup script
python start_server.py

# Option 2: Direct execution
python main.py

# Option 3: Using uvicorn directly
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## API Endpoints

### Core Endpoints

- `GET /` - Server information and available endpoints
- `GET /health` - Health check
- `GET /status` - System status and processing state

### Chat & AI

- `POST /chat` - Enhanced chatbot with AI analysis
- `POST /process` - MCP-style query processing

### Receipt Processing

- `POST /upload` - Upload and process receipt images
- `POST /extract` - Extract data from PDF files
- `POST /process-complete` - Complete pipeline: Upload → Extract → Generate Pass
- `GET /receipts/all` - Get all processed receipts

### Google Wallet

- `POST /passgen` - Generate Google Wallet pass from receipt data
- `POST /generate-shopping-pass` - Generate shopping list pass

### Bill Splitting

- `POST /split-bill` - Split bill among selected contacts
- `POST /share-upi` - Share UPI payment links via WhatsApp/SMS
- `GET /split-history` - Get bill split history

### Utilities

- `GET /categories` - Get available expense categories

## API Documentation

Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Example Usage

### 1. Chat with AI

```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Can I make pizza? I have flour, tomato sauce, and cheese.",
    "language": "en"
  }'
```

### 2. Upload Receipt

```bash
curl -X POST "http://localhost:8000/upload" \
  -F "file=@receipt.jpg"
```

### 3. Split Bill

```bash
curl -X POST "http://localhost:8000/split-bill" \
  -H "Content-Type: application/json" \
  -d '{
    "contacts": [
      {"name": "John", "phone": "+1234567890", "email": "john@example.com"},
      {"name": "Jane", "phone": "+0987654321", "email": "jane@example.com"}
    ],
    "upi_payee_vpa": "your-upi@bank",
    "upi_payee_name": "Your Name"
  }'
```

### 4. Complete Pipeline Processing

```bash
curl -X POST "http://localhost:8000/process-complete" \
  -F "file=@receipt.jpg"
```

### 5. Generate Shopping Pass

```bash
curl -X POST "http://localhost:8000/generate-shopping-pass" \
  -H "Content-Type: application/json" \
  -d '{
    "items": ["flour", "tomato sauce", "cheese", "olive oil"],
    "recipe_name": "Pizza Ingredients"
  }'
```

### 6. Share UPI Payment

```bash
curl -X POST "http://localhost:8000/share-upi" \
  -H "Content-Type: application/json" \
  -d '{
    "contact": {
      "name": "John",
      "phone": "+1234567890",
      "email": "john@example.com"
    },
    "amount": 25.50,
    "currency": "INR",
    "upi_link": "upi://pay?pa=payee@bank&pn=Payee&am=25.50",
    "store_name": "Restaurant",
    "method": "whatsapp"
  }'
```

## Configuration

### Environment Variables

The application automatically sets these environment variables:
- `GOOGLE_APPLICATION_CREDENTIALS` - Points to Google Cloud credentials
- `GOOGLE_APPLICATION_CREDENTIALS2` - Points to Google Wallet service account

### File Paths

The application expects these files to exist in the `backend-raseed` directory:
- Receipt processing scripts (`imageconvert.py`, `dataextract.py`, etc.)
- Google credential files
- Temporary data files

## Migration from Original Services

If you were using the original three-service setup:

1. **Stop the old services**:
   ```bash
   # Stop the old services (if running)
   pkill -f "new_chatbot.py"
   pkill -f "pipeline_api.py"
   pkill -f "mcp_server.py"
   ```

2. **Update your frontend** to use the new consolidated endpoints:
   - Base URL: `http://localhost:8000`
   - All endpoints remain the same, just on one port

3. **Test the new service**:
   ```bash
   curl http://localhost:8000/health
   ```

## Troubleshooting

### Common Issues

1. **Missing Dependencies**: Run `pip install -r requirements.txt`
2. **Missing Credentials**: Ensure Google credential files exist in `backend-raseed/`
3. **Port Already in Use**: Stop other services using port 8000
4. **Permission Errors**: Ensure write permissions for temporary files

### Logs

The application logs to stdout with detailed information about:
- Service startup
- API requests
- Processing errors
- Google API interactions

## Development

### Adding New Endpoints

1. Add the endpoint to `main.py`
2. Update the root endpoint documentation
3. Test with the API documentation

### Modifying Services

The consolidated backend maintains the same service classes as the original:
- `EnhancedWalletPassGenerator`
- `EnhancedReceiptAnalysisService`
- `BillSplitterService`

## License

This project follows the same license as the original TechTitan project. 