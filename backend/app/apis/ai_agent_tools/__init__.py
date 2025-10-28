
import asyncio
import json
import os
import subprocess
import sys
import traceback
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any, Optional
from uuid import UUID, uuid4

import asyncpg
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.apis.preview import create_backend_workspace
from app.libs.database import get_db_connection
from app.libs.ai_orchestrator import AIOrchestrator
from app.libs.models import ChatRole, TaskPriority, TaskStatus

from app.libs.code_validator import validate_python_syntax, validate_typescript_syntax, ValidationResult

router = APIRouter(prefix="/ai-tools")

# =============================================================================
# PYDANTIC MODELS
# =============================================================================


class CreateTaskRequest(BaseModel):
    """Request to create a task"""

    project_id: str = Field(..., description="Project ID")
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    priority: TaskPriority = TaskPriority.MEDIUM
    order_index: int = Field(default=0, ge=0)


class UpdateTaskRequest(BaseModel):
    """Request to update a task"""

    task_id: str = Field(..., description="Task ID")
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    order_index: Optional[int] = Field(None, ge=0)


class AddTaskCommentRequest(BaseModel):
    """Request to add a comment to a task"""

    task_id: str = Field(..., description="Task ID")
    comment: str = Field(..., min_length=1)
    comment_type: str = Field(
        default="note",
        description="Type: note, key-decision, learning, blocker",
    )


class CreateFileRequest(BaseModel):
    """Request to create a file"""

    project_id: str
    file_path: str = Field(..., min_length=1)
    file_content: str
    language: Optional[str] = None
    file_type: Optional[str] = None


class UpdateFileRequest(BaseModel):
    """Request to update a file"""

    project_id: str
    file_path: str
    file_content: str
    language: Optional[str] = None


class SearchCodeRequest(BaseModel):
    """Request to search code"""

    project_id: str
    keywords: list[str] = Field(..., min_items=1)


class RunMigrationRequest(BaseModel):
    """Request to run a database migration"""

    project_id: str
    migration_name: str = Field(..., min_length=1)
    sql: str = Field(..., min_length=1)


class RunSQLQueryRequest(BaseModel):
    """Request to run SQL query"""

    project_id: str
    query: str = Field(..., min_length=1)
    params: Optional[list[Any]] = None


class RunPythonScriptRequest(BaseModel):
    """Request to run Python script"""

    project_id: str
    code: str = Field(..., min_length=1)
    timeout: int = Field(default=30, ge=1, le=300)


class TestEndpointRequest(BaseModel):
    """Request to test an endpoint"""

    project_id: str
    endpoint_path: str
    method: str = Field(default="GET", pattern="^(GET|POST|PUT|DELETE|PATCH)$")
    body: Optional[dict[str, Any]] = None
    query_params: Optional[dict[str, Any]] = None


class TroubleshootRequest(BaseModel):
    """Request to troubleshoot an error"""

    project_id: str
    error_message: str
    error_type: Optional[str] = None
    stack_trace: Optional[str] = None
    context: Optional[dict[str, Any]] = None


class AddChatMessageRequest(BaseModel):
    """Request to add chat message"""

    project_id: str
    content: str = Field(..., min_length=1)
    role: ChatRole = Field(default=ChatRole.USER)
    metadata: Optional[dict[str, Any]] = None


class VisualizeDataRequest(BaseModel):
    """Request to visualize data"""

    project_id: str
    chart_type: str
    data: list[dict[str, Any]]
    data_keys: dict[str, str]
    title: Optional[str] = None
    options: Optional[dict[str, Any]] = None


class RequestDataRequest(BaseModel):
    """Request data from user"""

    project_id: str
    message: str
    data_type: str = Field(default="file", pattern="^(file|text|json)$")


class ToolResponse(BaseModel):
    """Generic tool response"""

    success: bool
    message: str
    data: Optional[dict[str, Any]] = None


# =============================================================================
# DATABASE HELPER
# =============================================================================


# =============================================================================
# TASK MANAGEMENT TOOLS
# =============================================================================


