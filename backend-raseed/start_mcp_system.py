#!/usr/bin/env python3
"""
Startup script for MCP Receipt Processing System
Launches all services: chatbot, pipeline, and MCP server
"""

import os
import sys
import time
import signal
import subprocess
from pathlib import Path
from threading import Thread
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ServiceManager:
    def __init__(self):
        self.processes = []
        self.running = True
        
    def start_service(self, name: str, script: str, port: int, delay: float = 0):
        """Start a service in a separate process."""
        try:
            if delay > 0:
                logger.info(f"⏳ Waiting {delay}s before starting {name}")
                time.sleep(delay)
                
            logger.info(f"🚀 Starting {name} on port {port}")
            
            # Start the service
            process = subprocess.Popen(
                [sys.executable, script],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            self.processes.append({
                'name': name,
                'process': process,
                'port': port
            })
            
            logger.info(f"✅ {name} started (PID: {process.pid})")
            
        except Exception as e:
            logger.error(f"❌ Failed to start {name}: {e}")
            
    def monitor_service(self, service_info):
        """Monitor a service and log its output."""
        name = service_info['name']
        process = service_info['process']
        
        try:
            while self.running and process.poll() is None:
                # Read stdout
                if process.stdout:
                    line = process.stdout.readline()
                    if line:
                        logger.info(f"[{name}] {line.strip()}")
                
                # Check if process is still running
                if process.poll() is not None:
                    break
                    
                time.sleep(0.1)
                
        except Exception as e:
            logger.error(f"❌ Error monitoring {name}: {e}")
            
        logger.info(f"🔴 {name} stopped")
        
    def stop_all(self):
        """Stop all services."""
        logger.info("🛑 Stopping all services...")
        self.running = False
        
        for service_info in self.processes:
            try:
                name = service_info['name']
                process = service_info['process']
                
                if process.poll() is None:
                    logger.info(f"⏹️ Stopping {name}")
                    process.terminate()
                    
                    # Wait for graceful shutdown
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        logger.warning(f"⚠️ Force killing {name}")
                        process.kill()
                        
            except Exception as e:
                logger.error(f"❌ Error stopping service: {e}")
                
        logger.info("✅ All services stopped")
        
    def check_prerequisites(self):
        """Check if all required files exist."""
        required_files = [
            'new_chatbot.py',
            'pipeline_api.py',
            'mcp_server.py'
        ]
        
        missing_files = []
        for file in required_files:
            if not Path(file).exists():
                missing_files.append(file)
                
        if missing_files:
            logger.error(f"❌ Missing required files: {', '.join(missing_files)}")
            return False
            
        return True
        
    def run_system(self):
        """Run the complete MCP system."""
        if not self.check_prerequisites():
            return
            
        logger.info("🎯 Starting MCP Receipt Processing System")
        logger.info("=" * 60)
        
        # Start services with staggered delays
        services = [
            ('Chatbot Service', 'new_chatbot.py', 8000, 0),
            ('MCP Server', 'mcp_server.py', 8002, 6)
        ]
        
        # Start all services
        for name, script, port, delay in services:
            service_thread = Thread(
                target=self.start_service,
                args=(name, script, port, delay)
            )
            service_thread.start()
            
        # Wait for all services to start
        time.sleep(10)
        
        # Start monitoring threads
        monitor_threads = []
        for service_info in self.processes:
            monitor_thread = Thread(
                target=self.monitor_service,
                args=(service_info,)
            )
            monitor_thread.start()
            monitor_threads.append(monitor_thread)
            
        logger.info("🌟 MCP System is running!")
        logger.info("=" * 60)
        logger.info("📋 Service URLs:")
        logger.info("   • Chatbot Service: http://localhost:8000")
        logger.info("   • MCP Server: http://localhost:8002")
        logger.info("=" * 60)
        logger.info("💡 Example MCP workflow:")
        logger.info("   POST http://localhost:8002/process")
        logger.info("   {")
        logger.info('     "query": "Can I make pizza? I have flour, tomato sauce, and cheese."')
        logger.info("   }")
        logger.info("=" * 60)
        logger.info("Press Ctrl+C to stop all services")
        
        try:
            # Keep the main thread alive
            while self.running:
                time.sleep(1)
                
                # Check if any service has died
                dead_services = []
                for service_info in self.processes:
                    if service_info['process'].poll() is not None:
                        dead_services.append(service_info['name'])
                        
                if dead_services:
                    logger.warning(f"⚠️ Dead services detected: {', '.join(dead_services)}")
                    
        except KeyboardInterrupt:
            logger.info("🛑 Shutdown requested")
            
        finally:
            self.stop_all()
            
            # Wait for monitor threads to finish
            for thread in monitor_threads:
                thread.join(timeout=1)

def signal_handler(signum, frame):
    """Handle system signals."""
    logger.info("📡 Received shutdown signal")
    sys.exit(0)

def main():
    """Main function."""
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Check if virtual environment is activated
    if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        logger.warning("⚠️ Virtual environment not detected. Please activate your venv:")
        logger.warning("   source venv/bin/activate")
        logger.warning("   pip install -r requirements.txt")
        
    # Create and run service manager
    service_manager = ServiceManager()
    
    try:
        service_manager.run_system()
    except Exception as e:
        logger.error(f"❌ System error: {e}")
        service_manager.stop_all()
        sys.exit(1)

if __name__ == "__main__":
    main() 