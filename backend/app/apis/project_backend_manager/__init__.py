"""Project Backend Process Manager

Manages lifecycle of isolated project backend processes:
- Start/stop FastAPI backends for user projects
- Track running processes (pid, port, status)
- Port allocation and health checks
- Auto-restart on code changes
"""

import asyncio
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Dict, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
import psutil
import asyncpg

router = APIRouter(prefix="/project-backend", tags=["project-backend"])

# ============================================================================
# GLOBAL STATE - Running Backends
# ============================================================================

running_backends: Dict[str, dict] = {}
# Format: {
#   "project_id": {
#       "pid": 12345,
#       "port": 8001,
#       "status": "running",  # running, stopped, error
#       "started_at": 1234567890.0,
#       "workspace_path": "/path/to/workspace",
#       "process": subprocess.Popen object
#   }
# }

# Base port for project backends (increment for each project)
BASE_PORT = 8001
MAX_BACKENDS = 100  # Max 100 concurrent project backends

# ============================================================================
# MODELS
# ============================================================================

class StartBackendRequest(BaseModel):
    project_id: str

class BackendStatus(BaseModel):
    project_id: str
    status: str  # running, stopped, error
    pid: Optional[int] = None
    port: Optional[int] = None
    started_at: Optional[float] = None
    uptime_seconds: Optional[float] = None
    workspace_path: Optional[str] = None
    health: Optional[str] = None  # healthy, unhealthy

# ============================================================================
# PORT ALLOCATION
# ============================================================================

def allocate_port() -> int:
    """Allocate next available port for a project backend."""
    used_ports = {info["port"] for info in running_backends.values()}
    
    for i in range(MAX_BACKENDS):
        candidate_port = BASE_PORT + i
        if candidate_port not in used_ports:
            return candidate_port
    
    raise Exception(f"No available ports (max {MAX_BACKENDS} backends)")

# ============================================================================
# PROCESS MANAGEMENT
# ============================================================================

def start_backend_process(project_id: str, workspace_path: Path, port: int) -> subprocess.Popen:
    """Start uvicorn process for project backend.
    
    Args:
        project_id: Project ID
        workspace_path: Path to backend workspace
        port: Port to run on
        
    Returns:
        subprocess.Popen object
    """
    print(f"[{project_id}] Starting backend on port {port}...")
    
    # Check if venv exists
    venv_path = workspace_path / ".venv"
    if not venv_path.exists():
        raise Exception(f"Virtual environment not found at {venv_path}")
    
    # Get Python path from venv
    python_path = venv_path / "bin" / "python"
    if not python_path.exists():
        raise Exception(f"Python not found in venv: {python_path}")
    
    # Start uvicorn
    # Command: python -m uvicorn main:app --reload --host 0.0.0.0 --port {port}
    cmd = [
        str(python_path),
        "-m", "uvicorn",
        "main:app",
        "--reload",
        "--host", "0.0.0.0",
        "--port", str(port),
        "--log-level", "info"
    ]
    
    print(f"[{project_id}] Command: {' '.join(cmd)}")
    print(f"[{project_id}] Working dir: {workspace_path}")
    
    # Start process
    process = subprocess.Popen(
        cmd,
        cwd=workspace_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,  # Line buffered
        env=os.environ.copy()
    )
    
    print(f"[{project_id}] ✅ Process started with PID {process.pid}")
    return process

def stop_backend_process(project_id: str) -> bool:
    """Stop backend process for project.
    
    Returns:
        True if stopped, False if not running
    """
    if project_id not in running_backends:
        return False
    
    backend_info = running_backends[project_id]
    pid = backend_info["pid"]
    
    print(f"[{project_id}] Stopping backend (PID {pid})...")
    
    try:
        # Try graceful shutdown first (SIGTERM)
        process = backend_info.get("process")
        if process:
            process.terminate()
            try:
                process.wait(timeout=5)
                print(f"[{project_id}] ✅ Process terminated gracefully")
            except subprocess.TimeoutExpired:
                # Force kill if not responding
                process.kill()
                process.wait()
                print(f"[{project_id}] ⚠️ Process killed forcefully")
        else:
            # Fallback: kill by PID
            os.kill(pid, signal.SIGTERM)
            time.sleep(2)
            # Check if still running
            try:
                os.kill(pid, 0)  # Check if process exists
                os.kill(pid, signal.SIGKILL)  # Force kill
                print(f"[{project_id}] ⚠️ Process killed forcefully")
            except ProcessLookupError:
                print(f"[{project_id}] ✅ Process terminated")
        
        # Remove from tracking
        del running_backends[project_id]
        return True
        
    except Exception as e:
        print(f"[{project_id}] ❌ Error stopping process: {e}")
        # Remove anyway
        del running_backends[project_id]
        return False

