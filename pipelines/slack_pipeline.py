import logging
from typing import Dict, Optional
from models.base import Message, BotConfig
from pipeline_base import BasePipeline
from action_manager import ActionManager
from personality import Personality, default_personality

logger = logging.getLogger(__name__)

class SlackPipeline(BasePipeline):
    def __init__(self, config: BotConfig, personality: Optional[Personality] = None):
        super().__init__(config)
        self.personality = personality or default_personality
        self.action_manager = ActionManager(config, self.personality)
    
    def _create_message(self, slack_event: Dict) -> Optional[Message]:
        """Create a Message object from Slack event data"""
        try:
            return Message(
                user_id=slack_event['user'],
                channel_name=slack_event['channel'],
                content=slack_event.get('text', ''),
                ts=float(slack_event.get('event_ts', slack_event.get('ts', 0))),
                files=slack_event.get('files', None),
                vector='',
                raw_vec=[]
            )
        except KeyError as e:
            logger.error(f"Missing required field in slack event: {e}")
            return None
    
    def process_message(self, slack_event: Dict, user_profile_dict: Dict[str, str]) -> Optional[str]:
        """Process a Slack message through the pipeline"""
        try:
            # Step 1-2: Extract metadata and create Message object
            logger.info("Step 1-2: Extracting message metadata")
            message = self._create_message(slack_event)
            if not message:
                return None

            # Step 3: Save message to database
            logger.info("Step 3: Saving message to database")
            self.db_manager.save_message(message)

            # Step 4: Gather context
            logger.info("Step 4: Gathering context")
            self.memory_manager.add_message(message, user_profile_dict)
            context = self.memory_manager.get_context(message.channel_name)

            # Step 5: Decide whether to respond
            logger.info("Step 5: Deciding whether to respond")
            should_respond = self.action_manager.should_respond(context, message)

            response = None
            if should_respond:
                # Step 6: Generate response
                logger.info("Step 6: Generating response")
                response = self._generate_response(context, message)
                if response:
                    # Step 7: Save response
                    logger.info("Step 7: Saving response")
                    self._save_response(response, message, user_profile_dict)

            return response

        except Exception as e:
            logger.error(f"Error in message pipeline: {str(e)}", exc_info=True)
            return "I apologize, but I encountered an error while processing your message." 