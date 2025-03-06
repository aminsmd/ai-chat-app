from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from models.models import Message
from flask_socketio import SocketIO, emit, join_room, leave_room
from pipelines.web_pipeline import WebPipeline
from models.web_config import WebBotConfig
from core.personality import (
    load_personality_from_json, 
    default_personality, 
    personality_to_behavior, 
    generate_name_and_summary
)
from core.database_manager import DatabaseManager
import os
from dotenv import load_dotenv
from pathlib import Path
import logging
import shutil
import json
import time
import uuid
import socket

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask and Socket.IO
app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = 3600
socketio = SocketIO(app, cors_allowed_origins="*", always_connect=True)

# Add these headers to all responses
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# Store active rooms and users
active_rooms = {}  # {room_id: {'name': str, 'pipeline': WebPipeline, 'participants': set(), 'messages': list}}
active_users = {}  # {user_id: {'name': str, 'room_id': str}}

# Ensure required directories exist
current_dir = Path(__file__).parent
config_dir = current_dir / 'config'
data_dir = current_dir / 'data'
cache_dir = current_dir / 'cache'
config_dir.mkdir(exist_ok=True)
data_dir.mkdir(exist_ok=True)
cache_dir.mkdir(exist_ok=True)

# Copy default personas.json if it doesn't exist
personas_file = config_dir / 'personas.json'
if not personas_file.exists():
    default_personas = current_dir / 'config/personas.json'
    if default_personas.exists():
        shutil.copy2(default_personas, personas_file)
    else:
        logger.warning("Default personas.json not found. Creating a basic version.")
        default_persona = {
            "personas": {
                "default": {
                    "name": "AI Teammate",
                    "description": "A helpful and professional AI teammate",
                    "traits": {
                        "emotional_stability": {"level": 0.8, "description": "Maintains composure and professionalism"},
                        "extraversion": {"level": 0.6, "description": "Friendly but focused on the task"},
                        "openness": {"level": 0.7, "description": "Open to new ideas and approaches"},
                        "agreeableness": {"level": 0.7, "description": "Cooperative and supportive"},
                        "conscientiousness": {"level": 0.9, "description": "Thorough and reliable"}
                    },
                    "communication_style": {
                        "formality": 0.7,
                        "directness": 0.8,
                        "enthusiasm": 0.6,
                        "respect": 0.9,
                        "humor": 0.3
                    },
                    "response_characteristics": {
                        "response_length": "medium",
                        "technical_level": "adaptive",
                        "empathy_level": "moderate",
                        "creativity_level": "balanced"
                    }
                }
            }
        }
        with open(personas_file, 'w') as f:
            json.dump(default_persona, f, indent=2)

# Load environment variables from Bolt/.env
env_path = current_dir / '.env'
load_dotenv(dotenv_path=env_path)
logger.info(f"Loading .env from: {env_path}")

def create_pipeline():
    """Create a new pipeline instance"""
    try:
        config = WebBotConfig.from_env(os.environ)
        if not config.openai_api_key:
            raise ValueError("OpenAI API key is not set")
        
        # Create pipeline without room name initially
        pipeline = WebPipeline(config)
        logger.info("Successfully initialized pipeline")
        return pipeline
    except Exception as e:
        logger.error(f"Error initializing pipeline: {str(e)}")
        return None

def create_room_dict(room_name, pipeline):
    """Create a new room dictionary with all required fields"""
    # Update pipeline with room name
    pipeline.room_name = room_name
    
    # Save initial personality to database
    if pipeline and pipeline.db_manager:
        pipeline.db_manager.save_persona(room_name, pipeline.personality)
    
    return {
        'name': room_name,
        'pipeline': pipeline,
        'participants': set(),
        'messages': []  # Store message history: [{'user': str, 'text': str}]
    }

@app.route('/')
def index():
    return render_template('index.html', rooms=active_rooms)

