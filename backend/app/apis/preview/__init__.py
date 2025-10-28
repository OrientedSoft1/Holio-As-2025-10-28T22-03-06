
import asyncpg
import json
import os
import subprocess
import re
import asyncio
import traceback
from pathlib import Path
from typing import Dict, Optional, Any

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel

router = APIRouter()

DATABASE_URL = os.environ.get("DATABASE_URL")

# Build cache to store compiled apps
BUILD_CACHE: Dict[str, Path] = {}

# Workspace base directory (created on-demand)
WORKSPACE_BASE = Path("/disk/backend/.preview-builds")

async def _create_venv_background(backend_workspace: Path, project_id: str):
    """Background task to create virtual environment with dependencies."""
    try:
        venv_path = backend_workspace / ".venv"
        print(f"[{project_id}] Creating Python venv...")
        
        # Create venv
        subprocess.run(
            ["python", "-m", "venv", str(venv_path)],
            check=True,
            capture_output=True
        )
        print(f"[{project_id}] ✅ Venv created")
        
        # Install uv
        pip_path = venv_path / "bin" / "pip"
        subprocess.run(
            [str(pip_path), "install", "uv"],
            check=True,
            capture_output=True
        )
        print(f"[{project_id}] ✅ uv installed")
        
        # Install base dependencies
        subprocess.run(
            ["uv", "pip", "install", "-r", "pyproject.toml"],
            cwd=backend_workspace,
            check=True,
            capture_output=True
        )
        print(f"[{project_id}] ✅ Base dependencies installed")
        
    except Exception as e:
        print(f"[{project_id}] ❌ Venv creation failed: {e}")
        traceback.print_exc()

async def create_backend_workspace(project_id: str, background_tasks: Optional[BackgroundTasks] = None) -> Path:
    """
    Create isolated backend workspace for a user project.
    
    Structure:
    /disk/backend/.preview-builds/{project_id}/backend/
      ├── pyproject.toml    ← Project dependencies
      ├── .venv/            ← Python virtual environment (created async)
      ├── main.py           ← FastAPI app
      └── app/
          └── apis/         ← Generated Python APIs
    
    Returns:
        Path to backend workspace directory
    """
    backend_workspace = WORKSPACE_BASE / project_id / "backend"
    backend_workspace.mkdir(parents=True, exist_ok=True)
    
    app_dir = backend_workspace / "app"
    apis_dir = app_dir / "apis"
    apis_dir.mkdir(parents=True, exist_ok=True)
    
    # Create __init__.py files for Python package structure
    (app_dir / "__init__.py").write_text("")
    (apis_dir / "__init__.py").write_text("")
    
    # Create pyproject.toml with base dependencies
    pyproject_content = """[project]
name = "user-project"
version = "1.0.0"
description = "User Generated Project"
requires-python = ">=3.11,<3.12"
dependencies = []

[dependency-groups]
base = [
  "databutton==0.39.0",
  "uvicorn[standard]>=0.34.0",
  "fastapi>=0.115.7",
  "pydantic>=2.10.5",
  "httpx>=0.28.1",
  "python-multipart>=0.0.9",
  "pyjwt>=2.10.1",
  "cryptography>=44.0.0",
  "asyncpg>=0.30.0",
  "dotenv>=0.9.9",
  "openai",
  "beautifulsoup4",
  "requests",
  "anthropic",
  "scrapy",
  "psutil",
  "toml",
]
app = []  # User-installed packages go here
"""
    (backend_workspace / "pyproject.toml").write_text(pyproject_content)
    
    # Create FastAPI main.py template
    main_py_content = """from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import user-generated API routers (will be added dynamically)
# from app.apis.example import router as example_router

def create_app() -> FastAPI:
    app = FastAPI(
        title="User Project API",
        version="1.0.0"
    )
    
    # Enable CORS for preview
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Auto-import routers from app/apis/
    import importlib
    import pkgutil
    from pathlib import Path
    
    apis_path = Path(__file__).parent / "app" / "apis"
    if apis_path.exists():
        for module_info in pkgutil.iter_modules([str(apis_path)]):
            try:
                module = importlib.import_module(f"app.apis.{module_info.name}")
                if hasattr(module, "router"):
                    app.include_router(module.router)
                    print(f"✅ Loaded API: {module_info.name}")
            except Exception as e:
                print(f"❌ Failed to load {module_info.name}: {e}")
    
    return app

app = create_app()
"""
    (backend_workspace / "main.py").write_text(main_py_content)
    
    # Create venv in background if not exists
    venv_path = backend_workspace / ".venv"
    if not venv_path.exists():
        if background_tasks:
            # Run in background task (FastAPI)
            background_tasks.add_task(_create_venv_background, backend_workspace, project_id)
            print(f"[{project_id}] 🔄 Venv creation scheduled in background")
        else:
            # Run async task (non-FastAPI context)
            asyncio.create_task(_create_venv_background(backend_workspace, project_id))
            print(f"[{project_id}] 🔄 Venv creation started async")
    
    return backend_workspace

