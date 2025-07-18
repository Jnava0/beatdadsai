# File: backend/task_scheduler.py
# Author: Enhanced MINI S System
# Date: January 17, 2025
# Description: Task scheduling and management system for coordinated multi-agent work

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"

class TaskPriority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

@dataclass
class Task:
    id: str
    title: str
    description: str
    assigned_agent: Optional[str]
    created_by: str
    status: TaskStatus
    priority: TaskPriority
    created_at: datetime
    updated_at: datetime
    due_date: Optional[datetime]
    dependencies: List[str]  # Task IDs this task depends on
    subtasks: List[str]  # Subtask IDs
    parent_task: Optional[str]  # Parent task ID
    metadata: Dict[str, Any]
    progress: float  # 0.0 to 1.0
    result: Optional[str]
    error_message: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['status'] = self.status.value
        data['priority'] = self.priority.value
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        if self.due_date:
            data['due_date'] = self.due_date.isoformat()
        return data

class TaskScheduler:
    """
    Advanced task scheduler for coordinating multi-agent work.
    Handles task creation, assignment, dependency management, and progress tracking.
    """
    
    def __init__(self, db_manager, message_broker):
        self.db_manager = db_manager
        self.message_broker = message_broker
        self.tasks: Dict[str, Task] = {}
        self.agent_workloads: Dict[str, List[str]] = {}  # agent_id -> task_ids
        self.task_callbacks: Dict[str, List[Callable]] = {}
        self._running = False
        
        logger.info("TaskScheduler initialized")

    async def start(self):
        """Start the task scheduler"""
        self._running = True
        # Load existing tasks from database
        await self._load_tasks_from_db()
        # Start the scheduler loop
        asyncio.create_task(self._scheduler_loop())
        logger.info("TaskScheduler started")

    async def stop(self):
        """Stop the task scheduler"""
        self._running = False
        logger.info("TaskScheduler stopped")

    async def create_task(
        self,
        title: str,
        description: str,
        created_by: str,
        assigned_agent: Optional[str] = None,
        priority: TaskPriority = TaskPriority.MEDIUM,
        due_date: Optional[datetime] = None,
        dependencies: Optional[List[str]] = None,
        parent_task: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Task:
        """Create a new task"""
        
        task = Task(
            id=str(uuid.uuid4()),
            title=title,
            description=description,
            assigned_agent=assigned_agent,
            created_by=created_by,
            status=TaskStatus.PENDING,
            priority=priority,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            due_date=due_date,
            dependencies=dependencies or [],
            subtasks=[],
            parent_task=parent_task,
            metadata=metadata or {},
            progress=0.0,
            result=None,
            error_message=None
        )
        
        self.tasks[task.id] = task
        
        # Add to parent's subtasks if applicable
        if parent_task and parent_task in self.tasks:
            self.tasks[parent_task].subtasks.append(task.id)
        
        # Save to database
        await self._save_task_to_db(task)
        
        # Auto-assign if agent specified
        if assigned_agent:
            await self.assign_task(task.id, assigned_agent)
        
        logger.info(f"Created task: {task.id} - {title}")
        return task

    async def assign_task(self, task_id: str, agent_id: str) -> bool:
        """Assign a task to an agent"""
        if task_id not in self.tasks:
            logger.error(f"Task {task_id} not found")
            return False
        
        task = self.tasks[task_id]
        
        # Check if dependencies are met
        if not await self._check_dependencies(task):
            logger.warning(f"Task {task_id} dependencies not met")
            task.status = TaskStatus.BLOCKED
            await self._update_task_in_db(task)
            return False
        
        task.assigned_agent = agent_id
        task.status = TaskStatus.ASSIGNED
        task.updated_at = datetime.now()
        
        # Add to agent workload
        if agent_id not in self.agent_workloads:
            self.agent_workloads[agent_id] = []
        self.agent_workloads[agent_id].append(task_id)
        
        # Notify agent
        message = self.message_broker.create_message(
            sender="TaskScheduler",
            recipient=agent_id,
            content=f"New task assigned: {task.title}\n\nDescription: {task.description}",
            message_type=self.message_broker.MessageType.TASK_ASSIGNMENT,
            metadata={
                "task_id": task_id,
                "priority": task.priority.value,
                "due_date": task.due_date.isoformat() if task.due_date else None
            }
        )
        
        await self.message_broker.send_message(message)
        await self._update_task_in_db(task)
        
        logger.info(f"Assigned task {task_id} to agent {agent_id}")
        return True

    async def update_task_progress(self, task_id: str, progress: float, status: Optional[TaskStatus] = None) -> bool:
        """Update task progress"""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        task.progress = max(0.0, min(1.0, progress))
        task.updated_at = datetime.now()
        
        if status:
            task.status = status
        elif progress >= 1.0:
            task.status = TaskStatus.COMPLETED
        elif progress > 0.0:
            task.status = TaskStatus.IN_PROGRESS
        
        await self._update_task_in_db(task)
        
        # Check if this completes any dependent tasks
        if task.status == TaskStatus.COMPLETED:
            await self._check_dependent_tasks(task_id)
        
        logger.info(f"Updated task {task_id} progress: {progress:.2%}")
        return True

    async def complete_task(self, task_id: str, result: Optional[str] = None) -> bool:
        """Mark a task as completed"""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        task.status = TaskStatus.COMPLETED
        task.progress = 1.0
        task.result = result
        task.updated_at = datetime.now()
        
        # Remove from agent workload
        if task.assigned_agent and task.assigned_agent in self.agent_workloads:
            if task_id in self.agent_workloads[task.assigned_agent]:
                self.agent_workloads[task.assigned_agent].remove(task_id)
        
        await self._update_task_in_db(task)
        
        # Notify task creator
        if task.created_by != task.assigned_agent:
            message = self.message_broker.create_message(
                sender="TaskScheduler",
                recipient=task.created_by,
                content=f"Task completed: {task.title}",
                message_type=self.message_broker.MessageType.TASK_COMPLETION,
                metadata={
                    "task_id": task_id,
                    "result": result
                }
            )
            await self.message_broker.send_message(message)
        
        # Check dependent tasks
        await self._check_dependent_tasks(task_id)
        
        logger.info(f"Completed task: {task_id}")
        return True

    async def fail_task(self, task_id: str, error_message: str) -> bool:
        """Mark a task as failed"""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        task.status = TaskStatus.FAILED
        task.error_message = error_message
        task.updated_at = datetime.now()
        
        # Remove from agent workload
        if task.assigned_agent and task.assigned_agent in self.agent_workloads:
            if task_id in self.agent_workloads[task.assigned_agent]:
                self.agent_workloads[task.assigned_agent].remove(task_id)
        
        await self._update_task_in_db(task)
        
        # Notify task creator
        message = self.message_broker.create_message(
            sender="TaskScheduler",
            recipient=task.created_by,
            content=f"Task failed: {task.title}\nError: {error_message}",
            message_type=self.message_broker.MessageType.NOTIFICATION,
            metadata={
                "task_id": task_id,
                "error": error_message
            }
        )
        await self.message_broker.send_message(message)
        
        logger.error(f"Task failed: {task_id} - {error_message}")
        return True

    async def get_agent_workload(self, agent_id: str) -> List[Task]:
        """Get all tasks assigned to an agent"""
        if agent_id not in self.agent_workloads:
            return []
        
        return [self.tasks[task_id] for task_id in self.agent_workloads[agent_id] 
                if task_id in self.tasks]

    async def get_available_tasks(self, agent_id: Optional[str] = None) -> List[Task]:
        """Get tasks that are ready to be assigned"""
        available_tasks = []
        
        for task in self.tasks.values():
            if (task.status == TaskStatus.PENDING and 
                await self._check_dependencies(task) and
                (agent_id is None or task.assigned_agent is None or task.assigned_agent == agent_id)):
                available_tasks.append(task)
        
        # Sort by priority and creation time
        available_tasks.sort(key=lambda t: (t.priority.value, t.created_at), reverse=True)
        return available_tasks

    async def break_down_task(self, task_id: str, subtask_descriptions: List[str], created_by: str) -> List[Task]:
        """Break down a task into subtasks"""
        if task_id not in self.tasks:
            return []
        
        parent_task = self.tasks[task_id]
        subtasks = []
        
        for i, description in enumerate(subtask_descriptions):
            subtask = await self.create_task(
                title=f"{parent_task.title} - Subtask {i+1}",
                description=description,
                created_by=created_by,
                priority=parent_task.priority,
                parent_task=task_id,
                metadata={"subtask_index": i}
            )
            subtasks.append(subtask)
        
        logger.info(f"Broke down task {task_id} into {len(subtasks)} subtasks")
        return subtasks

    async def _check_dependencies(self, task: Task) -> bool:
        """Check if all task dependencies are completed"""
        for dep_id in task.dependencies:
            if dep_id in self.tasks:
                if self.tasks[dep_id].status != TaskStatus.COMPLETED:
                    return False
            else:
                logger.warning(f"Dependency {dep_id} not found for task {task.id}")
                return False
        return True

    async def _check_dependent_tasks(self, completed_task_id: str):
        """Check and unblock tasks that depend on the completed task"""
        for task in self.tasks.values():
            if (completed_task_id in task.dependencies and 
                task.status == TaskStatus.BLOCKED and
                await self._check_dependencies(task)):
                
                task.status = TaskStatus.PENDING
                task.updated_at = datetime.now()
                await self._update_task_in_db(task)
                logger.info(f"Unblocked task {task.id}")

    async def _scheduler_loop(self):
        """Main scheduler loop for automatic task management"""
        while self._running:
            try:
                # Check for overdue tasks
                await self._check_overdue_tasks()
                
                # Auto-assign tasks if possible
                await self._auto_assign_tasks()
                
                # Clean up completed tasks older than 30 days
                await self._cleanup_old_tasks()
                
                await asyncio.sleep(60)  # Run every minute
                
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(60)

    async def _check_overdue_tasks(self):
        """Check for overdue tasks and notify"""
        now = datetime.now()
        for task in self.tasks.values():
            if (task.due_date and 
                task.due_date < now and 
                task.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.FAILED]):
                
                # Notify assigned agent and creator
                overdue_message = f"Task overdue: {task.title} (due: {task.due_date})"
                
                if task.assigned_agent:
                    message = self.message_broker.create_message(
                        sender="TaskScheduler",
                        recipient=task.assigned_agent,
                        content=overdue_message,
                        message_type=self.message_broker.MessageType.NOTIFICATION,
                        priority=3
                    )
                    await self.message_broker.send_message(message)

    async def _auto_assign_tasks(self):
        """Automatically assign tasks to available agents"""
        # This is a simple implementation - could be enhanced with load balancing
        available_tasks = await self.get_available_tasks()
        
        for task in available_tasks[:5]:  # Limit to 5 tasks per cycle
            # Find least loaded agent (simple strategy)
            min_workload = float('inf')
            best_agent = None
            
            for agent_id, workload in self.agent_workloads.items():
                if len(workload) < min_workload:
                    min_workload = len(workload)
                    best_agent = agent_id
            
            if best_agent and min_workload < 3:  # Don't overload agents
                await self.assign_task(task.id, best_agent)

    async def _cleanup_old_tasks(self):
        """Clean up old completed tasks"""
        cutoff_date = datetime.now() - timedelta(days=30)
        tasks_to_remove = []
        
        for task_id, task in self.tasks.items():
            if (task.status in [TaskStatus.COMPLETED, TaskStatus.CANCELLED] and
                task.updated_at < cutoff_date):
                tasks_to_remove.append(task_id)
        
        for task_id in tasks_to_remove:
            del self.tasks[task_id]
            # Keep in database for historical records

    async def _save_task_to_db(self, task: Task):
        """Save task to database"""
        try:
            query = """
                INSERT INTO tasks 
                (task_id, title, description, assigned_agent, created_by, status, priority, 
                 created_at, updated_at, due_date, dependencies, subtasks, parent_task, 
                 metadata, progress, result, error_message)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            params = (
                task.id, task.title, task.description, task.assigned_agent, task.created_by,
                task.status.value, task.priority.value, task.created_at, task.updated_at,
                task.due_date, json.dumps(task.dependencies), json.dumps(task.subtasks),
                task.parent_task, json.dumps(task.metadata), task.progress, task.result,
                task.error_message
            )
            
            self.db_manager.execute_query(query, params)
            
        except Exception as e:
            logger.error(f"Failed to save task to database: {e}")

    async def _update_task_in_db(self, task: Task):
        """Update task in database"""
        try:
            query = """
                UPDATE tasks SET 
                    title = %s, description = %s, assigned_agent = %s, status = %s, 
                    priority = %s, updated_at = %s, due_date = %s, dependencies = %s, 
                    subtasks = %s, metadata = %s, progress = %s, result = %s, error_message = %s
                WHERE task_id = %s
            """
            params = (
                task.title, task.description, task.assigned_agent, task.status.value,
                task.priority.value, task.updated_at, task.due_date, 
                json.dumps(task.dependencies), json.dumps(task.subtasks),
                json.dumps(task.metadata), task.progress, task.result, task.error_message,
                task.id
            )
            
            self.db_manager.execute_query(query, params)
            
        except Exception as e:
            logger.error(f"Failed to update task in database: {e}")

    async def _load_tasks_from_db(self):
        """Load existing tasks from database"""
        try:
            query = """
                SELECT task_id, title, description, assigned_agent, created_by, status, priority,
                       created_at, updated_at, due_date, dependencies, subtasks, parent_task,
                       metadata, progress, result, error_message
                FROM tasks 
                WHERE status NOT IN ('completed', 'cancelled')
            """
            
            results = self.db_manager.execute_query(query, fetch='all')
            
            for row in results:
                task = Task(
                    id=row[0],
                    title=row[1],
                    description=row[2],
                    assigned_agent=row[3],
                    created_by=row[4],
                    status=TaskStatus(row[5]),
                    priority=TaskPriority(row[6]),
                    created_at=row[7],
                    updated_at=row[8],
                    due_date=row[9],
                    dependencies=json.loads(row[10]) if row[10] else [],
                    subtasks=json.loads(row[11]) if row[11] else [],
                    parent_task=row[12],
                    metadata=json.loads(row[13]) if row[13] else {},
                    progress=row[14] or 0.0,
                    result=row[15],
                    error_message=row[16]
                )
                
                self.tasks[task.id] = task
                
                # Rebuild agent workloads
                if task.assigned_agent:
                    if task.assigned_agent not in self.agent_workloads:
                        self.agent_workloads[task.assigned_agent] = []
                    self.agent_workloads[task.assigned_agent].append(task.id)
            
            logger.info(f"Loaded {len(self.tasks)} tasks from database")
            
        except Exception as e:
            logger.error(f"Failed to load tasks from database: {e}")