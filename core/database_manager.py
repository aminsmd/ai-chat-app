import os
import sqlite3
import logging
from typing import Dict, Optional, List
from datetime import datetime
from models import Message, BotConfig, LongTermMemory
from core.personality import Personality
import threading
import json
from pathlib import Path
import time

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, config: BotConfig):
        self.config = config
        self.lock = threading.Lock()
        self._init_databases()
        
    def _init_databases(self):
        """Initialize all required databases and tables"""
        try:
            self._init_sqlite()
            logger.info("Successfully initialized all databases")
        except Exception as e:
            logger.error(f"Error initializing databases: {str(e)}")
            raise
        
    def _init_sqlite(self):
        """Initialize SQLite database and create required tables"""
        try:
            # Create data directory if it doesn't exist
            data_dir = Path("data")
            data_dir.mkdir(exist_ok=True)
            
            # Get database name from config, handling both WebBotConfig and BotConfig
            if hasattr(self.config, 'sqlite_db_name'):
                db_name = self.config.sqlite_db_name
            else:
                db_name = getattr(self.config, 'sqDB_NAME', 'chat_history.db')
            
            # Use the full path for SQLite database
            db_path = data_dir / db_name
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            
            # Initialize connection and cursor
            conn = None
            cursor = None
            
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # Create users table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        first_seen REAL NOT NULL,
                        last_seen REAL NOT NULL
                    )
                ''')
                
                # Create personas table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS personas (
                        channel_name TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT NOT NULL,
                        traits TEXT NOT NULL,
                        communication_style TEXT NOT NULL,
                        response_characteristics TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        updated_at REAL NOT NULL
                    )
                ''')
                
                # Create message queue table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS new_msg_queue (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        channel_name TEXT NOT NULL,
                        content TEXT NOT NULL,
                        ts REAL NOT NULL,
                        role TEXT DEFAULT 'user'
                    )
                ''')
                
                # Create history table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        channel_name TEXT NOT NULL,
                        content TEXT NOT NULL,
                        ts REAL NOT NULL,
                        role TEXT DEFAULT 'user'
                    )
                ''')
                
                # Create context history table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS context_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        message_ts REAL NOT NULL,
                        channel_name TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        message_content TEXT NOT NULL,
                        context TEXT,
                        long_term_memory_id INTEGER,
                        response TEXT,
                        response_type TEXT
                    )
                ''')
                
                # Create long-term memories table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS long_term_memories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        channel_name TEXT NOT NULL,
                        timestamp REAL NOT NULL,
                        summary TEXT NOT NULL,
                        insights TEXT NOT NULL,
                        key_points TEXT NOT NULL,
                        participants TEXT NOT NULL,
                        conversation_start REAL,
                        conversation_end REAL
                    )
                ''')
                
                # Create room tasks table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS room_tasks (
                        room_name TEXT PRIMARY KEY,
                        task TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                conn.commit()
                logger.info("Successfully initialized SQLite database")
                
            except Exception as e:
                logger.error(f"Error initializing SQLite database: {str(e)}")
                raise
            finally:
                if cursor:
                    cursor.close()
                if conn:
                    conn.close()
            
        except Exception as e:
            logger.error(f"Error initializing SQLite database: {str(e)}")
            raise
    
    def _get_db_path(self) -> Path:
        """Get the database path handling both config types"""
        data_dir = Path("data")
        if hasattr(self.config, 'sqlite_db_name'):
            db_name = self.config.sqlite_db_name
        else:
            db_name = getattr(self.config, 'sqDB_NAME', 'chat_history.db')
        return data_dir / db_name

    def save_user(self, user_id: str, name: str, timestamp: float) -> None:
        """Save or update user information"""
        with self.lock:
            db_path = self._get_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            try:
                # Try to update existing user
                cursor.execute('''
                    UPDATE users 
                    SET name = ?, last_seen = ?
                    WHERE user_id = ?
                ''', (name, timestamp, user_id))
                
                # If no user was updated, insert new user
                if cursor.rowcount == 0:
                    cursor.execute('''
                        INSERT INTO users (user_id, name, first_seen, last_seen)
                        VALUES (?, ?, ?, ?)
                    ''', (user_id, name, timestamp, timestamp))
                
                conn.commit()
                logger.info(f"Saved user information for {name} ({user_id})")
                
            finally:
                cursor.close()
                conn.close()
                
    def get_user_name(self, user_id: str) -> Optional[str]:
        """Get user's name from database"""
        db_path = self._get_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT name FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            return result[0] if result else None
            
        finally:
            cursor.close()
            conn.close()
    
    def save_message(self, message: Message) -> None:
        """Save message to queue"""
        with self.lock:
            db_path = self._get_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            try:
                cursor.execute('''
                    INSERT INTO new_msg_queue (user_id, channel_name, content, ts, role)
                    VALUES (?, ?, ?, ?, ?)
                ''', (message.user_id, message.channel_name, message.content, message.ts, message.role))
                conn.commit()
            finally:
                cursor.close()
                conn.close()
            
    def save_to_history(self, message_dict: Dict) -> None:
        """Save message to history"""
        with self.lock:
            db_path = self._get_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            try:
                cursor.execute('''
                    INSERT INTO history (user_id, channel_name, content, ts, role)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    message_dict['user_id'],
                    message_dict['channel_name'],
                    message_dict['content'],
                    message_dict['ts'],
                    message_dict.get('role', 'user')
                ))
                conn.commit()
            finally:
                cursor.close()
                conn.close()
                
    def save_context_history(self, message: Message, context: List[Dict], response: Optional[str], response_type: str) -> None:
        """Save context history"""
        with self.lock:
            db_path = self._get_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            try:
                cursor.execute('''
                    INSERT INTO context_history (
                        message_ts, channel_name, user_id, message_content,
                        context, response, response_type
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    message.ts,
                    message.channel_name,
                    message.user_id,
                    message.content,
                    json.dumps(context),
                    response,
                    response_type
                ))
                conn.commit()
            finally:
                cursor.close()
                conn.close()
                
    def save_long_term_memory(self, memory: LongTermMemory, channel_name: str, conversation_start: float, conversation_end: float) -> int:
        """Save long-term memory and return its ID"""
        with self.lock:
            db_path = self._get_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            try:
                cursor.execute('''
                    INSERT INTO long_term_memories (
                        channel_name, timestamp, summary, insights,
                        key_points, participants, conversation_start,
                        conversation_end
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    channel_name,
                    memory.timestamp,
                    memory.summary,
                    json.dumps(memory.insights),
                    json.dumps(memory.key_points),
                    json.dumps(memory.participants),
                    conversation_start,
                    conversation_end
                ))
                conn.commit()
                return cursor.lastrowid
            finally:
                cursor.close()
                conn.close()

    def get_message_from_queue(self, channel_name: str) -> Optional[Dict]:
        """Get and remove message from queue"""
        db_path = self._get_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        try:
            # Get the oldest message for the channel
            cursor.execute('''
                SELECT user_id, channel_name, content, ts, role
                FROM new_msg_queue
                WHERE channel_name = ?
                ORDER BY ts ASC
                LIMIT 1
            ''', (channel_name,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            # Delete the retrieved message
            cursor.execute('''
                DELETE FROM new_msg_queue
                WHERE channel_name = ? AND ts = ?
            ''', (channel_name, row[3]))
            
            conn.commit()
            
            return {
                'user_id': row[0],
                'channel_name': row[1],
                'content': row[2],
                'ts': row[3],
                'role': row[4]
            }
            
        finally:
            cursor.close()
            conn.close()

    def get_history(self, options: Dict) -> List[Dict]:
        """Get conversation history based on options"""
        db_path = self._get_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        try:
            query = '''
                SELECT user_id, channel_name, content, ts, role
                FROM history
                WHERE ts >= ? AND ts <= ?
            '''
            params = [
                float(options.get('start_time', 0)),
                float(options.get('end_time', datetime.now().timestamp()))
            ]
            
            if options.get('channel'):
                query += ' AND channel_name = ?'
                params.append(options['channel'])
            
            if options.get('users'):
                placeholders = ','.join('?' * len(options['users']))
                query += f' AND user_id IN ({placeholders})'
                params.extend(options['users'])
            
            query += ' ORDER BY ts ASC'
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [{
                'user_id': row[0],
                'channel_name': row[1],
                'content': row[2],
                'ts': row[3],
                'role': row[4]
            } for row in rows]
            
        finally:
            cursor.close()
            conn.close()

    def save_persona(self, channel_name: str, personality: Personality) -> bool:
        """Save or update a persona for a channel"""
        with self.lock:
            db_path = self._get_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            try:
                current_time = time.time()
                
                # Convert personality data to JSON strings
                traits = json.dumps(personality.traits)
                communication_style = json.dumps(personality.communication_style)
                response_characteristics = json.dumps(personality.response_characteristics)
                
                # Try to update existing persona
                cursor.execute("""
                    INSERT OR REPLACE INTO personas (
                        channel_name, name, description, traits, 
                        communication_style, response_characteristics,
                        created_at, updated_at
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, 
                        COALESCE((SELECT created_at FROM personas WHERE channel_name = ?), ?),
                        ?
                    )
                """, (
                    channel_name, personality.name, personality.description,
                    traits, communication_style, response_characteristics,
                    channel_name, current_time, current_time
                ))
                
                conn.commit()
                logger.info(f"Saved persona for channel {channel_name}")
                return True
                
            except Exception as e:
                logger.error(f"Error saving persona: {str(e)}")
                return False
            finally:
                cursor.close()
                conn.close()

    def load_persona(self, channel_name: str) -> Optional[Personality]:
        """Load a persona for a channel"""
        db_path = self._get_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT name, description, traits, communication_style, response_characteristics
                FROM personas
                WHERE channel_name = ?
            """, (channel_name,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            name, description, traits_json, comm_style_json, resp_char_json = row
            
            # Parse JSON strings back to dictionaries
            traits = json.loads(traits_json)
            communication_style = json.loads(comm_style_json)
            response_characteristics = json.loads(resp_char_json)
            
            return Personality(
                name=name,
                description=description,
                traits=traits,
                communication_style=communication_style,
                response_characteristics=response_characteristics
            )
            
        except Exception as e:
            logger.error(f"Error loading persona: {str(e)}")
            return None
        finally:
            cursor.close()
            conn.close()

    def save_task(self, room_name: str, task: str) -> None:
        """Save task for a room"""
        try:
            self.db.execute(
                "INSERT OR REPLACE INTO room_tasks (room_name, task) VALUES (?, ?)",
                (room_name, task)
            )
            self.db.commit()
        except Exception as e:
            logger.error(f"Error saving task: {str(e)}", exc_info=True)

    def load_task(self, room_name: str) -> Optional[str]:
        """Load task for a room"""
        try:
            result = self.db.execute(
                "SELECT task FROM room_tasks WHERE room_name = ?",
                (room_name,)
            ).fetchone()
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Error loading task: {str(e)}", exc_info=True)
            return None

    def _initialize_tables(self):
        """Initialize database tables"""
        try:
            # Create room tasks table
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS room_tasks (
                    room_name TEXT PRIMARY KEY,
                    task TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Existing table creation code goes here
            self.db.commit()
        except Exception as e:
            logger.error(f"Error initializing tables: {str(e)}", exc_info=True)