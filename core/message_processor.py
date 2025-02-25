import copy
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from openai import OpenAI

from models import Message, FileMetadata, BotConfig
from database_manager import DatabaseManager
from context_manager import ContextManager

class MessageProcessor:
    def __init__(self, config: BotConfig):
        self.config = config
        self.db_manager = DatabaseManager(config)
        self.context_manager = ContextManager()
        self.openai_client = OpenAI(api_key=config.openai_api_key)

    def prepare_message_context(self, message: Message, user_profile_dict: Dict[str, str]) -> Tuple[List[Dict], Dict]:
        """Process message and return context for response generation"""
        # Save message to queue
        self.db_manager.save_message(message)
        
        # Process files if any
        if message.files:
            self._process_files(message, user_profile_dict)
            return [], {}
        
        # Get and process message from queue
        new_msg = self.db_manager.get_message_from_queue(message.channel_name)
        if not new_msg:
            return [], {}

        # Save to history
        new_msg['type'] = 'memory'
        self.db_manager.save_to_history(new_msg)

        # Get context
        collection = self.db_manager.get_collection()
        try:
            listofmsg, last_imptce, avg_impce = self.context_manager.get_context(new_msg, collection)
        except Exception as e:
            # If there's an error getting context (e.g., first message), create empty context
            listofmsg = []
            last_imptce = 0
            avg_impce = 0

        # Add to ChromaDB
        clean_dict_ch = self._prepare_chroma_dict(new_msg, last_imptce, avg_impce)
        self.db_manager.add_to_chroma(clean_dict_ch)

        # Always return at least an empty context list
        context = []
        if listofmsg:
            context = self.context_manager.prepare_chat_context(listofmsg, user_profile_dict)
        
        return context, clean_dict_ch

    def save_response(self, response_content: str, message: Message, user_profile_dict: Dict[str, str]):
        """Save bot response to databases"""
        response_dict = {
            "user_id": "assistant",
            "role": "assistant",
            "content": response_content,
            "channel_name": message.channel_name,
            "ts": message.ts + 0.000001,
            "vector": "",
            "type": "memory"
        }
        
        # Save to history
        self.db_manager.save_to_history(response_dict)
        
        # Calculate importance and save to ChromaDB
        collection = self.db_manager.get_collection()
        sum_imp, avg_imp = self.context_manager.calculate_importance(
            response_content, 
            message.channel_name,
            collection
        )
        
        # Prepare ChromaDB dict - only include valid metadata types
        clean_dict = {
            "user_id": "assistant",
            "role": "assistant",
            "content": response_content,
            "channel_name": message.channel_name,
            "ts": message.ts + 0.000001,
            "sum_imptce": sum_imp,
            "importance": avg_imp,
            "type": "memory"
        }
        
        self.db_manager.add_to_chroma(clean_dict)
        
        # Handle reflection
        self.context_manager.handle_reflection(
            message, clean_dict, message.channel_name, 
            user_profile_dict, self.openai_client, collection
        )

    def _process_files(self, message: Message, user_profile_dict: Dict[str, str]):
        """Process and store file metadata"""
        for file in message.files:
            metadata = FileMetadata(
                file_id=file['id'],
                channel=message.channel_name,
                user_id=message.user_id,
                user_name=user_profile_dict[message.user_id],
                ts=message.ts,
                timestamp=str(datetime.fromtimestamp(float(message.ts))),
                title=file['name'],
                format=file['name'].split('.')[-1],
                role="user",
                path=None,
                content='',
                url=file['url_private']
            )
            self.db_manager.save_file_metadata(metadata)

    def _prepare_chroma_dict(self, msg_dict: Dict, last_imptce: float, avg_impce: float) -> Dict:
        """Prepare dictionary for ChromaDB"""
        clean_dict = copy.deepcopy(msg_dict)
        clean_dict.pop('table_name')
        clean_dict.pop('vector')
        clean_dict['sum_imptce'] = last_imptce
        clean_dict['importance'] = avg_impce
        return clean_dict