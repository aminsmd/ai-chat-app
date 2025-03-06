from typing import Dict, List, Optional
import logging
from models import Message, BotConfig, Personality
from utils.llm_cache import LLMCache

logger = logging.getLogger(__name__)

class ActionManager:
    def __init__(self, config: BotConfig, personality: Optional[Personality] = None):
        self.config = config
        self.llm_cache = LLMCache(cache_dir="cache/decisions")
        self.personality = personality
        
    def should_respond(self, context: List[Dict], message: Message) -> bool:
        """Use LLM to decide whether to respond based on context and personality"""
        try:
            conversation = self._format_conversation(context)
            
            # Add personality-specific prompt modifiers
            personality_prompt = ""
            if self.personality:
                personality_prompt = self.personality.get_prompt_modifiers() + "\n\n"
            
            messages = [
                {"role": "system", "content": personality_prompt + self.ACTION_PROMPT},
                {"role": "user", "content": f"Current conversation:\n{conversation}\n\nLatest message: {message.content}"}
            ]
            
            decision = self.llm_cache.generate_response(messages).strip().lower()
            should_respond = decision.startswith('respond:')
            
            if should_respond:
                reason = decision[8:].strip()  # Extract reason after "respond:"
                logger.info(f"Decided to respond because: {reason}")
            else:
                reason = decision[12:].strip()  # Extract reason after "don't respond:"
                logger.info(f"Decided not to respond because: {reason}")
            
            return should_respond
            
        except Exception as e:
            logger.error(f"Error in should_respond: {str(e)}", exc_info=True)
            return True  # Default to responding if there's an error
    
    def _format_conversation(self, context: List[Dict]) -> str:
        """Format conversation context for the prompt"""
        formatted = []
        for msg in context:
            if msg["role"] == "system":
                formatted.append(f"Context: {msg['content']}")
            else:
                name = msg.get("name", "AI Teammate" if msg["role"] == "assistant" else "User")
                formatted.append(f"{name}: {msg['content']}")
        return "\n".join(formatted)

    ACTION_PROMPT = """You are the decision-making system for an AI teammate participating in a team conversation. Your role is to help the AI engage naturally in discussions, just as any other team member would.

Consider these factors when deciding whether to contribute:
1. Natural conversation flow
   - Would a team member naturally join in at this point?
   - Is there an organic opening in the discussion?
   
2. Team dynamics
   - Are teammates seeking different perspectives?
   - Is this a moment for active participation or listening?
   - Would contributing strengthen team connections?

3. Value of input
   - Do you have relevant experience or insights to share?
   - Would your perspective help advance the discussion?
   - Could you help clarify or synthesize the current points?

4. Discussion rhythm
   - Is the conversation flowing smoothly between teammates?
   - Would joining in enhance or interrupt the current dynamic?
   - Has the discussion moved to a new topic?

Respond with either:
"Respond: [reason]" if joining the discussion would be natural, or
"Don't respond: [reason]" if it's better to continue listening.

Examples:
- If team is brainstorming → "Respond: Can contribute relevant ideas to the team's brainstorming"
- If two teammates are catching up → "Don't respond: Personal conversation between teammates"
- If someone asks for thoughts → "Respond: Team member seeking different perspectives"
- If someone shares success → "Respond: Natural moment to share in teammate's achievement"
- If it's rhetorical → "Don't respond: Comment wasn't meant to start discussion"

Remember:
- You're an equal member of the team
- Participate naturally in discussions
- Build genuine team connections
- Read social cues and respect boundaries
- Balance speaking and listening
- Let conversations flow organically
- Be strict about participating in the conversation, especially if you're in a team of multiple people (more that 1)
""" 