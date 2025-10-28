"""Package detection utilities for Python and TypeScript/JavaScript code.

This module analyzes generated code to detect required packages that need to be installed.
It maps import statements to their corresponding package names.
"""

import re
from typing import List, Set


# Mapping of import names to package names
# e.g., "cv2" imports from "opencv-python" package
PYTHON_PACKAGE_MAPPING = {
    "cv2": "opencv-python",
    "PIL": "Pillow",
    "sklearn": "scikit-learn",
    "yaml": "pyyaml",
    "dotenv": "python-dotenv",
    "dateutil": "python-dateutil",
    "jwt": "pyjwt",
    "bs4": "beautifulsoup4",
    "psycopg2": "psycopg2-binary",
}

# Standard library modules that should NOT be installed
PYTHON_STDLIB = {
    "abc", "asyncio", "collections", "datetime", "decimal", "enum", "functools",
    "hashlib", "itertools", "json", "logging", "math", "os", "pathlib", "re",
    "sys", "time", "typing", "uuid", "warnings", "io", "copy", "traceback",
    "dataclasses", "base64", "hmac", "secrets", "string", "random", "tempfile",
    "shutil", "subprocess", "urllib", "http", "email", "mimetypes", "platform",
    "contextlib", "inspect", "dis", "gc", "weakref", "operator", "types",
}

# Built-in Node.js modules that should NOT be installed
NODE_BUILTINS = {
    "assert", "buffer", "child_process", "cluster", "crypto", "dgram", "dns",
    "domain", "events", "fs", "http", "https", "net", "os", "path", "punycode",
    "querystring", "readline", "repl", "stream", "string_decoder", "timers",
    "tls", "tty", "url", "util", "v8", "vm", "zlib",
}

# Packages that are part of the Riff framework (already available)
RIFF_FRAMEWORK_PACKAGES = {
    "app",  # Riff app module
    "databutton",  # Databutton SDK
    "fastapi",  # FastAPI framework
    "pydantic",  # Pydantic models
    "asyncpg",  # PostgreSQL driver
}

# React/Riff UI packages that are already available
RIFF_UI_PACKAGES = {
    "react",
    "react-dom",
    "react-router-dom",
    "@/components/ui",  # shadcn components
    "@/hooks",  # shadcn hooks
    "app",  # Riff app module
    "types",  # Generated types
    "components",  # Riff components
    "utils",  # Riff utils
}


def detect_python_packages(code: str) -> List[str]:
    """Extract Python package names from import statements.
    
    Args:
        code: Python source code
        
    Returns:
        List of package names that need to be installed
        
    Examples:
        >>> detect_python_packages("import pandas as pd")
        ['pandas']
        >>> detect_python_packages("from sklearn.model_selection import train_test_split")
        ['scikit-learn']
    """
    packages: Set[str] = set()
    
    # Match: import package
    # Match: import package as alias
    import_pattern = r'^import\s+(\w+)(?:\s+as\s+\w+)?'
    for match in re.finditer(import_pattern, code, re.MULTILINE):
        module = match.group(1)
        packages.add(module)
    
    # Match: from package import ...
    from_pattern = r'^from\s+(\w+)'
    for match in re.finditer(from_pattern, code, re.MULTILINE):
        module = match.group(1)
        packages.add(module)
    
    # Filter out standard library and framework packages
    external_packages = [
        pkg for pkg in packages
        if pkg not in PYTHON_STDLIB
        and pkg not in RIFF_FRAMEWORK_PACKAGES
    ]
    
    # Map import names to package names
    mapped_packages = [
        PYTHON_PACKAGE_MAPPING.get(pkg, pkg)
        for pkg in external_packages
    ]
    
    return sorted(set(mapped_packages))


def detect_npm_packages(code: str) -> List[str]:
    """Extract NPM package names from import statements.
    
    Args:
        code: TypeScript/JavaScript source code
        
    Returns:
        List of package names that need to be installed
        
    Examples:
        >>> detect_npm_packages("import axios from 'axios'")
        ['axios']
        >>> detect_npm_packages("import { Chart } from 'recharts'")
        ['recharts']
    """
    packages: Set[str] = set()
    
    # Match: import ... from 'package'
    # Match: import ... from "package"
    import_pattern = r"from\s+['\"]([^'\"./][^'\"]*)['\"]"  
    for match in re.finditer(import_pattern, code):
        package = match.group(1)
        
        # Extract base package name (handle scoped packages)
        # e.g., '@radix-ui/react-dialog' → '@radix-ui/react-dialog'
        # e.g., 'lodash/debounce' → 'lodash'
        if package.startswith('@'):
            # Scoped package: keep @scope/package
            parts = package.split('/')
            if len(parts) >= 2:
                package = f"{parts[0]}/{parts[1]}"
        else:
            # Regular package: take first part before /
            package = package.split('/')[0]
        
        packages.add(package)
    
    # Filter out Node.js built-ins and Riff framework packages
    external_packages = [
        pkg for pkg in packages
        if pkg not in NODE_BUILTINS
        and pkg not in RIFF_UI_PACKAGES
        and not pkg.startswith('@/')  # Ignore alias imports (@/components)
    ]
    
    return sorted(set(external_packages))


def detect_packages_from_files(files: List[dict]) -> dict:
    """Detect packages from multiple generated files.
    
    Args:
        files: List of file dictionaries with 'file_path' and 'file_content'
        
    Returns:
        Dictionary with 'python' and 'npm' package lists
        
    Example:
        >>> files = [
        ...     {'file_path': 'backend/app.py', 'file_content': 'import pandas'},
        ...     {'file_path': 'frontend/App.tsx', 'file_content': 'import axios from "axios"'}
        ... ]
        >>> detect_packages_from_files(files)
        {'python': ['pandas'], 'npm': ['axios']}
    """
    python_packages: Set[str] = set()
    npm_packages: Set[str] = set()
    
    for file in files:
        file_path = file.get('file_path', '')
        file_content = file.get('file_content', '')
        
        # Detect Python packages
        if file_path.endswith('.py'):
            packages = detect_python_packages(file_content)
            python_packages.update(packages)
        
        # Detect NPM packages
        elif file_path.endswith(('.tsx', '.ts', '.jsx', '.js')):
            packages = detect_npm_packages(file_content)
            npm_packages.update(packages)
    
    return {
        'python': sorted(python_packages),
        'npm': sorted(npm_packages)
    }
