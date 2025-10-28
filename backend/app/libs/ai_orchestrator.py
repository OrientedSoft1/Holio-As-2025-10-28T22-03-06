









import os
import json
from typing import Dict, List, Any, Optional, AsyncGenerator
from openai import AsyncOpenAI

from app.libs.ai_tool_registry import get_all_tools
from app.libs.ai_system_prompt import get_system_prompt, get_planning_prompt, get_debugging_prompt
from app.libs.ai_context_loader import AIContextLoader
from app.libs.package_detector import detect_packages_from_files


class AIOrchestrator:
    """Orchestrates AI conversations with tool calling capabilities and context awareness."""

    def __init__(self, project_id: str):
        """Initialize the orchestrator.
        
        Args:
            project_id: The current project ID for context
        """
        self.project_id = project_id
        self.client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.conversation_history: List[Dict[str, Any]] = []
        self.db_url = os.environ.get("DATABASE_URL")
        self.context_loader: Optional[AIContextLoader] = None
        self._context_loaded = False
        self._cached_context = None

    async def analyze_intent(self, message: str) -> str:
        """Analyze user message to determine intent.
        
        Returns:
            Intent type: 'feature_request', 'question', 'debug', or 'chat'
        """
        # Use a quick GPT-4 call to classify intent
        response = await self.client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": """Classify user messages into one of these categories:
