from fastapi import FastAPI, HTTPException, Depends, Request, WebSocket
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
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
from pipelines.web_pipeline import WebPipeline
from core.exceptions import RoomNotFoundError, DatabaseError, PipelineError

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

class ChatRoomManager:
    """Handles chat room operations and state management"""
    def __init__(self, db: DatabaseManager, memory: MemoryManager):
        self.db = db
        self.memory = memory
        self.rooms: Dict[str, ChatRoomResponse] = {}
        self.messages: Dict[str, List[Message]] = {}
        self.pipelines: Dict[str, WebPipeline] = {}
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def create_pipeline(self, room_id: str, personality: dict) -> None:
        """Create and store a pipeline for a room"""
        try:
            self.pipelines[room_id] = WebPipeline(
                personality=personality,
                db_manager=self.db,
                memory_manager=self.memory
            )
        except Exception as e:
            raise PipelineError(f"Failed to create pipeline: {str(e)}")

    async def broadcast_message(self, room_id: str, message: dict) -> None:
        """Broadcast message to all connected clients in a room"""
        if room_id in self.active_connections:
            for connection in self.active_connections[room_id]:
                await connection.send_json(message)

    async def process_user_message(self, room_id: str, message: Message) -> Optional[Message]:
        """Process user message and get AI response"""
        try:
            if room_id not in self.pipelines:
                raise PipelineError(f"No pipeline found for room {room_id}")

            pipeline = self.pipelines[room_id]
            response = await pipeline.process_message(message)
            
            if response:
                return Message(
                    user_id="ai1",
                    channel_name=room_id,
                    content=response,
                    ts=datetime.utcnow().timestamp(),
                    role="assistant",
                    type="message"
                )
            return None
        except Exception as e:
            raise PipelineError(f"Failed to process message: {str(e)}")

class RoomController:
    """Handles room-related API endpoints"""
    def __init__(self, manager: ChatRoomManager):
        self.manager = manager

    async def create_room(self, room_data: ChatRoomCreate) -> ChatRoomResponse:
        """Create a new chat room"""
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
            
            # Initialize room resources
            self.manager.rooms[room_id] = room
            self.manager.messages[room_id] = []
            await self.manager.create_pipeline(room_id, room_data.personality)
            
            return room
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def get_room(self, room_id: str) -> ChatRoomResponse:
        """Get room details"""
        room = self.manager.rooms.get(room_id)
        if not room:
            raise RoomNotFoundError(room_id)
        return room

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
        chat_room = await get_chat_room()
        # Process message through ChatRoom
        message = {
            "user_id": data.get('user', 'Anonymous'),
            "content": data.get('text', ''),
            "type": "message",
            "role": "user"
        }
        await chat_room.add_message(room_id, message)

# Update the dependency injection
_chat_room_manager: Optional[ChatRoomManager] = None

async def get_chat_room() -> ChatRoomManager:
    """Get or create the ChatRoomManager singleton instance"""
    global _chat_room_manager
    if _chat_room_manager is None:
        try:
            db = DatabaseManager(config=bot_config)
            memory = MemoryManager(config=bot_config)
            _chat_room_manager = ChatRoomManager(db, memory)
        except Exception as e:
            print(f"Error initializing ChatRoomManager with database: {e}")
            memory = MemoryManager(config=bot_config)
            _chat_room_manager = ChatRoomManager(None, memory)
    return _chat_room_manager

# Update the API routes to use ChatRoomManager methods
@app.post("/api/rooms/", response_model=ChatRoomResponse)
async def create_chat_room(
    room_data: ChatRoomCreate,
    chat_room: ChatRoomManager = Depends(get_chat_room)
) -> ChatRoomResponse:
    controller = RoomController(chat_room)
    return await controller.create_room(room_data)

@app.get("/api/rooms/list", response_model=List[ChatRoomResponse])
async def list_user_rooms(
    user_id: str = None,
    chat_room: ChatRoomManager = Depends(get_chat_room)
):
    """List all chat rooms for a user"""
    if not user_id:
        # Return all rooms if no user_id specified
        return list(chat_room.rooms.values())
    # Filter rooms for specific user
    return [
        room for room in chat_room.rooms.values()
        if any(p.user_id == user_id for p in room.participants)
    ]

@app.get("/api/rooms/{room_id}", response_model=ChatRoomResponse)
async def get_room(
    room_id: str,
    chat_room: ChatRoomManager = Depends(get_chat_room)
) -> ChatRoomResponse:
    controller = RoomController(chat_room)
    return await controller.get_room(room_id)

