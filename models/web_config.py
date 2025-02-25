from dataclasses import dataclass
from typing import Dict, Optional
import os
from pathlib import Path

@dataclass
class WebBotConfig:
    openai_api_key: str
    openai_model: str = "gpt-4"
    sqlite_db_name: str = "chat_history.db"
    
    @classmethod
    def from_env(cls, env_dict):
        """Create config from environment variables"""
        return cls(
            openai_api_key=env_dict.get('OPENAI_API_KEY', ''),
            openai_model=env_dict.get('OPEN_AI_MODEL', 'gpt-4'),
            sqlite_db_name=env_dict.get('SQLITE_DB_NAME', 'chat_history.db')
        )

    def __post_init__(self):
        # Create data directory if it doesn't exist
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
            
        return self 