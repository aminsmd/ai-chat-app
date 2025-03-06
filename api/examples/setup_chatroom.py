import asyncio
import httpx
import websockets
import json
from datetime import datetime, timedelta
import random
from pathlib import Path
import sys
from core.personality import generate_random_persona

async def setup_and_connect_to_room():
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        # 1. Create room data
        selected_task = {
            "title": "Website Redesign Planning",
            "description": "Plan the redesign of our company website",
            "objectives": [
                "Define key design requirements",
                "Create timeline for implementation",
                "Assign team responsibilities"
            ],
            "deadline": (datetime.utcnow() + timedelta(days=7)).isoformat()
        }

        # 2. Generate random personality
        selected_persona = generate_random_persona()

        # 3. Define participants
        participants = [
            {"user_id": "u1", "name": "Alice Johnson", "role": "Project Manager"},
            {"user_id": "u2", "name": "Bob Smith", "role": "Developer"},
            {"user_id": "ai1", "name": "AI Assistant", "role": "Facilitator", "is_ai": True}
        ]

        # 4. Create room
        room_data = {
            "task": selected_task,
            "personality": selected_persona.dict(),
            "participants": participants
        }

        try:
            # Create room via REST API
            response = await client.post("/api/rooms/", json=room_data)
            response.raise_for_status()
            room = response.json()
            room_id = room["room_id"]
            print(f"\nCreated room: {room_id}")

            # Connect to WebSocket
            uri = f"ws://localhost:8000/ws/{room_id}"
            async with websockets.connect(uri) as websocket:
                print(f"Connected to WebSocket for room {room_id}")

                # Send initial message
                message = {
                    "user_id": "u1",
                    "content": "Hello everyone! Let's start planning.",
                    "type": "message",
                    "role": "user"
                }
                await websocket.send(json.dumps(message))

                # Wait for and print AI response
                response = await websocket.recv()
                print(f"\nAI Response: {response}")

                # Get room messages via REST API
                response = await client.get(f"/api/rooms/{room_id}/messages")
                messages = response.json()
                print("\nCurrent messages:", messages)

                print(f"\nYou can now access the chat room at: http://localhost:8000/chat/{room_id}")
                
                # Keep connection alive for a bit
                await asyncio.sleep(5)

        except Exception as e:
            print(f"Error: {str(e)}")

if __name__ == "__main__":
    print("Setting up chat room and connecting...")
    asyncio.run(setup_and_connect_to_room()) 