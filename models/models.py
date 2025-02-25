from dataclasses import dataclass, field
from typing import Optional, Dict, List
from datetime import datetime

@dataclass
class Message:
    user_id: str
    channel_name: str 
    content: str
    ts: float
    role: str = "user"
    importance: float = 0
    vector: str = ""
    raw_vec: List[float] = field(default_factory=list)
    files: Optional[List[Dict]] = None
    type: str = "memory"

@dataclass
class FileMetadata:
    file_id: str
    channel: str
    user_id: str
    user_name: str
    ts: float
    timestamp: str
    title: str
    format: Optional[str]
    role: str
    path: Optional[str]
    content: str
    url: str

@dataclass 
class BotConfig:
    slack_bot_token: str
    slack_app_token: str
    openai_api_key: str
    chroma_db_name: str
    sqlite_db_name: str
    table_metadata_file: str
    chatgpt_model: str
    
    @classmethod
    def from_env(cls, env_vars: Dict[str, str]):
        return cls(
            slack_bot_token=env_vars["SLACK_BOT_TOKEN"],
            slack_app_token=env_vars["SLACK_APP_TOKEN"], 
            openai_api_key=env_vars["OPENAI_API_KEY"],
            chroma_db_name=env_vars["chDB_Name"],
            sqlite_db_name=env_vars["sqDB_NAME"],
            table_metadata_file=env_vars["table_metadata_file"],
            chatgpt_model=env_vars["chatGPT_API_model"]
        ) 