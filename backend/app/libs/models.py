"""
Database Models for Riff Clone

This module contains Pydantic models and dataclasses that mirror the database schema.
These models are used for type safety, validation, and data transfer between the database and API.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# =============================================================================
# ENUMS
# =============================================================================


class ProjectStatus(str, Enum):
    """Project status values"""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class FeatureStatus(str, Enum):
    """Project feature status values"""
    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ChatRole(str, Enum):
    """Chat message role values"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class TaskStatus(str, Enum):
    """Task status values"""
    TODO = "todo"
    INPROGRESS = "inprogress"
    DONE = "done"
    BLOCKED = "blocked"


class TaskPriority(str, Enum):
    """Task priority values"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class DeploymentStatus(str, Enum):
    """Deployment status values"""
    PENDING = "pending"
    BUILDING = "building"
    DEPLOYED = "deployed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ThemeType(str, Enum):
    """Theme type values"""
    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"


class ContextType(str, Enum):
    """AI context type values"""
    PLAN = "plan"
    DECISION = "decision"
    LEARNING = "learning"
    ERROR = "error"


class LogLevel(str, Enum):
    """Log level values"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Environment(str, Enum):
    """Environment values"""
    DEV = "dev"
    PROD = "prod"


class ChartType(str, Enum):
    """Chart type values for visualizations"""
    AREA_CHART = "AreaChart"
    BAR_CHART = "BarChart"
    COMPOSED_CHART = "ComposedChart"
    LINE_CHART = "LineChart"
    PIE_CHART = "PieChart"
    RADAR_CHART = "RadarChart"
    TREEMAP = "Treemap"


class DataRequestType(str, Enum):
    """Data request type values"""
    STORAGE = "storage"
    STATIC_ASSETS = "static-assets"


class DataRequestStatus(str, Enum):
    """Data request status values"""
    PENDING = "pending"
    FULFILLED = "fulfilled"
    REJECTED = "rejected"


# =============================================================================
# DATABASE MODELS (using dataclass for database records)
# =============================================================================


@dataclass
class Project:
    """Project database model"""
    id: UUID
    user_id: str
    title: str
    description: Optional[str]
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime
    last_accessed_at: Optional[datetime]


@dataclass
class ProjectFeature:
    """Project feature database model"""
    id: UUID
    project_id: UUID
    feature_text: str
    order_index: int
    status: FeatureStatus
    created_at: datetime


@dataclass
class ProjectIntegration:
    """Project integration database model"""
    id: UUID
    project_id: UUID
    integration_name: str
    enabled: bool
    config: Optional[dict[str, Any]]
    credentials: Optional[dict[str, Any]]  # encrypted secrets
    enabled_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


@dataclass
class ProjectDesign:
    """Project design preferences database model"""
    id: UUID
    project_id: UUID
    theme: ThemeType
    color_scheme: Optional[str]
    design_preferences: Optional[dict[str, Any]]
    created_at: datetime
    updated_at: datetime


@dataclass
class ChatMessage:
    """Chat message database model"""
    id: UUID
    project_id: UUID
    role: ChatRole
    content: str
    metadata: Optional[dict[str, Any]]
    created_at: datetime


@dataclass
class Task:
    """Task database model"""
    id: UUID
    project_id: UUID
    title: str
    description: Optional[str]
    status: TaskStatus
    priority: TaskPriority
    order_index: int
    assigned_to: Optional[str]
    metadata: Optional[dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]


@dataclass
class GeneratedFile:
    """Generated file database model"""
    id: UUID
    project_id: UUID
    file_path: str
    file_content: str
    language: Optional[str]
    file_type: Optional[str]
    version: int
    is_active: bool
    metadata: Optional[dict[str, Any]]
    created_at: datetime
    updated_at: datetime


@dataclass
class Deployment:
    """Deployment database model"""
    id: UUID
    project_id: UUID
    url: Optional[str]
    status: DeploymentStatus
    version: Optional[str]
    commit_hash: Optional[str]
    build_logs: Optional[str]
    error_message: Optional[str]
    deployed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


