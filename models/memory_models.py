from dataclasses import dataclass
from typing import List, Dict

@dataclass
class LongTermMemory:
    summary: str
    insights: List[str]
    key_points: List[str]
    participants: List[str]
    timestamp: float

@dataclass
class ConversationMemory:
    channel_name: str
    messages: List[Dict]  # Recent messages
    long_term_memories: List[LongTermMemory]  # Historical summaries
    last_memory_ts: float = 0