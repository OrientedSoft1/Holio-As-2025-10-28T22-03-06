from fastapi import APIRouter
from pydantic import BaseModel
import subprocess
import json
from typing import List, Optional
from pathlib import Path
import toml

router = APIRouter()

class InstalledPackage(BaseModel):
    """Model for an installed package"""
    name: str
    version: str
    package_manager: str  # 'pip' or 'npm'
    description: Optional[str] = None

class InstalledPackagesResponse(BaseModel):
    """Response model for installed packages"""
    python_packages: List[InstalledPackage]
    npm_packages: List[InstalledPackage]
    total_count: int

@router.get("/installed-packages/{project_id}")
async def get_installed_packages(project_id: str) -> InstalledPackagesResponse:
    """
    Get all installed packages for a specific project (both Python and NPM)
    Returns package name, version, and package manager type from PROJECT workspace
    """
    
    python_packages = []
    npm_packages = []
    
    # Path to project workspace
    project_workspace = Path(f"/disk/backend/.preview-builds/{project_id}")
    
    if not project_workspace.exists():
        # Project workspace not created yet
        return InstalledPackagesResponse(
            python_packages=[],
            npm_packages=[],
            total_count=0
        )
    
    # Get Python packages from project's pyproject.toml
    try:
        pyproject_path = project_workspace / "backend" / "pyproject.toml"
        if pyproject_path.exists():
            pyproject_data = toml.load(pyproject_path)
            dependencies = pyproject_data.get("project", {}).get("dependencies", [])
            
            for dep in dependencies:
                # Parse dependency string (e.g., "fastapi>=0.100.0" -> "fastapi")
                pkg_name = dep.split(">")[0].split("<")[0].split("=")[0].split("[")[0].strip()
                
                # Try to get actual installed version from venv
                venv_path = project_workspace / "backend" / ".venv"
                version = "unknown"
                
                if venv_path.exists():
                    try:
                        # Run pip list in project venv
                        result = subprocess.run(
                            [str(venv_path / "bin" / "python"), "-m", "pip", "list", "--format=json"],
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        if result.returncode == 0:
                            installed = json.loads(result.stdout)
                            for pkg in installed:
                                if pkg.get("name", "").lower() == pkg_name.lower():
                                    version = pkg.get("version", "unknown")
                                    break
                    except Exception as e:
                        print(f"Warning: Failed to get version for {pkg_name}: {e}")
                
                python_packages.append(InstalledPackage(
                    name=pkg_name,
                    version=version,
                    package_manager="pip"
                ))
    except Exception as e:
        print(f"Error getting Python packages from project: {e}")
    
    # Get NPM packages from project's package.json
    try:
        package_json_path = project_workspace / "frontend" / "package.json"
        if package_json_path.exists():
            with open(package_json_path, 'r') as f:
                package_data = json.load(f)
            
            # Get dependencies
            dependencies = package_data.get("dependencies", {})
            dev_dependencies = package_data.get("devDependencies", {})
            
            # Combine all dependencies
            all_deps = {**dependencies, **dev_dependencies}
            
            # Get actual installed versions from node_modules
            for pkg_name, declared_version in all_deps.items():
                node_modules_path = project_workspace / "frontend" / "node_modules" / pkg_name / "package.json"
                
                actual_version = declared_version
                if node_modules_path.exists():
                    try:
                        with open(node_modules_path, 'r') as f:
                            pkg_data = json.load(f)
                            actual_version = pkg_data.get('version', declared_version)
                    except Exception:
                        pass
                
                npm_packages.append(InstalledPackage(
                    name=pkg_name,
                    version=actual_version.replace("^", "").replace("~", ""),
                    package_manager="npm",
                    description=None
                ))
    except Exception as e:
        print(f"Error getting NPM packages from project: {e}")
    
    # Sort packages by name
    python_packages.sort(key=lambda x: x.name.lower())
    npm_packages.sort(key=lambda x: x.name.lower())
    
    return InstalledPackagesResponse(
        python_packages=python_packages,
        npm_packages=npm_packages,
        total_count=len(python_packages) + len(npm_packages)
    )
