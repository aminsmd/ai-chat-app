import uvicorn
from api.chat_room import application

if __name__ == "__main__":
    uvicorn.run(
        "api.chat_room:application",
        host="127.0.0.1",
        port=8000,
        reload=True  # Enable auto-reload for development
    ) 