async def parse_and_report_build_errors(project_id: str, build_output: str, build_logs: list):
    """
    Parse Vite build errors and report them to the error API.
    
    Handles two formats:
    1. TypeScript: src/App.tsx:10:5 - error TS2304: Cannot find name 'foo'.
    2. esbuild: /path/file.tsx:16:12: ERROR: Expected "}" but found ";"
    """
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        errors_found = []
        
        # Pattern 1: esbuild format
        # /disk/backend/.preview-builds/{project_id}/frontend/src/components/BrokenComponent.tsx:16:12: ERROR: Expected "}" but found ";"
        esbuild_pattern = r'([^:]+\.tsx?):?(\d+)?:?(\d+)?:\s*ERROR:\s*(.+?)(?=\n|$)'
        for match in re.finditer(esbuild_pattern, build_output, re.MULTILINE):
            file_path = match.group(1)
            line_number = int(match.group(2)) if match.group(2) else None
            message = match.group(4).strip()
            
            # Normalize file path (remove workspace prefix)
            if 'frontend/src/' in file_path:
                file_path = 'src/' + file_path.split('frontend/src/')[1]
            
            errors_found.append({
                'file_path': file_path,
                'line_number': line_number,
                'message': message,
                'error_code': 'ESBUILD'
            })
        
        # Pattern 2: TypeScript compiler format
        # src/App.tsx:10:5 - error TS2304: Cannot find name 'foo'.
        ts_pattern = r'([^:]+\.tsx?):?(\d+)?:?(\d+)?\s*-\s*error\s*([^:]+):\s*(.+)'
        for match in re.finditer(ts_pattern, build_output, re.MULTILINE):
            file_path = match.group(1)
            line_number = int(match.group(2)) if match.group(2) else None
            error_code = match.group(4)
            message = match.group(5).strip()
            
            errors_found.append({
                'file_path': file_path,
                'line_number': line_number,
                'message': message,
                'error_code': error_code
            })
        
        # Insert all found errors into database
        for error in errors_found:
            file_path = error['file_path']
            line_number = error['line_number']
            message = error['message']
            error_code = error['error_code']
            
            # Extract code snippet if we have line number
            code_snippet = None
            if line_number and file_path:
                try:
                    # Read the file and extract surrounding lines
                    workspace = WORKSPACE_BASE / project_id / "frontend"
                    file_full_path = workspace / file_path
                    if file_full_path.exists():
                        lines = file_full_path.read_text().splitlines()
                        start = max(0, line_number - 3)
                        end = min(len(lines), line_number + 2)
                        code_snippet = '\n'.join(lines[start:end])
                except Exception:
                    pass
            
            # Insert error into database
            query = """
            INSERT INTO errors (
                project_id, error_type, message, stack_trace,
                file_path, line_number, code_snippet, context, status
            )
            VALUES ($1, 'build', $2, $3, $4, $5, $6, $7, 'open')
            """
            await conn.execute(
                query,
                project_id,
                f"{error_code}: {message}",
                build_output,  # Full build output as stack trace
                file_path,
                line_number,
                code_snippet,
                json.dumps({"error_code": error_code})
            )
            
            build_logs.append(f"[ERROR REPORTED] {file_path}:{line_number} - {message}")
            
        if errors_found:
            build_logs.append(f"[TOTAL ERRORS] Found and reported {len(errors_found)} errors")
    finally:
        await conn.close()

async def detect_python_imports(code: str) -> list[str]:
    """
    Detect imported packages from Python code.
    Returns list of package names (not stdlib modules).
    
    Maps import names to PyPI package names (e.g., PIL -> Pillow).
    """
    import ast
    import sys
    
    packages = set()
    
    try:
        tree = ast.parse(code)
        
        for node in ast.walk(tree):
            # Handle "import foo" or "import foo.bar"
            if isinstance(node, ast.Import):
                for alias in node.names:
                    package = alias.name.split('.')[0]
                    packages.add(package)
            
            # Handle "from foo import bar"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    package = node.module.split('.')[0]
                    packages.add(package)
    
    except SyntaxError:
        # If code has syntax errors, skip detection
        pass
    
    # Filter out stdlib modules
    stdlib_modules = set(sys.stdlib_module_names)
    third_party = [pkg for pkg in packages if pkg not in stdlib_modules]
    
    # Map import names to PyPI package names
    # Common cases where import name != package name
    IMPORT_TO_PACKAGE = {
        "PIL": "Pillow",
        "cv2": "opencv-python",
        "yaml": "PyYAML",
        "sklearn": "scikit-learn",
        "bs4": "beautifulsoup4",
        "dotenv": "python-dotenv",
        "discord": "discord.py",
        "telegram": "python-telegram-bot",
        "jose": "python-jose",
        "multipart": "python-multipart",
        "magic": "python-magic",
    }
    
    # Apply mapping
    mapped_packages = [
        IMPORT_TO_PACKAGE.get(pkg, pkg) 
        for pkg in third_party
    ]
    
    return mapped_packages


