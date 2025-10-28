"""
GitHub API Client Library

Provides a wrapper around the GitHub REST API for:
- Creating repositories
- Pushing files to repos (base64-encoded)
- Listing user's repositories
- Committing changes

Requires GITHUB_TOKEN environment variable with appropriate scopes:
- repo (for repository operations)
- workflow (for .github/workflows files)
"""

import os
import base64
from typing import Optional, Dict, Any, List
import requests
from pydantic import BaseModel


class GitHubRepo(BaseModel):
    """GitHub repository model"""
    id: int
    name: str
    full_name: str
    description: Optional[str] = None
    html_url: str
    clone_url: str
    ssh_url: str
    default_branch: str
    private: bool
    created_at: str
    updated_at: str
    pushed_at: Optional[str] = None


class GitHubFileContent(BaseModel):
    """Model for file to push to GitHub"""
    path: str  # File path in repo (e.g., "src/main.py")
    content: str  # File content (will be base64-encoded)
    message: str  # Commit message for this file


class GitHubCommitResponse(BaseModel):
    """Response from file commit operation"""
    sha: str
    url: str
    html_url: str


class GitHubError(Exception):
    """Custom exception for GitHub API errors"""
    def __init__(self, message: str, status_code: Optional[int] = None, response: Optional[Dict] = None):
        self.message = message
        self.status_code = status_code
        self.response = response
        super().__init__(self.message)


