# AI Chat App

AI-powered chat application with customizable personality traits and real-time collaboration features.

## Features

- 🤖 **AI-Powered Conversations** - Integrated with OpenAI for intelligent responses
- 🎭 **Configurable AI Personality** - Backend personality system for customizable AI behavior
- 👥 **Real-time Collaboration** - Multiple users can chat together in shared rooms
- 🔄 **WebSocket Support** - Real-time message delivery using Flask-SocketIO
- 💾 **Persistent Storage** - SQLite database for chat history and configurations
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
   docker-compose up
   ```

   Access at: http://localhost:3001

**OR**

3. **Run locally**
   ```bash
   pip install -r requirements.txt
   python web_app.py
   ```

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
# Run with docker-compose (easiest)
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

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


