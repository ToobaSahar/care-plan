#!/usr/bin/env python3
"""
Setup script for the Care Plan Generator Backend
"""

import os
import sys
import subprocess
from pathlib import Path

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        return False
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    return True

def install_dependencies():
    """Install required dependencies"""
    print("📦 Installing dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False

def check_env_file():
    """Check if .env file exists and has required variables"""
    env_file = Path(".env")
    if not env_file.exists():
        print("⚠️  .env file not found")
        print("📝 Creating .env template...")
        
        env_template = """# Supabase Configuration
SUPABASE_URL=your_supabase_url_here
SUPABASE_KEY=your_supabase_anon_key_here

# OpenAI Configuration (optional)
OPENAI_API_KEY=your_openai_api_key_here

# OpenRouter Configuration (for DeepSeek R1)
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# Server Configuration
HOST=0.0.0.0
PORT=8000
"""
        
        with open(env_file, "w") as f:
            f.write(env_template)
        
        print("✅ .env template created")
        print("⚠️  Please update the .env file with your actual credentials")
        return False
    
    print("✅ .env file found")
    return True

def test_imports():
    """Test if all required modules can be imported"""
    print("🧪 Testing imports...")
    try:
        import fastapi
        import uvicorn
        import crewai
        import supabase
        import dotenv
        import pydantic
        import langchain
        import langchain_openai
        print("✅ All imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def main():
    """Main setup function"""
    print("🚀 Care Plan Generator Backend Setup")
    print("=" * 50)
    
    # Check Python version
    if not check_python_version():
        return False
    
    # Install dependencies
    if not install_dependencies():
        return False
    
    # Check environment file
    check_env_file()
    
    # Test imports
    if not test_imports():
        return False
    
    print("\n" + "=" * 50)
    print("✅ Setup completed successfully!")
    print("\n📋 Next steps:")
    print("1. Update the .env file with your credentials")
    print("2. Run: python start.py")
    print("3. Visit: http://localhost:8000/docs")
    print("\n🔧 For testing:")
    print("   python test_api.py")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