async def detect_npm_imports(code: str) -> list[str]:
    """
    Detect imported NPM packages from TypeScript/JavaScript code.
    Returns list of third-party package names.
    
    Excludes:
    - React built-ins (react, react-dom, react-router-dom)
    - Relative imports (./components, ../utils)
    - Node.js built-ins (fs, path, http, etc.)
    - Type imports (import type)
    """
    import re
    
    packages = set()
    
    # Pattern: import ... from 'package-name' or "package-name"
    # Matches: import X from 'axios'
    #          import { X } from 'lodash'
    #          import * as X from 'date-fns'
    import_pattern = r"import\s+(?:type\s+)?(?:[\w*{},\s]+)\s+from\s+['\"]([^'\"]+)['\"]"
    
    matches = re.findall(import_pattern, code)
    
    for match in matches:
        # Skip relative imports (start with . or /)
        if match.startswith('.') or match.startswith('/'):
            continue
        
        # Extract package name (before any subpath)
        # e.g., '@mui/material/Button' -> '@mui/material'
        #       'lodash/debounce' -> 'lodash'
        if match.startswith('@'):
            # Scoped package: @org/package/subpath -> @org/package
            parts = match.split('/')
            if len(parts) >= 2:
                packages.add(f"{parts[0]}/{parts[1]}")
        else:
            # Regular package: package/subpath -> package
            package_name = match.split('/')[0]
            packages.add(package_name)
    
    # Filter out built-in packages that are always available
    builtin_packages = {
        'react', 'react-dom', 'react-router-dom',  # Already in base template
        # Node.js built-ins (shouldn't be used in browser code, but filter anyway)
        'fs', 'path', 'http', 'https', 'crypto', 'os', 'util', 'stream'
    }
    
    # Filter out Riff internal imports (these are configured in Vite/TypeScript)
    riff_internal = {
        'app',  # Riff app module (provides API_URL, apiClient, etc.)
        '@/components',  # Shadcn components (@ is alias for src/)
        '@/hooks',  # Shadcn hooks
        '@/lib',  # Internal lib folder
        'components',  # Internal components (direct import)
        'utils',  # Internal utils (direct import)
        'types',  # Internal types (direct import)
    }
    
    third_party = [
        pkg for pkg in packages 
        if pkg not in builtin_packages and pkg not in riff_internal
    ]
    
    return third_party


async def install_packages_in_project(
    project_id: str,
    packages: list[str]
) -> dict:
    """
    Install Python packages in RIFF workspace virtual environment.
    
    NOTE: Changed from project-specific venv to Riff workspace venv
    because all generated APIs run in Riff's main backend.
    
    Args:
        project_id: Project ID (kept for backward compatibility, but not used)
        packages: List of package names to install
    
    Returns:
        dict with success status and installed packages
    """
    # Update RIFF pyproject.toml first
    await update_project_pyproject(project_id, packages)
    print(f"[RIFF] ✅ Updated pyproject.toml with packages: {packages}")
    
    # Install in RIFF workspace venv (not project venv)
    riff_backend = Path("/disk/backend")
    venv_path = riff_backend / ".venv"
    uv_path = venv_path / "bin" / "uv"
    
    if not uv_path.exists():
        return {
            "success": True,  # Success means pyproject.toml updated
            "installed": [],
            "failed": [],
            "note": "Packages added to pyproject.toml. uv not found in RIFF venv."
        }
    
    installed = []
    failed = []
    
    for package in packages:
        try:
            result = subprocess.run(
                [str(uv_path), "pip", "install", package],
                cwd=riff_backend,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                installed.append(package)
                print(f"[RIFF] ✅ Installed {package} in RIFF workspace venv")
            else:
                failed.append({
                    "package": package,
                    "error": result.stderr
                })
                print(f"[RIFF] ❌ Failed to install {package}: {result.stderr}")
        
        except Exception as e:
            failed.append({
                "package": package,
                "error": str(e)
            })
            print(f"[RIFF] ❌ Exception installing {package}: {e}")
    
    return {
        "success": len(failed) == 0,
        "installed": installed,
        "failed": failed
    }


async def update_project_pyproject(project_id: str, packages: list[str]):
    """
    Update RIFF workspace pyproject.toml with new packages.
    Adds to [dependency-groups.app] section.
    
    NOTE: Changed from project-specific pyproject.toml to Riff workspace pyproject.toml
    because all generated APIs run in Riff's main backend.
    """
    import re
    
    # Update RIFF workspace pyproject.toml (not project workspace)
    riff_backend = Path("/disk/backend")
    pyproject_path = riff_backend / "pyproject.toml"
    
    if not pyproject_path.exists():
        print(f"[RIFF] ⚠️ pyproject.toml not found at {pyproject_path}")
        return
    
    content = pyproject_path.read_text()
    lines = content.split('\n')
    
    # Find [dependency-groups] and app = [] line
    app_line_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith('app = ['):
            app_line_idx = i
            break
    
    if app_line_idx is not None:
        # Parse existing packages (handles both quoted and unquoted)
        app_line = lines[app_line_idx]
        packages_str = app_line.split('=', 1)[1].strip()
        
        # Extract package names using regex (matches both "pkg" and pkg)
        existing_packages = re.findall(r'["\']([^"\',]+)["\']|([a-zA-Z0-9_-]+)', packages_str)
        existing = [pkg[0] if pkg[0] else pkg[1] for pkg in existing_packages if pkg[0] or pkg[1]]
        
        # Filter out brackets and empty strings
        existing = [pkg for pkg in existing if pkg and pkg not in ['[', ']']]
        
        # Add new packages (avoid duplicates)
        all_packages = list(set(existing + packages))
        
        # Always quote package names for consistency
        quoted_packages = [f'"{pkg}"' for pkg in sorted(all_packages)]
        
        # Update line
        lines[app_line_idx] = 'app = [' + ', '.join(quoted_packages) + ']'
        
        # Write back
        pyproject_path.write_text('\n'.join(lines))
        print(f"[RIFF] ✅ Updated RIFF pyproject.toml with {len(packages)} packages")


async def update_project_package_json(project_id: str, packages: list[str]):
    """
    Update project's package.json with new NPM packages.
    Adds to dependencies section with 'latest' version.
    """
    frontend_workspace = WORKSPACE_BASE / project_id / "frontend"
    package_json_path = frontend_workspace / "package.json"
    
    if not package_json_path.exists():
        print(f"[{project_id}] ⚠️ package.json not found, will be created during preview build")
        return
    
    # Read existing package.json
    with open(package_json_path, 'r') as f:
        package_data = json.load(f)
    
    # Ensure dependencies section exists
    if "dependencies" not in package_data:
        package_data["dependencies"] = {}
    
    # Add new packages with 'latest' version (avoid duplicates)
    for pkg in packages:
        if pkg not in package_data["dependencies"]:
            package_data["dependencies"][pkg] = "latest"
            print(f"[{project_id}] ➕ Added {pkg} to package.json")
        else:
            print(f"[{project_id}] ⏭️ Package {pkg} already in package.json")
    
    # Write back (pretty formatted)
    with open(package_json_path, 'w') as f:
        json.dump(package_data, f, indent=2)
    
    print(f"[{project_id}] ✅ Updated package.json with {len(packages)} packages")


@router.post("/preview/packages/test/{project_id}")
async def test_package_installation(project_id: str):
    """
    Test package detection and installation in project venv.
    
    1. Creates backend workspace if not exists
    2. Generates test Python code with imports
    3. Detects packages from code
    4. Installs packages in project venv
    5. Verifies installation
    """
    # Ensure backend workspace exists
    backend_workspace = await create_backend_workspace(project_id)
    
    # Test Python code with various imports
    test_code = '''
import pandas as pd
import requests
from sklearn.model_selection import train_test_split
import numpy as np
import json  # stdlib, should be filtered out
import sys   # stdlib, should be filtered out

def test():
    df = pd.DataFrame()
    response = requests.get("https://api.example.com")
    return df
'''
    
    # Detect packages
    packages = await detect_python_imports(test_code)
    
    # Install packages
    result = await install_packages_in_project(project_id, packages)
    
    # Read updated pyproject.toml
    pyproject_path = backend_workspace / "pyproject.toml"
    pyproject_content = pyproject_path.read_text() if pyproject_path.exists() else "Not found"
    
    return {
        "backend_workspace": str(backend_workspace),
        "test_code": test_code,
        "detected_packages": packages,
        "installation_result": result,
        "pyproject_content": pyproject_content
    }

@router.get("/preview/test")
async def test_preview():
    """Super simple test endpoint - hardcoded HTML."""
    return HTMLResponse(
        content="""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Test Preview</title>
            <style>
                body {
                    font-family: system-ui;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                }
                h1 { font-size: 3rem; margin: 0; }
                p { font-size: 1.2rem; margin: 1rem 0; opacity: 0.9; }
            </style>
        </head>
        <body>
            <div style="text-align: center;">
                <h1>🎉 Det funker!</h1>
                <p>Preview endpoint responderer riktig</p>
                <p style="font-size: 0.9rem; opacity: 0.7;">Ingen auth-blokkering her</p>
            </div>
        </body>
        </html>
        """
    )

@router.post("/preview/backend/create/{project_id}")
async def create_project_backend(project_id: str, background_tasks: BackgroundTasks):
    """
    Test endpoint: Create backend workspace for a project.
    """
    try:
        backend_path = await create_backend_workspace(project_id, background_tasks)
        
        # Check created files
        files_created = []
        for item in backend_path.rglob("*"):
            if item.is_file():
                rel_path = item.relative_to(backend_path)
                files_created.append(str(rel_path))
        
        return JSONResponse({
            "success": True,
            "backend_path": str(backend_path),
            "files_created": sorted(files_created),
            "message": "Backend workspace created successfully",
            "note": "Virtual environment creation is running in background"
        })
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
                "message": "Failed to create backend workspace"
            }
        )

