"""
GitHub Integration API

Endpoints for integrating with GitHub:
- List user's repositories
- Create new repository from project
- Push generated files to repository
- Get repository information
"""

import os
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.libs.github_client import (
    GitHubClient,
    GitHubRepo,
    GitHubError,
    GitHubCommitResponse
)

router = APIRouter(prefix="/github", tags=["GitHub"])


# Request/Response Models
class CreateRepoRequest(BaseModel):
    """Request to create a new GitHub repository"""
    name: str = Field(..., description="Repository name")
    description: Optional[str] = Field(None, description="Repository description")
    private: bool = Field(False, description="Make repository private")
    auto_init: bool = Field(True, description="Initialize with README")
    gitignore_template: Optional[str] = Field(None, description="Gitignore template (e.g., 'Python', 'Node')")


class PushFileRequest(BaseModel):
    """Request to push a single file"""
    owner: str = Field(..., description="Repository owner")
    repo: str = Field(..., description="Repository name")
    path: str = Field(..., description="File path in repo (e.g., 'src/main.py')")
    content: str = Field(..., description="File content")
    message: str = Field(..., description="Commit message")
    branch: str = Field("main", description="Branch name")


class PushFilesRequest(BaseModel):
    """Request to push multiple files"""
    owner: str = Field(..., description="Repository owner")
    repo: str = Field(..., description="Repository name")
    files: List[dict] = Field(
        ...,
        description="List of files with 'path', 'content', and optional 'message' keys"
    )
    branch: str = Field("main", description="Branch name")
    update_existing: bool = Field(True, description="Update existing files")


class ListReposRequest(BaseModel):
    """Request parameters for listing repositories"""
    visibility: str = Field("all", description="Filter by visibility (all, public, private)")
    sort: str = Field("updated", description="Sort by (created, updated, pushed, full_name)")
    per_page: int = Field(30, description="Results per page (max 100)")
    page: int = Field(1, description="Page number")


class RateLimitResponse(BaseModel):
    """GitHub API rate limit information"""
    limit: int
    remaining: int
    reset: int
    used: int


class ProjectFile(BaseModel):
    """Project file with path and content"""
    path: str
    content: str


