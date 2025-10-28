"""Riff Source Code Analysis and Reference
========================================

Analysis of the Riff AI Studio clone - what exists and what needs to be built.
"""

# =============================================================================
# CURRENT IMPLEMENTATION STATUS
# =============================================================================

CURRENT_STATUS = {
    "frontend": {
        "exists": [
            "Basic chat UI (App.tsx)",
            "Project plan form (title, description, features, integrations, design)",
            "Code display panel (static mock)",
            "Preview panel (placeholder)",
            "Three-tab interface (Plan, Code, Preview)",
            "Responsive layout with split panels",
            "shadcn/ui components library",
            "Tailwind CSS styling",
            "Dark/light theme support"
        ],
        "missing": [
            "Backend API integration",
            "Real-time chat streaming",
            "Message persistence",
            "Project data persistence",
            "Monaco code editor",
            "File tree navigation",
            "Live preview iframe",
            "Task board UI",
            "GitHub integration UI",
            "Deployment UI"
        ]
    },
    "backend": {
        "exists": [
            "FastAPI app setup",
            "Stack Auth integration",
            "PostgreSQL database connection",
            "OpenAI package installed"
        ],
        "missing": [
            "All API endpoints (chat, projects, tasks, code generation)",
            "Database schema/migrations",
            "AI integration logic",
            "File management system",
            "Code generation service",
            "GitHub API integration",
            "Deployment service"
        ]
    }
}

# =============================================================================
# DATABASE SCHEMA DESIGN
# =============================================================================

DATABASE_SCHEMA = """
-- Projects table
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Project features (array of feature descriptions)
CREATE TABLE project_features (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    feature_text TEXT NOT NULL,
    order_index INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Project integrations
CREATE TABLE project_integrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    integration_name TEXT NOT NULL,
    config JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Project design preferences
CREATE TABLE project_design (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    design_preferences TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Chat messages
CREATE TABLE chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tasks
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed')),
    order_index INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Generated code files
CREATE TABLE generated_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    file_content TEXT NOT NULL,
    language TEXT,
    version INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Deployments
CREATE TABLE deployments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    url TEXT,
    status TEXT NOT NULL CHECK (status IN ('pending', 'building', 'deployed', 'failed')),
    deployed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_projects_user_id ON projects(user_id);
CREATE INDEX idx_chat_messages_project_id ON chat_messages(project_id);
CREATE INDEX idx_tasks_project_id ON tasks(project_id);
CREATE INDEX idx_generated_files_project_id ON generated_files(project_id);
"""

# =============================================================================
# API ENDPOINTS TO IMPLEMENT
# =============================================================================

API_ENDPOINTS = {
    "chat": [
        "POST /chat/message - Send message and get AI response (streaming)",
        "GET /chat/history/{project_id} - Get chat history for a project",
        "DELETE /chat/history/{project_id} - Clear chat history"
    ],
    "projects": [
        "POST /projects - Create new project",
        "GET /projects - List user's projects",
        "GET /projects/{project_id} - Get project details",
        "PUT /projects/{project_id} - Update project",
        "DELETE /projects/{project_id} - Delete project"
    ],
    "tasks": [
        "POST /tasks - Create task",
        "GET /tasks/{project_id} - List tasks for project",
        "PUT /tasks/{task_id} - Update task",
        "DELETE /tasks/{task_id} - Delete task"
    ],
    "code_generation": [
        "POST /generate/code - Generate code from description",
        "GET /files/{project_id} - List generated files",
        "GET /files/{project_id}/{file_path} - Get file content",
        "PUT /files/{file_id} - Update file content"
    ],
    "deployment": [
        "POST /deploy/{project_id} - Deploy project",
        "GET /deployments/{project_id} - Get deployment history"
    ]
}

# =============================================================================
# FRONTEND COMPONENTS TO BUILD
# =============================================================================

FRONTEND_COMPONENTS = {
    "pages": [
        "Projects.tsx - List all projects",
        "ProjectEditor.tsx - Main project editing view (current App.tsx enhanced)"
    ],
    "components": [
        "ChatPanel.tsx - Chat interface with streaming",
        "ProjectPlanForm.tsx - Project details form",
        "TaskBoard.tsx - Task management interface",
        "CodeEditor.tsx - Monaco-based code editor",
        "FileTree.tsx - File navigation tree",
        "PreviewPanel.tsx - Live preview iframe",
        "DeploymentStatus.tsx - Deployment status and controls"
    ],
    "utils": [
        "api.ts - API client wrapper functions",
        "codeParser.ts - Parse AI-generated code",
        "streamHandler.ts - Handle SSE streaming"
    ]
}

# =============================================================================
# IMPLEMENTATION SEQUENCE
# =============================================================================

IMPLEMENTATION_PLAN = [
    {
        "phase": 1,
        "title": "Database & Projects Foundation",
        "tasks": [
            "Create database migrations for all tables",
            "Create Python models for database tables",
            "Build projects API (CRUD endpoints)",
            "Update UI to save/load projects from database",
            "Add project list page"
        ]
    },
    {
        "phase": 2,
        "title": "AI Chat Integration",
        "tasks": [
            "Create chat API with OpenAI/Claude integration",
            "Implement streaming response handling",
            "Save chat messages to database",
            "Update ChatPanel component with real API calls",
            "Add message persistence and history"
        ]
    },
    {
        "phase": 3,
        "title": "Task Management",
        "tasks": [
            "Create tasks API",
            "Build TaskBoard component",
            "Add drag-and-drop functionality",
            "Integrate task updates with project"
        ]
    },
    {
        "phase": 4,
        "title": "Code Generation",
        "tasks": [
            "Build code generation service",
            "Create code parsing utilities",
            "Implement file creation/update API",
            "Add Monaco code editor",
            "Build file tree navigation"
        ]
    },
    {
        "phase": 5,
        "title": "Preview System",
        "tasks": [
            "Create live preview iframe",
            "Implement hot reload",
            "Add error display",
            "Console output integration"
        ]
    },
    {
        "phase": 6,
        "title": "GitHub Integration",
        "tasks": [
            "Set up GitHub OAuth",
            "Implement repo creation",
            "Add commit/push functionality",
            "Version control UI"
        ]
    },
    {
        "phase": 7,
        "title": "Deployment",
        "tasks": [
            "Create deployment service",
            "Integrate with hosting platform",
            "Add deployment status tracking",
            "Build deployment UI"
        ]
    }
]

# =============================================================================
# TECHNOLOGY STACK
# =============================================================================

TECH_STACK = {
    "frontend": {
        "framework": "React 18.3.1 with TypeScript",
        "routing": "React Router 6.17.0",
        "styling": "Tailwind CSS + shadcn/ui",
        "state": "Zustand 4.5.5",
        "editor": "Monaco Editor (to be added)",
        "icons": "Lucide React"
    },
    "backend": {
        "framework": "FastAPI",
        "database": "PostgreSQL with asyncpg",
        "ai": "OpenAI API",
        "auth": "Stack Auth",
        "validation": "Pydantic"
    },
    "deployment": {
        "hosting": "TBD (Vercel/Railway/Render)",
        "database": "Neon PostgreSQL",
        "git": "GitHub API"
    }
}
