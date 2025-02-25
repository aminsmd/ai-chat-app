from pydantic import BaseModel
from typing import Optional

class MemoryConfig(BaseModel):
    memory_size: int = 1000
    vector_dimension: int = 384
    index_path: Optional[str] = "./data/memory_index"
    
    @classmethod
    def from_env(cls):
        import os
        from dotenv import load_dotenv
        
        load_dotenv()
        
        return cls(
            memory_size=int(os.getenv("MEMORY_SIZE", "1000")),
            vector_dimension=int(os.getenv("VECTOR_DIMENSION", "384")),
            index_path=os.getenv("MEMORY_INDEX_PATH", "./data/memory_index")
        ) 