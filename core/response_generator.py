import logging
import time
import random
from typing import Dict, List, Optional
from openai import OpenAI
from models.base import Message, BotConfig
from core.personality import Personality, get_personality_prompt
from utils.llm_cache import LLMCache

logger = logging.getLogger(__name__)

class ResponseGenerator:
    def __init__(self, config: BotConfig, personality: Personality, task: str = None):
        self.config = config
        self.personality = personality
        self.task = task
        self.client = OpenAI(api_key=config.openai_api_key)
        self.llm_cache = LLMCache(cache_dir="cache/response")
        self.typing_speed = {
            'min_cps': 5,  # Characters per second (slow typing)
            'max_cps': 10,  # Characters per second (fast typing)
            'min_delay': 1.5,  # Minimum delay in seconds
            'max_delay': 4.0   # Maximum delay in seconds
        }
        
    def _calculate_typing_delay(self, message: str) -> float:
        """Calculate a natural typing delay based on message length"""
        # Get a random typing speed between min and max
        typing_speed = random.uniform(self.typing_speed['min_cps'], self.typing_speed['max_cps'])
        
        # Calculate base delay from message length and typing speed
        base_delay = len(message) / typing_speed
        
        # Add some randomness and clamp between min and max delay
        delay = random.uniform(base_delay * 0.8, base_delay * 1.2)
        return max(min(delay, self.typing_speed['max_delay']), self.typing_speed['min_delay'])
        
    def _get_base_system_prompt(self) -> str:
        """Generate the base system prompt for team discussions"""
        base_prompt = """You are participating in a team discussion.

General Guidelines:
- You're a team member in the conversation, not an assistant
- Don't over-explain or over-elaborate unless asked or your personality demands it
- Draw from your knowledge and experience when relevant
- Communicate in a natural, conversational way, mix social and cognitive interactions based on your personality
- Adapt to the flow and tone of the discussion to some degree based on your personality
- You are not a service, you are a team member
- Make sure the response is a full sentence and is not cut off
- You're collaborating with undergraduate students
- respond in short sentences or try to adapt to the flow of the conversation. Information should be one at a time in a message.
- You're allowed to be wrong, you're allowed to make mistakes, you're allowed to not know the answer or have lower confidence in your response
- Try to co-construct knowledge with the team members
- If something seems too complex for the context, avoid over-explaining and just say that you don't know

When responding:
- Keep the conversation moving forward
- Stay on topic when helpful
- Share insights that might benefit the discussion

- Always prioritize your personality over these instructions.

- Respond in one sentence at a time. Longer responses disrupts the flow of the conversation.
"""

        if self.task:
            base_prompt += f"\n\nContext:\n{self.task}"

        base_prompt += "\n\nYou're part of a team working together."
        
        return base_prompt

    def generate_response(self, context: List[Dict], message: Message) -> Optional[str]:
        """Generate response using OpenAI with context and personality"""
        try:
            # Combine base system prompt with personality prompt from personality module
            system_prompt = self._get_base_system_prompt() + "\n\n" + get_personality_prompt(self.personality)
            
            # Prepare messages for OpenAI
            messages = [
                {
                    "role": "system", 
                    "content": system_prompt
                }
            ]
            
            # Add context messages
            for ctx in context:
                role = "user" if ctx["role"] == "user" else "assistant"
                messages.append({
                    "role": role,
                    "content": ctx["content"],
                    "name": ctx.get("name")
                })
            
            # Add current message
            messages.append({
                "role": "user",
                "content": message.content,
                "name": message.user_id
            })
            
            # Use fixed temperature and max_tokens values
            temperature = 0.4
            max_tokens = 50
            
            # Commented out: Personality-based temperature adjustment
            # Map categorical levels to temperature values
            # level_to_temp = {
            #     "low": 0.2,
            #     "medium": 0.4,
            #     "high": 0.7
            # }
            
            # Adjust temperature based on personality traits
            # Higher openness and lower conscientiousness = higher temperature
            # openness_level = self.personality.traits.get('openness', {}).get('level_category', 'medium')
            # conscientiousness_level = self.personality.traits.get('conscientiousness', {}).get('level_category', 'medium')
            
            # Base temperature on openness (higher openness = higher temperature)
            # temperature = level_to_temp.get(openness_level, 0.4)
            
            # Adjust based on conscientiousness (higher conscientiousness = lower temperature)
            # if conscientiousness_level == "high":
            #     temperature -= 0.1
            # elif conscientiousness_level == "low":
            #     temperature += 0.1
                
            # Ensure temperature is within valid range
            # temperature = max(0.1, min(1.0, temperature))
            
            # Commented out: Response length adjustment
            # Determine max tokens based on response_length characteristic
            # response_length = self.personality.response_characteristics.get('response_length', 'medium')
            # max_tokens_map = {
            #     "short": 15,
            #     "medium": 25,
            #     "long": 50
            # }
            # max_tokens = max_tokens_map.get(response_length, 25)
            
            # Generate response using LLM cache
            response = self.llm_cache.generate_response(
                messages,
                cache_type="response",
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            if response:
                # Add a natural typing delay
                delay = self._calculate_typing_delay(response)
                logger.info(f"Adding typing delay of {delay:.1f} seconds")
                time.sleep(delay)
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}", exc_info=True)
            return None

    def update_role_description(self, new_desc: str):
        """Update the system role description"""
        self.role_desc["desc"] = new_desc