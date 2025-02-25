# Slack AI Assistant

A context-aware Slack bot powered by OpenAI's GPT models with vector-based memory management.

## Overview

This Slack bot provides intelligent responses while maintaining conversation context through a combination of vector embeddings and SQL databases. The system uses a modular architecture for maintainability and scalability.

## Setup and Installation

### Prerequisites
- Python 3.10 or higher
- Slack App with appropriate permissions
- OpenAI API key

### Initial Setup
1. Clone this repository
2. Follow the setup instructions in this video tutorial to create your Slack App and get API keys:
   [Slack Bot Setup Tutorial](https://www.youtube.com/watch?v=oDoFvpDftBA)
3. Create your OpenAI API key at: https://platform.openai.com/account/api-keys

### Environment Setup
1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the Bolt directory with:
   ```env
   SLACK_BOT_TOKEN=xoxb-...  # From Slack App settings
   SLACK_APP_TOKEN=xapp-...   # From Slack App settings
   OPENAI_API_KEY=sk-...      # From OpenAI
   chDB_Name=your_chroma_db_name
   sqDB_NAME=your_sqlite_db_name
   table_metadata_file=file_metadata
   chatGPT_API_model=gpt-4
   ```

### Setup

1. Copy the environment template:
