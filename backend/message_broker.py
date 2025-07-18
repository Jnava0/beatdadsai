# File: backend/message_broker.py
# Author: Enhanced MINI S System
# Date: January 17, 2025
# Description: Internal messaging system for agent-to-agent communication

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)

class MessageType(Enum):
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    TASK_ASSIGNMENT = "task_assignment"
    TASK_COMPLETION = "task_completion"
    BROADCAST = "broadcast"
    SYSTEM = "system"

@dataclass
class Message:
    id: str
    sender: str
    recipient: str
    message_type: MessageType
    content: str
    metadata: Dict[str, Any]
    timestamp: datetime
    conversation_id: Optional[str] = None
    requires_response: bool = False
    priority: int = 1  # 1=low, 2=medium, 3=high

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['message_type'] = self.message_type.value
        data['timestamp'] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        data['message_type'] = MessageType(data['message_type'])
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)

class MessageBroker:
    """
    Central message broker for agent-to-agent communication.
    Handles message routing, queuing, and delivery with support for
    different communication patterns.
    """
    
    def __init__(self, db_manager=None):
        self.db_manager = db_manager
        self.agent_queues: Dict[str, asyncio.Queue] = {}
        self.message_handlers: Dict[str, List[Callable]] = {}
        self.active_conversations: Dict[str, List[str]] = {}
        self.broadcast_channels: Dict[str, List[str]] = {}
        self._running = False
        
        logger.info("MessageBroker initialized")

    async def start(self):
        """Start the message broker"""
        self._running = True
        logger.info("MessageBroker started")

    async def stop(self):
        """Stop the message broker"""
        self._running = False
        logger.info("MessageBroker stopped")

    def register_agent(self, agent_id: str) -> asyncio.Queue:
        """Register an agent and return its message queue"""
        if agent_id not in self.agent_queues:
            self.agent_queues[agent_id] = asyncio.Queue()
            self.message_handlers[agent_id] = []
            logger.info(f"Registered agent: {agent_id}")
        
        return self.agent_queues[agent_id]

    def unregister_agent(self, agent_id: str):
        """Unregister an agent"""
        if agent_id in self.agent_queues:
            del self.agent_queues[agent_id]
            del self.message_handlers[agent_id]
            logger.info(f"Unregistered agent: {agent_id}")

    async def send_message(self, message: Message) -> bool:
        """Send a message to the specified recipient"""
        try:
            # Log the message to database if available
            if self.db_manager:
                await self._log_message_to_db(message)
            
            # Handle broadcast messages
            if message.recipient == "ALL" or message.message_type == MessageType.BROADCAST:
                return await self._broadcast_message(message)
            
            # Handle direct messages
            if message.recipient in self.agent_queues:
                await self.agent_queues[message.recipient].put(message)
                logger.info(f"Message sent from {message.sender} to {message.recipient}")
                return True
            else:
                logger.warning(f"Recipient {message.recipient} not found")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False

    async def _broadcast_message(self, message: Message) -> bool:
        """Broadcast a message to all registered agents"""
        success_count = 0
        for agent_id in self.agent_queues:
            if agent_id != message.sender:  # Don't send to sender
                try:
                    broadcast_msg = Message(
                        id=str(uuid.uuid4()),
                        sender=message.sender,
                        recipient=agent_id,
                        message_type=message.message_type,
                        content=message.content,
                        metadata=message.metadata,
                        timestamp=message.timestamp,
                        conversation_id=message.conversation_id
                    )
                    await self.agent_queues[agent_id].put(broadcast_msg)
                    success_count += 1
                except Exception as e:
                    logger.error(f"Failed to broadcast to {agent_id}: {e}")
        
        logger.info(f"Broadcast message sent to {success_count} agents")
        return success_count > 0

    async def receive_message(self, agent_id: str, timeout: Optional[float] = None) -> Optional[Message]:
        """Receive a message for the specified agent"""
        if agent_id not in self.agent_queues:
            return None
        
        try:
            if timeout:
                message = await asyncio.wait_for(
                    self.agent_queues[agent_id].get(), 
                    timeout=timeout
                )
            else:
                message = await self.agent_queues[agent_id].get()
            
            logger.debug(f"Message received by {agent_id}")
            return message
            
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            logger.error(f"Error receiving message for {agent_id}: {e}")
            return None

    def create_message(
        self,
        sender: str,
        recipient: str,
        content: str,
        message_type: MessageType = MessageType.REQUEST,
        metadata: Optional[Dict[str, Any]] = None,
        conversation_id: Optional[str] = None,
        requires_response: bool = False,
        priority: int = 1
    ) -> Message:
        """Create a new message"""
        return Message(
            id=str(uuid.uuid4()),
            sender=sender,
            recipient=recipient,
            message_type=message_type,
            content=content,
            metadata=metadata or {},
            timestamp=datetime.now(),
            conversation_id=conversation_id,
            requires_response=requires_response,
            priority=priority
        )

    async def create_conversation(self, participants: List[str]) -> str:
        """Create a new conversation between multiple agents"""
        conversation_id = str(uuid.uuid4())
        self.active_conversations[conversation_id] = participants
        logger.info(f"Created conversation {conversation_id} with participants: {participants}")
        return conversation_id

    async def join_broadcast_channel(self, agent_id: str, channel: str):
        """Join an agent to a broadcast channel"""
        if channel not in self.broadcast_channels:
            self.broadcast_channels[channel] = []
        
        if agent_id not in self.broadcast_channels[channel]:
            self.broadcast_channels[channel].append(agent_id)
            logger.info(f"Agent {agent_id} joined channel {channel}")

    async def leave_broadcast_channel(self, agent_id: str, channel: str):
        """Remove an agent from a broadcast channel"""
        if channel in self.broadcast_channels and agent_id in self.broadcast_channels[channel]:
            self.broadcast_channels[channel].remove(agent_id)
            logger.info(f"Agent {agent_id} left channel {channel}")

    async def _log_message_to_db(self, message: Message):
        """Log message to database for audit trail"""
        if not self.db_manager:
            return
        
        try:
            query = """
                INSERT INTO agent_communications 
                (message_id, sender_id, recipient_id, message_type, content, metadata, timestamp, conversation_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            params = (
                message.id,
                message.sender,
                message.recipient,
                message.message_type.value,
                message.content,
                json.dumps(message.metadata),
                message.timestamp,
                message.conversation_id
            )
            
            self.db_manager.execute_query(query, params)
            
        except Exception as e:
            logger.error(f"Failed to log message to database: {e}")

    async def get_conversation_history(self, conversation_id: str, limit: int = 50) -> List[Message]:
        """Get conversation history from database"""
        if not self.db_manager:
            return []
        
        try:
            query = """
                SELECT message_id, sender_id, recipient_id, message_type, content, metadata, timestamp, conversation_id
                FROM agent_communications 
                WHERE conversation_id = %s 
                ORDER BY timestamp DESC 
                LIMIT %s
            """
            
            results = self.db_manager.execute_query(query, (conversation_id, limit), fetch='all')
            
            messages = []
            for row in results:
                message = Message(
                    id=row[0],
                    sender=row[1],
                    recipient=row[2],
                    message_type=MessageType(row[3]),
                    content=row[4],
                    metadata=json.loads(row[5]) if row[5] else {},
                    timestamp=row[6],
                    conversation_id=row[7]
                )
                messages.append(message)
            
            return list(reversed(messages))  # Return in chronological order
            
        except Exception as e:
            logger.error(f"Failed to get conversation history: {e}")
            return []

    def get_agent_queue_size(self, agent_id: str) -> int:
        """Get the number of pending messages for an agent"""
        if agent_id in self.agent_queues:
            return self.agent_queues[agent_id].qsize()
        return 0

    def get_system_stats(self) -> Dict[str, Any]:
        """Get system statistics"""
        return {
            "registered_agents": len(self.agent_queues),
            "active_conversations": len(self.active_conversations),
            "broadcast_channels": len(self.broadcast_channels),
            "total_queued_messages": sum(q.qsize() for q in self.agent_queues.values()),
            "running": self._running
        }