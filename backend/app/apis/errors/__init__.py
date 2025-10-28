from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import os
import asyncpg
from datetime import datetime

router = APIRouter()

DATABASE_URL = os.environ.get("DATABASE_URL")

# ============================================================================
# MODELS
# ============================================================================

class ErrorReport(BaseModel):
    """Error report from frontend or build process."""
    project_id: str
    error_type: str  # 'build', 'runtime', 'api'
    message: str
    stack_trace: Optional[str] = None
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    code_snippet: Optional[str] = None
    context: Optional[dict] = None

class Error(BaseModel):
    """Error from database."""
    id: str
    project_id: str
    error_type: str
    message: str
    stack_trace: Optional[str] = None
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    code_snippet: Optional[str] = None
    context: Optional[dict] = None
    status: str
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

class ErrorsResponse(BaseModel):
    """List of errors."""
    errors: List[Error]
    total: int

class ResolveErrorRequest(BaseModel):
    """Request to mark error as resolved."""
    resolution_notes: Optional[str] = None

# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/errors/{project_id}")
async def get_errors(project_id: str, status: Optional[str] = None) -> ErrorsResponse:
    """
    Get all errors for a project.
    
    Args:
        project_id: The project ID
        status: Filter by status ('open', 'resolved') - optional
    """
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        if status:
            query = """
            SELECT id, project_id, error_type, message, stack_trace,
                   file_path, line_number, code_snippet, context,
                   status, resolved_at, created_at, updated_at
            FROM errors
            WHERE project_id = $1 AND status = $2
            ORDER BY created_at DESC
            """
            rows = await conn.fetch(query, project_id, status)
        else:
            query = """
            SELECT id, project_id, error_type, message, stack_trace,
                   file_path, line_number, code_snippet, context,
                   status, resolved_at, created_at, updated_at
            FROM errors
            WHERE project_id = $1
            ORDER BY created_at DESC
            """
            rows = await conn.fetch(query, project_id)
        
        errors = [
            Error(
                id=str(row['id']),
                project_id=str(row['project_id']),
                error_type=row['error_type'],
                message=row['message'],
                stack_trace=row['stack_trace'],
                file_path=row['file_path'],
                line_number=row['line_number'],
                code_snippet=row['code_snippet'],
                context=row['context'],
                status=row['status'],
                resolved_at=row['resolved_at'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
            for row in rows
        ]
        
        return ErrorsResponse(errors=errors, total=len(errors))
    finally:
        await conn.close()

@router.post("/errors/report")
async def report_error(error: ErrorReport) -> dict:
    """
    Report a new error.
    
    Args:
        error: Error details
    """
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        query = """
        INSERT INTO errors (
            project_id, error_type, message, stack_trace,
            file_path, line_number, code_snippet, context, status
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'open')
        RETURNING id
        """
        error_id = await conn.fetchval(
            query,
            error.project_id,
            error.error_type,
            error.message,
            error.stack_trace,
            error.file_path,
            error.line_number,
            error.code_snippet,
            error.context
        )
        
        return {
            "success": True,
            "error_id": str(error_id),
            "message": "Error reported successfully"
        }
    finally:
        await conn.close()

@router.put("/errors/{error_id}/resolve")
async def resolve_error(error_id: str, request: ResolveErrorRequest) -> dict:
    """
    Mark an error as resolved.
    
    Args:
        error_id: The error ID
        request: Optional resolution notes
    """
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        # Update context with resolution notes if provided
        if request.resolution_notes:
            query = """
            UPDATE errors
            SET status = 'resolved',
                resolved_at = NOW(),
                context = COALESCE(context, '{}'::jsonb) || jsonb_build_object('resolution_notes', $2)
            WHERE id = $1
            RETURNING id
            """
            result = await conn.fetchval(query, error_id, request.resolution_notes)
        else:
            query = """
            UPDATE errors
            SET status = 'resolved',
                resolved_at = NOW()
            WHERE id = $1
            RETURNING id
            """
            result = await conn.fetchval(query, error_id)
        
        if not result:
            raise HTTPException(status_code=404, detail="Error not found")
        
        return {
            "success": True,
            "message": "Error marked as resolved"
        }
    finally:
        await conn.close()

@router.delete("/errors/{error_id}")
async def delete_error(error_id: str) -> dict:
    """
    Delete an error.
    
    Args:
        error_id: The error ID
    """
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        query = "DELETE FROM errors WHERE id = $1 RETURNING id"
        result = await conn.fetchval(query, error_id)
        
        if not result:
            raise HTTPException(status_code=404, detail="Error not found")
        
        return {
            "success": True,
            "message": "Error deleted successfully"
        }
    finally:
        await conn.close()

@router.post("/errors/test/{project_id}")
async def test_error_detection(project_id: str):
    """
    Test endpoint to verify error detection is working.
    Creates a test project with intentional errors.
    """
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        # Create test files with errors
        test_files = [
            {
                "filepath": "src/BadComponent.tsx",
                "content": """import React from 'react';

export const BadComponent = () => {
  // This will cause a build error - undefined variable
  const result = undefinedVariable + 123;
  
  return <div>{result}</div>;
};
"""
            },
            {
                "filepath": "src/RuntimeError.tsx",
                "content": """import React from 'react';

export const RuntimeError = () => {
  // This will cause runtime error
  const obj: any = null;
  const value = obj.someProperty;
  
  return <div>{value}</div>;
};
"""
            },
            {
                "filepath": "src/PromiseError.tsx",
                "content": """import React, { useEffect } from 'react';

export const PromiseError = () => {
  useEffect(() => {
    // This will cause unhandled promise rejection
    Promise.reject(new Error('Test promise rejection'));
  }, []);
  
  return <div>Promise Error Test</div>;
};
"""
            }
        ]
        
        # Insert test files into database
        for file in test_files:
            query = """
            INSERT INTO files (project_id, filepath, content, created_at, updated_at)
            VALUES ($1, $2, $3, NOW(), NOW())
            ON CONFLICT (project_id, filepath) 
            DO UPDATE SET content = $3, updated_at = NOW()
            """
            await conn.execute(query, project_id, file["filepath"], file["content"])
        
        return {
            "success": True,
            "message": "Test files created. Now run POST /preview/build/{project_id} to trigger error detection.",
            "files_created": len(test_files),
            "next_step": f"POST /preview/build/{project_id}"
        }
    finally:
        await conn.close()
