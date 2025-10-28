"""AI Context Loader - Prepares rich context for AI operations.

This module provides context awareness to AI operations by loading:
- Project information (title, description)
- Recent files and code
- Active and completed tasks
- Unresolved errors
- Recent chat history
- Stored AI memory

Usage:
    from app.libs.ai_context_loader import AIContextLoader
    
    async with AIContextLoader(project_id) as loader:
        # Load full context
        context = await loader.load_context()
        
        # Format for AI prompt
        system_prompt = loader.format_for_prompt(context)
        
        # Update AI memory
        await loader.update_memory(
            current_task="debugging",
            files_generated=["App.tsx"],
        )
"""

import os
import json
from typing import Any, Dict, List, Optional
from datetime import datetime

from app.libs.context_builder import ContextBuilder


class AIContextLoader:
    """Loads and formats project context for AI awareness."""
    
    def __init__(self, project_id: str):
        """Initialize context loader for a specific project.
        
        Args:
            project_id: UUID of the project
        """
        self.project_id = project_id
        self.context_builder: Optional[ContextBuilder] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.context_builder = ContextBuilder(self.project_id)
        await self.context_builder.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.context_builder:
            await self.context_builder.__aexit__(exc_type, exc_val, exc_tb)
    
    async def load_context(
        self,
        include_files: bool = True,
        include_tasks: bool = True,
        include_errors: bool = True,
        include_chat: bool = True,
        max_files: int = 15,
        max_chat_messages: int = 10,
        max_context_size: int = 25000,  # ~6k tokens
    ) -> Dict[str, Any]:
        """Load full project context.
        
        Args:
            include_files: Include recent file contents
            include_tasks: Include active and completed tasks
            include_errors: Include unresolved errors
            include_chat: Include recent chat history
            max_files: Maximum number of files to include
            max_chat_messages: Maximum chat messages to include
            max_context_size: Maximum context size in characters
        
        Returns:
            Full project context dictionary
        """
        if not self.context_builder:
            raise RuntimeError("AIContextLoader must be used as async context manager")
        
        # Build full context
        context = await self.context_builder.build_full_context(
            include_files=include_files,
            include_tasks=include_tasks,
            include_errors=include_errors,
            include_chat=include_chat,
            max_files=max_files,
            max_chat_messages=max_chat_messages,
        )
        
        # Optimize if too large
        size = self.context_builder.estimate_context_size(context)
        if size > max_context_size:
            context = self.context_builder.optimize_context(context, max_context_size)
        
        return context
    
    def format_for_prompt(self, context: Dict[str, Any]) -> str:
        """Format project context into AI-friendly system prompt.
        
        Args:
            context: Project context from load_context()
        
        Returns:
            Formatted system prompt string
        """
        sections = []
        
        # Header
        sections.append("# CURRENT PROJECT STATE")
        sections.append("")
        sections.append("This is the current state of the project you're working on. Use this information to maintain awareness of what exists, what's in progress, and what needs attention.")
        sections.append("")
        
        # Project info
        if context.get("project_info"):
            info = context["project_info"]
            sections.append("## Project Overview")
            sections.append(f"**Name:** {info.get('name', 'Unnamed Project')}")
            if info.get('description'):
                sections.append(f"**Description:** {info['description']}")
            sections.append("")
        
        # Current tasks
        if context.get("tasks"):
            tasks = context["tasks"]
            active = tasks.get("active", [])
            completed = tasks.get("recently_completed", [])
            
            if active:
                sections.append("## 📋 Active Tasks")
                for task in active:
                    status = task.get('status', 'unknown').upper()
                    priority = task.get('priority', 'medium')
                    sections.append(f"\n**{task['title']}** `[{status}]` `Priority: {priority}`")
                    if task.get('description'):
                        desc = task['description'][:300]
                        if len(task['description']) > 300:
                            desc += "..."
                        sections.append(f"{desc}")
                sections.append("")
            
            if completed:
                sections.append("## ✅ Recently Completed")
                for task in completed[:5]:
                    sections.append(f"- {task['title']}")
                sections.append("")
        
        # Recent errors
        if context.get("errors"):
            errors = context["errors"]
            if errors:
                sections.append("## ⚠️ Unresolved Errors")
                sections.append(f"There are currently {len(errors)} error(s) that need attention:")
                sections.append("")
                for i, error in enumerate(errors[:3], 1):
                    sections.append(f"**Error {i}: {error['type']}**")
                    sections.append(f"- File: `{error.get('file', 'Unknown')}`")
                    if error.get('line'):
                        sections.append(f"- Line: {error['line']}")
                    sections.append(f"- Message: {error['message']}")
                    if error.get('stack'):
                        stack = error['stack'][:200]
                        if len(error['stack']) > 200:
                            stack += "\n... (truncated)"
                        sections.append(f"```\n{stack}\n```")
                    sections.append("")
                
                if len(errors) > 3:
                    sections.append(f"*... and {len(errors) - 3} more errors*")
                    sections.append("")
        
        # Project files
        if context.get("files"):
            files = context["files"]
            if files:
                sections.append("## 📁 Project Files")
                sections.append(f"The project contains {len(files)} file(s):")
                sections.append("")
                
                # Group files by type
                apis = [f for f in files if '/apis/' in f['filepath']]
                pages = [f for f in files if '/pages/' in f['filepath']]
                components = [f for f in files if '/components/' in f['filepath']]
                libs = [f for f in files if '/libs/' in f['filepath']]
                utils = [f for f in files if '/utils/' in f['filepath']]
                other = [f for f in files if f not in apis + pages + components + libs + utils]
                
                if apis:
                    sections.append("**Backend APIs:**")
                    for f in apis[:5]:
                        sections.append(f"- `{f['filepath']}`")
                    if len(apis) > 5:
                        sections.append(f"  *... and {len(apis) - 5} more*")
                    sections.append("")
                
                if pages:
                    sections.append("**Frontend Pages:**")
                    for f in pages[:5]:
                        sections.append(f"- `{f['filepath']}`")
                    if len(pages) > 5:
                        sections.append(f"  *... and {len(pages) - 5} more*")
                    sections.append("")
                
                if components:
                    sections.append("**UI Components:**")
                    for f in components[:5]:
                        sections.append(f"- `{f['filepath']}`")
                    if len(components) > 5:
                        sections.append(f"  *... and {len(components) - 5} more*")
                    sections.append("")
                
                if libs:
                    sections.append("**Backend Libraries:**")
                    for f in libs[:3]:
                        sections.append(f"- `{f['filepath']}`")
                    if len(libs) > 3:
                        sections.append(f"  *... and {len(libs) - 3} more*")
                    sections.append("")
                
                if other:
                    sections.append("**Other Files:**")
                    for f in other[:3]:
                        sections.append(f"- `{f['filepath']}`")
                    if len(other) > 3:
                        sections.append(f"  *... and {len(other) - 3} more*")
                    sections.append("")
        
        # Stored AI memory
        if context.get("stored_context"):
            stored = context["stored_context"]
            if stored.get("data"):
                data = stored["data"]
                sections.append("## 🧠 AI Memory (From Previous Session)")
                
                memory_items = []
                
                if data.get('current_phase'):
                    memory_items.append(f"**Phase:** {data['current_phase']}")
                
                if data.get('current_task'):
                    memory_items.append(f"**Task:** {data['current_task']}")
                
                if data.get('files_generated'):
                    files_gen = data['files_generated']
                    count = len(files_gen)
                    examples = ', '.join(files_gen[:3])
                    if count > 3:
                        examples += f" and {count - 3} more"
                    memory_items.append(f"**Generated Files:** {examples}")
                
                if data.get('tasks_completed'):
                    tasks_done = data['tasks_completed']
                    count = len(tasks_done)
                    examples = ', '.join(tasks_done[:3])
                    if count > 3:
                        examples += f" and {count - 3} more"
                    memory_items.append(f"**Completed:** {examples}")
                
                if data.get('ai_memory'):
                    memory = data['ai_memory']
                    memory_items.append("**Notes:**")
                    for key, value in list(memory.items())[:3]:
                        memory_items.append(f"  - {key}: {value}")
                
                sections.extend(memory_items)
                sections.append("")
        
        # Recent conversation (minimal)
        if context.get("chat_history"):
            history = context["chat_history"]
            if history and len(history) > 0:
                sections.append("## 💬 Recent Conversation Context")
                # Only show last 3 messages for brevity
                for msg in history[-3:]:
                    role = msg['role'].capitalize()
                    content = msg['content'][:150]
                    if len(msg['content']) > 150:
                        content += "..."
                    sections.append(f"**{role}:** {content}")
                sections.append("")
        
        # Footer
        sections.append("---")
        sections.append("*Use this context to understand the current state and make informed decisions.*")
        sections.append("")
        
        return "\n".join(sections)
    
    async def update_memory(
        self,
        current_phase: Optional[str] = None,
        current_task: Optional[str] = None,
        files_generated: Optional[List[str]] = None,
        tasks_completed: Optional[List[str]] = None,
        recent_errors: Optional[List[str]] = None,
        ai_memory: Optional[Dict[str, Any]] = None,
        merge: bool = True,
    ) -> None:
        """Update AI memory/context after an operation.
        
        Args:
            current_phase: Current phase of work
            current_task: Current task being worked on
            files_generated: List of file paths generated
            tasks_completed: List of task IDs completed
            recent_errors: List of error IDs encountered
            ai_memory: Additional memory to store
            merge: If True, merge with existing. If False, replace.
        """
        if not self.context_builder:
            raise RuntimeError("AIContextLoader must be used as async context manager")
        
        from uuid import UUID
        conn = self.context_builder.conn
        
        # Build update data
        context_data = {}
        
        if current_phase is not None:
            context_data["current_phase"] = current_phase
        
        if current_task is not None:
            context_data["current_task"] = current_task
        
        if files_generated is not None:
            context_data["files_generated"] = files_generated
        
        if tasks_completed is not None:
            context_data["tasks_completed"] = tasks_completed
        
        if recent_errors is not None:
            context_data["recent_errors"] = recent_errors
        
        if ai_memory is not None:
            context_data["ai_memory"] = ai_memory
        
        if merge:
            # Get existing
            existing = await conn.fetchrow(
                "SELECT context_data FROM agent_context WHERE project_id = $1",
                UUID(self.project_id),
            )
            
            if existing:
                existing_data = existing["context_data"] or {}
                
                # Merge arrays
                if "files_generated" in context_data and "files_generated" in existing_data:
                    context_data["files_generated"] = list(set(
                        existing_data["files_generated"] + context_data["files_generated"]
                    ))
                
                if "tasks_completed" in context_data and "tasks_completed" in existing_data:
                    context_data["tasks_completed"] = list(set(
                        existing_data["tasks_completed"] + context_data["tasks_completed"]
                    ))
                
                if "recent_errors" in context_data and "recent_errors" in existing_data:
                    all_errors = existing_data["recent_errors"] + context_data["recent_errors"]
                    context_data["recent_errors"] = all_errors[-10:]
                
                # Deep merge ai_memory
                if "ai_memory" in context_data and "ai_memory" in existing_data:
                    merged_memory = existing_data["ai_memory"].copy()
                    merged_memory.update(context_data["ai_memory"])
                    context_data["ai_memory"] = merged_memory
                
                existing_data.update(context_data)
                context_data = existing_data
        
        # Upsert
        await conn.execute(
            """
            INSERT INTO agent_context (project_id, context_data)
            VALUES ($1, $2::jsonb)
            ON CONFLICT (project_id)
            DO UPDATE SET
                context_data = $2::jsonb,
                updated_at = NOW()
            """,
            UUID(self.project_id),
            json.dumps(context_data),
        )
    
    async def reset_memory(self) -> None:
        """Reset AI memory for the project."""
        if not self.context_builder:
            raise RuntimeError("AIContextLoader must be used as async context manager")
        
        from uuid import UUID
        await self.context_builder.conn.execute(
            "DELETE FROM agent_context WHERE project_id = $1",
            UUID(self.project_id),
        )
