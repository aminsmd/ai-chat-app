from typing import List, Dict, Optional
import logging
import json
import time
from models import Message, BotConfig, LongTermMemory, ConversationMemory
from utils.llm_cache import LLMCache
from core.database_manager import DatabaseManager
import sqlite3

logger = logging.getLogger(__name__)

class MemoryManager:
    def __init__(self, config: BotConfig):
        self.config = config
        self.db_manager = DatabaseManager(config)
        self.conversations = {}
        self.short_term_limit = 10  # Keep last 10 messages
        self.memory_threshold = 5   # Generate long-term memory every 5 messages
        self.llm_cache = LLMCache(cache_dir="cache/memory")
        
    def add_message(self, message: Message, user_profile_dict: Dict[str, str]) -> None:
        """Add a new message to memory"""
        channel = message.channel_name
        
        # Initialize conversation memory if needed
        if channel not in self.conversations:
            # Load previous messages from the database
            self.conversations[channel] = self._load_conversation(channel)
            logger.info(f"Initialized conversation for channel {channel} with {len(self.conversations[channel]['messages'])} messages")
        
        conv_memory = self.conversations[channel]
        
        # Add message to short-term memory
        msg_dict = {
            "role": message.role,
            "content": message.content,
            "user_id": message.user_id,
            "ts": message.ts,
            "name": user_profile_dict.get(message.user_id, message.user_id)
        }
        conv_memory["messages"].append(msg_dict)
        
        # Trim short-term memory if needed
        if len(conv_memory["messages"]) > self.short_term_limit:
            conv_memory["messages"] = conv_memory["messages"][-self.short_term_limit:]
        
        # Generate long-term memory if threshold reached and we have messages
        if len(conv_memory["messages"]) >= self.memory_threshold:
            if self._generate_long_term_memory(conv_memory):
                conv_memory["messages"] = []  # Only clear if memory was generated successfully
    
    def _load_conversation(self, channel_name: str) -> Dict:
        """Load conversation history from the database
        
        Args:
            channel_name (str): Channel/room name to load for
            
        Returns:
            Dict: Conversation memory with messages and long-term memories
        """
        # Initialize empty conversation memory
        conversation = {
            "messages": [],
            "long_term_memories": [],
            "last_memory_ts": time.time()
        }
        
        try:
            # Get recent messages from database (up to short_term_limit)
            options = {
                "channel_name": channel_name,
                "limit": self.short_term_limit
            }
            
            # Try to get messages from the history table first
            try:
                # Query the history table
                history_messages = self._get_messages_from_history_table(channel_name)
                if history_messages:
                    logger.info(f"Loaded {len(history_messages)} messages from history table for channel {channel_name}")
                    
                    # Convert messages to the required format and add to conversation
                    for msg in history_messages:
                        # Get username if available
                        user_name = self.db_manager.get_user_name(msg['user_id']) or msg['user_id']
                        
                        # Add to messages list
                        conversation["messages"].append({
                            "role": msg.get('role', 'user'),
                            "content": msg['content'],
                            "user_id": msg['user_id'],
                            "ts": msg['ts'],
                            "name": user_name
                        })
            except Exception as history_error:
                logger.error(f"Error loading from history table: {str(history_error)}")
            
            # If we didn't get any messages from history, try the messages table
            if not conversation["messages"]:
                messages = self.db_manager.get_history(options)
                
                # Convert messages to the required format
                for msg in messages:
                    # Get username if available
                    user_name = self.db_manager.get_user_name(msg['user_id']) or msg['user_id']
                    
                    # Add to messages list
                    conversation["messages"].append({
                        "role": msg.get('role', 'user'),
                        "content": msg['content'],
                        "user_id": msg['user_id'],
                        "ts": msg['ts'],
                        "name": user_name
                    })
                
                logger.info(f"Loaded {len(messages)} messages from messages table for channel {channel_name}")
            
            # Make sure most recent messages are last (as expected by get_context)
            conversation["messages"].reverse()
            
            logger.info(f"Total loaded: {len(conversation['messages'])} messages for channel {channel_name}")
        except Exception as e:
            logger.error(f"Error loading conversation for channel {channel_name}: {str(e)}")
        
        return conversation
    
    def _get_messages_from_history_table(self, channel_name: str) -> List[Dict]:
        """Query messages directly from the history table
        
        Args:
            channel_name (str): Channel/room name to query
            
        Returns:
            List[Dict]: Messages from the history table
        """
        messages = []
        try:
            db_path = self.db_manager._get_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT user_id, channel_name, content, ts, role 
                FROM history 
                WHERE channel_name = ? 
                ORDER BY ts DESC 
                LIMIT ?
            ''', (channel_name, self.short_term_limit))
            
            rows = cursor.fetchall()
            
            for row in rows:
                messages.append({
                    'user_id': row[0],
                    'channel_name': row[1],
                    'content': row[2],
                    'ts': row[3],
                    'role': row[4]
                })
            
            cursor.close()
            conn.close()
        except Exception as e:
            logger.error(f"Error querying history table: {str(e)}")
        
        return messages
    
    def get_context(self, channel: str) -> List[Dict]:
        """Get context combining short and long-term memory"""
        if channel not in self.conversations:
            # Initialize the conversation if it doesn't exist
            self.conversations[channel] = self._load_conversation(channel)
            logger.info(f"Late-initialized conversation for channel {channel}")
        
        context = []
        conv_memory = self.conversations[channel]
        
        # Add relevant long-term memories first
        if conv_memory["long_term_memories"]:
            latest_memory = conv_memory["long_term_memories"][-1]
            context.append({
                "role": "system",
                "content": self._format_long_term_memory(latest_memory)
            })
        
        # Add recent messages
        for msg in conv_memory["messages"]:
            context.append({
                "role": "user" if msg["role"] == "user" else "assistant",
                "content": msg["content"],
                "name": msg.get("name") if msg["role"] == "user" else None
            })
        
        return context
    
    def _generate_long_term_memory(self, conv_memory: Dict) -> Optional[int]:
        """Generate a long-term memory from the conversation memory"""
        if not conv_memory["messages"]:
            logger.warning("No messages to generate memory from")
            return None
        
        try:
            # TODO: Implement long-term memory generation logic
            # This would involve summarizing the messages, extracting key points, etc.
            return None  # For now, just return None
        except Exception as e:
            logger.error(f"Error generating long-term memory: {str(e)}")
            return None
    
    def _format_long_term_memory(self, memory: Dict) -> str:
        """Format a long-term memory for inclusion in context"""
        # This is a placeholder - actual implementation would format the memory nicely
        return f"Previous conversation summary: {memory.get('summary', 'No summary available')}"

    def _generate_memory_text(self, messages: List[Dict]) -> Optional[Dict]:
        """Generate structured memory text from messages"""
        try:
            # Convert messages to a readable format
            conversation_text = "\n".join([
                f"{msg['name']}: {msg['content']}" 
                for msg in messages
            ])
            
            # Generate structured memory using LLM
            response = self.llm_cache.generate_response(
                [
                    {
                        "role": "system", 
                        "content": """Analyze the conversation and create a structured summary with the following format:
{
    "summary": "Brief overview of the conversation",
    "insights": ["Key insight 1", "Key insight 2", ...],
    "key_points": ["Important point 1", "Important point 2", ...],
    "participants": ["participant1", "participant2", ...]
}"""
                    },
                    {"role": "user", "content": f"Here is the conversation:\n{conversation_text}"}
                ],
                cache_type="long_term_memory"
            )
            
            if not response:
                logger.error("Failed to generate memory from conversation")
                return None
            
            try:
                # Parse JSON response
                memory_dict = json.loads(response)
                return memory_dict
            except json.JSONDecodeError:
                logger.error("Failed to parse memory response as JSON")
                return None
            
        except Exception as e:
            logger.error(f"Error generating memory text: {str(e)}", exc_info=True)
            return None 