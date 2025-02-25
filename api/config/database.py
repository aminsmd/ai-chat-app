from pydantic import BaseModel
from typing import Optional

class DatabaseConfig(BaseModel):
    db_url: str = "sqlite:///./test.db"
    collection_name: str = "test_collection"
    username: Optional[str] = None
    password: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None

    @classmethod
    def from_env(cls):
        import os
        from dotenv import load_dotenv
        
        load_dotenv()
        
        return cls(
            db_url=os.getenv("DATABASE_URL", "sqlite:///./test.db"),
            collection_name=os.getenv("COLLECTION_NAME", "test_collection"),
            username=os.getenv("DB_USERNAME"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT")
        ) 