@app.route('/create_room', methods=['POST'])
def create_room():
    room_name = request.form.get('room_name')
    user_name = request.form.get('name')
    
    if not room_name or not user_name:
        return redirect(url_for('index'))
    
    # Create new room
    room_id = str(uuid.uuid4())
    pipeline = create_pipeline()
    
    if not pipeline:
        return "Failed to create room: AI assistant not properly configured", 500
    
    active_rooms[room_id] = create_room_dict(room_name, pipeline)
    room = active_rooms[room_id]
    
    # Create user and add to room
    user_id = f"web_user_{int(time.time())}"
    session['user_id'] = user_id
    session['name'] = user_name
    session['room_id'] = room_id
    
    # Save user to database
    if pipeline and pipeline.db_manager:
        pipeline.db_manager.save_user(user_id, user_name, time.time(), room_id)
    
    active_users[user_id] = {
        'name': user_name,
        'room_id': room_id
    }
    room['participants'].add(user_id)
    
    # Add system message about room creation
    room['messages'].append({
        'user': 'System',
        'text': f"Room '{room_name}' created"
    })
    
    return redirect(url_for('chat'))

@app.route('/join', methods=['POST'])
def join():
    if request.method == 'POST':
        user_name = request.form.get('name')
        room_id = request.form.get('room_id')
        
        if not user_name or not room_id:
            flash('Please enter your name and room ID')
            return redirect(url_for('index'))
        
        if room_id not in active_rooms:
            flash('Room not found')
            return redirect(url_for('index'))
        
        user_id = f"web_user_{int(time.time())}"
        session['user_id'] = user_id
        session['name'] = user_name
        session['room_id'] = room_id
        
        # Save user to database
        room = active_rooms[room_id]
        if room['pipeline'] and room['pipeline'].db_manager:
            room['pipeline'].db_manager.save_user(user_id, user_name, time.time(), room_id)
        
        active_users[user_id] = {
            'name': user_name,
            'room_id': room_id
        }
        room['participants'].add(user_id)
        
        # Broadcast participant update to all users in the room
        participant_names = []
        for uid in room['participants']:
            if uid in active_users:
                participant_names.append(active_users[uid]['name'])
            else:
                # Handle missing users by removing them from participants
                room['participants'].remove(uid)
        
        socketio.emit('update_participants', {
            'participants': participant_names
        }, room=room_id)
        
        return redirect(url_for('chat'))

@app.route('/chat')
def chat():
    if 'user_id' not in session or 'room_id' not in session:
        return redirect(url_for('index'))
    
    room_id = session['room_id']
    if room_id not in active_rooms:
        return redirect(url_for('index'))
    
    room = active_rooms[room_id]
    personality = room['pipeline'].personality
    task = room['pipeline'].task
    
    # Get behavior map for the personality using personality_to_behavior
    behavior_map = personality_to_behavior(personality.traits)
    
    # Ensure user is in the room's participants
    user_id = session['user_id']
    if user_id not in room['participants']:
        room['participants'].add(user_id)
    
    # Get current participants' names
    participant_names = []
    for uid in room['participants']:
        if uid in active_users:
            participant_names.append(active_users[uid]['name'])
        else:
            # Handle missing users by removing them from participants
            room['participants'].remove(uid)
    
    # Clean up any disconnected participants
    connected_participants = set()
    for uid in room['participants']:
        if uid in active_users and active_users[uid]['room_id'] == room_id:
            connected_participants.add(uid)
    room['participants'] = connected_participants
    
    # Generate share URL
    share_url = request.url_root + 'join/' + room_id
    
    return render_template('chat.html', 
                         username=session['name'],
                         room_name=room['name'],
                         room_id=room_id,
                         personality=personality,
                         task=task,
                         participants=participant_names,
                         share_url=share_url,
                         behavior_map=behavior_map)

