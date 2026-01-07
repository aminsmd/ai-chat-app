# AI Chat App

AI-powered chat application with customizable personality traits and real-time collaboration features.

## Features

- 🤖 **AI-Powered Conversations** - Integrated with OpenAI for intelligent responses
- 🎭 **Configurable AI Personality** - Backend personality system for customizable AI behavior
- 👥 **Real-time Collaboration** - Multiple users can chat together in shared rooms
- 🔄 **WebSocket Support** - Real-time message delivery using Flask-SocketIO
- 💾 **Persistent Storage** - SQLite database for chat history and configurations
- 🌐 **Network Access** - Access from any device on your local network
- 🐳 **Docker Ready** - Easy deployment with Docker and docker-compose

## Quick Start

### Prerequisites

- Python 3.11+
- OpenAI API key
- Docker (optional, for containerized deployment)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/aminsmd/ai-chat-app.git
   cd ai-chat-app
   ```

2. **Create environment file**
   ```bash
   # Create .env file with your OpenAI API key
   echo "OPENAI_API_KEY=your_openai_api_key_here" > .env
   echo "OPEN_AI_MODEL=gpt-4" >> .env
   echo "SQLITE_DB_NAME=chat_history.db" >> .env
   ```

3. **Run with Docker (Recommended)**
   ```bash
   # Using the helper script (automatically detects your network IP)
   ./start-docker.sh

   # OR manually
   docker-compose up
   ```

   The app will display URLs on startup:
   - `http://localhost:3001` - Access from your computer
   - `http://<your-ip>:3001` - Access from other devices on your network

**OR**

3. **Run locally**
   ```bash
   pip install -r requirements.txt
   python web_app.py
   ```

   The app will automatically detect and display all available network URLs on startup.

## Configuration

### Environment Variables

Create a `.env` file with:

```env
OPENAI_API_KEY=your_openai_api_key_here
OPEN_AI_MODEL=gpt-4
SQLITE_DB_NAME=chat_history.db
```

### AI Personality System

The application includes a sophisticated personality system that influences AI behavior:

- **Emotional Stability** - Controls how calm vs. reactive the AI responds
- **Extraversion** - Determines how outgoing vs. reserved the AI appears
- **Openness** - Adjusts how creative vs. conventional the AI's suggestions are
- **Agreeableness** - Influences how cooperative vs. competitive the AI is
- **Conscientiousness** - Affects how organized vs. spontaneous the AI's responses are

The personality configuration is stored in the database and applied during AI response generation. The UI sidebar for personality display has been simplified for a cleaner chat experience.

## Docker Deployment

### Build and Run

```bash
# Run with helper script (shows your network IP automatically)
./start-docker.sh

# OR run with docker-compose
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Network Access

The application is accessible from any device on your local network:

1. **Using the helper script** - Run `./start-docker.sh` and it will automatically detect and display your network IP
2. **Manual method** - Start with `HOST_IP=$(ipconfig getifaddr en0) docker-compose up`
3. **Find your IP manually** - Run `ipconfig getifaddr en0` on macOS or `hostname -I` on Linux

Once running, you'll see output like:
```
==================================================
   TRAIL CHAT APP SERVER STARTED
==================================================

App accessible at the following URLs:
----------------------------------------
  http://localhost:3001
  http://192.168.1.5:3001 (accessible from local network)
----------------------------------------

Share these URLs with devices on your local network
==================================================
```

Share the network URL with other devices (phones, tablets, other computers) on your local network to collaborate in real-time!

### Rebuild After Changes

```bash
docker-compose up --build
```

See [DOCKER.md](DOCKER.md) for detailed Docker instructions.

## Database Structure

The application uses SQLite for data persistence:
- `users`: User information and session data
- `personas`: AI personality configurations per room
- `new_msg_queue`: Message queue for processing
- `history`: Chat history
- `context_history`: Context for AI responses
- `long_term_memories`: Summarized conversation insights

## Tech Stack

- **Backend**: Flask, Flask-SocketIO
- **AI**: OpenAI API, LangChain
- **Database**: SQLite, SQLAlchemy
- **Frontend**: HTML, JavaScript, WebSocket
- **Deployment**: Docker, docker-compose

## Troubleshooting

See [DOCKER.md](DOCKER.md) for common Docker issues.

**Port Already in Use:**
```bash
docker run -p 8080:3001 --env-file .env ai-chat-app
```

**View Logs:**
```bash
docker logs -f trail-chat-web
```

## Preprint paper:

The AI Collaborator: Bridging Human-AI Interaction in Educational and Professional Settings\
Mohammad Amin Samadi, Spencer JaQuay, Jing Gu, Nia Nixon, [link](https://arxiv.org/abs/2405.10460)

### citation:
@article{samadi2024ai,
  title={The AI Collaborator: Bridging Human-AI Interaction in Educational and Professional Settings},
  author={Samadi, Mohammad Amin and JaQuay, Spencer and Gu, Jing and Nixon, Nia},
  journal={arXiv preprint arXiv:2405.10460},
  year={2024}
}