async def check_backend_health(project_id: str, port: int) -> str:
    """Check if backend is responding.
    
    Returns:
        "healthy" or "unhealthy"
    """
    try:
        # Try to connect to health endpoint
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://localhost:{port}/health",
                timeout=2.0
            )
            if response.status_code == 200:
                return "healthy"
            return "unhealthy"
    except Exception:
        return "unhealthy"

# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.post("/start/{project_id}")
async def start_backend(
    project_id: str,
    background_tasks: BackgroundTasks
) -> dict:
    """Start FastAPI backend for a project.
    
    Creates isolated backend process running in project workspace.
    """
    # Check if already running
    if project_id in running_backends:
        backend_info = running_backends[project_id]
        return {
            "success": True,
            "message": "Backend already running",
            "project_id": project_id,
            "port": backend_info["port"],
            "pid": backend_info["pid"],
            "status": backend_info["status"]
        }
    
    # Check if workspace exists
    workspace_path = Path(f"/disk/backend/.preview-builds/{project_id}/backend")
    if not workspace_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Backend workspace not found for project {project_id}. Run POST /preview/backend/create first."
        )
    
    # Check if main.py exists
    main_py = workspace_path / "main.py"
    if not main_py.exists():
        raise HTTPException(
            status_code=404,
            detail=f"main.py not found in workspace. Run POST /preview/backend/create first."
        )
    
    try:
        # Allocate port
        port = allocate_port()
        
        # Start process
        process = start_backend_process(project_id, workspace_path, port)
        
        # Track in global state
        running_backends[project_id] = {
            "pid": process.pid,
            "port": port,
            "status": "running",
            "started_at": time.time(),
            "workspace_path": str(workspace_path),
            "process": process
        }
        
        return {
            "success": True,
            "message": "Backend started successfully",
            "project_id": project_id,
            "port": port,
            "pid": process.pid,
            "url": f"http://localhost:{port}",
            "workspace": str(workspace_path)
        }
        
    except Exception as e:
        print(f"[{project_id}] ❌ Failed to start backend: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start backend: {str(e)}"
        )

@router.post("/stop/{project_id}")
async def stop_backend(project_id: str) -> dict:
    """Stop backend process for project."""
    if project_id not in running_backends:
        raise HTTPException(
            status_code=404,
            detail=f"No running backend found for project {project_id}"
        )
    
    success = stop_backend_process(project_id)
    
    return {
        "success": success,
        "message": "Backend stopped" if success else "Failed to stop backend",
        "project_id": project_id
    }

@router.post("/restart/{project_id}")
async def restart_backend(
    project_id: str,
    background_tasks: BackgroundTasks
) -> dict:
    """Restart backend (useful after code changes)."""
    # Stop if running
    if project_id in running_backends:
        stop_backend_process(project_id)
        await asyncio.sleep(1)  # Wait for port to be released
    
    # Start again
    result = await start_backend(project_id, background_tasks)
    return result

@router.get("/status/{project_id}")
async def get_backend_status(project_id: str) -> BackendStatus:
    """Get status of backend for project."""
    if project_id not in running_backends:
        return BackendStatus(
            project_id=project_id,
            status="stopped"
        )
    
    backend_info = running_backends[project_id]
    pid = backend_info["pid"]
    port = backend_info["port"]
    started_at = backend_info["started_at"]
    
    # Check if process still running
    try:
        process = psutil.Process(pid)
        if process.is_running():
            status = "running"
            uptime = time.time() - started_at
            health = await check_backend_health(project_id, port)
        else:
            status = "stopped"
            uptime = None
            health = None
    except psutil.NoSuchProcess:
        status = "stopped"
        uptime = None
        health = None
        # Clean up tracking
        del running_backends[project_id]
    
    return BackendStatus(
        project_id=project_id,
        status=status,
        pid=pid if status == "running" else None,
        port=port,
        started_at=started_at,
        uptime_seconds=uptime,
        workspace_path=backend_info["workspace_path"],
        health=health
    )

@router.get("/list")
async def list_backends() -> dict:
    """List all running backends."""
    backends = []
    
    for project_id in list(running_backends.keys()):
        status = await get_backend_status(project_id)
        backends.append(status.dict())
    
    return {
        "success": True,
        "total": len(backends),
        "backends": backends
    }

@router.post("/stop-all")
async def stop_all_backends() -> dict:
    """Stop all running backends."""
    stopped = []
    
    for project_id in list(running_backends.keys()):
        try:
            stop_backend_process(project_id)
            stopped.append(project_id)
        except Exception as e:
            print(f"Failed to stop {project_id}: {e}")
    
    return {
        "success": True,
        "stopped": stopped,
        "count": len(stopped)
    }
