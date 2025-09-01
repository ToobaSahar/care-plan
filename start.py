#!/usr/bin/env python3
"""
Startup script for the Care Plan Generator Backend
"""

import uvicorn
from config import Config

def main():
    """Start the FastAPI server"""
    print("🚀 Starting Care Plan Generator Backend...")
    print(f"📍 Server will be available at: http://{Config.HOST}:{Config.PORT}")
    print(f"📚 API Documentation: http://{Config.HOST}:{Config.PORT}/docs")
    print("=" * 50)
    
    uvicorn.run(
        "main:app",
        host=Config.HOST,
        port=Config.PORT,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    main()
