# TRAIL: Team Research and AI Integration Lab

## Python VENV
1. python version 3.11
2. Steps:   
    following tutorials in https://gist.github.com/ryumada/c22133988fd1c22a66e4ed1b23eca233   
    pip install -r requirement_venv.txt


## Tool information
Tool : Visual Studio Code
Extension: Remote Development

## Commit Conventions
### run pre-commit before commit files
pre-commit run --all-files

## Overview
This project aims to build an AI chatbot that can interact effectively in a collaborative environment, contributing to research on human-like AI behavior. It provides both a Slack integration and a web interface for team collaboration with AI.

## Features
- Multi-room chat support with persistent history
- Customizable AI teammate personality traits
- Long-term memory and context awareness
- Real-time collaboration with multiple users
- Shareable room links

## How to Run

### Environment Setup
1. Git clone this repo
2. Create a `.env` file in the `Bolt` directory with the following variables:
   ```
   # Required for Slack integration
   SLACK_APP_TOKEN=<your-slack-app-token>
   SLACK_BOT_TOKEN=<your-slack-bot-token>
   
   # Required for both Slack and Web interface
   OPENAI_API_KEY=<your-openai-api-key>
   
   # Optional configurations
   OPEN_AI_MODEL=gpt-4
   SQLITE_DB_NAME=chat_history.db
   ```

### Run Slack ChatBot
1. Follow the instructions to generate Slack API keys and add corresponding Scopes:
   https://www.youtube.com/watch?v=oDoFvpDftBA&ab_channel=PyBites
2. Add the Slack tokens to your `.env` file
3. Run `python3 app.py` to start the Slack bot

### Run Web Interface
1. Ensure you have the OpenAI API key in your `.env` file
2. Navigate to the `Bolt` directory
3. Run `python3 web_app.py`
4. Access the web interface at `http://localhost:5000`

#### Web Interface Features
- Create and join chat rooms
- Real-time chat with AI teammate
- Customize AI personality traits and communication style
- Share room links with other users
- Persistent chat history
- Multiple active rooms support

## How It Works

### Database Structure
The application uses SQLite3 for data persistence with the following tables:
- `users`: Stores user information and session data
- `personas`: Stores AI personality configurations per room
- `new_msg_queue`: Manages message queue for processing
- `history`: Stores chat history
- `context_history`: Maintains context for AI responses
- `long_term_memories`: Stores summarized conversation insights

### AI Interaction
- Uses OpenAI's GPT-4 model for natural language processing
- Maintains conversation context and long-term memory
- Adapts responses based on configured personality traits
- Supports real-time updates to AI behavior through personality adjustments

## Possible Setup Issues and Solutions
All package versions are listed in requirements.txt
current chromadb version: 0.4.15

1. When you create a new github Codespaces, you should install the packages manually.
run <code> "pip install --no-cache-dir -r .devcontainer/requirements.txt"</code>

NOTE: It is not recommended to upload your API token to the codebase because the GIT and Slack will lock the privilege.

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


