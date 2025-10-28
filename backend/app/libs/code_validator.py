

"""Code validation utilities for Python and TypeScript."""
import ast
import re
import os
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class ValidationError:
    """Represents a code validation error."""
    error_type: str  # 'syntax', 'import', 'type'
    message: str
    line_number: Optional[int] = None
    column: Optional[int] = None
    suggestion: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of code validation."""
    is_valid: bool
    errors: List[ValidationError]
    warnings: List[str]
    imports: List[str]  # Detected imports


# Common Python package name mappings (import → package name)
PYTHON_IMPORT_TO_PACKAGE = {
    'requests': 'requests',
    'numpy': 'numpy',
    'pandas': 'pandas',
    'sklearn': 'scikit-learn',
    'PIL': 'Pillow',
    'cv2': 'opencv-python',
    'bs4': 'beautifulsoup4',
    'yaml': 'pyyaml',
    'dotenv': 'python-dotenv',
    'jwt': 'pyjwt',
    'openai': 'openai',
    'anthropic': 'anthropic',
    'stripe': 'stripe',
    'httpx': 'httpx',
    'asyncpg': 'asyncpg',
    'sqlalchemy': 'sqlalchemy',
    'redis': 'redis',
    'celery': 'celery',
    'scrapy': 'scrapy',
}


def validate_python_syntax(code: str) -> ValidationResult:
    """Validate Python code syntax using AST parsing.
    
    Args:
        code: Python source code string
        
    Returns:
        ValidationResult with syntax errors and detected imports
    """
    errors: List[ValidationError] = []
    warnings: List[str] = []
    imports: List[str] = []
    
    # Try to parse the code
    try:
        tree = ast.parse(code)
        
        # Extract imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name.split('.')[0])  # Get base module
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module.split('.')[0])  # Get base module
        
        # Remove duplicates
        imports = list(set(imports))
        
        return ValidationResult(
            is_valid=True,
            errors=[],
            warnings=warnings,
            imports=imports
        )
        
    except SyntaxError as e:
        error = ValidationError(
            error_type='syntax',
            message=str(e.msg),
            line_number=e.lineno,
            column=e.offset,
            suggestion=_suggest_syntax_fix(e)
        )
        errors.append(error)
        
        return ValidationResult(
            is_valid=False,
            errors=errors,
            warnings=warnings,
            imports=[]
        )
    
    except Exception as e:
        error = ValidationError(
            error_type='unknown',
            message=f"Failed to parse code: {str(e)}",
            suggestion=None
        )
        errors.append(error)
        
        return ValidationResult(
            is_valid=False,
            errors=errors,
            warnings=warnings,
            imports=[]
        )


def _suggest_syntax_fix(syntax_error: SyntaxError) -> Optional[str]:
    """Suggest a fix for common syntax errors."""
    msg = syntax_error.msg.lower()
    
    # Common patterns
    if 'unexpected eof' in msg or 'expected' in msg:
        return "Check for missing closing brackets, parentheses, or quotes"
    
    if 'invalid syntax' in msg:
        if syntax_error.text and ':' in syntax_error.text:
            return "Check indentation after colon (:)"
        return "Check for typos or missing colons"
    
    if 'indentation' in msg:
        return "Fix indentation - use consistent spaces or tabs"
    
    if 'f-string' in msg:
        return "Check f-string syntax - ensure proper braces {}"
    
    return None


def get_missing_packages(imports: List[str], installed_packages: List[str]) -> List[str]:
    """Identify which packages need to be installed.
    
    Args:
        imports: List of imported module names
        installed_packages: List of currently installed package names
        
    Returns:
        List of package names that need to be installed
    """
    missing = []
    installed_lower = [pkg.lower() for pkg in installed_packages]
    
    for import_name in imports:
        # Skip standard library modules
        if import_name in _STANDARD_LIBRARY_MODULES:
            continue
        
        # Map import to package name
        package_name = PYTHON_IMPORT_TO_PACKAGE.get(import_name, import_name)
        
        # Check if installed
        if package_name.lower() not in installed_lower:
            missing.append(package_name)
    
    return missing


# Partial list of Python standard library modules (commonly used)
_STANDARD_LIBRARY_MODULES = {
    'abc', 'aifc', 'argparse', 'array', 'ast', 'asynchat', 'asyncio', 'asyncore',
    'atexit', 'audioop', 'base64', 'bdb', 'binascii', 'binhex', 'bisect',
    'builtins', 'bz2', 'calendar', 'cgi', 'cgitb', 'chunk', 'cmath', 'cmd',
    'code', 'codecs', 'codeop', 'collections', 'colorsys', 'compileall',
    'concurrent', 'configparser', 'contextlib', 'contextvars', 'copy', 'copyreg',
    'crypt', 'csv', 'ctypes', 'curses', 'dataclasses', 'datetime', 'dbm',
    'decimal', 'difflib', 'dis', 'distutils', 'doctest', 'email', 'encodings',
    'enum', 'errno', 'faulthandler', 'fcntl', 'filecmp', 'fileinput', 'fnmatch',
    'formatter', 'fractions', 'ftplib', 'functools', 'gc', 'getopt', 'getpass',
    'gettext', 'glob', 'graphlib', 'grp', 'gzip', 'hashlib', 'heapq', 'hmac',
    'html', 'http', 'imaplib', 'imghdr', 'imp', 'importlib', 'inspect', 'io',
    'ipaddress', 'itertools', 'json', 'keyword', 'lib2to3', 'linecache', 'locale',
    'lzma', 'mailbox', 'mailcap', 'marshal', 'math', 'mimetypes', 'mmap',
    'modulefinder', 'multiprocessing', 'netrc', 'nis', 'nntplib', 'numbers',
    'operator', 'optparse', 'os', 'ossaudiodev', 'parser', 'pathlib', 'pdb',
    'pickle', 'pickletools', 'pipes', 'pkgutil', 'platform', 'plistlib', 'poplib',
    'posix', 'posixpath', 'pprint', 'profile', 'pstats', 'pty', 'pwd', 'py_compile',
    'pyclbr', 'pydoc', 'queue', 'quopri', 'random', 're', 'readline', 'reprlib',
    'resource', 'rlcompleter', 'runpy', 'sched', 'secrets', 'select', 'selectors',
    'shelve', 'shlex', 'shutil', 'signal', 'site', 'smtpd', 'smtplib', 'sndhdr',
    'socket', 'socketserver', 'spwd', 'sqlite3', 'ssl', 'stat', 'statistics',
    'string', 'stringprep', 'struct', 'subprocess', 'sunau', 'symbol', 'symtable',
    'sys', 'sysconfig', 'syslog', 'tabnanny', 'tarfile', 'telnetlib', 'tempfile',
    'termios', 'test', 'textwrap', 'threading', 'time', 'timeit', 'tkinter',
    'token', 'tokenize', 'tomllib', 'trace', 'traceback', 'tracemalloc', 'tty',
    'turtle', 'turtledemo', 'types', 'typing', 'unicodedata', 'unittest', 'urllib',
    'uu', 'uuid', 'venv', 'warnings', 'wave', 'weakref', 'webbrowser', 'winreg',
    'winsound', 'wsgiref', 'xdrlib', 'xml', 'xmlrpc', 'zipapp', 'zipfile', 'zipimport',
    'zlib', 'zoneinfo',
    # Common third-party that shouldn't trigger (often pre-installed)
    'fastapi', 'pydantic', 'uvicorn', 'starlette',
}


def validate_typescript_syntax(code: str) -> ValidationResult:
    """Validate TypeScript/React code (basic checks).
    
    Note: This is a basic implementation. For full validation,
    we'd need to use TypeScript compiler API.
    
    Args:
        code: TypeScript source code string
        
    Returns:
        ValidationResult with detected issues
    """
    errors: List[ValidationError] = []
    warnings: List[str] = []
    imports: List[str] = []
    
    # Extract imports
    import_pattern = r'import\s+(?:{[^}]+}|\w+|\*\s+as\s+\w+)\s+from\s+["\']([^"\']+)["\']'
    for match in re.finditer(import_pattern, code):
        import_path = match.group(1)
        # Extract package name (before first /)
        if not import_path.startswith('.'):
            package = import_path.split('/')[0]
            if package.startswith('@'):
                # Scoped package like @radix-ui/react-dialog
                package = '/'.join(import_path.split('/')[:2])
            imports.append(package)
    
    # Remove duplicates
    imports = list(set(imports))
    
    # Basic syntax checks
    
    # Check for unmatched braces
    open_braces = code.count('{')
    close_braces = code.count('}')
    if open_braces != close_braces:
        errors.append(ValidationError(
            error_type='syntax',
            message=f"Unmatched braces: {open_braces} open, {close_braces} close",
            suggestion="Check for missing or extra braces"
        ))
    
    # Check for unmatched parentheses
    open_parens = code.count('(')
    close_parens = code.count(')')
    if open_parens != close_parens:
        errors.append(ValidationError(
            error_type='syntax',
            message=f"Unmatched parentheses: {open_parens} open, {close_parens} close",
            suggestion="Check for missing or extra parentheses"
        ))
    
    # Check for unmatched brackets
    open_brackets = code.count('[')
    close_brackets = code.count(']')
    if open_brackets != close_brackets:
        errors.append(ValidationError(
            error_type='syntax',
            message=f"Unmatched brackets: {open_brackets} open, {close_brackets} close",
            suggestion="Check for missing or extra brackets"
        ))
    
    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        imports=imports
    )


async def auto_heal_code(
    broken_code: str,
    validation_errors: List[ValidationError],
    language: str
) -> str:
    """Use AI to automatically fix code syntax errors.
    
    Args:
        broken_code: The code with syntax errors
        validation_errors: List of validation errors
        language: Programming language (python/typescript)
        
    Returns:
        Fixed code string
        
    Raises:
        Exception if AI fails to fix the code
    """
    from openai import AsyncOpenAI
    
    client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    
    # Format errors for prompt
    error_details = "\n".join([
        f"- Line {err.line_number}: {err.message}" + 
        (f" (Suggestion: {err.suggestion})" if err.suggestion else "")
        for err in validation_errors
    ])
    
    prompt = f"""You are a code fixing assistant. Fix the syntax errors in this {language} code.

**Errors Found:**
{error_details}

**Broken Code:**
```{language}
{broken_code}
```

**Instructions:**
1. Fix ONLY the syntax errors mentioned above
2. Do NOT change the logic or add new features
3. Preserve all comments and formatting
4. Return ONLY the fixed code without explanations or markdown
5. Do NOT wrap the code in code blocks (```)

**Fixed Code:**"""
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a precise code fixing assistant. Fix syntax errors without changing logic."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=2000
        )
        
        fixed_code = response.choices[0].message.content
        
        # Clean up potential markdown wrapper
        if fixed_code.startswith("```"):
            lines = fixed_code.split("\n")
            # Remove first line (```language) and last line (```))
            fixed_code = "\n".join(lines[1:-1])
        
        return fixed_code.strip()
        
    except Exception as e:
        raise Exception(f"AI auto-healing failed: {str(e)}")
