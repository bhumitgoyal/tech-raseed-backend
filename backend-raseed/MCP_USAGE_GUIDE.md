# MCP Receipt Processing System - Usage Guide

## Overview

This MCP (Model Context Protocol) architecture integrates your existing receipt processing system with intelligent ingredient checking and Google Wallet pass generation. The system answers questions like "Can I make pizza?" by checking your receipt history and creating shopping passes for missing ingredients.

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   MCP Server    │    │   Chatbot       │    │   Pipeline      │
│   (Port 8002)   │◄──►│   (Port 8000)   │    │   (Port 8001)   │
│                 │    │                 │    │                 │
│ • Tool Dispatch │    │ • Receipt Query │    │ • Image Process │
│ • Orchestration │    │ • AI Analysis   │    │ • Pass Creation │
│ • Workflow Mgmt │    │ • Wallet Pass   │    │ • PDF Extract   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## System Components

### 1. MCP Server (`mcp_server.py`)
- **Purpose**: Orchestrates the ingredient checking and pass generation workflow
- **Port**: 8002
- **Key Features**:
  - MCP tool definitions and execution
  - Ingredient availability checking
  - Shopping pass generation
  - Workflow orchestration

### 2. Chatbot Service (`new_chatbot.py`)
- **Purpose**: Analyzes receipt data and generates intelligent responses
- **Port**: 8000
- **Key Features**:
  - Receipt history analysis
  - Natural language processing
  - Shopping list generation
  - Google Wallet pass creation

### 3. Pipeline Service (`pipeline_api.py`)
- **Purpose**: Handles receipt processing and data extraction
- **Port**: 8001
- **Key Features**:
  - Image to PDF conversion
  - OCR data extraction
  - Receipt data processing

## MCP Tools Available

### 1. `check_ingredient_availability`
Checks if ingredients are available based on user's receipt history.

**Input Schema**:
```json
{
  "recipe_name": "string",
  "ingredients": ["string"],
  "user_id": "string (optional)"
}
```

**Example**:
```json
{
  "recipe_name": "Pizza",
  "ingredients": ["flour", "tomato sauce", "mozzarella cheese", "pepperoni"],
  "user_id": "user123"
}
```

### 2. `generate_shopping_pass`
Generates a Google Wallet pass for missing ingredients.

**Input Schema**:
```json
{
  "missing_ingredients": ["string"],
  "recipe_name": "string",
  "user_id": "string (optional)"
}
```

**Example**:
```json
{
  "missing_ingredients": ["pepperoni", "mozzarella cheese"],
  "recipe_name": "Pizza",
  "user_id": "user123"
}
```

## Quick Start

### 1. Setup Environment
```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Start All Services
```bash
# Start all services with one command
python start_mcp_system.py
```

This will start:
- Chatbot Service on http://localhost:8000
- Pipeline Service on http://localhost:8001
- MCP Server on http://localhost:8002

### 3. Test the System
```bash
# Run demo to see the system in action
python demo_mcp_tools.py
```

## Usage Examples

### Example 1: Using MCP Tools Directly

```python
import requests

# Check ingredient availability
response = requests.post("http://localhost:8002/mcp/tools/call", json={
    "name": "check_ingredient_availability",
    "arguments": {
        "recipe_name": "Pizza",
        "ingredients": ["flour", "tomato sauce", "cheese", "pepperoni"],
        "user_id": "user123"
    }
})

result = response.json()
print(result)
```

### Example 2: Using Simplified API

```python
import requests

# Complete workflow in one call
response = requests.post("http://localhost:8002/recipe-assistant", params={
    "recipe_name": "Pizza",
    "ingredients": ["flour", "tomato sauce", "cheese", "pepperoni"],
    "user_id": "user123"
})

result = response.json()
print(f"Has all ingredients: {result['availability_check']['has_all_ingredients']}")
if result['shopping_pass']:
    print(f"Wallet link: {result['shopping_pass']['wallet_link']}")
