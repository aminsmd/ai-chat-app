import os
import json
from typing import List, Dict, Optional
import hashlib
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_community.cache import SQLiteCache
from langchain.globals import set_llm_cache
import sqlite3
from datetime import datetime
import logging
from langchain.schema import HumanMessage, SystemMessage, AIMessage

logger = logging.getLogger(__name__)

class LLMCache:
    def __init__(self, cache_dir: str = "cache"):
        """Initialize LLM cache"""
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize LangChain cache
        cache_path = self.cache_dir / "langchain.db"
        set_llm_cache(SQLiteCache(database_path=str(cache_path)))
        
        # Initialize ChatOpenAI
        self.chat = ChatOpenAI(
            model_name="gpt-4",
            temperature=0.7,
            cache=SQLiteCache(database_path=str(self.cache_dir / "sqlite_cache.db"))
        )
    
    def _get_cache_key(self, messages: List[Dict]) -> str:
        """Generate a cache key from messages"""
        message_str = json.dumps(messages, sort_keys=True)
        return hashlib.md5(message_str.encode()).hexdigest()[:8]
    
    def get_cached_response(self, messages: List[Dict], cache_type: str = "response") -> Optional[str]:
        """Get cached response if available"""
        cache_key = self._get_cache_key(messages)
        cache_file = self.cache_dir / f"{cache_type}_{cache_key}.json"
        
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
                logger.info(f"Cache hit for key: {cache_key}...")
                return cache_data['response']
            except Exception as e:
                logger.error(f"Error reading cache: {str(e)}")
                return None
        return None
    
    def cache_response(self, messages: List[Dict], response: str, cache_type: str = "response") -> None:
        """Cache a response"""
        cache_key = self._get_cache_key(messages)
        cache_file = self.cache_dir / f"{cache_type}_{cache_key}.json"
        
        try:
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'messages': messages,
                'response': response,
                'cache_type': cache_type
            }
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
            logger.info(f"Cached response for key: {cache_key}...")
        except Exception as e:
            logger.error(f"Error caching response: {str(e)}")
    
    def generate_response(self, messages: List[Dict], cache_type: str = "default", temperature: float = 0.7, max_tokens: int = None) -> Optional[str]:
        """Generate a response using the LLM with caching"""
        try:
            # Generate cache key
            cache_key = self._get_cache_key(messages)
            cache_file = self.cache_dir / f"{cache_type}_{cache_key}.json"
            
            # Check cache
            if cache_file.exists():
                logger.info(f"Cache hit for key: {cache_key}...")
                with open(cache_file, 'r') as f:
                    return json.load(f)['response']
            
            # Convert to LangChain messages format
            langchain_messages = [
                {"role": msg["role"], "content": msg["content"]} 
                for msg in messages
            ]
            
            # Create chat model with specified parameters
            chat = ChatOpenAI(
                model_name="gpt-4",
                temperature=temperature,
                max_completion_tokens=max_tokens,
                cache=SQLiteCache(database_path=str(self.cache_dir / "sqlite_cache.db"))
            )
            
            # Generate response
            response = chat.invoke(langchain_messages).content
            
            # Cache response
            with open(cache_file, 'w') as f:
                json.dump({
                    'messages': messages,
                    'response': response,
                    'parameters': {
                        'temperature': temperature,
                        'max_tokens': max_tokens
                    }
                }, f)
            logger.info(f"Cached response for key: {cache_key}...")
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}", exc_info=True)
            return None 