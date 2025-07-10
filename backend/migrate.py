#!/usr/bin/env python3
"""
Migration script for TechTitan Backend
Helps transition from the old three-service setup to the new consolidated backend
"""

import os
import sys
import subprocess
import time
from pathlib import Path

def check_old_services():
    """Check if old services are running and stop them."""
    print("🔍 Checking for old services...")
    
    old_services = [
        ("new_chatbot.py", 8000),
        ("pipeline_api.py", 8001),
        ("mcp_server.py", 8002)
    ]
    
    running_services = []
    
    for script, port in old_services:
        try:
            # Check if process is running
            result = subprocess.run(
                ["pgrep", "-f", script],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                running_services.append((script, port))
                print(f"⚠️  Found running service: {script} on port {port}")
        except Exception:
            pass
    
    if running_services:
        print("\n🛑 Stopping old services...")
        for script, port in running_services:
            try:
                subprocess.run(["pkill", "-f", script], check=True)
                print(f"✅ Stopped {script}")
                time.sleep(1)  # Give time for graceful shutdown
            except subprocess.CalledProcessError:
                print(f"❌ Failed to stop {script}")
        print("✅ All old services stopped")
    else:
        print("✅ No old services found running")
    
    return True

def check_dependencies():
    """Check if all required dependencies are installed."""
    print("\n📦 Checking dependencies...")
    
    required_packages = [
        "fastapi",
        "uvicorn", 
        "google.auth",
        "vertexai",
        "requests",
        "pydantic",
        "aiofiles",
        "jwt",
        "cv2",
        "PIL",
        "numpy"
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ Missing packages: {', '.join(missing_packages)}")
        print("💡 Installing dependencies...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
            print("✅ Dependencies installed")
        except subprocess.CalledProcessError:
            print("❌ Failed to install dependencies")
            return False
    else:
        print("✅ All dependencies are installed")
    
    return True

def check_credentials():
    """Check if Google credentials exist."""
    print("\n🔐 Checking credentials...")
    
    backend_raseed = Path(__file__).parent.parent / "backend-raseed"
    required_files = [
        "splendid-yeti-464913-j2-e4fcc70357d3.json",
        "tempmail_service.json"
    ]
    
    missing_files = []
    for file in required_files:
        if not (backend_raseed / file).exists():
            missing_files.append(file)
    
    if missing_files:
        print(f"❌ Missing credential files: {', '.join(missing_files)}")
        print("💡 Please ensure these files exist in the backend-raseed directory")
        return False
    
    print("✅ All credential files found")
    return True

def test_new_service():
    """Test the new consolidated service."""
    print("\n🧪 Testing new service...")
    
    try:
        # Start the service in background
        process = subprocess.Popen(
            [sys.executable, "main.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Wait for service to start
        time.sleep(5)
        
        # Test health endpoint
        import requests
        response = requests.get("http://localhost:8000/health", timeout=10)
        
        if response.status_code == 200:
            print("✅ New service is working correctly")
            process.terminate()
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            process.terminate()
            return False
            
    except Exception as e:
        print(f"❌ Failed to test new service: {e}")
        if 'process' in locals():
            process.terminate()
        return False

def show_migration_guide():
    """Show migration guide for frontend updates."""
    print("\n📋 Migration Guide")
    print("=" * 50)
    print("To complete the migration, update your frontend configuration:")
    print()
    print("1. Change the base URL from multiple ports to single port:")
    print("   OLD: Multiple services on ports 8000, 8001, 8002")
    print("   NEW: Single service on port 8000")
    print()
    print("2. Update your API client configuration:")
    print("   const API_BASE_URL = 'http://localhost:8000'")
    print()
    print("3. All endpoints remain the same:")
    print("   - /chat (was on port 8000)")
    print("   - /upload (was on port 8001)")
    print("   - /process (was on port 8002)")
    print("   - /split-bill (was on port 8001)")
    print()
    print("4. Test the new endpoints:")
    print("   curl http://localhost:8000/health")
    print("   curl http://localhost:8000/docs")
    print()
    print("5. The API documentation is available at:")
    print("   http://localhost:8000/docs")
    print("=" * 50)

def main():
    """Main migration function."""
    print("🚀 TechTitan Backend Migration")
    print("=" * 50)
    print("This script will help you migrate from the old three-service")
    print("setup to the new consolidated backend.")
    print("=" * 50)
    
    # Check and stop old services
    if not check_old_services():
        print("❌ Failed to stop old services")
        sys.exit(1)
    
    # Check dependencies
    if not check_dependencies():
        print("❌ Failed to install dependencies")
        sys.exit(1)
    
    # Check credentials
    if not check_credentials():
        print("❌ Missing credentials")
        sys.exit(1)
    
    # Test new service
    if not test_new_service():
        print("❌ New service test failed")
        sys.exit(1)
    
    print("\n✅ Migration completed successfully!")
    print("=" * 50)
    
    # Show migration guide
    show_migration_guide()
    
    print("\n🎉 You can now start the consolidated backend with:")
    print("   python start_server.py")
    print("   or")
    print("   python main.py")

if __name__ == "__main__":
    main() 