@dataclass
class AIContext:
    """AI context database model"""
    id: UUID
    project_id: UUID
    context_type: ContextType
    content: str
    metadata: Optional[dict[str, Any]]
    created_at: datetime


@dataclass
class ErrorLog:
    """Error log database model"""
    id: UUID
    project_id: Optional[UUID]
    error_type: str
    error_message: str
    stack_trace: Optional[str]
    context: Optional[dict[str, Any]]
    resolved: bool
    resolution_notes: Optional[str]
    created_at: datetime
    resolved_at: Optional[datetime]


@dataclass
class ProjectMigration:
    """Project migration database model"""
    id: UUID
    project_id: UUID
    name: str
    sql: str
    applied_at: datetime
    created_at: datetime


@dataclass
class ProjectLog:
    """Project log database model"""
    id: UUID
    project_id: UUID
    environment: Environment
    level: LogLevel
    message: str
    timestamp: datetime
    metadata: Optional[dict[str, Any]]


@dataclass
class ProjectVisualization:
    """Project visualization database model"""
    id: UUID
    project_id: UUID
    title: str
    chart_type: ChartType
    chart_data: dict[str, Any]
    chart_data_keys: dict[str, str]
    options: Optional[dict[str, Any]]
    created_at: datetime


@dataclass
class ProjectDataRequest:
    """Project data request database model"""
    id: UUID
    project_id: UUID
    request_type: DataRequestType
    message: str
    status: DataRequestStatus
    file_path: Optional[str]
    created_at: datetime
    fulfilled_at: Optional[datetime]


# =============================================================================
# API REQUEST/RESPONSE MODELS (using Pydantic for validation)
# =============================================================================


class ProjectCreate(BaseModel):
    """Request model for creating a project"""
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None


class ProjectUpdate(BaseModel):
    """Request model for updating a project"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[ProjectStatus] = None


class ProjectResponse(BaseModel):
    """Response model for a project"""
    id: str
    user_id: str
    title: str
    description: Optional[str]
    status: str
    created_at: str
    updated_at: str
    last_accessed_at: Optional[str]


class FeatureCreate(BaseModel):
    """Request model for creating a feature"""
    feature_text: str = Field(..., min_length=1)
    order_index: int = Field(default=0, ge=0)


class FeatureUpdate(BaseModel):
    """Request model for updating a feature"""
    feature_text: Optional[str] = Field(None, min_length=1)
    status: Optional[FeatureStatus] = None
    order_index: Optional[int] = Field(None, ge=0)


class ChatMessageCreate(BaseModel):
    """Request model for creating a chat message"""
    role: ChatRole
    content: str = Field(..., min_length=1)
    metadata: Optional[dict[str, Any]] = None


class ChatMessageResponse(BaseModel):
    """Response model for a chat message"""
    id: str
    project_id: str
    role: str
    content: str
    metadata: Optional[dict[str, Any]]
    created_at: str


class TaskCreate(BaseModel):
    """Request model for creating a task"""
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    priority: TaskPriority = TaskPriority.MEDIUM
    order_index: int = Field(default=0, ge=0)


class TaskUpdate(BaseModel):
    """Request model for updating a task"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    order_index: Optional[int] = Field(None, ge=0)
    assigned_to: Optional[str] = None


class TaskResponse(BaseModel):
    """Response model for a task"""
    id: str
    project_id: str
    title: str
    description: Optional[str]
    status: str
    priority: str
    order_index: int
    assigned_to: Optional[str]
    metadata: Optional[dict[str, Any]]
    created_at: str
    updated_at: str
    completed_at: Optional[str]


class FileCreate(BaseModel):
    """Request model for creating a file"""
    file_path: str = Field(..., min_length=1)
    file_content: str
    language: Optional[str] = None
    file_type: Optional[str] = None


class FileUpdate(BaseModel):
    """Request model for updating a file"""
    file_content: Optional[str] = None
    language: Optional[str] = None
    file_type: Optional[str] = None


class FileResponse(BaseModel):
    """Response model for a file"""
    id: str
    project_id: str
    file_path: str
    file_content: str
    language: Optional[str]
    file_type: Optional[str]
    version: int
    is_active: bool
    created_at: str
    updated_at: str