```

### Example 3: cURL Commands

```bash
# Check ingredients
curl -X POST "http://localhost:8002/mcp/tools/call" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "check_ingredient_availability",
    "arguments": {
      "recipe_name": "Pizza",
      "ingredients": ["flour", "tomato sauce", "cheese", "pepperoni"]
    }
  }'

# Complete workflow
curl -X POST "http://localhost:8002/recipe-assistant" \
  -d "recipe_name=Pizza&ingredients=flour&ingredients=tomato sauce&ingredients=cheese&ingredients=pepperoni"
```

## Workflow Description

### The "Can I Make Pizza?" Workflow

1. **User Query**: "Can I make pizza?"
2. **Ingredient Analysis**: MCP server calls chatbot to check ingredient availability
3. **Receipt History Check**: Chatbot analyzes user's receipt history
4. **Missing Ingredients**: System identifies what's missing
5. **Pass Generation**: If ingredients are missing, create Google Wallet pass
6. **Response**: User gets availability status and shopping pass (if needed)

### Detailed Flow

```
User Query → MCP Server → Chatbot Service → Receipt Analysis
                ↓              ↓              ↓
            Tool Dispatch → AI Analysis → Missing Items
                ↓              ↓              ↓
         Pass Generation → Wallet API → Shopping Pass
                ↓              ↓              ↓
            Response ← Combined Result ← Wallet Link
```

## API Endpoints

### MCP Server (Port 8002)
- `GET /` - Server information
- `GET /health` - Health check
- `GET /mcp/tools` - List available tools
- `POST /mcp/tools/call` - Execute MCP tool
- `POST /recipe-assistant` - Complete workflow

### Chatbot Service (Port 8000)
- `POST /chat` - Chat with receipt analysis
- `GET /health` - Health check
- `GET /categories` - Get expense categories
- `GET /receipts/count` - Get receipt count

### Pipeline Service (Port 8001)
- `POST /upload` - Upload image for processing
- `POST /extract` - Extract data from PDF
- `POST /passgen` - Generate wallet pass
- `GET /status` - Processing status

## Error Handling

The system includes comprehensive error handling:
- Service unavailability fallbacks
- Graceful degradation
- Detailed error logging
- Retry mechanisms for API calls

## Configuration

### Environment Variables
- `GOOGLE_APPLICATION_CREDENTIALS` - Path to Google service account key
- `GOOGLE_APPLICATION_CREDENTIALS2` - Path to secondary service account key (for wallet)

### Service URLs
Configure in `mcp_server.py`:
```python
CHATBOT_BASE_URL = "http://localhost:8000"
PIPELINE_BASE_URL = "http://localhost:8001"
```

## Troubleshooting

### Common Issues

1. **Service Not Starting**
   - Check if ports are available
   - Verify virtual environment is activated
   - Check Google service account credentials

2. **Tool Execution Fails**
   - Ensure all services are running
   - Check network connectivity between services
   - Verify request format matches schema

3. **Pass Generation Fails**
   - Check Google Wallet API credentials
   - Verify service account permissions
   - Check wallet issuer configuration

### Debug Mode
Enable debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Integration with GenAI

This MCP system can be integrated with any GenAI system that supports MCP tools:

```python
# Example integration with a GenAI client
tools = [
    {
        "name": "check_ingredient_availability",
        "description": "Check if ingredients are available based on receipt history",
        "endpoint": "http://localhost:8002/mcp/tools/call"
    },
    {
        "name": "generate_shopping_pass",
        "description": "Generate Google Wallet pass for missing ingredients",
        "endpoint": "http://localhost:8002/mcp/tools/call"
    }
]

# Use tools in your GenAI conversations
response = genai_client.chat("Can I make pizza?", tools=tools)
```

## Next Steps

1. **Extend Recipe Database**: Add more recipes and ingredients
2. **Enhance NLP**: Improve ingredient extraction from chatbot responses
3. **Add Nutrition Data**: Include nutritional information in passes
4. **User Preferences**: Store user dietary preferences and restrictions
5. **Shopping Integration**: Connect with grocery store APIs for real-time pricing

---

**Happy Cooking! 🍕🛒** 