import logging
import time
from typing import Dict, Optional, Union
from models.models import Message
from models.web_config import WebBotConfig
from pipelines.pipeline_base import BasePipeline
from core.action_manager import ActionManager
from core.personality import Personality, default_personality, generate_random_persona
from core.response_generator import ResponseGenerator
from core.database_manager import DatabaseManager
from core.memory_manager import MemoryManager
from sample_info.tasks import desert_survival_task
import socket  # Add this import at the top

logger = logging.getLogger(__name__)

class WebPipeline(BasePipeline):
    def __init__(self, config: WebBotConfig, room_name: str = None, task: str = None):
        """Initialize the web pipeline with config and optional room name and task
        
        Args:
            config (WebBotConfig): Configuration for the web bot
            room_name (str, optional): Name of the chat room. Defaults to None.
            task (str, optional): Task description for the team. Defaults to desert_survival_task.
        """
        self.config = config
        self.room_name = room_name
        
        # Initialize database manager
        self.db_manager = DatabaseManager(config)
        
        # Try to load saved task for this room, or use provided/default task
        if room_name:
            saved_task = self.db_manager.load_task(room_name)
            self.task = task if task is not None else (saved_task if saved_task else desert_survival_task)
            # Save task if it's new or different
            if task and task != saved_task:
                self.db_manager.save_task(room_name, task)
        else:
            self.task = task if task is not None else desert_survival_task
        
        # Try to load saved personality for this room
        if room_name:
            saved_personality = self.db_manager.load_persona(room_name)
            if saved_personality:
                self.personality = saved_personality
            else:
                # Use random personality instead of default
                self.personality = generate_random_persona()
                # Save the random personality to database
                if self.db_manager:
                    self.db_manager.save_persona(room_name, self.personality)
        else:
            # Use random personality for new sessions
            self.personality = generate_random_persona()
        
        # Initialize other components
        self.memory_manager = MemoryManager(self.db_manager)
        self.action_manager = ActionManager(config, self.personality)
        self.response_generator = ResponseGenerator(config, self.personality, self.task)
        
        # Print local network IP address
        local_ip = self._get_local_ip()
        logger.info(f"App accessible on local network at: {local_ip}")
        print(f"App accessible on local network at: {local_ip}")
        
    def _create_message(self, message_data: Dict) -> Message:
        """Create a Message object from web message data"""
        return Message(
            user_id=message_data.get('user', 'web_user'),
            channel_name=self.room_name if self.room_name else message_data.get('room_id', 'web'),
            content=message_data['text'],
            ts=time.time(),
            role="user"
        )
    
    def process_message(self, message_data: Union[Dict, Message], user_profile_dict: Dict[str, str]) -> Optional[str]:
        """Process a message and return a response
        
        Args:
            message_data (Union[Dict, Message]): Either a dictionary with message data or a Message object
            user_profile_dict (Dict[str, str]): Dictionary with user profile information
            
        Returns:
            Optional[str]: Response text if generated, None otherwise
        """
        try:
            # Step 1-2: Extract metadata and create Message object if needed
            logger.info("Step 1-2: Extracting message metadata")
            if isinstance(message_data, Message):
                # If a Message object is provided, use it directly
                message = message_data
            else:
                # If a dictionary is provided, create a Message object
                message = self._create_message(message_data)
            
            # Set channel_name to room_name for consistency
            channel_name = self.room_name if self.room_name else message.channel_name
            logger.info(f"Using channel_name: {channel_name} (room_name: {self.room_name}, message channel: {message.channel_name})")
            
            # Update message channel name for consistency if needed
            if message.channel_name != channel_name:
                logger.info(f"Updating message channel from {message.channel_name} to {channel_name}")
                message.channel_name = channel_name
            
            # Step 3: Save message to database
            logger.info(f"Step 3: Saving message to database - Channel: {message.channel_name}, User: {message.user_id}")
            self.db_manager.save_message(message)
            
            # Step 4: Gathering context
            logger.info(f"Step 4: Gathering context for channel {channel_name}")
            self.memory_manager.add_message(message, user_profile_dict)
            context = self.memory_manager.get_context(channel_name)
            
            # Log context details
            logger.info(f"Context length: {len(context)} messages")
            for i, ctx_msg in enumerate(context):
                logger.info(f"Context message {i}: role={ctx_msg.get('role')}, content={ctx_msg.get('content')[:30]}...")
            
            # Step 5: Decide whether to respond
            logger.info("Step 5: Deciding whether to respond")
            should_respond = self.action_manager.should_respond(context, message)
            
            response = None
            if should_respond:
                # Step 6: Generate response
                logger.info("Step 6: Generating response")
                response = self.response_generator.generate_response(context, message)
                if response:
                    # Step 7: Saving response
                    logger.info("Step 7: Saving response")
                    self._save_response(response, message, user_profile_dict)
            
            # Save context history
            logger.info(f"Saving context history with {len(context)} messages")
            try:
                self.db_manager.save_context_history(
                    message=message,
                    context=context,
                    response=response,
                    response_type="responded" if response else "did not respond"
                )
                logger.info("Context history saved successfully")
            except Exception as ctx_err:
                logger.error(f"Error saving context history: {str(ctx_err)}")
            
            return response
            
        except Exception as e:
            logger.error(f"Error in message pipeline: {str(e)}", exc_info=True)
            return "I apologize, but I encountered an error while processing your message."
    
    def _save_response(self, response_content: str, message: Message, user_profile_dict: Dict[str, str]) -> None:
        """Save bot response to databases and memory"""
        try:
            # Create response message
            response_msg = Message(
                user_id="assistant",
                channel_name=message.channel_name,  # Use the same channel_name as the original message
                content=response_content,
                ts=time.time(),  # Use current time instead of message.ts + offset
                role="assistant"
            )
            
            logger.info(f"Saving assistant response to channel: {response_msg.channel_name}")
            
            # Save to database
            self.db_manager.save_message(response_msg)
            
            # Add to memory
            self.memory_manager.add_message(response_msg, user_profile_dict)
            
        except Exception as e:
            logger.error(f"Error saving response: {str(e)}", exc_info=True)

    def _get_local_ip(self):
        """Get the local network IP address of the machine."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except Exception as e:
            logger.error(f"Error obtaining local IP: {str(e)}", exc_info=True)
            return "Unable to determine local IP" 