@socketio.on('connect')
def handle_connect():
    logger.info('Client connected')
    if 'user_id' not in session or 'room_id' not in session:
        emit('message', {
            'user': 'System',
            'text': 'Please join a chat room first.'
        })
        return
    
    user_id = session['user_id']
    user_info = active_users.get(user_id)
    
    if not user_info:
        logger.warning(f"User {user_id} not found in active_users during connect")
        emit('message', {
            'user': 'System',
            'text': 'Your session has expired. Please rejoin the chat room.'
        })
        return
    
    room_id = user_info['room_id']
    room = active_rooms.get(room_id)
    
    if not room:
        logger.warning(f"Room {room_id} not found in active_rooms during connect")
        emit('message', {
            'user': 'System',
            'text': 'The chat room no longer exists. Please create or join another room.'
        })
        return
    
    join_room(room_id)
    
    # Send chat history to the new user
    for message in room['messages']:
        # Only send valid messages
        if 'user' in message and message['user'] and 'text' in message and message['text']:
            emit('message', message)
            
    # Notify others that user has joined
    join_message = {
        'user': 'System',
        'text': f"{user_info['name']} has joined the chat."
    }
    emit('message', join_message, room=room_id, include_self=False)
    room['messages'].append(join_message)
    
    # Send current participants list
    participant_names = []
    for uid in room['participants']:
        if uid in active_users:
            participant_names.append(active_users[uid]['name'])
    
    emit('update_participants', {
        'participants': participant_names
    }, room=room_id)

@socketio.on('disconnect')
def handle_disconnect():
    if 'user_id' in session:
        user_id = session['user_id']
        user_info = active_users.get(user_id)
        
        if user_info:
            room_id = user_info['room_id']
            room = active_rooms.get(room_id)
            
            if room:
                room['participants'].discard(user_id)
                
                # Remove room if empty
                if not room['participants']:
                    active_rooms.pop(room_id, None)
                else:
                    # Notify others that user has left
                    leave_message = {
                        'user': 'System',
                        'text': f"{user_info['name']} has left the chat."
                    }
                    emit('message', leave_message, room=room_id)
                    room['messages'].append(leave_message)
                    
                    # Update participants list for remaining users
                    participant_names = []
                    for uid in room['participants']:
                        if uid in active_users:
                            participant_names.append(active_users[uid]['name'])
                    
                    emit('update_participants', {
                        'participants': participant_names
                    }, room=room_id)
                
                leave_room(room_id)
            
            active_users.pop(user_id, None)
    
    logger.info('Client disconnected')

@socketio.on('message')
def handle_message(data):
    """Process incoming chat messages"""
    try:
        # Extract user ID and room ID from session
        user_id = session.get('user_id')
        room_id = session.get('room_id')
        
        if not user_id or not room_id:
            emit('error', {'message': 'User not authenticated or room not joined'})
            return
        
        if room_id not in active_rooms:
            emit('error', {'message': 'Room not found'})
            return
            
        room = active_rooms[room_id]
        
        # Get the user name
        user_name = active_users[user_id]['name'] if user_id in active_users else 'Unknown User'
        
        # Extract message content directly from data 
        # The client sends text directly in the data object, not nested in content
        message_content = data.get('text', '')
        
        logger.info(f"Received message from {user_name}: {message_content}")
        
        # Create message object with channel_name instead of room_id
        message = Message(
            content=message_content,
            user_id=user_id,
            channel_name=room_id,  # Use channel_name instead of room_id
            ts=time.time(),  # Use ts instead of timestamp
            type='chat',
            role='user'  # Add required role parameter
        )
        
        # Save message to database using the room's pipeline db_manager
        if room['pipeline'] and room['pipeline'].db_manager:
            room['pipeline'].db_manager.save_message(message)
        
        # Broadcast the message to the room
        emit_msg = {
            'user': user_name,
            'text': message_content
        }
        emit('message', emit_msg, room=room_id)
        
        # Store message in room history
        room['messages'].append(emit_msg)
        
        # Create user profile dict for the pipeline
        user_profile_dict = {
            'user_id': user_id,
            'name': user_name,
            'room_id': room_id
        }
        
        # Check if we should generate a response
        # Use the pipeline to process the message with the user profile
        if room['pipeline']:
            response = room['pipeline'].process_message(message, user_profile_dict)
            
            # If there's a response, broadcast it to the room
            if response:
                bot_msg = {
                    'user': 'AI',
                    'text': response
                }
                emit('message', bot_msg, room=room_id)
                room['messages'].append(bot_msg)
            
    except Exception as e:
        logger.exception(f"Error handling message: {e}")

