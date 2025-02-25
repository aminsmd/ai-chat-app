from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime
import uuid
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from pathlib import Path
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from socketio import AsyncServer, ASGIApp
import os
from dotenv import load_dotenv

from models.personality_models import Personality
from core.database_manager import DatabaseManager
from core.memory_manager import MemoryManager
from models.base import BotConfig, Message

# Load environment variables
load_dotenv()

# Create bot config from environment variables
bot_config = BotConfig.from_env({
    "SLACK_BOT_TOKEN": os.getenv("SLACK_BOT_TOKEN", ""),
    "SLACK_APP_TOKEN": os.getenv("SLACK_APP_TOKEN", ""),
    "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
    "chDB_Name": os.getenv("CHROMA_DB_NAME", "memory_db"),
    "sqDB_NAME": os.getenv("SQLITE_DB_NAME", "chat.db"),
    "table_metadata_file": os.getenv("TABLE_METADATA_FILE", "table_metadata.json"),
    "chatGPT_API_model": os.getenv("CHATGPT_MODEL", "gpt-3.5-turbo")
})

class Participant(BaseModel):
    user_id: str
    name: str
    role: str
    is_ai: bool = False

class TaskDescription(BaseModel):
    title: str
    description: str
    objectives: List[str]
    deadline: Optional[datetime] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class ChatRoomCreate(BaseModel):
    task: TaskDescription
    personality: dict  # Change to dict to be more flexible
    participants: List[Participant]

class ChatRoomResponse(BaseModel):
    room_id: str
    task: TaskDescription
    personality: dict
    participants: List[Participant]
    created_at: datetime
    status: str
    join_url: str

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class ChatRoom:
    def __init__(self, db: DatabaseManager, memory: MemoryManager):
        self.db = db
        self.memory = memory
        self.rooms: Dict[str, ChatRoomResponse] = {}
        self.messages: Dict[str, List[Message]] = {}  # room_id -> messages

    async def create_room(self, room_data: ChatRoomCreate) -> ChatRoomResponse:
        try:
            room_id = str(uuid.uuid4())
            
            room = ChatRoomResponse(
                room_id=room_id,
                task=room_data.task,
                personality=room_data.personality,
                participants=room_data.participants,
                created_at=datetime.utcnow(),
                status="active",
                join_url=f"/chat/{room_id}"
            )
            
            # Store in memory
            self.rooms[room_id] = room
            return room
            
        except Exception as e:
            print(f"Error creating room: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def get_room(self, room_id: str) -> ChatRoomResponse:
        room = self.rooms.get(room_id)
        if not room:
            raise HTTPException(status_code=404, detail=f"Room {room_id} not found")
        return room

    async def list_rooms(self, user_id: str) -> List[ChatRoomResponse]:
        # Return rooms from memory where user is a participant
        user_rooms = [
            room for room in self.rooms.values()
            if any(p.user_id == user_id for p in room.participants)
        ]
        
        # Try to get additional rooms from database
        try:
            db_rooms = await self.db.list_rooms(user_id)
            if db_rooms:
                # Combine with memory rooms, avoiding duplicates
                room_ids = {r.room_id for r in user_rooms}
                user_rooms.extend([r for r in db_rooms if r.room_id not in room_ids])
        except Exception as e:
            print(f"Database listing failed: {e}")
            
        return user_rooms

    async def add_message(self, room_id: str, message: dict) -> Message:
        if room_id not in self.rooms:
            raise HTTPException(status_code=404, detail=f"Room {room_id} not found")
            
        msg = Message(
            user_id=message["user_id"],
            channel_name=room_id,
            content=message["content"],
            ts=datetime.utcnow().timestamp(),
            role=message.get("role", "user"),
            type=message.get("type", "message")
        )
        
        if room_id not in self.messages:
            self.messages[room_id] = []
        self.messages[room_id].append(msg)
        return msg

    async def get_messages(self, room_id: str) -> List[Message]:
        if room_id not in self.rooms:
            raise HTTPException(status_code=404, detail=f"Room {room_id} not found")
        return self.messages.get(room_id, [])

# Create FastAPI app
app = FastAPI(title="Chat Room API")

# Create Socket.IO instance with proper configuration
sio = AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=[
        "http://127.0.0.1:8000",  # Add the correct port
        "http://localhost:8000",
        "http://127.0.0.1:5000",
        "http://localhost:5000"
    ],
    ping_timeout=60,  # Increase timeouts
    ping_interval=25,
    reconnection=True,
    reconnection_attempts=5
)

