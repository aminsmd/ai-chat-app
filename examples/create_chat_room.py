import asyncio
import httpx
from datetime import datetime, timedelta

async def create_test_room():
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        # Create room data
        room_data = {
            "task": {
                "title": "Project Planning Session",
                "description": "Collaborate on Q4 project roadmap",
                "objectives": [
                    "Define key milestones",
                    "Assign responsibilities",
                    "Set timeline"
                ],
                "deadline": (datetime.utcnow() + timedelta(days=1)).isoformat()
            },
            "personality": {
                "name": "Helpful Assistant",
                "description": "A friendly and professional AI assistant",
                "traits": {
                    "emotional_stability": {"level": 0.8, "description": "Maintains composure"},
                    "extraversion": {"level": 0.7, "description": "Engaging but balanced"},
                    "openness": {"level": 0.8, "description": "Open to new ideas"},
                    "agreeableness": {"level": 0.9, "description": "Highly cooperative"},
                    "conscientiousness": {"level": 0.9, "description": "Very thorough"}
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
                    "empathy_level": "high",
                    "creativity_level": "balanced"
                }
            },
            "participants": [
                {
                    "user_id": "u1",
                    "name": "John Doe",
                    "role": "Project Manager",
                    "is_ai": False
                },
                {
                    "user_id": "u2",
                    "name": "Jane Smith",
                    "role": "Developer",
                    "is_ai": False
                },
                {
                    "user_id": "ai1",
                    "name": "Assistant",
                    "role": "Facilitator",
                    "is_ai": True
                }
            ]
        }

        # Create room
        response = await client.post("/api/rooms/", json=room_data)
        print("Created room:", response.json())

        # Get room details
        room_id = response.json()["room_id"]
        response = await client.get(f"/api/rooms/{room_id}")
        print("\nRoom details:", response.json())

        # List rooms for user
        response = await client.get("/api/rooms?user_id=u1")
        print("\nUser's rooms:", response.json())

if __name__ == "__main__":
    asyncio.run(create_test_room()) 