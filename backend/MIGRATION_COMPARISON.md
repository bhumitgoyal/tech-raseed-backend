# Migration Comparison: Old vs New Backend

## Overview

This document compares the old three-service backend setup with the new consolidated backend.

## Old Setup (3 Services, 3 Ports)

### Services
1. **Chatbot Service** (`new_chatbot.py`) - Port 8000
2. **Pipeline API** (`pipeline_api.py`) - Port 8001  
3. **MCP Server** (`mcp_server.py`) - Port 8002

### Startup Process
```bash
# Old way - Start each service separately
python new_chatbot.py          # Port 8000
python pipeline_api.py         # Port 8001
python mcp_server.py           # Port 8002

# Or use the startup script
python start_mcp_system.py     # Starts all 3 services
```

### API Endpoints (Old)
- **Port 8000**: `/chat`, `/health`, `/categories`, `/receipts/count`
- **Port 8001**: `/upload`, `/extract`, `/passgen`, `/split-bill`, `/generate-shopping-pass`
- **Port 8002**: `/process`, `/`

### Frontend Configuration (Old)
```javascript
// Multiple API endpoints
const CHATBOT_API = 'http://localhost:8000';
const PIPELINE_API = 'http://localhost:8001';
const MCP_API = 'http://localhost:8002';
```

## New Setup (1 Service, 1 Port)

### Service
1. **Consolidated Backend** (`main.py`) - Port 8000

### Startup Process
```bash
# New way - Start single service
python main.py                 # Port 8000

# Or use the startup script
python start_server.py         # Port 8000
```

### API Endpoints (New)
- **Port 8000**: All endpoints from all three old services
  - `/chat`, `/process` (from old chatbot/MCP)
  - `/upload`, `/extract`, `/passgen`, `/split-bill` (from old pipeline)
  - `/generate-shopping-pass`, `/receipts/all`, `/categories` (from old services)
  - `/health`, `/status` (new consolidated endpoints)

### Frontend Configuration (New)
```javascript
// Single API endpoint
const API_BASE_URL = 'http://localhost:8000';
```

## Detailed Endpoint Mapping

| Old Endpoint | Old Port | New Endpoint | New Port | Status |
|--------------|----------|--------------|----------|---------|
| `/chat` | 8000 | `/chat` | 8000 | ✅ Same |
| `/health` | 8000 | `/health` | 8000 | ✅ Same |
| `/categories` | 8000 | `/categories` | 8000 | ✅ Same |
| `/receipts/count` | 8000 | `/receipts/all` | 8000 | ✅ Enhanced |
| `/upload` | 8001 | `/upload` | 8000 | ✅ Same |
| `/extract` | 8001 | `/extract` | 8000 | ✅ Same |
| `/passgen` | 8001 | `/passgen` | 8000 | ✅ Same |
| `/split-bill` | 8001 | `/split-bill` | 8000 | ✅ Same |
| `/generate-shopping-pass` | 8001 | `/generate-shopping-pass` | 8000 | ✅ Same |
| `/process-complete` | 8001 | `/process-complete` | 8000 | ✅ Same |
| `/share-upi` | 8001 | `/share-upi` | 8000 | ✅ Same |
| `/process` | 8002 | `/process` | 8000 | ✅ Same |
| `/` | 8002 | `/` | 8000 | ✅ Enhanced |

## Benefits of New Setup

### 1. Simplified Deployment
- **Old**: 3 separate processes to manage
- **New**: 1 process to manage

### 2. Single Port Configuration
- **Old**: Configure 3 different ports (8000, 8001, 8002)
- **New**: Configure 1 port (8000)

### 3. Unified API Documentation
- **Old**: 3 separate Swagger docs (one per service)
- **New**: 1 comprehensive Swagger doc at `/docs`

### 4. Easier Development
- **Old**: Need to understand 3 different codebases
- **New**: Single codebase with all functionality

### 5. Better Error Handling
- **Old**: Errors could occur in any of 3 services
- **New**: Centralized error handling and logging

### 6. Simplified Testing
- **Old**: Test 3 separate services
- **New**: Test 1 service with all endpoints

## Migration Steps

### 1. Stop Old Services
```bash
# Stop all old services
pkill -f "new_chatbot.py"
pkill -f "pipeline_api.py"
pkill -f "mcp_server.py"
```

### 2. Install New Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 3. Start New Service
```bash
python start_server.py
```

### 4. Update Frontend
```javascript
// Change from multiple APIs to single API
const API_BASE_URL = 'http://localhost:8000';

// All endpoint calls remain the same, just change the base URL
fetch(`${API_BASE_URL}/chat`, { ... })
fetch(`${API_BASE_URL}/upload`, { ... })
fetch(`${API_BASE_URL}/process`, { ... })
```

### 5. Test Migration
```bash
# Test health endpoint
curl http://localhost:8000/health

# Test API documentation
curl http://localhost:8000/docs
```

## Backward Compatibility

The new consolidated backend maintains **100% backward compatibility** with the old API endpoints:

- All request/response formats remain the same
- All endpoint paths remain the same
- All functionality is preserved
- Only the port number changes (from multiple ports to single port)

## Performance Considerations

### Resource Usage
- **Old**: 3 separate Python processes
- **New**: 1 Python process (potentially more efficient)

### Memory Usage
- **Old**: 3 separate memory spaces
- **New**: Shared memory space (may be more efficient)

### Network Overhead
- **Old**: Potential inter-service communication overhead
- **New**: No inter-service communication (all internal)

## Troubleshooting

### Common Issues During Migration

1. **Port Already in Use**
   ```bash
   # Check what's using port 8000
   lsof -i :8000
   
   # Kill the process if needed
   kill -9 <PID>
   ```

2. **Missing Dependencies**
   ```bash
   # Install dependencies
   pip install -r requirements.txt
   ```

3. **Missing Credentials**
   - Ensure Google credential files exist in `backend-raseed/`
   - Check file permissions

4. **Frontend Connection Issues**
   - Update API base URL to `http://localhost:8000`
   - Clear browser cache
   - Check CORS settings

## Support

If you encounter issues during migration:

1. Run the migration script: `python migrate.py`
2. Check the logs for detailed error messages
3. Verify all credential files are in place
4. Test individual endpoints using curl or Postman
5. Check the API documentation at `http://localhost:8000/docs` 