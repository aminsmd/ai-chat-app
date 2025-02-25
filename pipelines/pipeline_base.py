from typing import Dict, Optional, List
import logging
from openai import OpenAI
from models.base import Message, BotConfig
from core.database_manager import DatabaseManager
from core.memory_manager import MemoryManager
from utils.llm_cache import LLMCache
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class BasePipeline(ABC):
    def __init__(self, config: BotConfig):
        self.config = config
        self.client = OpenAI(api_key=config.openai_api_key)
        self.llm_cache = LLMCache(cache_dir="cache")
        
        # Initialize managers
        self.db_manager = DatabaseManager(config)
        self.memory_manager = MemoryManager(config)
    
    @abstractmethod
    def _create_message(self, message_data: Dict) -> Message:
        """Create a Message object from raw message data"""
        pass
    
    @abstractmethod
    def process_message(self, message_data: Dict, user_profile_dict: Dict[str, str]) -> Optional[str]:
        """Process a message and return a response"""
        pass
    
    def _generate_response(self, context: List[Dict], message: Message) -> Optional[str]:
        """Generate response using OpenAI with context"""
        try:
            # Prepare messages for OpenAI
            messages = [
                {"role": "system", "content": "You are a helpful AI teammate. Be concise and professional in your responses. Use the following conversation history for context."}
            ]
            
            # Add context messages
            for ctx in context:
                messages.append({
                    "role": ctx["role"],
                    "content": ctx["content"]
                })
            
            # Add current message
            messages.append({
                "role": "user",
                "content": message.content
            })
            
            # Generate response using OpenAI
            response = self.client.chat.completions.create(
                model=self.config.chatgpt_model,
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}", exc_info=True)
            return None
    
    def _save_response(self, response_content: str, message: Message, user_profile_dict: Dict[str, str]) -> None:
        """Save bot response to databases and memory"""
        try:
            # Create response message
            response_msg = Message(
                user_id="assistant",
                channel_name=message.channel_name,
                content=response_content,
                ts=message.ts + 0.000001,
                role="assistant"
            )
            
            # Save to database
            self.db_manager.save_message(response_msg)
            
            # Add to memory
            self.memory_manager.add_message(response_msg, user_profile_dict)
            
            # Save context history
            context = self.memory_manager.get_context(message.channel_name)
            self.db_manager.save_context_history(
                message=message,
                context=context,
                response=response_content,
                response_type="responded"
            )
            
        except Exception as e:
            logger.error(f"Error saving response: {str(e)}", exc_info=True) 