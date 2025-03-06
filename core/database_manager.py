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
import uuid

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
            
            # Initialize tables using the _initialize_tables method
            self._initialize_tables()
            
            logger.info(f"Successfully initialized SQLite database at {db_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing SQLite database: {str(e)}")
            return False
    
    def _get_db_path(self) -> Path:
        """Get the database path handling both config types"""
        data_dir = Path("data")
        if hasattr(self.config, 'sqlite_db_name'):
            db_name = self.config.sqlite_db_name
        else:
            db_name = getattr(self.config, 'sqDB_NAME', 'chat_history.db')
        return data_dir / db_name

    def save_user(self, user_id: str, name: str, timestamp: float, room_id: str) -> None:
        """Save or update user information"""
        with self.lock:
            db_path = self._get_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            try:
                # Try to update existing user
                cursor.execute('''
                    UPDATE users 
                    SET name = ?, timestamp = ?, room_id = ?
                    WHERE user_id = ?
                ''', (name, timestamp, room_id, user_id))
                
                # If no user was updated, insert new user
                if cursor.rowcount == 0:
                    cursor.execute('''
                        INSERT INTO users (user_id, name, timestamp, room_id)
                        VALUES (?, ?, ?, ?)
                    ''', (user_id, name, timestamp, room_id))
                
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
        """Save a message to the database with room_id"""
        try:
            # Get a fresh connection to the database with timeout
            db_path = self._get_db_path()
            conn = sqlite3.connect(db_path, timeout=30.0, isolation_level=None)
            cursor = conn.cursor()
            
            try:
                # Begin immediate transaction to acquire a write lock
                cursor.execute('BEGIN IMMEDIATE')
                
                # Generate an ID if not present
                message_id = getattr(message, 'id', str(uuid.uuid4()))
                
                # Extract channel_name from message
                channel_name = message.channel_name
                
                # Insert into messages table with room_id
                cursor.execute(
                    "INSERT INTO messages (id, content, user_id, room_id, timestamp, type) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        message_id,
                        message.content,
                        message.user_id,
                        channel_name,  # Use channel_name as room_id
                        message.ts,  # Use ts as timestamp
                        message.type
                    )
                )
                
                # Commit the transaction
                cursor.execute('COMMIT')
                
                logger.info(f"Saved message {message_id} to database for room {channel_name}")
                
                # Also save to history table with field names matching what save_to_history expects
                # This is done in a separate transaction to avoid holding locks too long
                history_data = {
                    'id': message_id,
                    'content': message.content,
                    'user_id': message.user_id,
                    'room_id': channel_name,
                    'channel_name': channel_name,  # Required by save_to_history
                    'ts': message.ts,  # Required by save_to_history (not 'timestamp')
                    'type': message.type,
                    'role': getattr(message, 'role', 'user')  # Required by save_to_history
                }
                
                # Save to history in a separate try block to avoid dependency
                self.save_to_history(history_data)
                
            except Exception as e:
                # Rollback if there's an error
                try:
                    cursor.execute('ROLLBACK')
                except:
                    pass
                logger.error(f"Error saving message to database: {str(e)}")
                raise
            finally:
                cursor.close()
                conn.close()
        except Exception as e:
            logger.error(f"Error in save_message: {str(e)}")
            # Don't re-raise to allow the application to continue
            
    def save_to_history(self, message_dict: Dict) -> None:
        """Save message to history"""
        # Use a local lock instead of self.lock to prevent deadlocks
        try:
            db_path = self._get_db_path()
            # Add timeout and isolation_level parameters to prevent locking
            conn = sqlite3.connect(db_path, timeout=30.0, isolation_level=None)
            cursor = conn.cursor()
            
            try:
                # Begin immediate transaction to acquire a write lock
                cursor.execute('BEGIN IMMEDIATE')
                
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
                
                # Explicitly commit the transaction
                cursor.execute('COMMIT')
                
            except Exception as e:
                # Rollback if there's an error
                try:
                    cursor.execute('ROLLBACK')
                except:
                    pass
                logger.error(f"Error saving to history: {str(e)}")
                raise
            finally:
                cursor.close()
                conn.close()
        except Exception as e:
            logger.error(f"Error in save_to_history: {str(e)}")
            # Re-raise the exception to let the caller handle it
            raise
                
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
        """Get message history with room_id filtering"""
        try:
            # Get a fresh connection to the database with timeout
            db_path = self._get_db_path()
            conn = sqlite3.connect(db_path, timeout=30.0)
            cursor = conn.cursor()
            
            try:
                # Base query
                query = "SELECT * FROM messages WHERE 1=1"
                params = []
                
                # Filter by room_id if provided
                if options.get('room_id'):
                    query += " AND room_id = ?"
                    params.append(options['room_id'])
                
                # Filter by channel_name if provided (alternative to room_id)
                elif options.get('channel_name'):
                    query += " AND room_id = ?"
                    params.append(options['channel_name'])
                    
                # Filter by user_id if provided
                if options.get('user_id'):
                    query += " AND user_id = ?"
                    params.append(options['user_id'])
                
                # Add timestamp constraints if provided
                if options.get('start_time'):
                    query += " AND timestamp >= ?"
                    params.append(options['start_time'])
                
                if options.get('end_time'):
                    query += " AND timestamp <= ?"
                    params.append(options['end_time'])
                
                # Add limit if provided
                if options.get('limit'):
                    query += " ORDER BY timestamp DESC LIMIT ?"
                    params.append(options['limit'])
                else:
                    query += " ORDER BY timestamp DESC"
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                # Convert to list of dictionaries
                messages = []
                for row in rows:
                    messages.append({
                        'id': row[0],
                        'content': row[1],
                        'user_id': row[2],
                        'room_id': row[3],
                        'channel_name': row[3],  # Add channel_name as alias for room_id
                        'timestamp': row[4],
                        'ts': row[4],  # Add ts as alias for timestamp
                        'type': row[5]
                    })
                    
                return messages
            finally:
                cursor.close()
                conn.close()
        except Exception as e:
            logger.error(f"Error retrieving message history: {str(e)}")
            return []

    def save_persona(self, channel_name: str, personality: Personality) -> bool:
        """Save or update a persona for a channel"""
        with self.lock:
            db_path = self._get_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            try:
                current_time = time.time()
                
                # Convert personality to dictionary format and then to JSON
                personality_dict = personality.to_dict()
                traits = json.dumps(personality_dict["traits"])
                response_characteristics = json.dumps(personality_dict["response_characteristics"])
                communication_style = personality_dict.get("communication_style", "standard") 
                
                # Try to update existing persona
                cursor.execute("""
                    INSERT OR REPLACE INTO personas (
                        channel_name, name, description, traits, 
                        response_characteristics, communication_style,
                        created_at, updated_at
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, 
                        COALESCE((SELECT created_at FROM personas WHERE channel_name = ?), ?),
                        ?
                    )
                """, (
                    channel_name, personality.name, personality.description,
                    traits, response_characteristics, communication_style,
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
                SELECT name, description, traits, response_characteristics, communication_style
                FROM personas
                WHERE channel_name = ?
            """, (channel_name,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            name, description, traits_json, resp_char_json, communication_style = row
            
            # Parse JSON strings back to dictionaries
            traits = json.loads(traits_json)
            response_characteristics = json.loads(resp_char_json)
            
            # Create personality dictionary and convert to Personality object
            personality_dict = {
                "name": name,
                "description": description,
                "traits": traits,
                "response_characteristics": response_characteristics,
                "communication_style": communication_style or "standard"
            }
            
            return Personality.from_dict(personality_dict)
            
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
            db_path = self._get_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Create messages table with room_id column
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                content TEXT,
                user_id TEXT,
                room_id TEXT,
                timestamp REAL,
                type TEXT
            )
            ''')
            
            # Create index on room_id for faster queries
            cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_messages_room_id ON messages(room_id)
            ''')
            
            # Create history table if it doesn't exist
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                channel_name TEXT,
                content TEXT,
                ts REAL,
                role TEXT DEFAULT 'user'
            )
            ''')
            
            # Create index on channel_name for faster queries
            cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_history_channel_name ON history(channel_name)
            ''')
            
            # Create users table - add room_id field
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                name TEXT,
                room_id TEXT,
                timestamp REAL
            )
            ''')
            
            # Create index on room_id for users table
            cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_users_room_id ON users(room_id)
            ''')
            
            # Create personas table if it doesn't exist - match table name with save_persona
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS personas (
                channel_name TEXT PRIMARY KEY,
                name TEXT,
                description TEXT,
                traits TEXT,
                response_characteristics TEXT,
                communication_style TEXT,
                created_at REAL,
                updated_at REAL
            )
            ''')
            
            # Create message queue table if it doesn't exist
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS new_msg_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                channel_name TEXT,
                content TEXT,
                ts REAL,
                role TEXT DEFAULT 'user'
            )
            ''')
            
            # Create long-term memories table if it doesn't exist
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS long_term_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_name TEXT,
                timestamp REAL,
                summary TEXT,
                insights TEXT,
                key_points TEXT,
                participants TEXT,
                conversation_start REAL,
                conversation_end REAL
            )
            ''')
            
            # Create context history table if it doesn't exist
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS context_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_ts REAL,
                channel_name TEXT,
                user_id TEXT,
                message_content TEXT,
                context TEXT,
                long_term_memory_id INTEGER,
                response TEXT,
                response_type TEXT
            )
            ''')
            
            # Create room_tasks table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS room_tasks (
                    room_name TEXT PRIMARY KEY,
                task TEXT,
                timestamp REAL
                )
            ''')
            
            conn.commit()
            logger.info("Database tables initialized successfully")
        except Exception as e:
            conn.rollback()
            logger.error(f"Error initializing database tables: {str(e)}")
            raise
        finally:
            cursor.close()
            conn.close()