@socketio.on('update_personality')
def handle_personality_update(data):
    if 'user_id' not in session or 'room_id' not in session:
        return
    
    user_id = session['user_id']
    room_id = session['room_id']
    room = active_rooms.get(room_id)
    
    if not room:
        return
    
    try:
        # Update personality traits
        personality = room['pipeline'].personality
        traits_updated = False
        
        # Check if traits were provided and update them
        if 'traits' in data:
            # Update traits with subcomponents
            for trait, subcomponents in data['traits'].items():
                if trait in personality.traits:
                    # For each subcomponent of the trait
                    for subcomponent, level in subcomponents.items():
                        # Update the level for this subcomponent
                        if personality.traits[trait].get(subcomponent) != level:
                            traits_updated = True
                        personality.traits[trait][subcomponent] = level
        
        # If traits were updated, regenerate name and description
        if traits_updated:
            # Get behavior map
            behavior_map = personality_to_behavior(personality.traits)
            
            try:
                # Generate new name and description based on the traits
                name_desc = generate_name_and_summary(personality.traits, behavior_map)
                personality.name = name_desc.get("name", personality.name)
                personality.description = name_desc.get("summary", personality.description)
                logger.info(f"Generated new name: {personality.name} and description for personality")
            except Exception as e:
                # If generation fails, keep existing name and description
                logger.error(f"Error generating name and description: {str(e)}")
                # Use manually provided name and description as fallback
                if 'name' in data:
                    personality.name = data['name']
                if 'description' in data:
                    personality.description = data['description']
        else:
            # If traits weren't updated, use the provided name and description
            if 'name' in data:
                personality.name = data['name']
            if 'description' in data:
                personality.description = data['description']
        
        # Update response characteristics
        if 'response_characteristics' in data:
            # Update response characteristics dictionary
            for characteristic, value in data['response_characteristics'].items():
                personality.response_characteristics[characteristic] = value
        
        # Update communication style if provided
        if 'communication_style' in data:
            personality.communication_style = data['communication_style']
        
        # Save updated personality to database
        if room['pipeline'].db_manager:
            room['pipeline'].db_manager.save_persona(room_id, personality)
        
        # Get updated behavior map for response
        behavior_map = personality_to_behavior(personality.traits)
        
        # Notify all users in the room about the personality update
        response_data = {
            'name': personality.name,
            'description': personality.description,
            'traits': personality.traits,
            'response_characteristics': personality.response_characteristics,
            'behavior_map': behavior_map
        }
        
        logger.info(f"Emitting personality_updated event with name: {personality.name}, description: {personality.description}")
        emit('personality_updated', response_data, room=room_id)
        
        # Add system message about the update
        update_message = {
            'user': 'System',
            'text': f"{session['name']} has updated the team interaction settings."
        }
        emit('message', update_message, room=room_id)
        room['messages'].append(update_message)
        
    except Exception as e:
        logger.error(f"Error updating personality: {str(e)}")
        emit('message', {
            'user': 'System',
            'text': 'Failed to update team interaction settings.'
        })

@app.route('/join/<room_id>')
def join_room_link(room_id):
    """Handle joining a room via shareable link"""
    # Log the room_id and active rooms for debugging
    logger.info(f"Attempting to join room: {room_id}")
    logger.info(f"Active rooms: {list(active_rooms.keys())}")
    
    if room_id not in active_rooms:
        logger.warning(f"Room {room_id} not found in active rooms")
        flash('This chat room is no longer active.')
        return redirect(url_for('index'))
    
    room = active_rooms[room_id]
    logger.info(f"Found room: {room['name']}")
    
    return render_template('join.html', 
                         room_name=room['name'],
                         room_id=room_id)

