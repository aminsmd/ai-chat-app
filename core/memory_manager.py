from typing import List, Dict, Optional
import logging
import json
from models import Message, BotConfig, LongTermMemory, ConversationMemory
from utils.llm_cache import LLMCache
from core.database_manager import DatabaseManager

logger = logging.getLogger(__name__)

class MemoryManager:
    def __init__(self, config: BotConfig):
        self.config = config
        self.db_manager = DatabaseManager(config)
        self.conversations: Dict[str, ConversationMemory] = {}
        self.short_term_limit = 10  # Keep last 10 messages
        self.memory_threshold = 5   # Generate long-term memory every 5 messages
        self.llm_cache = LLMCache(cache_dir="cache/memory")
        
    def add_message(self, message: Message, user_profile_dict: Dict[str, str]) -> None:
        """Add a new message to memory"""
        channel = message.channel_name
        
        # Initialize conversation memory if needed
        if channel not in self.conversations:
            self.conversations[channel] = ConversationMemory(
                channel_name=channel,
                messages=[],
                long_term_memories=[],
                last_memory_ts=message.ts
            )
        
        conv_memory = self.conversations[channel]
        
        # Add message to short-term memory
        msg_dict = {
            "role": message.role,
            "content": message.content,
            "user_id": message.user_id,
            "ts": message.ts,
            "name": user_profile_dict.get(message.user_id, message.user_id)
        }
        conv_memory.messages.append(msg_dict)
        
        # Trim short-term memory if needed
        if len(conv_memory.messages) > self.short_term_limit:
            conv_memory.messages = conv_memory.messages[-self.short_term_limit:]
        
        # Generate long-term memory if threshold reached and we have messages
        if len(conv_memory.messages) >= self.memory_threshold:
            if self._generate_long_term_memory(conv_memory):
                conv_memory.messages = []  # Only clear if memory was generated successfully
    
    def get_context(self, channel: str) -> List[Dict]:
        """Get context combining short and long-term memory"""
        if channel not in self.conversations:
            return []
        
        context = []
        conv_memory = self.conversations[channel]
        
        # Add relevant long-term memories first
        if conv_memory.long_term_memories:
            latest_memory = conv_memory.long_term_memories[-1]
            context.append({
                "role": "system",
                "content": self._format_long_term_memory(latest_memory)
            })
        
        # Add recent messages
        for msg in conv_memory.messages:
            context.append({
                "role": "user" if msg["role"] == "user" else "assistant",
                "content": msg["content"],
                "name": msg["name"] if msg["role"] == "user" else None
            })
        
        return context
    
    def _generate_long_term_memory(self, conv_memory: ConversationMemory) -> Optional[int]:
        """Generate a long-term memory from the conversation memory"""
        if not conv_memory.messages:
            logger.warning("No messages to generate memory from")
            return None
        
        try:
            # Get timestamps from first and last messages
            first_msg = conv_memory.messages[0]
            last_msg = conv_memory.messages[-1]
            
            # Generate memory text
            memory_text = self._generate_memory_text(conv_memory.messages)
            if not memory_text:
                logger.error("Failed to generate memory text")
                return None
            
            # Create and return the memory
            memory = LongTermMemory(
                timestamp=last_msg['ts'],
                summary=memory_text.get('summary', ''),
                insights=memory_text.get('insights', []),
                key_points=memory_text.get('key_points', []),
                participants=list(set(msg['user_id'] for msg in conv_memory.messages))
            )
            
            # Save to database
            memory_id = self.db_manager.save_long_term_memory(
                memory, 
                conv_memory.channel_name,
                first_msg['ts'],
                last_msg['ts']
            )
            
            if memory_id:
                conv_memory.long_term_memories.append(memory)
                logger.info(f"Generated and saved long-term memory for channel {conv_memory.channel_name}")
            
            return memory_id
            
        except Exception as e:
            logger.error(f"Error generating long-term memory: {str(e)}", exc_info=True)
            return None
    
    def _format_long_term_memory(self, memory: LongTermMemory) -> str:
        """Format long-term memory for context"""
        return f"""Previous conversation summary:
{memory.summary}

Key insights:
{chr(10).join(f'- {insight}' for insight in memory.insights)}

Key points:
{chr(10).join(f'- {point}' for point in memory.key_points)}

Participants: {', '.join(memory.participants)}"""

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