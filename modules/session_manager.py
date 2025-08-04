import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union, Any
from datetime import datetime


logger = logging.getLogger(__name__)


@dataclass
class MessageData:
    message: str
    thread_id: Optional[str] = None

@dataclass
class UserSession:
    user_id: Union[int, str]
    chat_id: Union[int, str]
    message_queue: List[MessageData] = field(default_factory=list)
    is_executing: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    
    def add_message(self, message: str, thread_id: Optional[str] = None):
        """Add message to queue"""
        self.message_queue.append(MessageData(message=message, thread_id=thread_id))
        self.last_activity = datetime.now()
    
    
    def get_next_message(self) -> Optional[Dict[str, Any]]:
        """Get and remove the next message from queue"""
        if self.message_queue:
            message_data = self.message_queue.pop(0)
            self.last_activity = datetime.now()
            return {
                'message': message_data.message,
                'thread_id': message_data.thread_id
            }
        return None
    
    def clear_queue(self):
        """Clear message queue"""
        self.message_queue.clear()
        self.last_activity = datetime.now()
    
    def get_status(self) -> str:
        """Get session status summary"""
        status = f"📊 Session Status\n"
        status += f"━━━━━━━━━━━━━━━━\n"
        status += f"User ID: {self.user_id}\n"
        status += f"Messages in queue: {len(self.message_queue)}\n"
        status += f"Status: {'🟢 Processing' if self.is_executing else '⭕ Idle'}\n"
        status += f"Last activity: {self.last_activity.strftime('%Y-%m-%d %H:%M:%S')}"
        
        if self.message_queue:
            status += "\n\n📋 Queued messages:"
            for idx, msg_data in enumerate(self.message_queue, 1):
                msg = msg_data.message
                preview = msg[:50] + "..." if len(msg) > 50 else msg
                status += f"\n{idx}. {preview}"
        elif self.is_executing:
            status += "\n\n⏳ Currently processing your message..."
        else:
            status += "\n\n💤 No messages in queue"
        
        return status


class SessionManager:
    def __init__(self):
        self.sessions: Dict[Union[int, str], UserSession] = {}
        self._lock = asyncio.Lock()
    
    async def get_or_create_session(self, user_id: Union[int, str], chat_id: Union[int, str]) -> UserSession:
        """Get existing session or create new one"""
        async with self._lock:
            if user_id not in self.sessions:
                self.sessions[user_id] = UserSession(user_id=user_id, chat_id=chat_id)
                logger.info(f"Created new session for user {user_id}")
            
            return self.sessions[user_id]
    
    async def add_message(self, user_id: Union[int, str], chat_id: Union[int, str], message: str) -> str:
        """Add message to user's queue"""
        session = await self.get_or_create_session(user_id, chat_id)
        session.add_message(message)
        
        return f"Message added to queue. Total messages: {len(session.message_queue)}"
    
    async def add_message_with_context(self, user_id: Union[int, str], chat_id: Union[int, str], 
                                      message: str, thread_id: Optional[str] = None) -> str:
        """Add message with thread context to user's queue"""
        session = await self.get_or_create_session(user_id, chat_id)
        session.add_message(message, thread_id=thread_id)
        
        return f"Message added to queue. Total messages: {len(session.message_queue)}"
    
    async def get_next_message(self, user_id: Union[int, str]) -> Optional[str]:
        """Get next message from user's queue (legacy method)"""
        message_data = await self.get_next_message_with_context(user_id)
        return message_data['message'] if message_data else None
    
    async def get_next_message_with_context(self, user_id: Union[int, str]) -> Optional[Dict[str, Any]]:
        """Get next message with thread context from user's queue"""
        if user_id not in self.sessions:
            return None
        
        session = self.sessions[user_id]
        return session.get_next_message()
    
    async def has_messages(self, user_id: Union[int, str]) -> bool:
        """Check if user has messages in queue"""
        if user_id not in self.sessions:
            return False
        return len(self.sessions[user_id].message_queue) > 0
    
    async def get_queue_details(self, user_id: Union[int, str]) -> str:
        """Get detailed queue information for user"""
        if user_id not in self.sessions:
            return "No active session. Send a message to start."
        
        session = self.sessions[user_id]
        
        if not session.message_queue:
            if session.is_executing:
                return "📋 Queue is empty\n⏳ Currently executing a message..."
            else:
                return "📋 Queue is empty\n💤 No messages to process"
        
        queue_info = f"📋 Message Queue ({len(session.message_queue)} messages)\n"
        queue_info += f"Status: {'🟢 Processing' if session.is_executing else '⭕ Waiting'}\n\n"
        
        for idx, msg_data in enumerate(session.message_queue, 1):
            # Show first 100 characters of each message
            msg = msg_data.message
            preview = msg[:100] + "..." if len(msg) > 100 else msg
            # Replace newlines with spaces for better display
            preview = preview.replace('\n', ' ').replace('\r', ' ')
            queue_info += f"{idx}. {preview}\n"
        
        return queue_info
    
    async def clear_queue(self, user_id: Union[int, str]) -> str:
        """Clear user's message queue"""
        if user_id not in self.sessions:
            return "No active session found."
        
        session = self.sessions[user_id]
        message_count = len(session.message_queue)
        session.clear_queue()
        
        return f"Cleared {message_count} messages from queue."
    
    async def get_status(self, user_id: Union[int, str]) -> str:
        """Get user's session status"""
        if user_id not in self.sessions:
            return "No active session. Send a message to start."
        
        session = self.sessions[user_id]
        return session.get_status()
    
    async def set_executing(self, user_id: Union[int, str], is_executing: bool):
        """Set execution status for user session"""
        if user_id in self.sessions:
            async with self._lock:
                self.sessions[user_id].is_executing = is_executing
                self.sessions[user_id].last_activity = datetime.now()
    
    async def is_executing(self, user_id: Union[int, str]) -> bool:
        """Check if user has an active execution"""
        if user_id not in self.sessions:
            return False
        return self.sessions[user_id].is_executing
    
    async def cleanup_inactive_sessions(self, inactive_hours: int = 24):
        """Clean up inactive sessions"""
        async with self._lock:
            current_time = datetime.now()
            to_remove = []
            
            for user_id, session in self.sessions.items():
                time_diff = current_time - session.last_activity
                if time_diff.total_seconds() > inactive_hours * 3600:
                    to_remove.append(user_id)
            
            for user_id in to_remove:
                del self.sessions[user_id]
                logger.info(f"Cleaned up inactive session for user {user_id}")
            
            return len(to_remove)