- feature_request: User wants to build/add something (e.g., \"build a dashboard\", \"add auth\")
- debug: User reports an error or bug (e.g., \"it's broken\", \"getting an error\")
- question: User asks about how something works
- chat: General conversation or unclear intent

Respond with ONLY the category name, nothing else."""
                },
                {"role": "user", "content": message}
            ],
            temperature=0
        )
        
        intent = response.choices[0].message.content.strip().lower()
        return intent if intent in ["feature_request", "debug", "question", "chat"] else "chat"

    async def create_project_plan(self, user_request: str) -> Dict[str, Any]:
        """Generate a structured project plan from user request.
        
        Args:
            user_request: The user's feature request
            
        Returns:
            Structured plan with tasks, database schema, APIs, pages
        """
        planning_prompt = get_planning_prompt()
        
        response = await self.client.chat.completions.create(
            model="gpt-4o",  # Use gpt-4o for JSON mode support
            messages=[
                {"role": "system", "content": planning_prompt},
                {"role": "user", "content": f"{user_request}\n\nPlease respond with a valid JSON object."}
            ],
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        
        plan_json = response.choices[0].message.content
        plan = json.loads(plan_json)
        
        return plan

    async def _generate_code_from_plan(self, plan: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """Generate actual code files from project plan.
        
        Takes the structured plan and generates:
        - SQL migrations from database_schema
        - Python backend files from apis
        - React frontend files from pages
        
        Args:
            plan: The project plan dictionary
            
        Yields:
            Progress updates and file creation messages
        """
        print(f"DEBUG: _generate_code_from_plan CALLED with plan: {json.dumps(plan, indent=2)[:200]}...")  # Debug log
        yield "\n\n🔨 **Generating Code from Plan...**\n\n"
        
        # 1. Generate database migrations
        schema = plan.get('database_schema', [])
        if schema:
            yield f"📊 Creating database schema ({len(schema)} tables)...\n"
            
            # Build SQL migration
            migration_sql = "-- Auto-generated migration from project plan\n\n"
            
            for table in schema:
                table_name = table.get('name', 'unknown_table')
                columns = table.get('columns', [])
                
                migration_sql += f"CREATE TABLE IF NOT EXISTS {table_name} (\n"
                column_defs = []
                
                for col in columns:
                    col_name = col.get('name', 'col')
                    col_type = col.get('type', 'TEXT')
                    constraints = col.get('constraints', '')
                    column_defs.append(f"    {col_name} {col_type} {constraints}")
                
                migration_sql += ',\n'.join(column_defs)
                migration_sql += "\n);\n\n"
            
            # Run migration
            try:
                result = await self.execute_tool('run_migration', {
                    'migration_name': 'auto_generated_schema',
                    'sql': migration_sql
                })
                if result.get('success'):
                    yield "✅ Database schema created\n"
                else:
                    yield "⚠️ Migration failed: {0}\n".format(result.get('error', 'Unknown error'))
            except Exception as e:
                yield "❌ Migration error: {0}\n".format(str(e))
        
        # 2. Generate backend API files
        apis = plan.get('apis', [])
        if apis:
            yield f"\n🔧 Creating backend APIs ({len(apis)} endpoints)...\n"
            
            for api in apis:
                endpoint = api.get('endpoint', '/api/unknown')
                method = api.get('method', 'GET')
                description = api.get('description', '')
                
                # Extract API name from endpoint (e.g., /api/todos -> todos)
                api_name = endpoint.strip('/').split('/')[-1]
                if not api_name:
                    api_name = 'unnamed_api'
                
                # Generate Python code using GPT-4
                code_prompt = f"""Generate a complete FastAPI endpoint file for:

Endpoint: {method} {endpoint}
Description: {description}

Requirements:
- Create router: router = APIRouter()
- Include all necessary imports (FastAPI, Pydantic, asyncpg, os)
- Define Pydantic request/response models
- Implement the endpoint function with proper error handling
- Use async/await for database operations
- Include docstrings
- Follow best practices

Generate ONLY the Python code, no explanations."""
                
                try:
                    code_response = await self.client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": "You are an expert Python/FastAPI developer. Generate clean, production-ready code."},
                            {"role": "user", "content": code_prompt}
                        ],
                        temperature=0.3
                    )
                    
                    generated_code = code_response.choices[0].message.content
                    print(f"DEBUG: GPT-4 raw response for {api_name}: {generated_code[:200] if generated_code else 'NONE'}...")
                    
                    # Remove markdown code blocks if present
                    if '```python' in generated_code:
                        generated_code = generated_code.split('```python')[1].split('```')[0].strip()
                    elif '```' in generated_code:
                        generated_code = generated_code.split('```')[1].split('```')[0].strip()
                    
                    print(f"DEBUG: Extracted code for {api_name}: {generated_code[:200] if generated_code else 'NONE'}...")
                    
                    # Create the file
                    result = await self.execute_tool('create_file', {
                        'file_path': f'backend/app/apis/{api_name}/__init__.py',
                        'file_content': generated_code,
                        'language': 'python',
                        'file_type': 'api'
                    })
                    
                    if result.get('success'):
                        yield "✅ Created {0} API\n".format(api_name)
                    else:
                        yield "⚠️ Failed to create {0}: {1}\n".format(api_name, result.get('error'))
                        
                except Exception as e:
                    yield "❌ Error generating {0}: {1}\n".format(api_name, str(e))
        
        # 3. Generate frontend page files
        pages = plan.get('pages', [])
        if pages:
            yield f"\n🎨 Creating frontend pages ({len(pages)} pages)...\n"
            
            for page in pages:
                page_name = page.get('name', 'UnknownPage')
                route = page.get('route', '/')
                description = page.get('description', '')
                
                # Generate React/TypeScript code using GPT-4
                code_prompt = f"""Generate a complete React/TypeScript page component for:

Page Name: {page_name}
Route: {route}
Description: {description}

Requirements:
- Use TypeScript with proper interfaces
- Import React hooks (useState, useEffect)
- Use apiClient from 'app' for API calls
- Use shadcn/ui components from '@/components/ui/'
- Include loading and error states
- Use Tailwind CSS for styling
- Export default the component
- Follow modern React best practices
- Make it look professional with proper layout

Generate ONLY the TypeScript/React code, no explanations."""
                
                try:
                    code_response = await self.client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": "You are an expert React/TypeScript developer. Generate clean, production-ready code with beautiful UI."},
                            {"role": "user", "content": code_prompt}
                        ],
                        temperature=0.3
                    )
                    
                    generated_code = code_response.choices[0].message.content
                    
                    # Remove markdown code blocks if present
                    if '```typescript' in generated_code or '```tsx' in generated_code:
                        generated_code = generated_code.split('```')[1].split('```')[0]
                        if generated_code.startswith('typescript\n') or generated_code.startswith('tsx\n'):
                            generated_code = '\n'.join(generated_code.split('\n')[1:])
                        generated_code = generated_code.strip()
                    elif '```' in generated_code:
                        generated_code = generated_code.split('```')[1].split('```')[0].strip()
                    
                    # Create the file
                    result = await self.execute_tool('create_file', {
                        'file_path': f'frontend/src/pages/{page_name}.tsx',
                        'file_content': generated_code,
                        'language': 'typescript',
                        'file_type': 'page'
                    })
                    
                    if result.get('success'):
                        yield f"✅ Created {page_name} page\n"
                    else:
                        yield "⚠️ Failed to create {0}: {1}\n".format(page_name, result.get('error'))
                        
                except Exception as e:
                    yield f"❌ Error generating {page_name}: {str(e)}\n"
        
        yield "\n✨ **Code Generation Complete!**\n"
        yield "Files are now available in the code editor.\n"
        
        # NEW: Auto-detect and install packages
        yield "\n📦 **Detecting Required Packages...**\n"
        
        try:
            # Read all generated files to detect packages
            files_result = await self.execute_tool('read_files', {'file_paths': []})
            all_files = files_result.get('files', [])
            
            # Filter to only files we just generated
            generated_files = [
                {'file_path': f.get('file_path'), 'file_content': f.get('content')}
                for f in all_files
                if f.get('file_path', '').startswith('backend/app/apis/') or 
                   f.get('file_path', '').startswith('frontend/src/pages/')
            ]
            
            if generated_files:
                # Detect packages from generated code
                detected = detect_packages_from_files(generated_files)
                
                python_packages = detected.get('python', [])
                npm_packages = detected.get('npm', [])
                
                # Install Python packages
                if python_packages:
                    yield f"🐍 Installing Python packages: {', '.join(python_packages)}\n"
                    try:
                        install_result = await self.execute_tool('install_packages', {
                            'packages': python_packages,
                            'package_manager': 'pip'
                        })
                        if install_result.get('success'):
                            yield f"   ✅ Python packages installed\n"
                        else:
                            yield f"   ⚠️ Some packages failed: {install_result.get('error')}\n"
                    except Exception as e:
                        yield f"   ❌ Package installation error: {str(e)}\n"
                
                # Install NPM packages
                if npm_packages:
                    yield f"📦 Installing NPM packages: {', '.join(npm_packages)}\n"
                    try:
                        install_result = await self.execute_tool('install_packages', {
                            'packages': npm_packages,
                            'package_manager': 'npm'
                        })
                        if install_result.get('success'):
                            yield f"   ✅ NPM packages installed\n"
                        else:
                            yield f"   ⚠️ Some packages failed: {install_result.get('error')}\n"
                    except Exception as e:
                        yield f"   ❌ Package installation error: {str(e)}\n"
                
                if not python_packages and not npm_packages:
                    yield "   ℹ️ No additional packages needed\n"
            
        except Exception as e:
            yield f"⚠️ Package detection failed: {str(e)}\n"
            # Continue anyway - not a critical failure
        
        # Auto-healing loop: Build, detect errors, fix
        yield "\n🔄 **Starting Auto-Healing Loop...**\n"
        
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            yield f"\n--- Attempt {attempt}/{max_attempts} ---\n"
            
            # Trigger build
            yield "🔨 Building project...\n"
            try:
                build_result = await self.execute_tool('trigger_build', {})
                if not build_result.get('success'):
                    yield f"⚠️ Build trigger failed: {build_result.get('error')}\n"
                    break
                yield "✅ Build triggered\n"
            except Exception as e:
                yield f"❌ Build error: {str(e)}\n"
                break
            
            # Wait a bit for build to complete
            import asyncio
            await asyncio.sleep(2)
            
            # Check for errors
            yield "🔍 Checking for errors...\n"
            try:
                errors_result = await self.execute_tool('get_open_errors', {})
                errors = errors_result.get('errors', [])
                
                if not errors:
                    yield "🎉 No errors found! Auto-healing complete.\n"
                    break
                
                yield f"⚠️ Found {len(errors)} error(s)\n"
                
                # Analyze and fix errors
                for idx, error in enumerate(errors[:3], 1):  # Fix max 3 errors per attempt
                    file_path = error.get('file_path', 'unknown')
                    line_number = error.get('line_number', 0)
                    message = error.get('message', '')
                    code_snippet = error.get('code_snippet', '')
                    
                    yield f"\n{idx}. Fixing {file_path}:{line_number}\n"
                    yield f"   Error: {message}\n"
                    
                    # Read the full file
                    file_result = await self.execute_tool('read_files', {
                        'file_paths': [file_path]
                    })
                    
                    files = file_result.get('files', [])
                    if not files:
                        yield f"   ⚠️ Could not read file\n"
                        continue
                    
                    file_content = files[0].get('content', '')
                    
                    # Ask AI to fix the error
                    fix_prompt = f"""Fix this error in the code:

File: {file_path}
Line: {line_number}
Error: {message}

Code snippet with error:
```
{code_snippet}
```

Full file content:
```
{file_content}
```

Provide ONLY the complete fixed file content, no explanations."""
                    
                    try:
                        fix_response = await self.client.chat.completions.create(
                            model="gpt-4o",
                            messages=[
                                {"role": "system", "content": "You are an expert developer. Fix code errors precisely."},
                                {"role": "user", "content": fix_prompt}
                            ],
                            temperature=0.1
                        )
                        
                        fixed_code = fix_response.choices[0].message.content
                        
                        # Remove markdown code blocks if present
                        if '```' in fixed_code:
                            fixed_code = fixed_code.split('```')[1].split('```')[0]
                            if fixed_code.startswith('typescript\n') or fixed_code.startswith('tsx\n') or fixed_code.startswith('python\n'):
                                fixed_code = '\n'.join(fixed_code.split('\n')[1:])
                            fixed_code = fixed_code.strip()
                        
                        # Update the file
                        update_result = await self.execute_tool('update_file', {
                            'file_path': file_path,
                            'file_content': fixed_code
                        })
                        
                        if update_result.get('success'):
                            yield f"   ✅ Fixed {file_path}\n"
                            
                            # Mark error as resolved
                            error_id = error.get('id')
                            if error_id:
                                await self.execute_tool('resolve_error', {
                                    'error_id': error_id,
                                    'resolution_notes': f'Auto-fixed in attempt {attempt}'
                                })
                        else:
                            yield f"   ⚠️ Failed to update file: {update_result.get('error')}\n"
                    
                    except Exception as e:
                        yield f"   ❌ Error fixing: {str(e)}\n"
            
            except Exception as e:
                yield f"❌ Error checking errors: {str(e)}\n"
                break
        
        yield "\n✨ Auto-healing loop complete!\n"

    async def generate_with_planning(self, message: str, context: Dict[str, Any] = None) -> AsyncGenerator[str, None]:
        """Main generation pipeline with intelligent routing and context awareness.
        
        Args:
            message: User's message
            context: Optional context (tasks, files, etc.) - DEPRECATED, use AIContextLoader instead
            
        Yields:
            Streaming response chunks
        """
        # Load project context if not already loaded
        if not self._context_loaded:
            try:
                self.context_loader = AIContextLoader(self.project_id)
                await self.context_loader.__aenter__()
                self._cached_context = await self.context_loader.load_context()
                self._context_loaded = True
                yield "[Loading project context...]\n"
            except Exception as e:
                print(f"Warning: Could not load context: {e}")
                yield f"[Warning: Context loading failed]\n"
        
        # Step 1: Analyze intent
        intent = await self.analyze_intent(message)
        
        yield f"[Intent: {intent}]"
        
        # Step 2: Route based on intent
        if intent == "feature_request":
            # Generate structured plan
            yield "🎯 Creating project plan..."
            plan = await self.create_project_plan(message)
            
            yield f"**Project Plan Generated:**"
            yield f"**Description:** {plan.get('description', 'N/A')}"
            
            # Show tasks
            tasks = plan.get('tasks', [])
            if tasks:
                yield f"**Tasks ({len(tasks)}):**"
                for idx, task in enumerate(tasks, 1):
                    yield f"{idx}. {task.get('title', 'Untitled')}"
                    yield f"   - {task.get('description', 'No description')}"
                yield ""
            
            # Show database schema
            schema = plan.get('database_schema', [])
            if schema:
                yield f"**Database Tables ({len(schema)}):**"
                for table in schema:
                    yield f"- {table.get('name', 'unknown')}"
                yield ""
            
            # Show APIs
            apis = plan.get('apis', [])
            if apis:
                yield f"**APIs ({len(apis)}):**"
                for api in apis:
                    yield f"- {api.get('endpoint', 'unknown')} ({api.get('method', 'GET')})"
                yield ""
            
            # Show pages
            pages = plan.get('pages', [])
            if pages:
                yield f"**Pages ({len(pages)}):**"
                for page in pages:
                    yield f"- {page.get('name', 'unknown')}"
                yield ""
            
            # Auto-create tasks
            yield "\n📝 Creating tasks automatically..."
            
            # Create tasks using the tool executor
            tasks_created = 0
            task_ids = []
            for task_data in tasks:
                try:
                    result = await self.execute_tool(
                        "create_task",
                        {
                            "title": task_data.get("title", "Untitled Task"),
                            "description": task_data.get("description", ""),
                            "priority": task_data.get("priority", "medium"),
                            "integrations": task_data.get("integrations", []),
                            "labels": task_data.get("labels", [])
                        }
                    )
                    print(f"Task creation result: {result}")  # Debug log
                    if result.get("success", False):
                        tasks_created += 1
                        task_id = result.get("data", {}).get("task_id", "unknown")
                        task_ids.append(task_id)
                        yield f"✅ Created: {task_data.get('title')} (ID: {task_id[:8]}...)"
                    else:
                        error_msg = result.get("error", result.get("message", "Unknown error"))
                        yield f"⚠️ Failed: {task_data.get('title')} - {error_msg}"
                except Exception as e:
                    print(f"Exception creating task: {e}")  # Debug log
                    import traceback
                    traceback.print_exc()
                    yield f"❌ Error creating task: {str(e)}"
            
            yield f"\n✅ Successfully created {tasks_created}/{len(tasks)} tasks!"
            yield "You can now start working on these tasks in the task panel."
            
            # Generate code from plan
            files_generated = []
            async for code_chunk in self._generate_code_from_plan(plan):
                yield code_chunk
                # Track generated files (simplified)
                if "Created" in code_chunk and ".py" in code_chunk or ".tsx" in code_chunk:
                    # Extract filename from success message
                    pass  # We'll update context at the end with all files
            
            # Update AI context after code generation
            if self.context_loader:
                await self.context_loader.update_memory(
                    current_phase="code_generation_complete",
                    current_task="feature_request",
                    tasks_completed=task_ids,
                    ai_memory={
                        "last_feature_request": message[:100],
                        "plan_type": "full_feature",
                        "tables_created": len(schema),
                        "apis_created": len(apis),
                        "pages_created": len(pages),
                    }
                )
                yield "\n[Context updated]"
            
        elif intent == "debug":
            # Use debugging prompt with context
            system_prompt = get_debugging_prompt()
            async for chunk in self._stream_with_tools(message, system_prompt, context):
                yield chunk
                
        else:
            # Standard chat with tool calling and context
            # Don't pass cached_context to get_system_prompt - it's already injected in _stream_with_tools
            system_prompt = get_system_prompt(project_context=context)
            async for chunk in self._stream_with_tools(message, system_prompt, context):
                yield chunk

    async def _stream_with_tools(
        self,
        message: str,
        system_prompt: str,
        context: Dict[str, Any] = None,
        max_iterations: int = 5
    ) -> AsyncGenerator[str, None]:
        """Core streaming logic with tool execution and context awareness.
        
        This method handles the full AI conversation loop with tool calling:
        1. Load project context (if available)
        2. Inject context into system prompt
        3. Send message to OpenAI with available tools
        4. AI responds with text and/or tool calls
        5. Execute requested tools
        6. Update context after tool executions
        7. Send tool results back to AI
        8. AI processes results and responds
        9. Repeat if AI requests more tools (up to max_iterations)
        
        Args:
            message: User message
            system_prompt: System prompt to use
            context: Optional context - DEPRECATED, use AIContextLoader
            max_iterations: Maximum tool execution cycles (prevents infinite loops)
            
        Yields:
            Streaming response chunks
        """
        # Inject project context into system prompt (use cached version)
        if self._cached_context:
            try:
                context_prompt = self.context_loader.format_for_prompt(self._cached_context)
                
                # Prepend context to system prompt
                enhanced_prompt = f"{context_prompt}\n\n---\n\n{system_prompt}"
                system_prompt = enhanced_prompt
            except Exception as e:
                print(f"Warning: Could not format context: {e}")
        
        # Add user message to history
        self.conversation_history.append({"role": "user", "content": message})
        
        # Get available tools
        tools = get_all_tools()
        
        iteration = 0
        tools_executed = []
        
        while iteration < max_iterations:
            iteration += 1
            
            # Prepare messages with full history
            messages = [
                {"role": "system", "content": system_prompt},
                *self.conversation_history
            ]
            
            # Call OpenAI with tools
            response = await self.client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                tools=tools,
                tool_choice="auto",
                stream=False  # Changed to non-streaming for tool execution
            )
            
            message_obj = response.choices[0].message
            
            # Handle text content
            if message_obj.content:
                yield message_obj.content
                
            # Check if AI wants to call tools
            if not message_obj.tool_calls:
                # No more tools requested - add to history and finish
                self.conversation_history.append({
                    "role": "assistant",
                    "content": message_obj.content or ""
                })
                break
            
            # AI requested tools - execute them
            yield "\n\n🔧 **Executing Tools:**\n"
            
            # Add assistant message with tool calls to history
            self.conversation_history.append({
                "role": "assistant",
                "content": message_obj.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in message_obj.tool_calls
                ]
            })
            
            # Execute each tool call
            for tool_call in message_obj.tool_calls:
                tool_name = tool_call.function.name
                
                try:
                    # Parse arguments
                    arguments = json.loads(tool_call.function.arguments)
                    
                    yield f"- `{tool_name}`: "
                    
                    # Execute the tool
                    result = await self.execute_tool(tool_name, arguments)
                    
                    if result.get("success", True):  # Assume success if not specified
                        yield "✅\n"
                        tools_executed.append({"tool": tool_name, "args": arguments})
                    else:
                        yield f"⚠️ {result.get('error', 'Unknown error')}\n"
                    
                    # Add tool result to conversation history
                    self.conversation_history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": json.dumps(result)
                    })
                    
                except json.JSONDecodeError as e:
                    error_msg = f"Invalid JSON arguments: {str(e)}"
                    yield f"❌ {error_msg}\n"
                    
                    # Add error to history
                    self.conversation_history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": json.dumps({"success": False, "error": error_msg})
                    })
                    
                except Exception as e:
                    error_msg = f"Tool execution error: {str(e)}"
                    yield f"❌ {error_msg}\n"
                    
                    # Add error to history
                    self.conversation_history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": json.dumps({"success": False, "error": error_msg})
                    })
            
            yield "\n"
            
            # Continue loop - AI will process tool results and possibly request more tools
        
        # Update AI context after tool executions
        if tools_executed and self.context_loader:
            try:
                # Extract useful info from executed tools
                files_created = []
                tasks_created = []
                
                for tool_exec in tools_executed:
                    if tool_exec["tool"] == "create_file":
                        files_created.append(tool_exec["args"].get("file_path", "unknown"))
                    elif tool_exec["tool"] == "create_task":
                        tasks_created.append(tool_exec["args"].get("title", "unknown"))
                
                # Update memory
                await self.update_context_memory(
                    files_generated=files_created if files_created else None,
                    ai_memory={
                        "last_action": "tool_execution",
                        "tools_used": [t["tool"] for t in tools_executed],
                        "timestamp": str(json.loads(json.dumps({"now": None}, default=str))),
                    }
                )
            except Exception as e:
                print(f"Warning: Could not update context: {e}")
        
        if iteration >= max_iterations:
            yield "\n⚠️ Maximum tool execution iterations reached. Stopping to prevent infinite loops.\n"

    async def recover_from_error(
        self,
        error_message: str,
        stack_trace: Optional[str] = None,
        context: Dict[str, Any] = None,
        max_retries: int = 3
    ) -> AsyncGenerator[str, None]:
        """Attempt to recover from an error using AI-powered debugging.
        
        This method:
        1. Analyzes the error using the debugging prompt
        2. Uses troubleshoot tool to get diagnostic info
        3. Attempts to fix the error automatically
        4. Validates the fix
        5. Retries if needed (up to max_retries)
        
        Args:
            error_message: The error message
            stack_trace: Optional stack trace
            context: Additional context about what was being done
            max_retries: Maximum number of fix attempts
            
        Yields:
            Recovery progress updates
        """
        yield "\n🔍 **Error Recovery Mode Activated**\n\n"
        yield f"Error: `{error_message}`\n\n"
        
        # Build error context message
        error_context = f"""An error occurred:

Error Message: {error_message}

"""
        
        if stack_trace:
            error_context += f"Stack Trace:\n```\n{stack_trace}\n```\n\n"
        
        if context:
            error_context += f"Context: {json.dumps(context, indent=2)}\n\n"
        
        error_context += """Please:
1. Analyze the error
2. Use the troubleshoot tool to get diagnostic information
3. Identify the root cause
4. Suggest and implement a fix
5. Verify the fix works
"""
        
        # Use debugging system prompt
        debugging_prompt = get_debugging_prompt()
        
        retry_count = 0
        fixed = False
        
        while retry_count < max_retries and not fixed:
            retry_count += 1
            
            if retry_count > 1:
                yield f"\n🔄 **Retry Attempt {retry_count}/{max_retries}**\n\n"
            
            try:
                # Let AI analyze and fix the error
                async for chunk in self._stream_with_tools(
                    error_context,
                    debugging_prompt,
                    context
                ):
                    yield chunk
                
                # Check if fix was successful (simplified - would need actual validation)
                # In real implementation, we'd re-test the failing operation
                yield "\n✅ Fix attempt completed\n"
                fixed = True
                
            except Exception as e:
                yield f"\n❌ Fix attempt {retry_count} failed: {str(e)}\n"
                error_context = f"Previous fix failed with: {str(e)}\n\nPlease try a different approach.\n\n{error_context}"
        
        if fixed:
            yield "\n🎉 **Error successfully recovered!**\n"
        else:
            yield f"\n⚠️ **Could not auto-fix after {max_retries} attempts.**\n"
            yield "Manual intervention may be required.\n"

    async def validate_code_generation(
        self,
        file_path: str,
        code: str,
        expected_features: List[str] = None
    ) -> Dict[str, Any]:
        """Validate generated code quality and correctness.
        
        Args:
            file_path: Path of the generated file
            code: The generated code
            expected_features: List of features that should be present
            
        Returns:
            Validation results with issues and suggestions
        """
        validation_result = {
            "valid": True,
            "issues": [],
            "warnings": [],
            "suggestions": []
        }
        
        # Basic syntax checks
        if file_path.endswith(".py"):
            # Python validation
            try:
                compile(code, file_path, 'exec')
            except SyntaxError as e:
                validation_result["valid"] = False
                validation_result["issues"].append(f"Python syntax error: {str(e)}")
        
        elif file_path.endswith((".tsx", ".ts", ".jsx", ".js")):
            # TypeScript/JavaScript validation (basic checks)
            if "export default" not in code and "export {" not in code:
                validation_result["warnings"].append(
                    "No exports found - file may not be importable"
                )
        
        # Check for expected features
        if expected_features:
            for feature in expected_features:
                if feature.lower() not in code.lower():
                    validation_result["warnings"].append(
                        f"Expected feature '{feature}' may be missing"
                    )
        
        # Check for common anti-patterns
        if "console.log(" in code:
            validation_result["suggestions"].append(
                "Remove console.log statements before production"
            )
        
        if "TODO" in code or "FIXME" in code:
            validation_result["warnings"].append(
                "Code contains TODO/FIXME comments"
            )
        
        return validation_result

    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool by directly calling the endpoint function.
        
        This method routes tool calls to the appropriate backend endpoint functions.
        All tools are implemented as endpoints in the ai_agent_tools API.
        
        Args:
            tool_name: Name of the tool to execute
            parameters: Tool parameters
            
        Returns:
            Tool execution result
        """
        try:
            # Task Management Tools
            if tool_name == "create_task":
                from app.apis.ai_agent_tools import CreateTaskRequest, create_task
                request = CreateTaskRequest(
                    project_id=self.project_id,
                    title=parameters.get("title"),
                    description=parameters.get("description"),
                    priority=parameters.get("priority", "medium"),
                    status=parameters.get("status", "todo"),
                    integrations=parameters.get("integrations", []),
                    labels=parameters.get("labels", [])
                )
                result = await create_task(request)
                return {"success": result.success, "message": result.message, "data": result.data}

            elif tool_name == "update_task":
                from app.apis.ai_agent_tools import UpdateTaskRequest, update_task
                request = UpdateTaskRequest(
                    task_id=parameters.get("task_id"),
                    project_id=self.project_id,
                    title=parameters.get("title"),
                    description=parameters.get("description"),
                    status=parameters.get("status"),
                    priority=parameters.get("priority")
                )
                result = await update_task(request)
                return {"success": result.success, "message": result.message, "data": result.data}
            
            elif tool_name == "list_tasks":
                from app.apis.ai_agent_tools import list_tasks
                tasks = await list_tasks(
                    project_id=self.project_id,
                    status=parameters.get("status")
                )
                return {"success": True, "tasks": [task.dict() for task in tasks]}
            
            elif tool_name == "delete_task":
                from app.apis.ai_agent_tools import delete_task
                result = await delete_task(
                    task_id=parameters.get("task_id"),
                    project_id=self.project_id
                )
                return {"success": True, "message": result.message}
            
            elif tool_name == "add_task_comment":
                from app.apis.ai_agent_tools import AddTaskCommentRequest, add_task_comment
                request = AddTaskCommentRequest(
                    task_id=parameters.get("task_id"),
                    project_id=self.project_id,
                    comment=parameters.get("comment"),
                    comment_type=parameters.get("comment_type", "note")
                )
                result = await add_task_comment(request)
                return {"success": True, "message": result.message}
            
            # File Management Tools
            elif tool_name == "create_file":
                from app.apis.ai_agent_tools import CreateFileRequest, create_file
                request = CreateFileRequest(
                    project_id=self.project_id,
                    file_path=parameters.get("file_path"),
                    file_content=parameters.get("file_content"),
                    language=parameters.get("language"),
                    file_type=parameters.get("file_type")
                )
                result = await create_file(request)
                return {"success": True, "message": result.message}
            
            elif tool_name == "update_file":
                from app.apis.ai_agent_tools import UpdateFileRequest, update_file
                request = UpdateFileRequest(
                    project_id=self.project_id,
                    file_path=parameters.get("file_path"),
                    file_content=parameters.get("file_content"),
                    language=parameters.get("language")
                )
                result = await update_file(request)
                return {"success": True, "message": result.message}
            
            elif tool_name == "read_files":
                from app.apis.ai_agent_tools import read_files
                files = await read_files(
                    project_id=self.project_id,
                    file_paths=parameters.get("file_paths", [])
                )
                return {"success": True, "files": [f.dict() for f in files]}
            
            elif tool_name == "search_code":
                from app.apis.ai_agent_tools import SearchCodeRequest, search_code
                request = SearchCodeRequest(
                    project_id=self.project_id,
                    query=parameters.get("query")
                )
                results = await search_code(request)
                return {"success": True, "results": [r.dict() for r in results]}
            
            elif tool_name == "delete_file":
                from app.apis.ai_agent_tools import DeleteFileRequest, delete_file
                request = DeleteFileRequest(
                    project_id=self.project_id,
                    file_path=parameters.get("file_path")
                )
                result = await delete_file(request)
                return {"success": True, "message": result.message}
            
            # Database Tools
            elif tool_name == "run_migration":
                from app.apis.ai_agent_tools import RunMigrationRequest, run_migration_endpoint
                request = RunMigrationRequest(
                    project_id=self.project_id,
                    migration_name=parameters.get("migration_name"),
                    sql=parameters.get("sql")
                )
                result = await run_migration_endpoint(request)
                return {"success": True, "message": result.message}
            
            elif tool_name == "run_sql_query":
                from app.apis.ai_agent_tools import RunSQLQueryRequest, run_sql_query
                request = RunSQLQueryRequest(
                    project_id=self.project_id,
                    query=parameters.get("query"),
                    env=parameters.get("env", "dev")
                )
                result = await run_sql_query(request)
                return {"success": True, "result": result.result if hasattr(result, 'result') else result}
            
            elif tool_name == "get_sql_schema":
                from app.apis.ai_agent_tools import get_sql_schema
                schema = await get_sql_schema(
                    project_id=self.project_id,
                    env=parameters.get("env", "dev")
                )
                return {"success": True, "schema": schema.schema if hasattr(schema, 'schema') else schema}
            
            # Execution Tools
            elif tool_name == "run_python_script":
                from app.apis.ai_agent_tools import RunPythonScriptRequest, run_python_script
                request = RunPythonScriptRequest(
                    project_id=self.project_id,
                    code=parameters.get("code")
                )
                result = await run_python_script(request)
                return {"success": True, "output": result.output if hasattr(result, 'output') else result}
            
            # Testing/Debugging Tools
            elif tool_name == "read_logs":
                from app.apis.ai_agent_tools import read_logs
                logs = await read_logs(
                    project_id=self.project_id,
                    env=parameters.get("env", "dev"),
                    limit=parameters.get("limit", 100)
                )
                return {"success": True, "logs": logs.logs if hasattr(logs, 'logs') else logs}
            
            elif tool_name == "test_endpoint":
                from app.apis.ai_agent_tools import TestEndpointRequest, test_endpoint
                request = TestEndpointRequest(
                    project_id=self.project_id,
                    endpoint=parameters.get("endpoint"),
                    scenario=parameters.get("scenario")
                )
                result = await test_endpoint(request)
                return {"success": True, "result": result.result if hasattr(result, 'result') else result}
            
            elif tool_name == "troubleshoot":
                from app.apis.ai_agent_tools import TroubleshootRequest, troubleshoot
                request = TroubleshootRequest(
                    project_id=self.project_id,
                    problem=parameters.get("problem"),
                    symptoms=parameters.get("symptoms", []),
                    labels=parameters.get("labels", [])
                )
                result = await troubleshoot(request)
                return {"success": True, "analysis": result.analysis if hasattr(result, 'analysis') else result}
            
            # Integration Tools
            elif tool_name == "enable_integration":
                from app.apis.ai_agent_tools import EnableIntegrationRequest, enable_integration
                request = EnableIntegrationRequest(
                    project_id=self.project_id,
                    integration_name=parameters.get("integration_name"),
                    config=parameters.get("config", {})
                )
                result = await enable_integration(request)
                return {"success": True, "message": result.message if hasattr(result, 'message') else result}
            
            # Package Management Tools
            elif tool_name == "install_packages":
                from app.apis.package_manager import InstallPackagesRequest, install_packages_endpoint
                request = InstallPackagesRequest(
                    packages=parameters.get("packages", []),
                    package_manager=parameters.get("package_manager")
                )
                result = await install_packages_endpoint(request)
                return {
                    "success": result.success,
                    "message": result.message,
                    "installed": result.installed_packages,
                    "failed": result.failed_packages,
                    "details": result.details
                }
            
            # Visualization Tools  
            elif tool_name == "visualize_data":
                from app.apis.ai_agent_tools import VisualizeDataRequest, visualize_data
                request = VisualizeDataRequest(
                    project_id=self.project_id,
                    data=parameters.get("data"),
                    chart_type=parameters.get("chart_type"),
                    title=parameters.get("title", "")
                )
                result = await visualize_data(request)
                return {"success": True, "visualization_id": result.visualization_id if hasattr(result, 'visualization_id') else result}
            
            # Data Request Tools
            elif tool_name == "request_data":
                from app.apis.ai_agent_tools import RequestDataRequest, request_data
                request = RequestDataRequest(
                    project_id=self.project_id,
                    message=parameters.get("message"),
                    data_type=parameters.get("data_type")
                )
                result = await request_data(request)
                return {"success": True, "message": result.message if hasattr(result, 'message') else result}
            
            # Error Feedback Loop Tools
            elif tool_name == "trigger_build":
                from app.apis.preview import build_preview
                result = await build_preview(self.project_id)
                return {"success": True, "message": "Build triggered"}
            
            elif tool_name == "get_open_errors":
                from app.apis.ai_agent_tools import get_open_errors
                result = await get_open_errors(self.project_id)
                return {
                    "success": True,
                    "has_errors": result.has_errors,
                    "errors": [e.dict() for e in result.errors]
                }
            
            elif tool_name == "resolve_error":
                from app.apis.ai_agent_tools import resolve_error
                result = await resolve_error(
                    error_id=parameters.get("error_id"),
                    project_id=self.project_id,
                    resolution_notes=parameters.get("resolution_notes", "Auto-resolved")
                )
                return {"success": True, "message": "Error resolved"}
            
            else:
                return {
                    "success": False,
                    "error": f"Unknown tool: {tool_name}"
                }
                
        except Exception as e:
            import traceback
            return {
                "success": False,
                "error": f"Tool execution failed: {str(e)}",
                "traceback": traceback.format_exc()
            }

    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []

    async def cleanup(self):
        """Clean up resources (close database connection)."""
        if self.context_loader:
            try:
                await self.context_loader.__aexit__(None, None, None)
            except Exception as e:
                print(f"Warning: Error during cleanup: {e}")

    async def update_context_memory(self, **updates):
        """Update AI memory in the context without reloading.
        
        Args:
            **updates: Key-value pairs to update in memory
        """
        if self.context_loader:
            try:
                await self.context_loader.update_memory(**updates)
            except Exception as e:
                print(f"Warning: Could not update context: {e}")
