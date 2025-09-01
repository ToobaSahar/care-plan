import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")  # Service role key to bypass RLS
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENROUTER_API_KEY = "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"
    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8000))
