import logging
import os
from datetime import datetime
from pathlib import Path
import csv
from langchain_chroma import Chroma
from langchain.embeddings.openai import OpenAIEmbeddings
from typing import Optional

logger = logging.getLogger(__name__)

def save_conversation_history(database_path: str, channel_name: str = None, 
                              start_ts: float = None, end_ts: float = None,
                              session_id: str = None) -> Optional[str]:
    """
    Extract and save conversation history from ChromaDB to CSV.
    """
    try:
        # Initialize OpenAI embeddings
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set.")
        
        embeddings = OpenAIEmbeddings(api_key=api_key)

        # Initialize ChromaDB
        if not os.path.exists(database_path):
            logger.warning(f"Database directory '{database_path}' does not exist.")
            return None
        
        vectorstore = Chroma(persist_directory=database_path, embedding_function=embeddings)

        # Build filters
        where = {}
        if channel_name:
            where["channel_name"] = channel_name
        if session_id:
            where["session_id"] = session_id

        results = vectorstore._collection.get(where=where, include=["documents", "metadatas"])

        if not results or not results['ids']:
            logger.warning("No messages found matching the given criteria.")
            return None

        # Filter and sort results
        conversation_data = []
        for i in range(len(results['ids'])):
            metadata = results['metadatas'][i]
            ts = float(metadata['ts'])
            if start_ts and end_ts and not (start_ts <= ts <= end_ts):
                continue
            conversation_data.append({
                "timestamp": datetime.fromtimestamp(ts).isoformat(),
                "channel": metadata.get("channel_name"),
                "user_id": metadata.get("user_id"),
                "role": metadata.get("role"),
                "message": results['documents'][i]
            })

        if not conversation_data:
            logger.warning("No messages found in the specified time range.")
            return None
        
        # Save to CSV
        conversations_dir = Path("conversations")
        conversations_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = conversations_dir / f"conversation_history_{timestamp}.csv"

        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=["timestamp", "channel", "user_id", "role", "message"])
            writer.writeheader()
            writer.writerows(conversation_data)

        logger.info(f"Saved {len(conversation_data)} messages to {filename}")
        return str(filename.absolute())

    except Exception as e:
        logger.error(f"Error saving conversation history: {e}")
        return None