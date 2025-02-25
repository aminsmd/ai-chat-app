from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_socketio import SocketIO, emit, join_room, leave_room
from pipelines.web_pipeline import WebPipeline
from models.web_config import WebBotConfig
from core.personality import load_personality_from_json, default_personality
from core.database_manager import DatabaseManager
import os
from dotenv import load_dotenv
from pathlib import Path
import logging
import shutil
import json
import time
import uuid

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask and Socket.IO
app = Flask(__name__)
app.secret_key = os.urandom(24)
socketio = SocketIO(app, cors_allowed_origins="*")

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
        pipeline.db_manager.save_user(user_id, user_name, time.time())
    
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
    room_id = request.form.get('room_id')
    user_name = request.form.get('name')
    
    if not room_id or not user_name or room_id not in active_rooms:
        return redirect(url_for('index'))
    
    # Create user and add to room
    user_id = f"web_user_{int(time.time())}"
    session['user_id'] = user_id
    session['name'] = user_name
    session['room_id'] = room_id
    
    # Save user to database
    room = active_rooms[room_id]
    if room['pipeline'] and room['pipeline'].db_manager:
        room['pipeline'].db_manager.save_user(user_id, user_name, time.time())
    
    active_users[user_id] = {
        'name': user_name,
        'room_id': room_id
    }
    room['participants'].add(user_id)
    
    # Broadcast participant update to all users in the room
    participant_names = [active_users[uid]['name'] for uid in room['participants']]
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
    
    # Ensure user is in the room's participants
    user_id = session['user_id']
    if user_id not in room['participants']:
        room['participants'].add(user_id)
    
    # Get current participants' names
    participant_names = [active_users[uid]['name'] for uid in room['participants']]
    
    # Clean up any disconnected participants
    connected_participants = set()
    for uid in room['participants']:
        if uid in active_users and active_users[uid]['room_id'] == room_id:
            connected_participants.add(uid)
    room['participants'] = connected_participants
    
    return render_template('chat.html', 
                         username=session['name'],
                         room_name=room['name'],
                         room_id=room_id,
                         personality=personality,
                         task=task,
                         participants=participant_names)

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
        return
    
    room_id = user_info['room_id']
    room = active_rooms.get(room_id)
    
    if room:
        join_room(room_id)
        # Send chat history to the new user
        for message in room['messages']:
            emit('message', message)
            
        # Notify others that user has joined
        join_message = {
            'user': 'System',
            'text': f"{user_info['name']} has joined the chat."
        }
        emit('message', join_message, room=room_id, include_self=False)
        room['messages'].append(join_message)
        
        # Send current participants list
        participant_names = [active_users[uid]['name'] for uid in room['participants']]
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
                    participant_names = [active_users[uid]['name'] for uid in room['participants']]
                    emit('update_participants', {
                        'participants': participant_names
                    }, room=room_id)
                
                leave_room(room_id)
            
            active_users.pop(user_id, None)
    
    logger.info('Client disconnected')

@socketio.on('message')
def handle_message(data):
    if 'user_id' not in session or 'room_id' not in session:
        emit('message', {
            'user': 'System',
            'text': 'Please join a chat room first.'
        })
        return

    user_id = session['user_id']
    user_info = active_users.get(user_id)
    
    if not user_info:
        return
    
    room_id = user_info['room_id']
    room = active_rooms.get(room_id)
    
    if not room:
        return
    
    pipeline = room['pipeline']
    if not pipeline:
        emit('message', {
            'user': 'System',
            'text': 'Sorry, the AI assistant is not properly configured.'
        })
        return

    try:
        # Add user information to the message
        data['user_id'] = user_id
        data['user_name'] = user_info['name']
        
        # Create and broadcast user message
        user_message = {
            'user': user_info['name'],
            'text': data['text']
        }
        emit('message', user_message, room=room_id)
        room['messages'].append(user_message)
        
        # Process message through pipeline
        response = pipeline.process_message(data, {})
        
        if response:
            # Create and broadcast AI response
            ai_message = {
                'user': 'AI Teammate',
                'text': response
            }
            emit('message', ai_message, room=room_id)
            room['messages'].append(ai_message)
            
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        error_message = {
            'user': 'AI Teammate',
            'text': "I ran into an issue processing that message. Could you try rephrasing it?"
        }
        emit('message', error_message)
        room['messages'].append(error_message)

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
        if 'traits' in data:
            # Update traits dictionary
            for trait, info in data['traits'].items():
                if trait in personality.traits:
                    personality.traits[trait]['level'] = info['level']
        
        # Update communication style
        if 'communication_style' in data:
            # Update communication style dictionary
            for style, level in data['communication_style'].items():
                personality.communication_style[style] = level
        
        # Save updated personality to database
        if room['pipeline'].db_manager:
            room['pipeline'].db_manager.save_persona(room_id, personality)
        
        # Notify all users in the room about the personality update
        emit('personality_updated', {
            'traits': personality.traits,
            'communication_style': personality.communication_style,
            'response_characteristics': personality.response_characteristics
        }, room=room_id)
        
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
        room['pipeline'].db_manager.save_user(user_id, username, time.time())
    
    active_users[user_id] = {
        'name': username,
        'room_id': room_id
    }
    room['participants'].add(user_id)
    
    return redirect(url_for('chat'))

if __name__ == '__main__':
    socketio.run(app, debug=True) 