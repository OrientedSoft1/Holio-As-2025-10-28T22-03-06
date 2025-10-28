"""
AI Tool Registry

Defines all available tools in OpenAI function calling format.
Each tool maps to a backend endpoint that the AI can execute.
"""

from typing import List, Dict, Any


def get_all_tools() -> List[Dict[str, Any]]:
    """Get all available AI tools in OpenAI function format."""
    return [
        # Task Management Tools
        {
            "type": "function",
            "function": {
                "name": "create_task",
                "description": "Create a new task in the project. Use this to break down work into actionable items.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Short, clear task title (e.g., 'Build login page', 'Add API endpoint')"
                        },
                        "description": {
                            "type": "string",
                            "description": "Detailed description of what needs to be done, including technical details"
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                            "description": "Task priority level"
                        },
                        "status": {
                            "type": "string",
                            "enum": ["todo", "in_progress", "done"],
                            "description": "Initial task status"
                        }
                    },
                    "required": ["title", "description"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "update_task",
                "description": "Update an existing task's properties (title, description, status, priority).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_id": {
                            "type": "string",
                            "description": "UUID of the task to update"
                        },
                        "title": {
                            "type": "string",
                            "description": "New task title"
                        },
                        "description": {
                            "type": "string",
                            "description": "New task description"
                        },
                        "status": {
                            "type": "string",
                            "enum": ["todo", "in_progress", "done"],
                            "description": "New task status"
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                            "description": "New priority level"
                        }
                    },
                    "required": ["task_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "list_tasks",
                "description": "Get all tasks for the current project. Useful for checking what work has been done or needs to be done.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "delete_task",
                "description": "Delete a task from the project.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_id": {
                            "type": "string",
                            "description": "UUID of the task to delete"
                        }
                    },
                    "required": ["task_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "add_task_comment",
                "description": "Add a comment or progress update to a task. Use this to document decisions, learnings, or blockers.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_id": {
                            "type": "string",
                            "description": "UUID of the task to comment on"
                        },
                        "comment": {
                            "type": "string",
                            "description": "Comment text"
                        },
                        "comment_type": {
                            "type": "string",
                            "enum": ["note", "blocker", "decision", "learning"],
                            "description": "Type of comment"
                        }
                    },
                    "required": ["task_id", "comment"]
                }
            }
        },
        
        # File Management Tools
        {
            "type": "function",
            "function": {
                "name": "create_file",
                "description": "Create a new code file in the project. Use this to generate React components, Python APIs, configs, etc.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path where file should be created (e.g., 'backend/app.py', 'frontend/src/components/Button.tsx')"
                        },
                        "file_content": {
                            "type": "string",
                            "description": "Complete file content including all code, imports, and comments"
                        },
                        "file_type": {
                            "type": "string",
                            "enum": ["python", "typescript", "javascript", "json", "yaml", "markdown", "css", "html", "other"],
                            "description": "Type of file being created"
                        },
                        "description": {
                            "type": "string",
                            "description": "Brief description of what this file does"
                        }
                    },
                    "required": ["file_path", "file_content", "file_type"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "update_file",
                "description": "Update an existing file with new content. Creates a new version while preserving history.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_id": {
                            "type": "string",
                            "description": "UUID of the file to update"
                        },
                        "file_content": {
                            "type": "string",
                            "description": "New complete file content"
                        },
                        "description": {
                            "type": "string",
                            "description": "Description of what changed in this update"
                        }
                    },
                    "required": ["file_id", "file_content"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "read_files",
                "description": "Read all files in the project to see what code has been generated.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "search_code",
                "description": "Search for specific code patterns or keywords across all project files.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query (code snippet, function name, keyword, etc.)"
                        }
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "delete_file",
                "description": "Delete a file from the project (soft delete - marks as inactive).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_id": {
                            "type": "string",
                            "description": "UUID of the file to delete"
                        }
                    },
                    "required": ["file_id"]
                }
            }
        },
        
        # Project Tools
        {
            "type": "function",
            "function": {
                "name": "get_project_stats",
                "description": "Get statistics about the project (file count, task count, etc.). Useful for progress updates.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_file_tree",
                "description": "Get a hierarchical view of all files in the project structure.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        
        # Database Tools
        {
            "type": "function",
            "function": {
                "name": "run_sql_query",
                "description": "Execute a SQL query against the project database. Use for data inspection or simple operations.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "SQL query to execute"
                        },
                        "query_type": {
                            "type": "string",
                            "enum": ["select", "insert", "update", "delete"],
                            "description": "Type of SQL operation"
                        }
                    },
                    "required": ["query", "query_type"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_sql_schema",
                "description": "Get the current database schema for the project.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "run_migration",
                "description": "Run a database migration script to create or modify tables.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "migration_name": {
                            "type": "string",
                            "description": "Name of the migration"
                        },
                        "sql": {
                            "type": "string",
                            "description": "SQL migration script"
                        }
                    },
                    "required": ["migration_name", "sql"]
                }
            }
        },
        
        # Development Tools
        {
            "type": "function",
            "function": {
                "name": "run_python_script",
                "description": "Execute a Python script for testing, data processing, or prototyping.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "script": {
                            "type": "string",
                            "description": "Python code to execute"
                        },
                        "description": {
                            "type": "string",
                            "description": "Description of what the script does"
                        }
                    },
                    "required": ["script"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "read_logs",
                "description": "Read application logs to debug issues or check execution status.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "level": {
                            "type": "string",
                            "enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                            "description": "Minimum log level to retrieve"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of log entries to return"
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "test_endpoint",
                "description": "Test an API endpoint with sample data to verify it works correctly.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "endpoint_path": {
                            "type": "string",
                            "description": "API endpoint path to test"
                        },
                        "method": {
                            "type": "string",
                            "enum": ["GET", "POST", "PUT", "DELETE"],
                            "description": "HTTP method"
                        },
                        "test_data": {
                            "type": "object",
                            "description": "Test data to send to the endpoint"
                        }
                    },
                    "required": ["endpoint_path", "method"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "troubleshoot",
                "description": "Analyze errors and get suggestions for fixing issues.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "error_message": {
                            "type": "string",
                            "description": "Error message or description of the problem"
                        },
                        "context": {
                            "type": "string",
                            "description": "Additional context about when/where the error occurred"
                        }
                    },
                    "required": ["error_message"]
                }
            }
        },
        
        # Integration Tools
        {
            "type": "function",
            "function": {
                "name": "enable_integration",
                "description": "Enable a third-party integration (e.g., GitHub, OpenAI, database).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "integration_name": {
                            "type": "string",
                            "description": "Name of the integration to enable"
                        },
                        "config": {
                            "type": "object",
                            "description": "Integration configuration (API keys, settings, etc.)"
                        }
                    },
                    "required": ["integration_name"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "list_integrations",
                "description": "List all enabled integrations for the project.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        
        # Package Management Tools
        {
            "type": "function",
            "function": {
                "name": "install_packages",
                "description": "Install Python (pip) or NPM packages required by generated code. Use this when creating code that imports external libraries like pandas, axios, recharts, etc.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "packages": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of package names to install (e.g., ['pandas', 'numpy'] or ['axios', 'recharts'])"
                        },
                        "package_manager": {
                            "type": "string",
                            "enum": ["pip", "npm"],
                            "description": "Which package manager to use: 'pip' for Python packages, 'npm' for JavaScript/TypeScript packages"
                        }
                    },
                    "required": ["packages", "package_manager"]
                }
            }
        },
        
        # Data & Visualization Tools
        {
            "type": "function",
            "function": {
                "name": "visualize_data",
                "description": "Create a data visualization (chart, graph, table) from data.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "data": {
                            "type": "array",
                            "description": "Array of data objects to visualize"
                        },
                        "chart_type": {
                            "type": "string",
                            "enum": ["bar", "line", "pie", "table", "scatter"],
                            "description": "Type of visualization"
                        },
                        "title": {
                            "type": "string",
                            "description": "Chart title"
                        }
                    },
                    "required": ["data", "chart_type"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "request_data",
                "description": "Request data or files from the user.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "Message asking the user for specific data"
                        },
                        "data_type": {
                            "type": "string",
                            "enum": ["file", "text", "json", "csv"],
                            "description": "Type of data being requested"
                        }
                    },
                    "required": ["message", "data_type"]
                }
            }
        },
    ]


def get_tool_by_name(tool_name: str) -> Dict[str, Any] | None:
    """Get a specific tool definition by name."""
    tools = get_all_tools()
    for tool in tools:
        if tool["function"]["name"] == tool_name:
            return tool
    return None
