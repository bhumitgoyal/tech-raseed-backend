# Quick Start Guide - TechTitan Consolidated Backend

## 🚀 Get Started in 3 Steps

### Step 1: Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### Step 2: Start the Server
```bash
python start_server.py
```

### Step 3: Test the API
```bash
# Health check
curl http://localhost:8000/health

# View API documentation
open http://localhost:8000/docs
```

## 📋 What's New

✅ **Single Port**: Everything runs on port 8000  
✅ **Unified API**: All endpoints in one place  
✅ **Same Functionality**: All features from the old 3-service setup  
✅ **Better Documentation**: Complete API docs at `/docs`  

## 🔄 Migration from Old Setup

If you're coming from the old 3-service setup:

1. **Stop old services**:
   ```bash
   pkill -f "new_chatbot.py"
   pkill -f "pipeline_api.py" 
   pkill -f "mcp_server.py"
   ```

2. **Run migration script**:
   ```bash
   python migrate.py
   ```

3. **Update your frontend**:
   ```javascript
   // Change from multiple APIs to single API
   const API_BASE_URL = 'http://localhost:8000';
   ```

## 🎯 Key Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Server info and available endpoints |
| `POST /chat` | AI-powered chatbot |
| `POST /upload` | Upload and process receipts |
| `POST /process-complete` | Complete pipeline: Upload → Extract → Generate Pass |
| `POST /split-bill` | Split bills with UPI links |
| `POST /share-upi` | Share UPI payment links via WhatsApp/SMS |
| `POST /generate-shopping-pass` | Create Google Wallet passes |
| `GET /docs` | Interactive API documentation |

## 🛠️ Development

### Start with Auto-reload
```bash
uvicorn main:app --reload --port 8000
```

### View Logs
All logs are printed to stdout with timestamps and log levels.

### Test Endpoints
Use the interactive docs at `http://localhost:8000/docs` or curl:

```bash
# Test chat
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"query": "Hello!", "language": "en"}'

# Test health
curl http://localhost:8000/health
```

## 🔧 Configuration

### Environment Variables
The app automatically sets:
- `GOOGLE_APPLICATION_CREDENTIALS` → `backend-raseed/splendid-yeti-464913-j2-e4fcc70357d3.json`
- `GOOGLE_APPLICATION_CREDENTIALS2` → `backend-raseed/tempmail_service.json`

### File Structure
```
backend/
├── main.py              # Main FastAPI application
├── start_server.py      # Startup script with checks
├── migrate.py           # Migration helper
├── requirements.txt     # Dependencies
├── README.md           # Detailed documentation
└── MIGRATION_COMPARISON.md  # Old vs new comparison
```

## 🚨 Troubleshooting

### Port Already in Use
```bash
lsof -i :8000
kill -9 <PID>
```

### Missing Dependencies
```bash
pip install -r requirements.txt
```

### Missing Credentials
Ensure these files exist in `backend-raseed/`:
- `splendid-yeti-464913-j2-e4fcc70357d3.json`
- `tempmail_service.json`

### Service Won't Start
```bash
# Check logs
python start_server.py

# Manual start with verbose output
python main.py
```

## 📞 Support

1. Check the logs for error messages
2. Verify all files are in the correct locations
3. Test with the API documentation at `/docs`
4. Run the migration script: `python migrate.py`

## 🎉 Success!

Once running, you'll see:
```
🚀 Starting TechTitan Consolidated Backend API on port 8000
✅ All checks passed
🌐 Starting server on http://localhost:8000
📚 API documentation: http://localhost:8000/docs
```

Your consolidated backend is ready! 🚀 