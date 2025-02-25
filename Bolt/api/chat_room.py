from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid

from ..models.personality_models import Personality
from ..core.database_manager import DatabaseManager
from ..core.memory_manager import MemoryManager
from ..utils.context_manager import ContextManager

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

class ChatRoomCreate(BaseModel):
    task: TaskDescription
    personality: Personality
    participants: List[Participant]

class ChatRoomResponse(BaseModel):
    room_id: str
    task: TaskDescription
    personality: Personality
    participants: List[Participant]
    created_at: datetime
    status: str
    join_url: str

class ChatRoom:
    def __init__(self, db: DatabaseManager, memory: MemoryManager):
        self.db = db
        self.memory = memory
        self.context = ContextManager()

    async def create_room(self, room_data: ChatRoomCreate) -> ChatRoomResponse:
        room_id = str(uuid.uuid4())
        
        # Initialize room context
        await self.context.initialize_room(
            room_id=room_id,
            task=room_data.task,
            personality=room_data.personality
        )
        
        # Store room data
        room = ChatRoomResponse(
            room_id=room_id,
            task=room_data.task,
            personality=room_data.personality,
            participants=room_data.participants,
            created_at=datetime.utcnow(),
            status="active",
            join_url=f"/chat/{room_id}"
        )
        
        await self.db.store_room(room)
        return room

    async def get_room(self, room_id: str) -> ChatRoomResponse:
        room = await self.db.get_room(room_id)
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")
        return room

    async def list_rooms(self, user_id: str) -> List[ChatRoomResponse]:
        return await self.db.list_rooms(user_id)

app = FastAPI(title="Chat Room API")

# Dependency injection
async def get_chat_room():
    db = DatabaseManager()
    memory = MemoryManager()
    return ChatRoom(db, memory)

@app.post("/rooms/", response_model=ChatRoomResponse)
async def create_chat_room(
    room_data: ChatRoomCreate,
    chat_room: ChatRoom = Depends(get_chat_room)
):
    """Create a new chat room with specified task, personality, and participants"""
    return await chat_room.create_room(room_data)

@app.get("/rooms/{room_id}", response_model=ChatRoomResponse)
async def get_chat_room(
    room_id: str,
    chat_room: ChatRoom = Depends(get_chat_room)
):
    """Get details of a specific chat room"""
    return await chat_room.get_room(room_id)

@app.get("/rooms/", response_model=List[ChatRoomResponse])
async def list_user_rooms(
    user_id: str,
    chat_room: ChatRoom = Depends(get_chat_room)
):
    """List all chat rooms for a user"""
    return await chat_room.list_rooms(user_id) 