class GitHubClient:
    """
    GitHub API Client
    
    Handles all interactions with the GitHub REST API.
    """
    
    BASE_URL = "https://api.github.com"
    
    def __init__(self, token: Optional[str] = None):
        """
        Initialize GitHub client
        
        Args:
            token: GitHub Personal Access Token. If not provided, will use GITHUB_TOKEN env var.
        """
        self.token = token or os.environ.get("GITHUB_TOKEN")
        if not self.token:
            raise GitHubError("GitHub token not found. Please set GITHUB_TOKEN environment variable.")
        
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        
        # Get authenticated user info
        self.user = self._get_authenticated_user()
        print(f"✅ GitHub client initialized for user: {self.user['login']}")
    
    def _get_authenticated_user(self) -> Dict[str, Any]:
        """Get authenticated user information"""
        response = requests.get(
            f"{self.BASE_URL}/user",
            headers=self.headers
        )
        
        if response.status_code != 200:
            raise GitHubError(
                f"Failed to authenticate with GitHub: {response.status_code}",
                status_code=response.status_code,
                response=response.json() if response.text else None
            )
        
        return response.json()
    
    def get_rate_limit(self) -> Dict[str, Any]:
        """Check GitHub API rate limit status"""
        response = requests.get(
            f"{self.BASE_URL}/rate_limit",
            headers=self.headers
        )
        
        if response.status_code == 200:
            data = response.json()
            return data['rate']
        
        return {"error": "Failed to fetch rate limit"}
    
    def list_repositories(
        self,
        visibility: str = "all",  # all, public, private
        sort: str = "updated",  # created, updated, pushed, full_name
        per_page: int = 30,
        page: int = 1
    ) -> List[GitHubRepo]:
        """
        List authenticated user's repositories
        
        Args:
            visibility: Filter by visibility (all, public, private)
            sort: Sort by field (created, updated, pushed, full_name)
            per_page: Results per page (max 100)
            page: Page number
        
        Returns:
            List of GitHubRepo objects
        """
        params = {
            "visibility": visibility,
            "sort": sort,
            "per_page": min(per_page, 100),
            "page": page
        }
        
        response = requests.get(
            f"{self.BASE_URL}/user/repos",
            headers=self.headers,
            params=params
        )
        
        if response.status_code != 200:
            raise GitHubError(
                f"Failed to list repositories: {response.status_code}",
                status_code=response.status_code,
                response=response.json() if response.text else None
            )
        
        repos_data = response.json()
        return [GitHubRepo(**repo) for repo in repos_data]
    
    def get_repository(self, owner: str, repo: str) -> GitHubRepo:
        """
        Get repository information
        
        Args:
            owner: Repository owner username
            repo: Repository name
        
        Returns:
            GitHubRepo object
        """
        response = requests.get(
            f"{self.BASE_URL}/repos/{owner}/{repo}",
            headers=self.headers
        )
        
        if response.status_code != 200:
            raise GitHubError(
                f"Failed to get repository: {response.status_code}",
                status_code=response.status_code,
                response=response.json() if response.text else None
            )
        
        return GitHubRepo(**response.json())
    
    def create_repository(
        self,
        name: str,
        description: Optional[str] = None,
        private: bool = False,
        auto_init: bool = True,
        gitignore_template: Optional[str] = None
    ) -> GitHubRepo:
        """
        Create a new repository for the authenticated user
        
        Args:
            name: Repository name
            description: Repository description
            private: Whether the repository should be private
            auto_init: Create initial commit with README
            gitignore_template: Language or platform for .gitignore template
        
        Returns:
            GitHubRepo object for the created repository
        """
        payload = {
            "name": name,
            "description": description or f"AI-generated app: {name}",
            "private": private,
            "auto_init": auto_init,
            "has_issues": True,
            "has_projects": False,
            "has_wiki": False
        }
        
        if gitignore_template:
            payload["gitignore_template"] = gitignore_template
        
        response = requests.post(
            f"{self.BASE_URL}/user/repos",
            headers=self.headers,
            json=payload
        )
        
        if response.status_code not in [201, 200]:
            raise GitHubError(
                f"Failed to create repository: {response.status_code}",
                status_code=response.status_code,
                response=response.json() if response.text else None
            )
        
        repo_data = response.json()
        print(f"✅ Created repository: {repo_data['html_url']}")
        return GitHubRepo(**repo_data)
    
    def push_file(
        self,
        owner: str,
        repo: str,
        path: str,
        content: str,
        message: str,
        branch: str = "main",
        sha: Optional[str] = None
    ) -> GitHubCommitResponse:
        """
        Create or update a file in a repository
        
        Args:
            owner: Repository owner username
            repo: Repository name
            path: File path in repo (e.g., "src/main.py")
            content: File content (will be base64-encoded)
            message: Commit message
            branch: Branch name (default: main)
            sha: File SHA if updating existing file
        
        Returns:
            GitHubCommitResponse with commit details
        """
        # Base64 encode the content
        content_encoded = base64.b64encode(content.encode('utf-8')).decode('utf-8')
        
        payload = {
            "message": message,
            "content": content_encoded,
            "branch": branch
        }
        
        # If updating existing file, need to provide SHA
        if sha:
            payload["sha"] = sha
        
        response = requests.put(
            f"{self.BASE_URL}/repos/{owner}/{repo}/contents/{path}",
            headers=self.headers,
            json=payload
        )
        
        if response.status_code not in [200, 201]:
            raise GitHubError(
                f"Failed to push file {path}: {response.status_code}",
                status_code=response.status_code,
                response=response.json() if response.text else None
            )
        
        commit_data = response.json()['commit']
        print(f"✅ Pushed file: {path}")
        return GitHubCommitResponse(
            sha=commit_data['sha'],
            url=commit_data['url'],
            html_url=commit_data['html_url']
        )
    
    def get_file_sha(self, owner: str, repo: str, path: str, branch: str = "main") -> Optional[str]:
        """
        Get the SHA of an existing file (needed for updates)
        
        Args:
            owner: Repository owner username
            repo: Repository name
            path: File path in repo
            branch: Branch name
        
        Returns:
            File SHA or None if file doesn't exist
        """
        response = requests.get(
            f"{self.BASE_URL}/repos/{owner}/{repo}/contents/{path}",
            headers=self.headers,
            params={"ref": branch}
        )
        
        if response.status_code == 200:
            return response.json()['sha']
        elif response.status_code == 404:
            return None  # File doesn't exist
        else:
            raise GitHubError(
                f"Failed to get file SHA for {path}: {response.status_code}",
                status_code=response.status_code,
                response=response.json() if response.text else None
            )
    
    def push_files(
        self,
        owner: str,
        repo: str,
        files: List[Dict[str, str]],
        branch: str = "main",
        update_existing: bool = True
    ) -> List[GitHubCommitResponse]:
        """
        Push multiple files to a repository
        
        Args:
            owner: Repository owner username
            repo: Repository name
            files: List of dicts with 'path', 'content', and 'message' keys
            branch: Branch name
            update_existing: Whether to update existing files (requires fetching SHAs)
        
        Returns:
            List of GitHubCommitResponse objects
        """
        results = []
        
        for i, file_info in enumerate(files):
            # Validate required keys
            if 'path' not in file_info:
                print(f"❌ File {i}: missing 'path' key")
                continue
            if 'content' not in file_info:
                print(f"❌ File {i} ({file_info.get('path', 'unknown')}): missing 'content' key")
                continue
            
            path = file_info['path']
            content = file_info['content']
            message = file_info.get('message', f"Update {path}")
            
            sha = None
            if update_existing:
                # Try to get existing file SHA
                try:
                    sha = self.get_file_sha(owner, repo, path, branch)
                except GitHubError:
                    # If error getting SHA, treat as new file
                    pass
            
            # Push the file
            try:
                commit_response = self.push_file(
                    owner=owner,
                    repo=repo,
                    path=path,
                    content=content,
                    message=message,
                    branch=branch,
                    sha=sha
                )
                results.append(commit_response)
            except GitHubError as e:
                print(f"❌ Failed to push {path}: {e.message}")
                # Continue with other files
                continue
        
        print(f"✅ Pushed {len(results)}/{len(files)} files successfully")
        return results
    
    def delete_repository(self, owner: str, repo: str) -> bool:
        """
        Delete a repository (use with caution!)
        
        Args:
            owner: Repository owner username
            repo: Repository name
        
        Returns:
            True if successful
        """
        response = requests.delete(
            f"{self.BASE_URL}/repos/{owner}/{repo}",
            headers=self.headers
        )
        
        if response.status_code == 204:
            print(f"✅ Deleted repository: {owner}/{repo}")
            return True
        else:
            raise GitHubError(
                f"Failed to delete repository: {response.status_code}",
                status_code=response.status_code,
                response=response.json() if response.text else None
            )