# Create ASGI app that combines FastAPI and Socket.IO
socket_app = ASGIApp(sio)
app.mount("/socket.io", socket_app)

# This is the main application that should be referenced when running the server
application = app

# Update CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5000", "http://localhost:5000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Only mount static files and templates if directories exist
current_dir = Path(__file__).parent

# Mount API docs if they exist
docs_path = current_dir / "docs"
if docs_path.exists():
    app.mount("/api/docs/static", StaticFiles(directory=str(docs_path), html=True), name="api-docs")

# Socket.IO event handlers
@sio.on('connect')
async def handle_connect(sid, environ):
    print(f"Client connected: {sid}")
    await sio.emit('message', {
        'user': 'System',
        'text': 'Connected to server'
    }, room=sid)

@sio.on('disconnect')
async def handle_disconnect(sid):
    print(f"Client disconnected: {sid}")

@sio.on('join')
async def handle_join(sid, room_id):
    print(f"Client {sid} joining room {room_id}")
    sio.enter_room(sid, room_id)
    await sio.emit('message', {
        'user': 'System',
        'text': 'Joined the chat room'
    }, room=room_id)

@sio.on('message')
async def handle_message(sid, data):
    print(f"Message from {sid}: {data}")
    room_id = data.get('room_id')
    if room_id:
        # Broadcast message to room
        await sio.emit('message', {
            'user': data.get('user', 'Anonymous'),
            'text': data.get('text', '')
        }, room=room_id)

# Updated dependency injection
_chat_room: Optional[ChatRoom] = None

async def get_chat_room() -> ChatRoom:
    global _chat_room
    if _chat_room is None:
        try:
            db = DatabaseManager(config=bot_config)
            memory = MemoryManager(config=bot_config)
            _chat_room = ChatRoom(db, memory)
        except Exception as e:
            print(f"Error initializing ChatRoom: {e}")
            # Create without database but with memory
            memory = MemoryManager(config=bot_config)
            _chat_room = ChatRoom(None, memory)
    return _chat_room

# API routes
@app.post("/api/rooms/", response_model=ChatRoomResponse)
async def create_chat_room(
    room_data: ChatRoomCreate,
    chat_room: ChatRoom = Depends(get_chat_room)
) -> ChatRoomResponse:
    return await chat_room.create_room(room_data)

@app.get("/api/rooms/list", response_model=List[ChatRoomResponse])
async def list_user_rooms(
    user_id: str = None,
    chat_room: ChatRoom = Depends(get_chat_room)
):
    """List all chat rooms for a user"""
    if not user_id:
        # Return all rooms if no user_id specified
        return list(chat_room.rooms.values())
    return await chat_room.list_rooms(user_id)

@app.get("/api/rooms/{room_id}", response_model=ChatRoomResponse)
async def get_room(
    room_id: str,
    chat_room: ChatRoom = Depends(get_chat_room)
) -> ChatRoomResponse:
    return await chat_room.get_room(room_id)

@app.post("/api/rooms/{room_id}/messages", response_model=Message)
async def add_message(
    room_id: str,
    message: dict,
    chat_room: ChatRoom = Depends(get_chat_room)
) -> Message:
    return await chat_room.add_message(room_id, message)

@app.get("/api/rooms/{room_id}/messages", response_model=List[Message])
async def get_messages(
    room_id: str,
    chat_room: ChatRoom = Depends(get_chat_room)
) -> List[Message]:
    return await chat_room.get_messages(room_id)

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}

# Setup templates
templates = Jinja2Templates(directory="templates")

# Add chat route to handle join URLs
@app.get("/chat/{room_id}", response_class=HTMLResponse)
async def join_chat(
    request: Request,
    room_id: str,
    chat_room: ChatRoom = Depends(get_chat_room)
):
    """Join a chat room"""
    try:
        room = await chat_room.get_room(room_id)
        
        # Create share URL
        share_url = str(request.url)
        
        return templates.TemplateResponse(
            "chat.html",
            {
                "request": request,
                "room": room,
                "room_name": room.task.title,
                "username": "User",  # Default username
                "personality": room.personality,
                "task": room.task.description,
                "participants": [p.name for p in room.participants],
                "share_url": share_url,
                "room_id": room_id,
                # Remove session and url_for references
                "ws_url": f"ws://{request.url.hostname}:{request.url.port}/ws/chat/{room_id}"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Chat room not found: {str(e)}") 