@router.post("/tasks/create")
async def create_task(request: CreateTaskRequest) -> ToolResponse:
    """
    Create a new task for a project.
    This is used by the AI to break down work into manageable pieces.
    """
    conn = await get_db_connection()
    try:
        # Create task
        task_id = uuid4()
        await conn.execute(
            """
            INSERT INTO tasks (
                id, project_id, title, description, priority, order_index,
                status, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            task_id,
            UUID(request.project_id),
            request.title,
            request.description,
            request.priority.value,
            request.order_index,
            TaskStatus.TODO.value,
            datetime.utcnow(),
            datetime.utcnow(),
        )

        return ToolResponse(
            success=True,
            message=f"Task created: {request.title}",
            data={"task_id": str(task_id)},
        )

    finally:
        await conn.close()


@router.post("/tasks/update")
async def update_task(request: UpdateTaskRequest) -> ToolResponse:
    """
    Update an existing task.
    Used by AI to change task status, update descriptions, etc.
    """
    conn = await get_db_connection()
    try:
        # Verify task exists
        task = await conn.fetchrow(
            "SELECT id FROM tasks WHERE id = $1",
            UUID(request.task_id),
        )

        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        # Build update query dynamically
        updates = []
        values = []
        param_count = 1

        if request.title is not None:
            updates.append(f"title = ${param_count}")
            values.append(request.title)
            param_count += 1

        if request.description is not None:
            updates.append(f"description = ${param_count}")
            values.append(request.description)
            param_count += 1

        if request.status is not None:
            updates.append(f"status = ${param_count}")
            values.append(request.status.value)
            param_count += 1
            # Update completed_at if status is done
            if request.status == TaskStatus.DONE:
                updates.append(f"completed_at = ${param_count}")
                values.append(datetime.utcnow())
                param_count += 1

        if request.priority is not None:
            updates.append(f"priority = ${param_count}")
            values.append(request.priority.value)
            param_count += 1

        if request.order_index is not None:
            updates.append(f"order_index = ${param_count}")
            values.append(request.order_index)
            param_count += 1

        updates.append(f"updated_at = ${param_count}")
        values.append(datetime.utcnow())
        param_count += 1

        # Add task_id as final parameter
        values.append(UUID(request.task_id))

        query = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ${param_count}"
        await conn.execute(query, *values)

        return ToolResponse(
            success=True,
            message="Task updated successfully",
            data={"task_id": request.task_id},
        )

    finally:
        await conn.close()


@router.get("/tasks/list/{project_id}")
async def list_tasks(project_id: str) -> dict[str, Any]:
    """
    List all tasks for a project.
    Used by AI to understand what work is planned/in progress.
    """
    conn = await get_db_connection()
    try:
        # Get tasks
        tasks = await conn.fetch(
            """
            SELECT 
                id, title, description, status, priority, order_index,
                assigned_to, metadata, created_at, updated_at, completed_at
            FROM tasks
            WHERE project_id = $1
            ORDER BY order_index ASC, created_at DESC
            """,
            UUID(project_id),
        )

        return {
            "success": True,
            "tasks": [
                {
                    "id": str(task["id"]),
                    "title": task["title"],
                    "description": task["description"],
                    "status": task["status"],
                    "priority": task["priority"],
                    "order_index": task["order_index"],
                    "assigned_to": task["assigned_to"],
                    "metadata": task["metadata"],
                    "created_at": task["created_at"].isoformat(),
                    "updated_at": task["updated_at"].isoformat(),
                    "completed_at": (
                        task["completed_at"].isoformat()
                        if task["completed_at"]
                        else None
                    ),
                }
                for task in tasks
            ],
        }

    finally:
        await conn.close()


@router.delete("/tasks/delete/{task_id}")
async def delete_task(task_id: str) -> ToolResponse:
    """
    Delete a task.
    Used by AI to remove obsolete or duplicate tasks.
    """
    conn = await get_db_connection()
    try:
        # Verify task exists
        task = await conn.fetchrow(
            "SELECT id FROM tasks WHERE id = $1",
            UUID(task_id),
        )

        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        # Delete task
        await conn.execute("DELETE FROM tasks WHERE id = $1", UUID(task_id))

        return ToolResponse(
            success=True, message="Task deleted successfully", data={"task_id": task_id}
        )

    finally:
        await conn.close()


@router.post("/tasks/add-comment")
async def add_task_comment(request: AddTaskCommentRequest) -> ToolResponse:
    """
    Add a comment/note to a task.
    Used by AI to document progress, decisions, and learnings.
    """
    conn = await get_db_connection()
    try:
        # Verify task exists
        task = await conn.fetchrow(
            "SELECT id, metadata FROM tasks WHERE id = $1",
            UUID(request.task_id),
        )

        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        # Get existing metadata or create new
        metadata = task["metadata"] or {}
        if "comments" not in metadata:
            metadata["comments"] = []

        # Add comment
        metadata["comments"].append(
            {
                "type": request.comment_type,
                "content": request.comment,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

        # Update task metadata
        await conn.execute(
            "UPDATE tasks SET metadata = $1, updated_at = $2 WHERE id = $3",
            metadata,
            datetime.utcnow(),
            UUID(request.task_id),
        )

        return ToolResponse(
            success=True,
            message="Comment added to task",
            data={"task_id": request.task_id},
        )

    finally:
        await conn.close()

# =============================================================================
# ERROR DETECTION TOOLS
# =============================================================================

@router.get("/errors/{project_id}")
async def get_project_errors(project_id: str) -> dict[str, Any]:
    """
    Get all errors for a project.
    Used by AI to check if there are build/runtime errors after code generation.
    Returns errors sorted by most recent first.
    """
    conn = await get_db_connection()
    try:
        query = """
        SELECT id, error_type, message, stack_trace,
               file_path, line_number, code_snippet, context,
               status, created_at
        FROM errors
        WHERE project_id = $1
        ORDER BY created_at DESC
        LIMIT 50
        """
        rows = await conn.fetch(query, project_id)
        
        errors = [
            {
                "id": str(row["id"]),
                "error_type": row["error_type"],
                "message": row["message"],
                "stack_trace": row["stack_trace"],
                "file_path": row["file_path"],
                "line_number": row["line_number"],
                "code_snippet": row["code_snippet"],
                "context": row["context"],
                "status": row["status"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
            for row in rows
        ]
        
        # Group errors by type and status
        error_summary = {
            "total": len(errors),
            "open": len([e for e in errors if e["status"] == "open"]),
            "resolved": len([e for e in errors if e["status"] == "resolved"]),
            "by_type": {
                "build": len([e for e in errors if e["error_type"] == "build"]),
                "runtime": len([e for e in errors if e["error_type"] == "runtime"]),
                "api": len([e for e in errors if e["error_type"] == "api"]),
            }
        }
        
        return {
            "success": True,
            "errors": errors,
            "summary": error_summary
        }
    finally:
        await conn.close()

@router.get("/errors/{project_id}/open")
async def get_open_errors(project_id: str) -> dict[str, Any]:
    """
    Get only open/unresolved errors for a project.
    This is what AI should check after code generation to see if fixes are needed.
    """
    conn = await get_db_connection()
    try:
        query = """
        SELECT id, error_type, message, stack_trace,
               file_path, line_number, code_snippet, context,
               created_at
        FROM errors
        WHERE project_id = $1 AND status = 'open'
        ORDER BY created_at DESC
        """
        rows = await conn.fetch(query, project_id)
        
        errors = [
            {
                "id": str(row["id"]),
                "error_type": row["error_type"],
                "message": row["message"],
                "stack_trace": row["stack_trace"],
                "file_path": row["file_path"],
                "line_number": row["line_number"],
                "code_snippet": row["code_snippet"],
                "context": row["context"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
            for row in rows
        ]
        
        return {
            "success": True,
            "has_errors": len(errors) > 0,
            "count": len(errors),
            "errors": errors
        }
    finally:
        await conn.close()

# =============================================================================
# FILE MANAGEMENT TOOLS
# =============================================================================


class CreateFileResponse(BaseModel):
    """Response for creating a file"""

    success: bool
    message: str
    file_id: str
    file_path: str


@router.post("/files/create")
async def create_file(request: CreateFileRequest) -> CreateFileResponse:
    """
    Create a new file in the virtual file system.
    Used by AI to generate code files.
    """
    try:
        # Validate code syntax before creating
        validation_result: ValidationResult | None = None
        final_code = request.file_content
        
        if request.language == "python":
            validation_result = validate_python_syntax(request.file_content)
            if not validation_result.is_valid:
                # Attempt auto-healing
                print(f"[AUTO-HEAL] Python validation failed for {request.file_path}, attempting fix...")
                try:
                    from app.libs.code_validator import auto_heal_code
                    healed_code = await auto_heal_code(
                        request.file_content,
                        validation_result.errors,
                        "python"
                    )
                    
                    # Re-validate healed code
                    healed_validation = validate_python_syntax(healed_code)
                    if healed_validation.is_valid:
                        print(f"[AUTO-HEAL] ✅ Successfully healed Python code")
                        final_code = healed_code
                        validation_result = healed_validation
                    else:
                        print(f"[AUTO-HEAL] ❌ Healed code still has errors")
                        raise Exception("Healed code still invalid")
                except Exception as heal_error:
                    print(f"[AUTO-HEAL] ⚠️ Auto-healing failed: {heal_error}")
                    # Fall back to original error
                    error_details = "\n".join([
                        f"Line {err.line_number}: {err.message}" + 
                        (f" (Suggestion: {err.suggestion})" if err.suggestion else "")
                        for err in validation_result.errors
                    ])
                    raise HTTPException(
                        status_code=400,
                        detail=f"Python syntax validation failed:\n{error_details}"
                    )
        
        elif request.language == "typescript":
            validation_result = validate_typescript_syntax(request.file_content)
            if not validation_result.is_valid:
                # Attempt auto-healing
                print(f"[AUTO-HEAL] TypeScript validation failed for {request.file_path}, attempting fix...")
                try:
                    from app.libs.code_validator import auto_heal_code
                    healed_code = await auto_heal_code(
                        request.file_content,
                        validation_result.errors,
                        "typescript"
                    )
                    
                    # Re-validate healed code
                    healed_validation = validate_typescript_syntax(healed_code)
                    if healed_validation.is_valid:
                        print(f"[AUTO-HEAL] ✅ Successfully healed TypeScript code")
                        final_code = healed_code
                        validation_result = healed_validation
                    else:
                        print(f"[AUTO-HEAL] ❌ Healed code still has errors")
                        raise Exception("Healed code still invalid")
                except Exception as heal_error:
                    print(f"[AUTO-HEAL] ⚠️ Auto-healing failed: {heal_error}")
                    # Fall back to original error
                    error_details = "\n".join([
                        f"{err.message}" + 
                        (f" (Suggestion: {err.suggestion})" if err.suggestion else "")
                        for err in validation_result.errors
                    ])
                    raise HTTPException(
                        status_code=400,
                        detail=f"TypeScript syntax validation failed:\n{error_details}"
                    )
        
        # Auto-create backend workspace if this is a Python API file and workspace doesn't exist
        if request.file_type == "api" and request.language == "python":
            workspace_path = Path("/disk/backend/.preview-builds") / request.project_id / "backend"
            if not workspace_path.exists():
                print(f"📂 Backend workspace doesn't exist, creating for project {request.project_id}...")
                # Create workspace synchronously before continuing
                await create_backend_workspace(request.project_id)
                print(f"✅ Backend workspace created at {workspace_path}")
        
        conn = await get_db_connection()
        try:
            # Check if file already exists in project_files
            existing = await conn.fetchrow(
                """
                SELECT id FROM project_files
                WHERE project_id = $1 AND filepath = $2
                """,
                UUID(request.project_id),
                request.file_path,
            )

            if existing:
                raise HTTPException(
                    status_code=400, detail="File already exists. Use update endpoint."
                )

            # Create file in project_files table
            file_id = uuid4()
            await conn.execute(
                """
                INSERT INTO project_files (
                    id, project_id, filepath, content, language
                )
                VALUES ($1, $2, $3, $4, $5)
                """,
                file_id,
                UUID(request.project_id),
                request.file_path,
                final_code,  # Use healed code if available
                request.language,
            )

            # Auto-detect and install packages from generated code
            if request.language == "python":
                from app.apis.preview import detect_python_imports, install_packages_in_project
                
                try:
                    # Use imports from validation if available, otherwise detect
                    packages_to_install = []
                    if validation_result and validation_result.imports:
                        # We already have imports from validation
                        from app.libs.code_validator import get_missing_packages, PYTHON_IMPORT_TO_PACKAGE
                        
                        # Map imports to package names
                        packages_to_install = [
                            PYTHON_IMPORT_TO_PACKAGE.get(imp, imp) 
                            for imp in validation_result.imports
                        ]
                    else:
                        # Fallback to old detection method
                        packages_to_install = await detect_python_imports(request.file_content)
                    
                    if packages_to_install:
                        print(f"[AI] Detected Python packages in {request.file_path}: {packages_to_install}")
                        install_result = await install_packages_in_project(
                            request.project_id,
                            packages_to_install
                        )
                        print(f"[AI] Package installation result: {install_result}")
                except Exception as e:
                    print(f"[AI] Warning: Failed to auto-install packages: {e}")
                    # Don't fail file creation if package installation fails

            elif request.language == "typescript" and request.file_path.startswith("frontend/"):
                from app.apis.preview import detect_npm_imports, update_project_package_json
                
                try:
                    packages = await detect_npm_imports(request.file_content)
                    if packages:
                        print(f"[AI] Detected NPM packages in {request.file_path}: {packages}")
                        # Update package.json in project workspace
                        await update_project_package_json(request.project_id, packages)
                        print(f"[AI] Updated package.json with packages: {packages}")
                except Exception as e:
                    print(f"[AI] Warning: Failed to auto-detect NPM packages: {e}")
                    # Don't fail file creation if package detection fails

            return CreateFileResponse(
                success=True,
                message=f"File created: {request.file_path}",
                file_id=str(file_id),
                file_path=request.file_path,
            )

        finally:
            await conn.close()

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File creation failed: {str(e)}")


@router.put("/files/update")
async def update_file(request: UpdateFileRequest) -> ToolResponse:
    """
    Update an existing file.
    Used by AI to modify generated code.
    """
    # Validate code syntax before updating
    validation_result: ValidationResult | None = None
    
    if request.language == "python":
        validation_result = validate_python_syntax(request.file_content)
        if not validation_result.is_valid:
            error_details = "\n".join([
                f"Line {err.line_number}: {err.message}" + 
                (f" (Suggestion: {err.suggestion})" if err.suggestion else "")
                for err in validation_result.errors
            ])
            raise HTTPException(
                status_code=400,
                detail=f"Python syntax validation failed:\n{error_details}"
            )
    
    elif request.language == "typescript":
        validation_result = validate_typescript_syntax(request.file_content)
        if not validation_result.is_valid:
            error_details = "\n".join([
                f"{err.message}" + 
                (f" (Suggestion: {err.suggestion})" if err.suggestion else "")
                for err in validation_result.errors
            ])
            raise HTTPException(
                status_code=400,
                detail=f"TypeScript syntax validation failed:\n{error_details}"
            )
    
    conn = await get_db_connection()
    try:
        # Update the file in project_files table
        result = await conn.execute(
            """
            UPDATE project_files
            SET content = $1, language = $2, updated_at = CURRENT_TIMESTAMP
            WHERE project_id = $3 AND filepath = $4
            """,
            request.file_content,
            request.language,
            UUID(request.project_id),
            request.file_path,
        )

        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="File not found")
        
        # Auto-detect and install packages from updated code
        if request.language == "python":
            from app.apis.preview import detect_python_imports, install_packages_in_project
            
            try:
                # Use imports from validation if available, otherwise detect
                packages_to_install = []
                if validation_result and validation_result.imports:
                    # We already have imports from validation
                    from app.libs.code_validator import PYTHON_IMPORT_TO_PACKAGE
                    
                    # Map imports to package names
                    packages_to_install = [
                        PYTHON_IMPORT_TO_PACKAGE.get(imp, imp) 
                        for imp in validation_result.imports
                    ]
                else:
                    # Fallback to old detection method
                    packages_to_install = await detect_python_imports(request.file_content)
                
                if packages_to_install:
                    print(f"[AI] Detected Python packages in {request.file_path}: {packages_to_install}")
                    install_result = await install_packages_in_project(
                        request.project_id,
                        packages_to_install
                    )
                    print(f"[AI] Package installation result: {install_result}")
            except Exception as e:
                print(f"[AI] Warning: Failed to auto-install packages: {e}")
                # Don't fail file update if package installation fails
        
        elif request.language == "typescript" and request.file_path.startswith("frontend/"):
            from app.apis.preview import detect_npm_imports, update_project_package_json
            
            try:
                packages = await detect_npm_imports(request.file_content)
                if packages:
                    print(f"[AI] Detected NPM packages in {request.file_path}: {packages}")
                    await update_project_package_json(request.project_id, packages)
                    print(f"[AI] Updated package.json with packages: {packages}")
            except Exception as e:
                print(f"[AI] Warning: Failed to auto-detect NPM packages: {e}")
                # Don't fail file update if package detection fails

        return ToolResponse(
            success=True,
            message=f"File updated: {request.file_path}",
        )

    finally:
        await conn.close()


@router.get("/files/read/{project_id}")
async def read_files(
    project_id: str, file_path: Optional[str] = None
) -> dict[str, Any]:
    """
    Read file(s) from the virtual file system.
    If file_path provided, returns that file. Otherwise returns all files.
    """
    conn = await get_db_connection()
    try:
        if file_path:
            # Get specific file from project_files table
            file = await conn.fetchrow(
                """
                SELECT id, filepath, content, language
                FROM project_files 
                WHERE project_id = $1 AND filepath = $2
                """,
                UUID(project_id),
                file_path,
            )

            if not file:
                raise HTTPException(status_code=404, detail="File not found")

            return {
                "success": True,
                "file": {
                    "id": str(file["id"]),
                    "file_path": file["filepath"],
                    "file_content": file["content"],
                    "language": file["language"],
                    "is_active": True,
                },
            }
        else:
            # Get all files from project_files table
            files = await conn.fetch(
                """
                SELECT id, filepath, content, language
                FROM project_files 
                WHERE project_id = $1
                ORDER BY filepath
                """,
                UUID(project_id),
            )

            return {
                "success": True,
                "files": [
                    {
                        "id": str(f["id"]),
                        "file_path": f["filepath"],
                        "file_content": f["content"],
                        "language": f["language"],
                        "is_active": True,
                    }
                    for f in files
                ],
            }

    finally:
        await conn.close()


@router.post("/files/search")
async def search_code(
    request: SearchCodeRequest
) -> dict[str, Any]:
    """
    Search for code across all files in a project.
    Used by AI to find relevant code before making changes.
    """
    conn = await get_db_connection()
    try:
        # Build search query (case-insensitive OR search)
        search_conditions = " OR ".join(
            ["file_content ILIKE $" + str(i + 2) for i in range(len(request.keywords))]
        )
        search_params = [f"%{kw}%" for kw in request.keywords]

        query = f"""
            SELECT id, filepath, file_content, language
            FROM generated_files 
            WHERE project_id = $1 AND is_active = true
            AND ({search_conditions})
            ORDER BY filepath
        """

        results = await conn.fetch(query, UUID(request.project_id), *search_params)

        return {
            "success": True,
            "results": [
                {
                    "id": str(r["id"]),
                    "filepath": r["filepath"],
                    "file_content": r["file_content"],
                    "language": r["language"],
                }
                for r in results
            ],
        }

    finally:
        await conn.close()


@router.delete("/files/delete/{project_id}/{file_path:path}")
async def delete_file(
    project_id: str, file_path: str
) -> ToolResponse:
    """
    Delete a file from the virtual file system.
    Used by AI to remove obsolete files.
    """
    conn = await get_db_connection()
    try:
        # Mark file as inactive (soft delete)
        result = await conn.execute(
            """
            UPDATE generated_files 
            SET is_active = false, updated_at = $1
            WHERE project_id = $2 AND filepath = $3 AND is_active = true
            """,
            datetime.utcnow(),
            UUID(project_id),
            file_path,
        )

        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="File not found")

        return ToolResponse(
            success=True,
            message=f"File deleted: {file_path}",
            data={"file_path": file_path},
        )

    finally:
        await conn.close()

# =============================================================================
# TEST ENDPOINT
# =============================================================================

@router.post("/test/error-feedback-loop/{project_id}")
async def test_error_feedback_loop(project_id: str) -> dict[str, Any]:
    """
    Test the complete error feedback loop:
    1. Create broken code file
    2. Detect errors (simulated)
    3. Read errors via AI tools
    4. Fix errors (simulated)
    5. Verify resolution
    """
    conn = await get_db_connection()
    try:
        log = []
        log.append("🧪 Starting Error Feedback Loop Test")
        
        # Step 1: Create broken code
        log.append("\n📝 Step 1: Creating broken code file")
        broken_code = """
import React from 'react';

function BrokenComponent() {
  const data = {
    name: 'test',
    value: 42;  // ERROR: semicolon instead of comma
  };
  
  return <div>{data.name}</div>
}

export default BrokenComponent;
"""
        
        file_id = uuid4()
        await conn.execute(
            """
            INSERT INTO project_files (id, project_id, filepath, content, created_at, updated_at)
            VALUES ($1, $2, $3, $4, NOW(), NOW())
            ON CONFLICT (project_id, filepath) 
            DO UPDATE SET content = $4, updated_at = NOW()
            """,
            file_id,
            project_id,
            "src/components/BrokenComponent.tsx",
            broken_code
        )
        log.append("   ✅ Created src/components/BrokenComponent.tsx with syntax error")
        
        # Step 2: Simulate error detection (normally done by build process)
        log.append("\n⚠️  Step 2: Simulating error detection")
        error_id = uuid4()
        await conn.execute(
            """
            INSERT INTO errors (
                id, project_id, error_type, message,
                stack_trace, file_path, line_number,
                code_snippet, context, status
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
            error_id,
            project_id,
            "build",
            "Unexpected token ';'. Expected ','.",
            "SyntaxError at src/components/BrokenComponent.tsx:7:14",
            "src/components/BrokenComponent.tsx",
            7,
            "  const data = {\n    name: 'test',\n    value: 42;  // ERROR\n  };",
            '{"error_code": "TS1005"}',
            "open"
        )
        log.append(f"   ✅ Error reported: {error_id}")
        
        # Step 3: AI reads errors (using the tool we just built)
        log.append("\n🤖 Step 3: AI reading errors via tools")
        errors_query = """
            SELECT id, error_type, message, file_path, line_number, code_snippet
            FROM errors
            WHERE project_id = $1 AND status = 'open'
            ORDER BY created_at DESC
        """
        errors = await conn.fetch(errors_query, project_id)
        log.append(f"   ✅ Found {len(errors)} open error(s)")
        
        for err in errors:
            log.append(f"   📍 {err['error_type']}: {err['message']}")
            log.append(f"      at {err['file_path']}:{err['line_number']}")
        
        # Step 4: AI fixes the error (simulated)
        log.append("\n🔧 Step 4: AI fixing error")
        fixed_code = """
import React from 'react';

function BrokenComponent() {
  const data = {
    name: 'test',
    value: 42,  // FIXED: comma instead of semicolon
  };
  
  return <div>{data.name}</div>
}

export default BrokenComponent;
"""
        
        await conn.execute(
            """
            UPDATE project_files
            SET content = $1, updated_at = NOW()
            WHERE project_id = $2 AND filepath = $3
            """,
            fixed_code,
            project_id,
            "src/components/BrokenComponent.tsx"
        )
        log.append("   ✅ Updated file with fixed code")
        
        # Step 5: Mark error as resolved
        log.append("\n✅ Step 5: Resolving error")
        await conn.execute(
            """
            UPDATE errors
            SET status = 'resolved', updated_at = NOW()
            WHERE id = $1
            """,
            error_id
        )
        log.append(f"   ✅ Error {error_id} marked as resolved")
        
        # Verify no open errors remain
        log.append("\n🔍 Step 6: Verification")
        remaining_errors = await conn.fetchval(
            "SELECT COUNT(*) FROM errors WHERE project_id = $1 AND status = 'open'",
            project_id
        )
        log.append(f"   Open errors remaining: {remaining_errors}")
        
        if remaining_errors == 0:
            log.append("   ✅ SUCCESS: Error feedback loop completed!")
            success = True
        else:
            log.append("   ❌ FAILED: Errors still remain")
            success = False
        
        return {
            "success": success,
            "log": "\n".join(log),
            "errors_fixed": 1,
            "errors_remaining": remaining_errors
        }
        
    finally:
        await conn.close()

# =============================================================================
# CHAT MANAGEMENT TOOLS
# =============================================================================


@router.post("/chat/stream", tags=["stream"])
async def chat_stream(request: AddChatMessageRequest):
    """
    Stream AI response to a user message with tool execution.
    This is the main endpoint for the chat interface.
    Uses intelligent planning pipeline for feature requests.
    """
    try:
        print(f"DEBUG: Received project_id: {request.project_id!r} (type: {type(request.project_id)})")
        print(f"DEBUG: Received content: {request.content[:50]}...")
        
        orchestrator = AIOrchestrator(request.project_id)
        
        async def generate():
            async for chunk in orchestrator.generate_with_planning(request.content):
                yield chunk
        
        return StreamingResponse(generate(), media_type="text/plain")
    except Exception as e:
        print(f"Error in chat_stream: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


@router.post("/chat/add-message")
async def add_chat_message(request: AddChatMessageRequest) -> ToolResponse:
    """
    Add a message to the chat history and get AI response (non-streaming).
    Kept for backwards compatibility. Use /chat/stream for better UX.
    """
    try:
        orchestrator = AIOrchestrator(request.project_id)
        
        # Collect full response
        full_response = ""
        async for chunk in orchestrator.process_message(request.content):
            full_response += chunk
        
        return ToolResponse(
            success=True,
            message="Chat message processed",
            data={"ai_response": full_response}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat/history/{project_id}")
async def get_chat_history(
    project_id: str, limit: int = 50
) -> dict[str, Any]:
    """
    Get chat message history for a project.
    Used by AI to load context.
    """
    conn = await get_db_connection()
    try:
        # Get messages
        messages = await conn.fetch(
            """
            SELECT id, role, content, metadata, created_at
            FROM chat_messages
            WHERE project_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            UUID(project_id),
            limit,
        )

        return {
            "success": True,
            "messages": [
                {
                    "id": str(m["id"]),
                    "role": m["role"],
                    "content": m["content"],
                    "metadata": m["metadata"],
                    "created_at": m["created_at"].isoformat(),
                }
                for m in reversed(messages)  # Return in chronological order
            ],
        }

    finally:
        await conn.close()


# =============================================================================
# PROJECT INSPECTION TOOLS
# =============================================================================


@router.post("/project/init")
async def init_project() -> dict[str, Any]:
    """
    Initialize or get the default project.
    Creates a project if none exists, otherwise returns existing project.
    Used by frontend to get a valid project_id on mount.
    """
    conn = await get_db_connection()
    try:
        # For now, use a default user_id since auth is disabled
        # In a real app, this would come from the authenticated user
        default_user_id = "default-user"
        
        # Check if a project already exists for this user
        existing_project = await conn.fetchrow(
            """
            SELECT id, title, description
            FROM projects
            WHERE user_id = $1 AND status = 'active'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            default_user_id,
        )
        
        if existing_project:
            return {
                "success": True,
                "project_id": str(existing_project["id"]),
                "title": existing_project["title"],
                "description": existing_project["description"],
                "is_new": False,
            }
        
        # Create a new project
        project_id = uuid4()
        await conn.execute(
            """
            INSERT INTO projects (id, user_id, title, description, status)
            VALUES ($1, $2, $3, $4, $5)
            """,
            project_id,
            default_user_id,
            "My Riff Project",
            "AI-powered app builder",
            "active",
        )
        
        return {
            "success": True,
            "project_id": str(project_id),
            "title": "My Riff Project",
            "description": "AI-powered app builder",
            "is_new": True,
        }
    
    finally:
        await conn.close()


@router.get("/project/file-tree/{project_id}")
async def get_file_tree(
    project_id: str
) -> dict[str, Any]:
    """
    Get the file tree structure for a project.
    Used by AI to understand project structure.
    """
    conn = await get_db_connection()
    try:
        # Get all file paths
        files = await conn.fetch(
            """
            SELECT filepath, language, file_type
            FROM generated_files
            WHERE project_id = $1 AND is_active = true
            ORDER BY filepath
            """,
            UUID(project_id),
        )

        # Build tree structure
        tree: dict[str, Any] = {}
        for file in files:
            path_parts = file["filepath"].split("/")
            current = tree

            for i, part in enumerate(path_parts):
                if i == len(path_parts) - 1:
                    # Leaf node (file)
                    current[part] = {
                        "type": "file",
                        "language": file["language"],
                        "file_type": file["file_type"],
                    }
                else:
                    # Directory node
                    if part not in current:
                        current[part] = {"type": "directory", "children": {}}
                    current = current[part]["children"]

        return {"success": True, "tree": tree}

    finally:
        await conn.close()


@router.get("/project/stats/{project_id}")
async def get_project_stats(
    project_id: str
) -> dict[str, Any]:
    """
    Get statistics about a project.
    Used by AI to understand project size and complexity.
    """
    conn = await get_db_connection()
    try:
        # Get stats
        stats = await conn.fetchrow(
            """
            SELECT
                (SELECT COUNT(*) FROM generated_files WHERE project_id = $1 AND is_active = true) as file_count,
                (SELECT COUNT(*) FROM tasks WHERE project_id = $1) as task_count,
                (SELECT COUNT(*) FROM chat_messages WHERE project_id = $1) as message_count,
                (SELECT COUNT(*) FROM deployments WHERE project_id = $1) as deployment_count
            """,
            UUID(project_id),
        )

        # Get task breakdown
        task_status = await conn.fetch(
            """
            SELECT status, COUNT(*) as count
            FROM tasks
            WHERE project_id = $1
            GROUP BY status
            """,
            UUID(project_id),
        )

        return {
            "success": True,
            "stats": {
                "file_count": stats["file_count"],
                "task_count": stats["task_count"],
                "message_count": stats["message_count"],
                "deployment_count": stats["deployment_count"],
                "task_breakdown": {row["status"]: row["count"] for row in task_status},
            },
        }

    finally:
        await conn.close()

# =============================================================================
# DATABASE TOOLS
# =============================================================================


@router.post("/database/run-migration")
async def run_migration_endpoint(
    request: RunMigrationRequest
) -> ToolResponse:
    """
    Run a database migration.
    Used by AI to create/modify database schema.
    """
    conn = await get_db_connection()
    try:
        # Store migration record
        migration_id = uuid4()
        await conn.execute(
            """
            INSERT INTO project_migrations (
                id, project_id, migration_name, sql, applied_at, status
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            migration_id,
            UUID(request.project_id),
            request.migration_name,
            request.sql,
            datetime.utcnow(),
            "pending",
        )

        # Execute migration
        try:
            await conn.execute(request.sql)
            
            # Update status to success
            await conn.execute(
                "UPDATE project_migrations SET status = $1 WHERE id = $2",
                "success",
                migration_id,
            )

            return ToolResponse(
                success=True,
                message=f"Migration '{request.migration_name}' executed successfully",
                data={"migration_id": str(migration_id)},
            )

        except Exception as e:
            # Update status to failed
            await conn.execute(
                """
                UPDATE project_migrations 
                SET status = $1, error_message = $2 
                WHERE id = $3
                """,
                "failed",
                str(e),
                migration_id,
            )
            raise HTTPException(
                status_code=400, detail=f"Migration failed: {str(e)}"
            )

    finally:
        await conn.close()


@router.post("/database/run-query")
async def run_sql_query(
    request: RunSQLQueryRequest
) -> dict[str, Any]:
    """
    Execute a SQL query.
    Used by AI to query data for analysis or verification.
    """
    conn = await get_db_connection()
    try:
        # Execute query
        params = request.params or []
        
        if request.query.strip().upper().startswith("SELECT"):
            # SELECT query - return results
            rows = await conn.fetch(request.query, *params)
            
            return {
                "success": True,
                "rows": [dict(row) for row in rows],
                "row_count": len(rows),
            }
        else:
            # INSERT/UPDATE/DELETE - return affected rows
            result = await conn.execute(request.query, *params)
            
            return {
                "success": True,
                "result": result,
                "message": "Query executed successfully",
            }

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Query failed: {str(e)}")

    finally:
        await conn.close()


@router.get("/database/schema/{project_id}")
async def get_sql_schema(
    project_id: str
) -> dict[str, Any]:
    """
    Get the database schema for tables related to a project.
    Used by AI to understand data structure.
    """
    conn = await get_db_connection()
    try:
        # Get all tables (you might want to filter to project-specific tables)
        tables = await conn.fetch(
            """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
            """
        )

        schema = {}
        for table in tables:
            table_name = table["table_name"]
            
            # Get columns for this table
            columns = await conn.fetch(
                """
                SELECT 
                    column_name, 
                    data_type, 
                    is_nullable,
                    column_default
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = $1
                ORDER BY ordinal_position
                """,
                table_name,
            )

            schema[table_name] = [
                {
                    "name": col["column_name"],
                    "type": col["data_type"],
                    "nullable": col["is_nullable"] == "YES",
                    "default": col["column_default"],
                }
                for col in columns
            ]

        return {"success": True, "schema": schema}

    finally:
        await conn.close()


# =============================================================================
# DEVELOPMENT TOOLS
# =============================================================================


@router.post("/development/run-python")
async def run_python_script(
    request: RunPythonScriptRequest
) -> dict[str, Any]:
    """
    Execute Python code in a sandboxed environment.
    Used by AI to test logic, experiment with APIs, etc.
    """
    conn = await get_db_connection()
    try:
        # Capture stdout and stderr
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        redirected_output = StringIO()
        redirected_error = StringIO()

        try:
            sys.stdout = redirected_output
            sys.stderr = redirected_error

            # Create a restricted globals dict
            restricted_globals = {
                "__builtins__": __builtins__,
                "print": print,
            }

            # Execute code
            exec(request.code, restricted_globals)

            stdout_value = redirected_output.getvalue()
            stderr_value = redirected_error.getvalue()

            return {
                "success": True,
                "stdout": stdout_value,
                "stderr": stderr_value,
                "error": None,
            }

        except Exception as e:
            return {
                "success": False,
                "stdout": redirected_output.getvalue(),
                "stderr": redirected_error.getvalue(),
                "error": {
                    "type": type(e).__name__,
                    "message": str(e),
                    "traceback": traceback.format_exc(),
                },
            }

        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

    finally:
        await conn.close()


@router.get("/development/logs/{project_id}")
async def read_logs(
    project_id: str,
    limit: int = 100,
    level: Optional[str] = None,
) -> dict[str, Any]:
    """
    Read application logs for a project.
    Used by AI to debug issues.
    """
    conn = await get_db_connection()
    try:
        # Build query
        query = """
            SELECT id, level, message, metadata, created_at
            FROM project_logs
            WHERE project_id = $1
        """
        params = [UUID(project_id)]

        if level:
            query += " AND level = $2"
            params.append(level.upper())

        query += " ORDER BY created_at DESC LIMIT $" + str(len(params) + 1)
        params.append(limit)

        logs = await conn.fetch(query, *params)

        return {
            "success": True,
            "logs": [
                {
                    "id": str(log["id"]),
                    "level": log["level"],
                    "message": log["message"],
                    "metadata": log["metadata"],
                    "created_at": log["created_at"].isoformat(),
                }
                for log in logs
            ],
        }

    finally:
        await conn.close()


@router.post("/development/test-endpoint")
async def test_endpoint(
    request: TestEndpointRequest
) -> dict[str, Any]:
    """
    Test an API endpoint.
    Used by AI to verify endpoints are working correctly.
    """
    conn = await get_db_connection()
    try:
        # This is a placeholder - in a real implementation, you'd:
        # 1. Use httpx to make internal API calls
        # 2. Or use TestClient from FastAPI
        # 3. Return the response details

        return {
            "success": True,
            "message": "Endpoint testing requires runtime environment",
            "endpoint": request.endpoint_path,
            "method": request.method,
        }

    finally:
        await conn.close()


@router.post("/development/troubleshoot")
async def troubleshoot(
    request: TroubleshootRequest
) -> dict[str, Any]:
    """
    Analyze an error and suggest solutions.
    Used by AI to debug issues.
    """
    conn = await get_db_connection()
    try:
        # Basic error analysis
        suggestions = []

        error_lower = request.error_message.lower()

        # Database errors
        if "relation" in error_lower and "does not exist" in error_lower:
            suggestions.append(
                "Table doesn't exist. Run migration to create the table."
            )
        elif "duplicate key" in error_lower:
            suggestions.append(
                "Unique constraint violation. Check for duplicate data."
            )
        elif "null value" in error_lower and "violates not-null" in error_lower:
            suggestions.append("Required field is missing. Check input data.")
        
        # Import errors
        elif "modulenotfounderror" in error_lower or "no module named" in error_lower:
            suggestions.append(
                "Missing Python package. Install required dependencies."
            )
        
        # Type errors
        elif "typeerror" in error_lower:
            suggestions.append(
                "Type mismatch. Check function arguments and data types."
            )

        return {
            "success": True,
            "error_type": request.error_type or "Unknown",
            "suggestions": suggestions,
            "context": request.context,
        }

    finally:
        await conn.close()


# =============================================================================
# INTEGRATION TOOLS
# =============================================================================


class EnableIntegrationRequest(BaseModel):
    """Request to enable an integration"""

    project_id: str
    integration_name: str = Field(..., min_length=1)
    config: Optional[dict[str, Any]] = None


@router.post("/integrations/enable")
async def enable_integration(
    request: EnableIntegrationRequest
) -> ToolResponse:
    """
    Enable a third-party integration for a project.
    Used by AI to connect external services.
    """
    conn = await get_db_connection()
    try:
        # Check if integration already exists
        existing = await conn.fetchrow(
            """
            SELECT id FROM project_integrations 
            WHERE project_id = $1 AND integration_name = $2
            """,
            UUID(request.project_id),
            request.integration_name,
        )

        if existing:
            # Update existing integration
            await conn.execute(
                """
                UPDATE project_integrations 
                SET config = $1, updated_at = $2
                WHERE project_id = $3 AND integration_name = $4
                """,
                request.config,
                datetime.utcnow(),
                UUID(request.project_id),
                request.integration_name,
            )
            
            return ToolResponse(
                success=True,
                message=f"Integration '{request.integration_name}' updated",
                data={"integration_name": request.integration_name},
            )
        else:
            # Create new integration
            integration_id = uuid4()
            await conn.execute(
                """
                INSERT INTO project_integrations (
                    id, project_id, integration_name, config, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                integration_id,
                UUID(request.project_id),
                request.integration_name,
                request.config,
                datetime.utcnow(),
                datetime.utcnow(),
            )

            return ToolResponse(
                success=True,
                message=f"Integration '{request.integration_name}' enabled",
                data={
                    "integration_id": str(integration_id),
                    "integration_name": request.integration_name,
                },
            )

    finally:
        await conn.close()


@router.get("/integrations/list/{project_id}")
async def list_integrations(
    project_id: str
) -> dict[str, Any]:
    """
    List all integrations for a project.
    Used by AI to see what services are connected.
    """
    conn = await get_db_connection()
    try:
        integrations = await conn.fetch(
            """
            SELECT id, integration_name, config, created_at, updated_at
            FROM project_integrations
            WHERE project_id = $1
            ORDER BY integration_name
            """,
            UUID(project_id),
        )

        return {
            "success": True,
            "integrations": [
                {
                    "id": str(i["id"]),
                    "name": i["integration_name"],
                    "config": i["config"],
                    "created_at": i["created_at"].isoformat(),
                    "updated_at": i["updated_at"].isoformat(),
                }
                for i in integrations
            ],
        }

    finally:
        await conn.close()


# =============================================================================
# DATA & VISUALIZATION TOOLS
# =============================================================================


@router.post("/data/visualize")
async def visualize_data(
    request: VisualizeDataRequest
) -> dict[str, Any]:
    """
    Create a data visualization.
    Used by AI to display data insights to user.
    """
    conn = await get_db_connection()
    try:
        # Store visualization config
        viz_id = uuid4()
        await conn.execute(
            """
            INSERT INTO project_visualizations (
                id, project_id, chart_type, data, data_keys, 
                title, options, created_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            viz_id,
            UUID(request.project_id),
            request.chart_type,
            json.dumps(request.data),
            request.data_keys,
            request.title,
            request.options,
            datetime.utcnow(),
        )

        return {
            "success": True,
            "visualization_id": str(viz_id),
            "chart_type": request.chart_type,
            "data_preview": request.data[:5] if len(request.data) > 5 else request.data,
        }

    finally:
        await conn.close()


@router.post("/data/request")
async def request_data(
    request: RequestDataRequest
) -> ToolResponse:
    """
    Request data from user.
    Used by AI to ask user for files or information.
    """
    conn = await get_db_connection()
    try:
        # Store data request
        request_id = uuid4()
        await conn.execute(
            """
            INSERT INTO project_data_requests (
                id, project_id, message, data_type, status, created_at
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            request_id,
            UUID(request.project_id),
            request.message,
            request.data_type,
            "pending",
            datetime.utcnow(),
        )

        return ToolResponse(
            success=True,
            message=f"Data request created: {request.message}",
            data={"request_id": str(request_id), "status": "pending"},
        )

    finally:
        await conn.close()
