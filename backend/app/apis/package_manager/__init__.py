"""
Package Manager API

Handles automatic installation of Python (pip) and NPM packages.
"""

import re
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

router = APIRouter()

class InstallPackagesRequest(BaseModel):
    packages: List[str]
    package_manager: str

class InstallPackagesResponse(BaseModel):
    success: bool
    installed_packages: List[str]
    failed_packages: List[str]
    message: str
    details: Optional[str] = None

PYTHON_PACKAGE_MAPPING = {
    "cv2": "opencv-python",
    "PIL": "Pillow",
    "sklearn": "scikit-learn",
    "yaml": "pyyaml",
}

PYTHON_BUILTINS = {
    "os", "sys", "re", "json", "typing", "datetime", "pathlib", "asyncio",
    "collections", "itertools", "functools", "math", "random", "time",
}

async def install_pip_packages(packages: List[str]) -> Dict[str, Any]:
    print(f"Installing pip packages: {packages}")
    installed = []
    failed = []
    details = []
    
    try:
        # Riff uses uv as package manager
        result = subprocess.run(
            ["uv", "pip", "install", *packages],
            capture_output=True,
            text=True,
            timeout=300,
            cwd="/disk/backend"  # Run in backend directory where pyproject.toml is
        )
        details.append(f"STDOUT: {result.stdout}")
        
        if result.returncode != 0:
            details.append(f"STDERR: {result.stderr}")
            failed.extend(packages)
            return {"success": False, "installed": installed, "failed": failed, "details": "\n".join(details)}
        
        installed = packages
        return {"success": True, "installed": installed, "failed": failed, "details": "\n".join(details)}
    except Exception as e:
        return {"success": False, "installed": [], "failed": packages, "details": f"Error: {str(e)}"}

async def install_npm_packages(packages: List[str]) -> Dict[str, Any]:
    print(f"Installing npm packages: {packages}")
    installed = []
    failed = []
    details = []
    
    try:
        # Frontend uses Yarn, not npm
        result = subprocess.run(
            ["yarn", "add", *packages],
            capture_output=True,
            text=True,
            timeout=300,
            cwd="/disk/frontend"
        )
        details.append(f"STDOUT: {result.stdout}")
        
        if result.returncode != 0:
            details.append(f"STDERR: {result.stderr}")
            failed.extend(packages)
            return {"success": False, "installed": installed, "failed": failed, "details": "\n".join(details)}
        
        installed = packages
        return {"success": True, "installed": installed, "failed": failed, "details": "\n".join(details)}
    except Exception as e:
        return {"success": False, "installed": [], "failed": packages, "details": f"Error: {str(e)}"}

@router.post("/install", response_model=InstallPackagesResponse)
async def install_packages_endpoint(request: InstallPackagesRequest) -> InstallPackagesResponse:
    print(f"\n🔧 Installing packages: {request.packages} via {request.package_manager}")
    
    if not request.packages:
        return InstallPackagesResponse(
            success=True,
            installed_packages=[],
            failed_packages=[],
            message="No packages to install"
        )
    
    if request.package_manager == "pip":
        result = await install_pip_packages(request.packages)
    elif request.package_manager == "npm":
        result = await install_npm_packages(request.packages)
    else:
        raise HTTPException(status_code=400, detail=f"Invalid package manager: {request.package_manager}")
    
    message = f"✅ Installed {len(result['installed'])} package(s)" if result["success"] else f"⚠️ Failed: {len(result['failed'])} package(s)"
    
    return InstallPackagesResponse(
        success=result["success"],
        installed_packages=result["installed"],
        failed_packages=result["failed"],
        message=message,
        details=result.get("details")
    )