@router.get("/rate-limit")
async def get_rate_limit() -> RateLimitResponse:
    """
    Get GitHub API rate limit status
    
    Returns current rate limit information including:
    - Total limit
    - Remaining requests
    - Reset timestamp
    - Used requests
    """
    try:
        client = GitHubClient()
        rate_limit = client.get_rate_limit()
        return RateLimitResponse(**rate_limit)
    except GitHubError as e:
        raise HTTPException(status_code=e.status_code or 500, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get rate limit: {str(e)}")


@router.post("/repos/list")
async def list_repositories(request: ListReposRequest) -> List[GitHubRepo]:
    """
    List authenticated user's GitHub repositories
    
    Returns a list of repositories with details like:
    - Name, full name, description
    - URLs (html_url, clone_url, ssh_url)
    - Visibility (public/private)
    - Timestamps (created, updated, pushed)
    """
    try:
        client = GitHubClient()
        repos = client.list_repositories(
            visibility=request.visibility,
            sort=request.sort,
            per_page=request.per_page,
            page=request.page
        )
        return repos
    except GitHubError as e:
        raise HTTPException(status_code=e.status_code or 500, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list repositories: {str(e)}")


@router.get("/repos/{owner}/{repo}")
async def get_repository(owner: str, repo: str) -> GitHubRepo:
    """
    Get information about a specific repository
    
    Args:
        owner: Repository owner username
        repo: Repository name
    
    Returns detailed repository information
    """
    try:
        client = GitHubClient()
        repository = client.get_repository(owner, repo)
        return repository
    except GitHubError as e:
        raise HTTPException(status_code=e.status_code or 500, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get repository: {str(e)}")


@router.post("/repos/create")
async def create_repository(request: CreateRepoRequest) -> GitHubRepo:
    """
    Create a new GitHub repository for the authenticated user
    
    Creates a new repository with the specified settings.
    Returns the created repository details including clone URLs.
    """
    try:
        client = GitHubClient()
        repo = client.create_repository(
            name=request.name,
            description=request.description,
            private=request.private,
            auto_init=request.auto_init,
            gitignore_template=request.gitignore_template
        )
        return repo
    except GitHubError as e:
        # Handle specific errors
        if e.status_code == 422 and e.response:
            # Repository name already exists or validation error
            errors = e.response.get('errors', [])
            if errors:
                error_msg = ", ".join([err.get('message', '') for err in errors])
                raise HTTPException(status_code=422, detail=f"Validation error: {error_msg}")
        raise HTTPException(status_code=e.status_code or 500, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create repository: {str(e)}")


@router.post("/files/push")
async def push_file(request: PushFileRequest) -> GitHubCommitResponse:
    """
    Push a single file to a GitHub repository
    
    Creates or updates a file in the repository.
    File content will be base64-encoded automatically.
    """
    try:
        client = GitHubClient()
        
        # Check if file exists to get SHA
        sha = None
        try:
            sha = client.get_file_sha(request.owner, request.repo, request.path, request.branch)
        except GitHubError:
            # File doesn't exist, will create new
            pass
        
        commit = client.push_file(
            owner=request.owner,
            repo=request.repo,
            path=request.path,
            content=request.content,
            message=request.message,
            branch=request.branch,
            sha=sha
        )
        return commit
    except GitHubError as e:
        raise HTTPException(status_code=e.status_code or 500, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to push file: {str(e)}")


@router.post("/files/push-batch")
async def push_files(request: PushFilesRequest) -> List[GitHubCommitResponse]:
    """
    Push multiple files to a GitHub repository
    
    Pushes multiple files in sequence.
    Each file should have 'path', 'content', and optional 'message' keys.
    
    Returns a list of commit responses for successfully pushed files.
    """
    try:
        client = GitHubClient()
        commits = client.push_files(
            owner=request.owner,
            repo=request.repo,
            files=request.files,
            branch=request.branch,
            update_existing=request.update_existing
        )
        return commits
    except GitHubError as e:
        raise HTTPException(status_code=e.status_code or 500, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to push files: {str(e)}")


@router.delete("/repos/{owner}/{repo}")
async def delete_repository(owner: str, repo: str) -> dict:
    """
    Delete a GitHub repository
    
    ⚠️ WARNING: This action is irreversible!
    
    Args:
        owner: Repository owner username
        repo: Repository name
    
    Returns success message
    """
    try:
        client = GitHubClient()
        success = client.delete_repository(owner, repo)
        if success:
            return {"message": f"Repository {owner}/{repo} deleted successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete repository")
    except GitHubError as e:
        raise HTTPException(status_code=e.status_code or 500, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete repository: {str(e)}")

@router.get("/project-files")
async def get_project_files() -> List[ProjectFile]:
    """
    Collect all project files from the workspace
    
    Returns a list of files with their paths and content,
    ready to be pushed to GitHub
    """
    try:
        project_root = Path("/disk")
        files = []
        
        # Files to include
        include_patterns = [
            # Root config files
            "backend/pyproject.toml",
            "backend/main.py",
            "frontend/package.json",
            "frontend/index.html",
            "frontend/tailwind.config.js",
            
            # Backend files
            "backend/app/libs/*.py",
            "backend/app/apis/**/__init__.py",
            
            # Frontend files  
            "frontend/src/main.tsx",
            "frontend/src/pages/*.tsx",
            "frontend/src/components/*.tsx",
            "frontend/src/utils/*.ts",
        ]
        
        # Files to exclude
        exclude_patterns = [
            "__pycache__",
            "node_modules",
            ".venv",
            "dist",
            "build",
            ".git",
            "*.pyc",
            ".DS_Store"
        ]
        
        def should_exclude(path: Path) -> bool:
            path_str = str(path)
            return any(pattern in path_str for pattern in exclude_patterns)
        
        # Collect backend files
        backend_dir = project_root / "backend"
        if backend_dir.exists():
            # Add main files
            for file_path in ["pyproject.toml", "main.py"]:
                full_path = backend_dir / file_path
                if full_path.exists() and full_path.is_file():
                    try:
                        content = full_path.read_text(encoding="utf-8")
                        files.append(ProjectFile(
                            path=f"backend/{file_path}",
                            content=content
                        ))
                    except Exception as e:
                        print(f"Error reading {full_path}: {e}")
            
            # Add libs
            libs_dir = backend_dir / "app" / "libs"
            if libs_dir.exists():
                for py_file in libs_dir.glob("*.py"):
                    if not should_exclude(py_file):
                        try:
                            content = py_file.read_text(encoding="utf-8")
                            files.append(ProjectFile(
                                path=f"backend/app/libs/{py_file.name}",
                                content=content
                            ))
                        except Exception as e:
                            print(f"Error reading {py_file}: {e}")
            
            # Add API files
            apis_dir = backend_dir / "app" / "apis"
            if apis_dir.exists():
                for api_dir in apis_dir.iterdir():
                    if api_dir.is_dir() and not should_exclude(api_dir):
                        init_file = api_dir / "__init__.py"
                        if init_file.exists():
                            try:
                                content = init_file.read_text(encoding="utf-8")
                                files.append(ProjectFile(
                                    path=f"backend/app/apis/{api_dir.name}/__init__.py",
                                    content=content
                                ))
                            except Exception as e:
                                print(f"Error reading {init_file}: {e}")
        
        # Collect frontend files
        frontend_dir = project_root / "frontend"
        if frontend_dir.exists():
            # Add main config files
            for file_path in ["package.json", "index.html", "tailwind.config.js"]:
                full_path = frontend_dir / file_path
                if full_path.exists() and full_path.is_file():
                    try:
                        content = full_path.read_text(encoding="utf-8")
                        files.append(ProjectFile(
                            path=f"frontend/{file_path}",
                            content=content
                        ))
                    except Exception as e:
                        print(f"Error reading {full_path}: {e}")
            
            # Add src/main.tsx
            main_file = frontend_dir / "src" / "main.tsx"
            if main_file.exists():
                try:
                    content = main_file.read_text(encoding="utf-8")
                    files.append(ProjectFile(
                        path="frontend/src/main.tsx",
                        content=content
                    ))
                except Exception as e:
                    print(f"Error reading {main_file}: {e}")
            
            # Add pages
            pages_dir = frontend_dir / "src" / "pages"
            if pages_dir.exists():
                for tsx_file in pages_dir.glob("*.tsx"):
                    if not should_exclude(tsx_file):
                        try:
                            content = tsx_file.read_text(encoding="utf-8")
                            files.append(ProjectFile(
                                path=f"frontend/src/pages/{tsx_file.name}",
                                content=content
                            ))
                        except Exception as e:
                            print(f"Error reading {tsx_file}: {e}")
            
            # Add components
            components_dir = frontend_dir / "src" / "components"
            if components_dir.exists():
                for tsx_file in components_dir.glob("*.tsx"):
                    if not should_exclude(tsx_file):
                        try:
                            content = tsx_file.read_text(encoding="utf-8")
                            files.append(ProjectFile(
                                path=f"frontend/src/components/{tsx_file.name}",
                                content=content
                            ))
                        except Exception as e:
                            print(f"Error reading {tsx_file}: {e}")
            
            # Add utils
            utils_dir = frontend_dir / "src" / "utils"
            if utils_dir.exists():
                for ts_file in utils_dir.glob("*.ts"):
                    if not should_exclude(ts_file):
                        try:
                            content = ts_file.read_text(encoding="utf-8")
                            files.append(ProjectFile(
                                path=f"frontend/src/utils/{ts_file.name}",
                                content=content
                            ))
                        except Exception as e:
                            print(f"Error reading {ts_file}: {e}")
        
        # Add README
        readme_content = """# Holio As - Riff AI Studio

An AI-powered platform for building apps through natural language.

## Features
- Conversational AI chat interface
- Interactive project plan editor  
- Natural language to code generation (Python + React)
- Live app preview and testing
- One-click GitHub deployment
- Integration marketplace

## Tech Stack
- **Frontend:** React + TypeScript + Vite + Tailwind CSS + shadcn/ui
- **Backend:** FastAPI + Python
- **Database:** PostgreSQL
- **AI:** OpenAI GPT-4
- **Auth:** Stack Auth

## Project Structure
```
backend/
├── app/
│   ├── apis/       # FastAPI route handlers
│   └── libs/       # Reusable Python modules
├── main.py         # FastAPI app entry point
└── pyproject.toml  # Python dependencies

frontend/
├── src/
│   ├── pages/      # React page components
│   ├── components/ # Reusable UI components
│   └── utils/      # Frontend utilities
├── package.json    # NPM dependencies
└── index.html      # App entry point
```

## Getting Started

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend  
```bash
cd frontend
npm install
npm run dev
```

Built with ❤️ using Riff
"""
        files.append(ProjectFile(path="README.md", content=readme_content))
        
        # Add .gitignore
        gitignore_content = """# Dependencies
node_modules/
__pycache__/
*.pyc
.venv/
venv/

# Build outputs
dist/
build/
.next/

# Environment variables
.env
.env.local

# IDE
.vscode/
.idea/
*.swp
*.swo
.DS_Store

# Logs
*.log
npm-debug.log*
"""
        files.append(ProjectFile(path=".gitignore", content=gitignore_content))
        
        print(f"Collected {len(files)} project files")
        return files
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to collect project files: {str(e)}")