@app.route('/join_room', methods=['POST'])
def join_room_post():
    """Handle the form submission for joining a room"""
    username = request.form.get('username')
    room_id = request.form.get('room_id')
    
    if not username:
        flash('Please enter a username')
        return redirect(url_for('join_room_link', room_id=room_id))
    
    if room_id not in active_rooms:
        flash('This room no longer exists')
        return redirect(url_for('index'))
    
    # Create user and add to room
    user_id = f"web_user_{int(time.time())}"
    session['user_id'] = user_id
    session['name'] = username
    session['room_id'] = room_id  # Use room_id instead of room
    
    # Save user to database
    room = active_rooms[room_id]
    if room['pipeline'] and room['pipeline'].db_manager:
        room['pipeline'].db_manager.save_user(user_id, username, time.time(), room_id)
    
    active_users[user_id] = {
        'name': username,
        'room_id': room_id
    }
    room['participants'].add(user_id)
    
    return redirect(url_for('chat'))

@app.route('/api/rooms/<room_id>/messages')
def get_room_messages(room_id):
    """API endpoint to get messages for a room"""
    if room_id not in active_rooms:
        return jsonify([])
    
    room = active_rooms[room_id]
    
    # Get messages from database first if available
    db_messages = []
    if room['pipeline'] and room['pipeline'].db_manager:
        # Query database for messages with this room_id
        db_messages = room['pipeline'].db_manager.get_history({
            'room_id': room_id,
            'limit': 100  # Limit to latest 100 messages
        })
    
    # If we have database messages, use those
    if db_messages:
        valid_messages = []
        for msg in db_messages:
            # Get user name from user_id if possible
            user_name = "Unknown User"
            if room['pipeline'] and room['pipeline'].db_manager:
                db_user_name = room['pipeline'].db_manager.get_user_name(msg['user_id'])
                if db_user_name:
                    user_name = db_user_name
            elif msg['user_id'] in active_users:
                user_name = active_users[msg['user_id']]['name']
            
            # Special names for system and AI
            if msg['user_id'] == 'system':
                user_name = 'System'
            elif msg.get('role') == 'assistant':
                user_name = 'AI Teammate'
                
            valid_messages.append({
                'user_id': user_name,
                'content': msg['content'],
                'role': msg.get('role', 'user')
            })
        
        return jsonify(valid_messages)
    
    # Fallback to in-memory messages if no database results
    valid_messages = []
    for msg in room['messages']:
        if 'user' in msg and msg['user'] and 'text' in msg and msg['text']:
            # Convert to API format
            valid_messages.append({
                'user_id': msg['user'],
                'content': msg['text'],
                'role': 'user' if msg['user'] != 'AI Teammate' and msg['user'] != 'System' else 
                       ('assistant' if msg['user'] == 'AI Teammate' else 'system')
            })
    
    return jsonify(valid_messages)

def get_local_ip():
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

def get_all_local_ips():
    """Get all possible local network IPs of the machine."""
    try:
        # Get the preferred outbound IP
        preferred_ip = get_local_ip()
        
        # Also get all available IPs
        import socket
        hostname = socket.gethostname()
        all_ips = socket.gethostbyname_ex(hostname)[2]
        
        # Add loopback address for local testing
        all_ips.append('127.0.0.1')
        
        # Ensure preferred IP is included and at the front
        if preferred_ip in all_ips:
            all_ips.remove(preferred_ip)
        all_ips.insert(0, preferred_ip)
        
        return all_ips
    except Exception as e:
        logger.error(f"Error obtaining local IPs: {str(e)}", exc_info=True)
        return ["127.0.0.1"]  # Fallback to localhost

if __name__ == '__main__':
    port = 3000  # Use port 3000 which is less likely to be in use
    all_ips = get_all_local_ips()
    
    print("\n" + "="*50)
    print("   TRAIL CHAT APP SERVER STARTED")
    print("="*50)
    print("\nApp accessible at the following URLs:")
    print("-"*40)
    for ip in all_ips:
        print(f"  http://{ip}:{port}")
    print("-"*40)
    print("\nShare these URLs with devices on your local network")
    print("="*50 + "\n")
    
    logger.info(f"App accessible on local network at multiple IPs: {', '.join(all_ips)}")
    socketio.run(app, host='0.0.0.0', port=port, debug=False)  # Set debug to False for better security 