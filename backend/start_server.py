#!/usr/bin/env python3
"""
Startup script for TechTitan Consolidated Backend
Runs the complete backend service on a single port (8000)
"""

import os
import sys
import subprocess
from pathlib import Path

def check_dependencies():
    """Check if all required dependencies are installed."""
    try:
        import fastapi
        import uvicorn
        import google.auth
        import vertexai
        import requests
        import pydantic
        import aiofiles
        import jwt
        import cv2
        import PIL
        import numpy
        print("✅ All dependencies are installed")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("💡 Please install dependencies: pip install -r requirements.txt")
        return False

def main():
    """Main startup function."""
    print("🚀 Starting TechTitan Consolidated Backend")
    print("=" * 50)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    print("✅ All checks passed")
    print("=" * 50)
    print("🌐 Starting server on http://localhost:8000")
    print("📚 API documentation: http://localhost:8000/docs")
    print("=" * 50)
    print("Press Ctrl+C to stop the server")
    print("=" * 50)
    
    # Start the server
    try:
        import uvicorn
        from main import app
        
        uvicorn.run(
            "main:app", 
            host="0.0.0.0", 
            port=8000, 
            reload=True,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 
