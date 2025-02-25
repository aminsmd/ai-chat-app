import asyncio
import httpx
from datetime import datetime, timedelta
import json
import random
from pathlib import Path
import sys

# Add the parent directory to the Python path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from core.personality import generate_random_persona

async def setup_chatroom():
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        # 1. Create sample users
        users = [
            {"user_id": "u1", "name": "Alice Johnson", "role": "Project Manager"},
            {"user_id": "u2", "name": "Bob Smith", "role": "Developer"},
            {"user_id": "u3", "name": "Carol White", "role": "Designer"},
            {"user_id": "ai1", "name": "AI Assistant", "role": "Facilitator", "is_ai": True}
        ]

        # 2. Create sample tasks
        tasks = [
            {
                "title": "Website Redesign Planning",
                "description": "Plan the redesign of our company website",
                "objectives": [
                    "Define key design requirements",
                    "Create timeline for implementation",
                    "Assign team responsibilities",
                    "Identify potential challenges"
                ],
                "deadline": (datetime.utcnow() + timedelta(days=7)).isoformat()
            },
            {
                "title": "API Integration Project",
                "description": "Integrate third-party payment API into our platform",
                "objectives": [
                    "Review API documentation",
                    "Design integration architecture",
                    "Create implementation plan",
                    "Set up testing environment"
                ],
                "deadline": (datetime.utcnow() + timedelta(days=14)).isoformat()
            }
        ]

        # 3. Generate random personality
        selected_persona = generate_random_persona()

        # 4. Select random task
        selected_task = random.choice(tasks)

        # 5. Create room data
        room_data = {
            "task": selected_task,
            "personality": selected_persona.dict(),  # Convert Pydantic model to dict
            "participants": users
        }

        try:
            # 6. Create the room
            print("\nCreating chat room...")
            response = await client.post("/api/rooms/", json=room_data)
            response.raise_for_status()
            room_data = response.json()
            print(f"\nCreated room: {room_data['room_id']}")
            print(f"Join URL: {room_data['join_url']}")
            
            # 7. Send initial message
            room_id = room_data["room_id"]
            welcome_message = {
                "user_id": "ai1",
                "content": f"Welcome to the {selected_task['title']} discussion! I'll be your AI assistant for this project.",
                "type": "message",
                "role": "assistant"
            }
            
            response = await client.post(f"/api/rooms/{room_id}/messages", json=welcome_message)
            response.raise_for_status()
            print("\nSent welcome message!")
            
            # 8. Get and display room details
            response = await client.get(f"/api/rooms/{room_id}")
            response.raise_for_status()
            print("\nRoom details:")
            print(f"Task: {selected_task['title']}")
            print(f"Participants: {', '.join(user['name'] for user in users)}")
            print(f"AI Personality: {selected_persona.name}")
            print(f"\nYou can now access the chat room at: http://localhost:8000/chat/{room_id}")
            
        except httpx.HTTPStatusError as e:
            print(f"HTTP Error: {e.response.status_code}")
            print(f"Error detail: {e.response.text}")
        except Exception as e:
            print(f"Error: {str(e)}")

if __name__ == "__main__":
    print("Setting up chat room...")
    asyncio.run(setup_chatroom()) 