@router.get("/preview/simple/{project_id}")
async def simple_preview(project_id: str):
    """Simple hardcoded counter app - all inline, no external assets."""
    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Simple Preview - {project_id}</title>
            <meta charset="UTF-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1.0" />
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                body {{
                    font-family: system-ui, -apple-system, sans-serif;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    min-height: 100vh;
                    background: #0f172a;
                    color: white;
                }}
                .container {{
                    text-align: center;
                    padding: 3rem;
                    background: #1e293b;
                    border-radius: 1rem;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.5);
                }}
                h1 {{
                    font-size: 2.5rem;
                    margin-bottom: 1rem;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    background-clip: text;
                }}
                .count {{
                    font-size: 4rem;
                    font-weight: bold;
                    margin: 2rem 0;
                    color: #60a5fa;
                }}
                .buttons {{
                    display: flex;
                    gap: 1rem;
                    justify-content: center;
                    margin-top: 2rem;
                }}
                button {{
                    padding: 1rem 2rem;
                    font-size: 1.1rem;
                    font-weight: 600;
                    border: none;
                    border-radius: 0.5rem;
                    cursor: pointer;
                    transition: all 0.2s;
                }}
                button:hover {{
                    transform: translateY(-2px);
                    box-shadow: 0 10px 20px rgba(0,0,0,0.3);
                }}
                .btn-increment {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                }}
                .btn-decrement {{
                    background: #ef4444;
                    color: white;
                }}
                .btn-reset {{
                    background: #64748b;
                    color: white;
                }}
                .project-id {{
                    margin-top: 2rem;
                    font-size: 0.9rem;
                    color: #94a3b8;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🚀 Counter App</h1>
                <div class="count" id="count">0</div>
                <div class="buttons">
                    <button class="btn-increment" onclick="increment()">➕ Increment</button>
                    <button class="btn-decrement" onclick="decrement()">➖ Decrement</button>
                    <button class="btn-reset" onclick="reset()">🔄 Reset</button>
                </div>
                <div class="project-id">Project ID: {project_id}</div>
            </div>
            
            <script>
                let count = 0;
                const countEl = document.getElementById('count');
                
                function updateDisplay() {{
                    countEl.textContent = count;
                }}
                
                function increment() {{
                    count++;
                    updateDisplay();
                }}
                
                function decrement() {{
                    count--;
                    updateDisplay();
                }}
                
                function reset() {{
                    count = 0;
                    updateDisplay();
                }}
            </script>
        </body>
        </html>
        """
    )

@router.post("/preview/build/{project_id}")
async def build_preview(project_id: str) -> JSONResponse:
    """
    Build preview from AI-generated code in database.
    """
    build_logs = []
    
    # Ensure workspace directory exists
    WORKSPACE_BASE.mkdir(parents=True, exist_ok=True)
    
    try:
        # Fetch all generated files for this project
        conn = await asyncpg.connect(DATABASE_URL)
        try:
            # Fetch files from database
            build_logs.append("[DB] Fetching generated files from database...")
            query = """
            SELECT file_path, file_content
            FROM generated_files
            WHERE project_id = $1 AND is_active = true
            """
            rows = await conn.fetch(query, project_id)
            
            if not rows:
                return JSONResponse(
                    status_code=404,
                    content={"success": False, "error": "No files found for project", "logs": build_logs}
                )
            
            build_logs.append(f"[DB] Found {len(rows)} files")
            
            # Normalize file paths: strip 'frontend/' prefix if present
            files = {}
            for row in rows:
                file_path = row['file_path']
                # Strip 'frontend/' prefix to get correct relative path
                if file_path.startswith('frontend/'):
                    normalized_path = file_path[len('frontend/'):]
                else:
                    normalized_path = file_path
                
                # Skip backend files
                if normalized_path.startswith('backend/') or file_path.startswith('backend/'):
                    continue
                    
                files[normalized_path] = row['file_content']
                build_logs.append(f"[FILE] Mapped {file_path} -> {normalized_path}")
            
            if not files:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "error": "No frontend files found", "logs": build_logs}
                )
        finally:
            await conn.close()

        # Use workspace directory instead of temp
        workspace = WORKSPACE_BASE / project_id / "frontend"
        workspace.mkdir(parents=True, exist_ok=True)
        src_dir = workspace / "src"
        src_dir.mkdir(exist_ok=True)
        
        build_logs.append(f"[SETUP] Created workspace at {workspace}")
        
        # Normalize file paths and organize by directory
        normalized_files = {}
        for file_path, content in files.items():
            # Strip 'frontend/' prefix if present
            clean_path = file_path
            if clean_path.startswith('frontend/'):
                clean_path = clean_path[len('frontend/'):]
            
            # Ensure files are under src/ directory
            if not clean_path.startswith('src/'):
                clean_path = f"src/{clean_path}"
            
            normalized_files[clean_path] = content
            build_logs.append(f"[NORMALIZE] {file_path} → {clean_path}")
        
        # Write all files to workspace
        for file_path, content in normalized_files.items():
            full_path = workspace / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding='utf-8')
            build_logs.append(f"[WRITE] {file_path}")
        
        # Auto-fix missing imports: check if App.tsx imports missing pages
        app_tsx_path = src_dir / "App.tsx"
        if app_tsx_path.exists():
            app_content = app_tsx_path.read_text()
            import re
            # Find imports like: import HomePage from './pages/HomePage'
            page_imports = re.findall(r"import\s+(\w+)\s+from\s+['\"]\./pages/(\w+)['\"]", app_content)
            
            pages_dir = src_dir / "pages"
            pages_dir.mkdir(exist_ok=True)
            
            # Check which pages actually exist
            existing_pages = {f.stem for f in pages_dir.glob("*.tsx")} if pages_dir.exists() else set()
            
            for component_name, file_name in page_imports:
                if file_name not in existing_pages:
                    # Find first existing page to use as fallback
                    if existing_pages:
                        fallback_page = list(existing_pages)[0]
                        stub_content = f"""import React from 'react';
import {fallback_page} from './{fallback_page}';

// Auto-generated stub - redirects to {fallback_page}
export default {fallback_page};
"""
                        stub_path = pages_dir / f"{file_name}.tsx"
                        stub_path.write_text(stub_content)
                        build_logs.append(f"[AUTO-GEN] Created {file_name}.tsx → re-exports {fallback_page}.tsx")
        
        # Auto-fix component imports: scan all files for missing component imports
        components_dir = src_dir / "components"
        if components_dir.exists():
            # Get list of existing components
            existing_components = {f.stem for f in components_dir.glob("*.tsx")}
            
            # Scan all .tsx files for component imports
            import re
            for tsx_file in src_dir.rglob("*.tsx"):
                content = tsx_file.read_text()
                # Find imports like: import { Button } from './components' or './components/Button'
                comp_imports = re.findall(r"import\s+\{\s*([^}]+)\s*\}\s+from\s+['\"]\./components(?:/?(\w+))?['\"];", content)
                
                for match in comp_imports:
                    components = [c.strip() for c in match[0].split(',')]
                    for comp_name in components:
                        if comp_name not in existing_components:
                            # Create stub component
                            stub_content = f"""import React from 'react';

export function {comp_name}() {{
  return <div>{comp_name} (auto-generated stub)</div>;
}}
"""
                            stub_path = components_dir / f"{comp_name}.tsx"
                            stub_path.write_text(stub_content)
                            existing_components.add(comp_name)
                            build_logs.append(f"[AUTO-GEN] Created {comp_name}.tsx stub")
            
            # Generate components/index.tsx to export all components
            if existing_components:
                exports = [f"export {{ {comp} }} from './{comp}';" for comp in sorted(existing_components)]
                index_content = "\n".join(exports) + "\n"
                index_path = components_dir / "index.tsx"
                index_path.write_text(index_content)
                build_logs.append(f"[AUTO-GEN] Created components/index.tsx with {len(existing_components)} exports")
        
        # Create minimal package.json for frontend
        package_json = {
            "name": "preview-app",
            "version": "1.0.0",
            "type": "module",
            "scripts": {
                "dev": "vite",
                "build": "vite build",
                "preview": "vite preview"
            },
            "dependencies": {
                "react": "^18.3.1",
                "react-dom": "^18.3.1",
                "react-router-dom": "^6.20.0"
            },
            "devDependencies": {
                "@vitejs/plugin-react-swc": "^3.3.2",
                "vite": "^4.4.5",
                "typescript": "^5.2.2",
                "@types/react": "^18.2.32",
                "@types/react-dom": "^18.3.1",
                "tailwindcss": "^3.3.0",
                "postcss": "^8.4.31",
                "autoprefixer": "^10.4.16"
            }
        }
        
        # Auto-detect NPM packages from all frontend files
        detected_packages = set()
        for tsx_file in src_dir.rglob("*.tsx"):
            try:
                content = tsx_file.read_text()
                packages = await detect_npm_imports(content)
                detected_packages.update(packages)
            except Exception as e:
                print(f"Warning: Failed to detect imports from {tsx_file}: {e}")
        
        for ts_file in src_dir.rglob("*.ts"):
            try:
                content = ts_file.read_text()
                packages = await detect_npm_imports(content)
                detected_packages.update(packages)
            except Exception as e:
                print(f"Warning: Failed to detect imports from {ts_file}: {e}")
        
        # Add detected packages to dependencies
        if detected_packages:
            build_logs.append(f"[AUTO-DETECT] Found NPM packages: {sorted(detected_packages)}")
            print(f"[{project_id}] Detected NPM packages: {sorted(detected_packages)}")
            
            for package in detected_packages:
                # Add with 'latest' version (npm will resolve to latest stable)
                package_json["dependencies"][package] = "latest"
        
        (workspace / "package.json").write_text(json.dumps(package_json, indent=2))
        
        # Create Tailwind config
        tailwind_config = """/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
"""
        (workspace / "tailwind.config.js").write_text(tailwind_config)

        # Create PostCSS config
        postcss_config = """export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
"""
        (workspace / "postcss.config.js").write_text(postcss_config)

        # Create index.css with Tailwind directives IF NOT EXISTS
        index_css_path = src_dir / "index.css"
        if not index_css_path.exists():
            index_css = """@tailwind base;
@tailwind components;
@tailwind utilities;
"""
            index_css_path.write_text(index_css)
            build_logs.append("[AUTO-GEN] Created src/index.css")
        
        # Create minimal index.html
        index_html = f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Preview App</title>
    <script>
      // Global error handler for runtime errors
      window.addEventListener('error', function(event) {{
        const errorData = {{
          project_id: '{project_id}',
          error_type: 'runtime',
          message: event.message || 'Unknown error',
          stack_trace: event.error?.stack || '',
          file_path: event.filename || '',
          line_number: event.lineno || null,
          column_number: event.colno || null,
        }};
        
        // Report to error API
        fetch('/routes/errors/report', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify(errorData),
        }}).catch(console.error);
      }});
      
      // Promise rejection handler
      window.addEventListener('unhandledrejection', function(event) {{
        const errorData = {{
          project_id: '{project_id}',
          error_type: 'runtime',
          message: 'Unhandled Promise Rejection: ' + (event.reason?.message || event.reason),
          stack_trace: event.reason?.stack || '',
          file_path: '',
          line_number: null,
        }};
        
        fetch('/routes/errors/report', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify(errorData),
        }}).catch(console.error);
      }});
    </script>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
"""
        (workspace / "index.html").write_text(index_html)
        
        # Create minimal main.tsx if not exists
        main_tsx_path = src_dir / "main.tsx"
        if not main_tsx_path.exists():
            main_tsx = """import React from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'
import App from './App'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
"""
            main_tsx_path.write_text(main_tsx)
            build_logs.append("[AUTO-GEN] Created src/main.tsx")
        
        # Create app framework stub (Riff framework mock)
        app_stub_path = src_dir / "app.ts"
        if not app_stub_path.exists():
            app_stub = """// Stub for Riff 'app' framework module
export const API_URL = 'http://localhost:8000';
export const WS_API_URL = 'ws://localhost:8000';
export const APP_BASE_PATH = '/';

// Mock apiClient
export const apiClient = {
  get: async (url: string) => ({ data: { message: 'Mock API Response' } }),
  post: async (url: string, data?: any) => ({ data: { message: 'Mock API Response' } }),
  put: async (url: string, data?: any) => ({ data: { message: 'Mock API Response' } }),
  delete: async (url: string) => ({ data: { message: 'Mock API Response' } }),
};

export enum Mode {
  DEV = 'dev',
  PROD = 'prod'
}
export const mode = Mode.DEV;
"""                
            app_stub_path.write_text(app_stub)
        
        # Create shadcn UI component stubs
        ui_dir = src_dir / "components" / "ui"
        ui_dir.mkdir(parents=True, exist_ok=True)
        
        # Button stub
        if not (ui_dir / "button.tsx").exists():
            (ui_dir / "button.tsx").write_text("""import React from 'react';
export const Button = ({ children, onClick, className = '' }: any) => (
  <button onClick={onClick} className={`px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 ${className}`}>
    {children}
  </button>
);
""")
        
        # Spinner stub
        if not (ui_dir / "spinner.tsx").exists():
            (ui_dir / "spinner.tsx").write_text("""import React from 'react';
export const Spinner = ({ size = 'medium' }: any) => (
  <div className="animate-spin rounded-full border-4 border-gray-300 border-t-blue-500" 
       style={{ width: size === 'large' ? '48px' : '24px', height: size === 'large' ? '48px' : '24px' }} />
);
""")
        
        # Alert stub
        if not (ui_dir / "alert.tsx").exists():
            (ui_dir / "alert.tsx").write_text("""import React from 'react';
export const Alert = ({ type = 'info', message }: any) => (
  <div className={`p-4 rounded ${type === 'error' ? 'bg-red-100 text-red-700' : 'bg-blue-100 text-blue-700'}`}>
    {message}
  </div>
);
""")
        
        # Index file to export all UI components
        if not (ui_dir / "index.tsx").exists():
            (ui_dir / "index.tsx").write_text("""export { Button } from './button';
export { Spinner } from './spinner';
export { Alert } from './alert';
""")
        
        # Write vite.config.ts
        vite_config = f"""import {{ defineConfig }} from 'vite'
import react from '@vitejs/plugin-react-swc'
import path from 'path'

export default defineConfig({{
  plugins: [react()],
  base: './',  // Use relative paths to avoid Riff routing conflicts
  resolve: {{
    alias: {{
      '@': path.resolve(__dirname, './src'),
      'app': path.resolve(__dirname, './src/app.ts'),
    }},
  }},
  define: {{
    '__API_URL__': JSON.stringify('http://localhost:8000'),
    '__APP_BASE_PATH__': JSON.stringify('/'),
  }},
  build: {{
    outDir: 'dist',
    emptyOutDir: true,
  }},
}})
"""
        (workspace / "vite.config.ts").write_text(vite_config)
        
        # Create tsconfig.json
        tsconfig = {
            "compilerOptions": {
                "target": "ES2020",
                "useDefineForClassFields": True,
                "lib": ["ES2020", "DOM", "DOM.Iterable"],
                "module": "ESNext",
                "skipLibCheck": True,
                "moduleResolution": "bundler",
                "allowImportingTsExtensions": True,
                "resolveJsonModule": True,
                "isolatedModules": True,
                "noEmit": True,
                "jsx": "react-jsx",
                "strict": True,
                "noUnusedLocals": True,
                "noUnusedParameters": True,
                "noFallthroughCasesInSwitch": True
            },
            "include": ["src"]
        }
        (workspace / "tsconfig.json").write_text(json.dumps(tsconfig, indent=2))
        
        # Install dependencies
        build_logs.append("Installing dependencies...")
        install_result = subprocess.run(
            ["npm", "install", "--legacy-peer-deps", "--no-audit", "--no-fund"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=120
        )
        if install_result.returncode != 0:
            error_detail = f"npm install failed:\n{install_result.stderr}"
            build_logs.append(f"❌ {error_detail}")
            raise Exception(error_detail)
        build_logs.append("✅ Dependencies installed")
        print("Dependencies installed successfully")
        
        # Build with Vite
        print("Building with Vite...")
        build_logs.append("🔨 Building with Vite...")
        build_result = subprocess.run(
            ["npm", "run", "build"],
            cwd=workspace,
            capture_output=True,
            text=True,
        )
        
        if build_result.stdout:
            print(f"Vite build stdout: {build_result.stdout}")
            build_logs.append(f"Build output:\n{build_result.stdout}")
        if build_result.stderr:
            print(f"Vite build stderr: {build_result.stderr}")
            build_logs.append(f"Build errors:\n{build_result.stderr}")
        
        if build_result.returncode != 0:
            error_detail = f"Vite build failed: {build_result.stderr}"
            build_logs.append(f"❌ {error_detail}")
            
            # Parse and report errors to database
            await parse_and_report_build_errors(project_id, build_result.stderr, build_logs)
            
            raise Exception(error_detail)
        
        build_logs.append("✅ Build completed successfully")
        
        # Store the build output path (in production, this would go to DB or cache)
        # For now, we'll keep it in memory/temp and serve from there
        dist_dir = workspace / "dist"
        
        # After successful build, store in cache
        BUILD_CACHE[project_id] = dist_dir
        
        return {
            "success": True,
            "message": "Preview built successfully",
            "temp_dir": workspace,
            "dist_dir": str(dist_dir),
            "files_processed": len(rows)
        }
        
    except asyncpg.PostgresError as e:
        print(f"Database error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Build timeout (120s limit exceeded)")
    except Exception as e:
        print(f"Build error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Build error: {str(e)}")


@router.get("/preview/{project_id}")
async def serve_preview(project_id: str):
    """
    Serve the built preview HTML from cache.
    """
    print(f"[SERVE] Preview request for project_id: {project_id}")
    print(f"[SERVE] BUILD_CACHE keys: {list(BUILD_CACHE.keys())}")
    
    # Check if build exists in cache
    if project_id not in BUILD_CACHE:
        print(f"[SERVE ERROR] Project not in cache, showing build required page")
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Preview - Build Required</title>
                <style>
                    body {
                        font-family: system-ui, -apple-system, sans-serif;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        height: 100vh;
                        margin: 0;
                        background: #1a1a1a;
                        color: #fff;
                    }
                    .container {
                        text-align: center;
                        max-width: 500px;
                        padding: 2rem;
                    }
                    h1 { margin: 0 0 1rem; }
                    p { margin: 0.5rem 0; color: #aaa; }
                    code {
                        background: #2a2a2a;
                        padding: 0.2rem 0.5rem;
                        border-radius: 4px;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>🔨 Preview Build Required</h1>
                    <p>Please build the preview first by calling:</p>
                    <p><code>POST /preview/build/{project_id}</code></p>
                </div>
            </body>
            </html>
            """
        )
    
    # Serve the built index.html
    dist_dir = Path(BUILD_CACHE[project_id])
    print(f"[SERVE] dist_dir from cache: {dist_dir}")
    
    index_html = dist_dir / "index.html"
    print(f"[SERVE] index.html path: {index_html}")
    print(f"[SERVE] index.html exists: {index_html.exists()}")
    
    if not index_html.exists():
        raise HTTPException(
            status_code=500, detail="Built index.html not found"
        )
    
    html_content = index_html.read_text()
    
    # Rewrite asset paths to be relative to current directory
    # This ensures they work correctly with Riff's routing proxy
    import re
    
    # Replace paths that start with ./ or without ./ to use project_id
    # Change ./assets/file.js -> 96c089f1-14bb-4a5d-b18f-1a1e1066453a/assets/file.js
    
    # Fix script src paths
    html_content = re.sub(
        r'src="\./assets/([^"]+)"',
        f'src="{project_id}/assets/\\1"',
        html_content
    )
    html_content = re.sub(
        r'src="assets/([^"]+)"',
        f'src="{project_id}/assets/\\1"',
        html_content
    )
    
    # Fix link href paths
    html_content = re.sub(
        r'href="\./assets/([^"]+)"',
        f'href="{project_id}/assets/\\1"',
        html_content
    )
    html_content = re.sub(
        r'href="assets/([^"]+)"',
        f'href="{project_id}/assets/\\1"',
        html_content
    )
    
    # DEBUG: Log the actual HTML content (first 1000 chars)
    print(f"[SERVE] HTML preview (first 1000 chars):")
    print(html_content[:1000])
    print(f"[SERVE] Full HTML length: {len(html_content)} chars")
    
    # Check for asset references
    if '<script' in html_content:
        print(f"[SERVE] Found <script> tags in HTML")
        import re
        scripts = re.findall(r'<script[^>]*src=["\']([^"\'>]+)["\']', html_content)
        print(f"[SERVE] Script sources: {scripts}")
    
    if '<link' in html_content:
        print(f"[SERVE] Found <link> tags in HTML")
        import re
        links = re.findall(r'<link[^>]*href=["\']([^"\'>]+)["\']', html_content)
        print(f"[SERVE] Link hrefs: {links}")
    
    return HTMLResponse(content=html_content)


@router.get("/preview/{project_id}/assets/{filepath:path}")
async def serve_preview_assets(project_id: str, filepath: str):
    """
    Serve static assets (CSS, JS) for preview builds.
    """
    print(f"[ASSET REQUEST] project_id={project_id}, filepath={filepath}")
    print(f"[BUILD_CACHE] Keys in cache: {list(BUILD_CACHE.keys())}")
    
    if project_id not in BUILD_CACHE:
        print(f"[ASSET ERROR] Project {project_id} not found in BUILD_CACHE")
        raise HTTPException(status_code=404, detail="Preview not built")
    
    dist_dir = Path(BUILD_CACHE[project_id])
    print(f"[ASSET] dist_dir from cache: {dist_dir}")
    
    asset_path = dist_dir / "assets" / filepath
    print(f"[ASSET] Resolved asset_path: {asset_path}")
    print(f"[ASSET] File exists: {asset_path.exists()}")
    
    if not asset_path.exists() or not asset_path.is_file():
        print(f"[ASSET ERROR] Asset not found: {asset_path}")
        raise HTTPException(status_code=404, detail="Asset not found")
    
    # Security check: ensure path is within dist/assets
    if not str(asset_path.resolve()).startswith(str((dist_dir / "assets").resolve())):
        print(f"[ASSET ERROR] Path traversal attempt detected")
        raise HTTPException(status_code=403, detail="Invalid asset path")
    
    # Determine media type
    media_type = "application/octet-stream"
    if filepath.endswith(".js"):
        media_type = "application/javascript"
    elif filepath.endswith(".css"):
        media_type = "text/css"
    elif filepath.endswith(".json"):
        media_type = "application/json"
    elif filepath.endswith(".svg"):
        media_type = "image/svg+xml"
    
    print(f"[ASSET] Serving with media_type: {media_type}")
    return FileResponse(asset_path, media_type=media_type)
