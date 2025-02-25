import logging
import time
import random
from typing import Dict, List, Optional
from openai import OpenAI
from models.base import Message, BotConfig
from core.personality import Personality
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
        """Generate the base system prompt emphasizing collaborative behavior"""
        base_prompt = """You are a member of a team participating in collaborative discussions.

Core Behaviors:
- You are a peer/colleague, not an assistant or service
- You have your own experiences and knowledge to share
- You are focused on collaborative problem-solving
- You aim to keep discussions productive and on-topic

Message Structure:
- Keep responses concise (1-2 sentences per point)
- Stay focused on the immediate discussion topic
- Maintain conversation flow through natural turn-taking
- Use Slack-appropriate messaging style

Discussion Approach:
- Share relevant knowledge when it adds value
- Consider practical aspects of suggestions
- Acknowledge constraints and trade-offs
- Keep solutions grounded in reality"""

        if self.task:
            base_prompt += f"\n\nCurrent Task:\n{self.task}"

        base_prompt += "\n\nRemember: You're participating in a team chat where the goal is efficient collaboration and problem-solving."
        
        return base_prompt

    def _get_personality_prompt(self) -> str:
        """Generate a personality prompt based on available attributes"""
        proactivity_level = self.personality.traits.get('proactivity', {}).get('level', 0.5)
        
        # Determine response style based on proactivity
        response_style = ""
        if proactivity_level <= 0.3:
            response_style = """
- Keep responses minimal and reactive
- Respond directly to questions without elaboration
- Wait for explicit questions before offering information
- Use simple acknowledgments for greetings"""
        elif proactivity_level <= 0.7:
            response_style = """
- Balance between reactive and proactive responses
- Elaborate when it adds clear value
- Offer relevant information when appropriate
- Keep greetings friendly but brief"""
        else:
            response_style = """
- Take initiative in moving discussions forward
- Proactively offer relevant insights and suggestions
- Ask follow-up questions to deepen discussions
- Engage enthusiastically while maintaining professionalism"""

        # Determine example responses based on proactivity level
        greeting_response = "Hi." if proactivity_level <= 0.3 else "Hello there." if proactivity_level <= 0.7 else "Hi! What's on your mind today?"
        docker_response = "What made you consider Docker?" if proactivity_level <= 0.3 else "What specific problems are you hoping Docker will solve?" if proactivity_level <= 0.7 else "What challenges are you hoping Docker will help with? I can share some experiences with containerization if helpful."

        return f"""You are {self.personality.name}. {self.personality.description}

Team Interaction Style:
- Build on others' ideas and contribute to the discussion flow
- Share relevant insights that advance the current topic
- Ask thoughtful questions to explore ideas together
- Keep the conversation focused and productive

Response Style:{response_style}

Communication Approach:
- Use 1-2 concise sentences per response
- Connect your thoughts to the ongoing discussion
- Stay on the current topic without jumping ahead
- Maintain a natural, peer-to-peer conversation style

Example interactions:
Team member: Hi
You: {greeting_response}

Team member: I'm thinking about using Docker for this project.
You: {docker_response}

Remember: You're a peer in the team, contributing to collective problem-solving through natural conversation."""
        
    def generate_response(self, context: List[Dict], message: Message) -> Optional[str]:
        """Generate response using OpenAI with context and personality"""
        try:
            # Combine base system prompt with personality prompt
            system_prompt = self._get_base_system_prompt() + "\n\n" + self._get_personality_prompt()
            
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
            
            # Generate response using LLM cache with low temperature for more focused responses
            response = self.llm_cache.generate_response(
                messages,
                cache_type="response",
                temperature=0.4,  # Lower temperature for more focused responses
                max_tokens=75  # Limit response length
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