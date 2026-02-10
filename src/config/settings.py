import json
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List


class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str

    # JWT
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    # Groq
    groq_api_key: str
    groq_primary_model: str = "llama-3.1-8b-instant"
    groq_fallback_model: str = "gemma2-9b-it"

    # Rate Limits
    rate_limit_standard_rpm: int = 60
    rate_limit_ai_rpm: int = 10

    # CORS
    cors_origins: str = '["http://localhost:3000","http://localhost:5173"]'

    # App
    app_env: str = "development"
    app_debug: bool = False

    @property
    def cors_origin_list(self) -> List[str]:
        try:
            return json.loads(self.cors_origins)
        except (json.JSONDecodeError, TypeError):
            return ["http://localhost:3000"]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


settings = Settings()