@app.post("/api/rooms/{room_id}/messages", response_model=Message)
async def add_message(
    room_id: str,
    message: dict,
    chat_room: ChatRoomManager = Depends(get_chat_room)
) -> Message:
    """Add a message to a chat room"""
    if room_id not in chat_room.rooms:
        raise RoomNotFoundError(room_id)
        
    msg = Message(
        user_id=message["user_id"],
        channel_name=room_id,
        content=message["content"],
        ts=datetime.utcnow().timestamp(),
        role=message.get("role", "user"),
        type=message.get("type", "message")
    )
    
    if room_id not in chat_room.messages:
        chat_room.messages[room_id] = []
    chat_room.messages[room_id].append(msg)
    
    # Process message through pipeline if available
    try:
        ai_response = await chat_room.process_user_message(room_id, msg)
        if ai_response:
            chat_room.messages[room_id].append(ai_response)
    except PipelineError as e:
        print(f"Pipeline error: {e}")
        
    return msg

@app.get("/api/rooms/{room_id}/messages", response_model=List[Message])
async def get_messages(
    room_id: str,
    chat_room: ChatRoomManager = Depends(get_chat_room)
) -> List[Message]:
    """Get all messages in a chat room"""
    if room_id not in chat_room.rooms:
        raise RoomNotFoundError(room_id)
    return chat_room.messages.get(room_id, [])

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}

# Setup templates
templates = Jinja2Templates(directory="templates")

# Update the chat route
@app.get("/chat/{room_id}", response_class=HTMLResponse)
async def join_chat(
    request: Request,
    room_id: str,
    chat_room: ChatRoomManager = Depends(get_chat_room)
):
    """Join a chat room"""
    try:
        controller = RoomController(chat_room)
        room = await controller.get_room(room_id)
        
        # Create share URL
        share_url = str(request.url)
        
        return templates.TemplateResponse(
            "chat.html",
            {
                "request": request,
                "room": room,
                "room_name": room.task.title,
                "username": "User",
                "personality": room.personality,
                "task": room.task.description,
                "participants": [p.name for p in room.participants],
                "share_url": share_url,
                "room_id": room_id,
                "ws_url": f"ws://{request.url.hostname}:{request.url.port}/ws/{room_id}"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Chat room not found: {str(e)}")

# Update setup_routes to use dependency injection and add error handling
def setup_routes(app: FastAPI):
    """Setup WebSocket and API routes with proper error handling"""
    
    @app.websocket("/ws/{room_id}")
    async def websocket_endpoint(
        websocket: WebSocket, 
        room_id: str,
        manager: ChatRoomManager = Depends(get_chat_room)
    ):
        try:
            await websocket.accept()
            
            # Initialize room connections if needed
            if room_id not in manager.active_connections:
                manager.active_connections[room_id] = []
            
            # Initialize room messages if needed    
            if room_id not in manager.messages:
                manager.messages[room_id] = []
                
            # Verify room exists
            if room_id not in manager.rooms:
                await websocket.close(code=4004, reason="Room not found")
                return
                
            manager.active_connections[room_id].append(websocket)
            
            try:
                while True:
                    data = await websocket.receive_json()
                    message = Message(**data)
                    
                    # Store user message
                    manager.messages[room_id].append(message)
                    await manager.broadcast_message(room_id, message.dict())
                    
                    # Get and broadcast AI response
                    try:
                        ai_response = await manager.process_user_message(room_id, message)
                        if ai_response:
                            manager.messages[room_id].append(ai_response)
                            await manager.broadcast_message(room_id, ai_response.dict())
                    except PipelineError as e:
                        await websocket.send_json({
                            "error": f"Failed to process message: {str(e)}"
                        })
                        
            except Exception as e:
                print(f"WebSocket error in room {room_id}: {e}")
                
            finally:
                # Safely remove connection
                if room_id in manager.active_connections:
                    try:
                        manager.active_connections[room_id].remove(websocket)
                    except ValueError:
                        pass  # Connection already removed
                        
        except Exception as e:
            print(f"Failed to initialize WebSocket connection: {e}")
            await websocket.close(code=4000)

# Initialize routes when app starts
@app.on_event("startup")
async def startup_event():
    """Initialize routes and manager on startup"""
    setup_routes(app)

# Error handlers
@app.exception_handler(RoomNotFoundError)
async def room_not_found_handler(request: Request, exc: RoomNotFoundError):
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)}
    )

@app.exception_handler(PipelineError)
async def pipeline_error_handler(request: Request, exc: PipelineError):
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)}
    ) 