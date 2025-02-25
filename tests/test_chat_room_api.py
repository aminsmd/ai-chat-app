import pytest
from httpx import AsyncClient
from datetime import datetime, timedelta

from Bolt.api.chat_room import app, ChatRoomCreate, TaskDescription, Participant
from Bolt.models.personality_models import (
    Personality, EmotionalStability, Extraversion, 
    Openness, Agreeableness, Conscientiousness
)

@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.fixture
def sample_personality():
    return Personality(
        emotional_stability=EmotionalStability(
            adjustment=8,
            self_esteem=7
        ),
        extraversion=Extraversion(
            sociability=8,
            assertiveness=7,
            energy_level=8
        ),
        openness=Openness(
            curiosity=9,
            creativity=8,
            adaptability=7
        ),
        agreeableness=Agreeableness(
            trust=8,
            cooperation=9
        ),
        conscientiousness=Conscientiousness(
            organization=8,
            responsibility=9,
            achievement_striving=8
        ),
        name="Helpful Assistant",
        description="A friendly and professional AI assistant"
    )

@pytest.fixture
def sample_task():
    return TaskDescription(
        title="Project Planning Session",
        description="Collaborate on Q4 project roadmap",
        objectives=[
            "Define key milestones",
            "Assign responsibilities",
            "Set timeline"
        ],
        deadline=datetime.utcnow() + timedelta(days=1)
    )

@pytest.fixture
def sample_participants():
    return [
        Participant(
            user_id="u1",
            name="John Doe",
            role="Project Manager",
            is_ai=False
        ),
        Participant(
            user_id="u2",
            name="Jane Smith",
            role="Developer",
            is_ai=False
        ),
        Participant(
            user_id="ai1",
            name="Assistant",
            role="Facilitator",
            is_ai=True
        )
    ]

@pytest.mark.asyncio
async def test_create_chat_room(
    client,
    sample_personality,
    sample_task,
    sample_participants
):
    # Create room request
    room_data = ChatRoomCreate(
        task=sample_task,
        personality=sample_personality,
        participants=sample_participants
    )
    
    response = await client.post("/rooms/", json=room_data.dict())
    assert response.status_code == 200
    
    data = response.json()
    assert "room_id" in data
    assert data["task"]["title"] == sample_task.title
    assert len(data["participants"]) == len(sample_participants)
    assert data["status"] == "active"

@pytest.mark.asyncio
async def test_get_chat_room(client):
    # First create a room
    room_data = ChatRoomCreate(
        task=sample_task,
        personality=sample_personality,
        participants=sample_participants
    )
    create_response = await client.post("/rooms/", json=room_data.dict())
    room_id = create_response.json()["room_id"]
    
    # Then get the room
    response = await client.get(f"/rooms/{room_id}")
    assert response.status_code == 200
    assert response.json()["room_id"] == room_id

@pytest.mark.asyncio
async def test_list_user_rooms(client, sample_participants):
    user_id = sample_participants[0].user_id
    response = await client.get(f"/rooms/?user_id={user_id}")
    assert response.status_code == 200
    assert isinstance(response.json(), list) 