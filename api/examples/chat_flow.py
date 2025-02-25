import asyncio
import httpx
from datetime import datetime, timedelta
import webbrowser
import time

async def create_and_join_chat():
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

        try:
            # Create room
            response = await client.post("/api/rooms/", json=room_data)
            response.raise_for_status()
            room_data = response.json()
            print("\nCreated room:", room_data)
            
            room_id = room_data["room_id"]
            chat_url = f"http://localhost:8000/chat/{room_id}"
            
            print(f"\nChat room created! Opening browser to join at: {chat_url}")
            
            # Open browser to join the chat
            webbrowser.open(chat_url)
            
            # Keep the script running for a bit to allow browser to connect
            await asyncio.sleep(2)
            
            # Send a test message
            message = {
                "user_id": "u1",
                "content": "Hello everyone! Let's start planning.",
                "type": "message"
            }
            
            response = await client.post(f"/api/rooms/{room_id}/messages", json=message)
            response.raise_for_status()
            print("\nSent initial message!")
            
            # Get messages
            response = await client.get(f"/api/rooms/{room_id}/messages")
            response.raise_for_status()
            messages = response.json()
            print("\nCurrent messages:", messages)
            
        except httpx.HTTPStatusError as e:
            print(f"HTTP Error: {e.response.status_code}")
            print(f"Error detail: {e.response.text}")
        except Exception as e:
            print(f"Error: {str(e)}")

if __name__ == "__main__":
    print("Creating and joining chat room...")
    asyncio.run(create_and_join_chat()) 