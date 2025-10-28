"""AI Context Management API

Provides endpoints for storing and retrieving AI agent's project context.
This enables the AI to maintain awareness across sessions.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Any, Dict, Optional
import asyncpg
import os
from uuid import UUID
from datetime import datetime

from app.libs.database import get_db_connection

router = APIRouter()

DATABASE_URL = os.environ.get("DATABASE_URL")


class ContextData(BaseModel):
    """Structure for AI context data."""
    current_phase: Optional[str] = None
    files_generated: list[str] = []
    tasks_completed: list[str] = []
    current_task: Optional[str] = None
    recent_errors: list[Dict[str, Any]] = []
    ai_memory: Dict[str, Any] = {}
    

class UpdateContextRequest(BaseModel):
    """Request to update AI context."""
    project_id: str
    session_id: Optional[str] = None
    context_data: ContextData
    merge: bool = True  # If True, merge with existing; if False, replace


class ContextResponse(BaseModel):
    """Response containing AI context."""
    project_id: str
    session_id: Optional[str] = None
    context_data: ContextData
    updated_at: datetime
    created_at: datetime


@router.get("/context/{project_id}")
async def get_context(project_id: str) -> ContextResponse:
    """
    Get AI context for a project.
    Returns the agent's memory and awareness of project state.
    """
    conn = await get_db_connection()
    try:
        context = await conn.fetchrow(
            """
            SELECT 
                project_id, session_id, context_data, 
                created_at, updated_at
            FROM agent_context
            WHERE project_id = $1
            """,
            UUID(project_id),
        )
        
        if not context:
            # Return empty context if none exists
            return ContextResponse(
                project_id=project_id,
                session_id=None,
                context_data=ContextData(),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        
        return ContextResponse(
            project_id=str(context["project_id"]),
            session_id=context["session_id"],
            context_data=ContextData(**context["context_data"]),
            created_at=context["created_at"],
            updated_at=context["updated_at"],
        )
        
    finally:
        await conn.close()


@router.post("/context/update")
async def update_context(request: UpdateContextRequest) -> ContextResponse:
    """
    Update AI context for a project.
    If merge=True, merges with existing context.
    If merge=False, replaces entire context.
    """
    conn = await get_db_connection()
    try:
        # Check if context exists
        existing = await conn.fetchrow(
            "SELECT context_data FROM agent_context WHERE project_id = $1",
            UUID(request.project_id),
        )
        
        if existing and request.merge:
            # Merge with existing context
            existing_data = existing["context_data"]
            new_data = request.context_data.model_dump()
            
            # Smart merge: combine lists, update scalars
            merged = {**existing_data}
            
            # Merge files_generated (unique)
            if new_data.get("files_generated"):
                existing_files = set(existing_data.get("files_generated", []))
                new_files = set(new_data["files_generated"])
                merged["files_generated"] = list(existing_files | new_files)
            
            # Merge tasks_completed (unique)
            if new_data.get("tasks_completed"):
                existing_tasks = set(existing_data.get("tasks_completed", []))
                new_tasks = set(new_data["tasks_completed"])
                merged["tasks_completed"] = list(existing_tasks | new_tasks)
            
            # Keep only recent errors (last 10)
            if new_data.get("recent_errors"):
                existing_errors = existing_data.get("recent_errors", [])
                merged["recent_errors"] = (
                    existing_errors + new_data["recent_errors"]
                )[-10:]
            
            # Update current state
            if new_data.get("current_phase"):
                merged["current_phase"] = new_data["current_phase"]
            
            if new_data.get("current_task"):
                merged["current_task"] = new_data["current_task"]
            
            # Merge ai_memory
            if new_data.get("ai_memory"):
                existing_memory = existing_data.get("ai_memory", {})
                merged["ai_memory"] = {**existing_memory, **new_data["ai_memory"]}
            
            context_data = merged
        else:
            context_data = request.context_data.model_dump()
        
        # Upsert context
        result = await conn.fetchrow(
            """
            INSERT INTO agent_context (project_id, session_id, context_data)
            VALUES ($1, $2, $3)
            ON CONFLICT (project_id)
            DO UPDATE SET
                session_id = EXCLUDED.session_id,
                context_data = EXCLUDED.context_data,
                updated_at = NOW()
            RETURNING project_id, session_id, context_data, created_at, updated_at
            """,
            UUID(request.project_id),
            request.session_id,
            context_data,
        )
        
        return ContextResponse(
            project_id=str(result["project_id"]),
            session_id=result["session_id"],
            context_data=ContextData(**result["context_data"]),
            created_at=result["created_at"],
            updated_at=result["updated_at"],
        )
        
    finally:
        await conn.close()


@router.post("/context/reset/{project_id}")
async def reset_context(project_id: str) -> dict[str, str]:
    """
    Reset AI context for a project.
    Clears all stored memory and state.
    """
    conn = await get_db_connection()
    try:
        await conn.execute(
            "DELETE FROM agent_context WHERE project_id = $1",
            UUID(project_id),
        )
        
        return {
            "success": True,
            "message": f"Context reset for project {project_id}",
        }
        
    finally:
        await conn.close()
