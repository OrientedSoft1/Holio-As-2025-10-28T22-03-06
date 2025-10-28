"""Projects API - Complete CRUD operations for project management."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import asyncpg
import os
from datetime import datetime
from app.auth import AuthorizedUser
from app.libs.database import get_db_connection

router = APIRouter()

# Pydantic Models

class FeatureCreate(BaseModel):
    """Feature definition for project creation."""
    text: str
    order_index: int = 0

class IntegrationCreate(BaseModel):
    """Integration definition for project creation."""
    name: str
    enabled: bool = True
    config: Optional[Dict[str, Any]] = None

class DesignCreate(BaseModel):
    """Design preferences for project."""
    theme: Optional[str] = "light"
    color_scheme: Optional[str] = "blue"
    design_preferences: Optional[Dict[str, Any]] = None

class ProjectCreate(BaseModel):
    """Request model for creating a new project."""
    title: str
    description: Optional[str] = None
    features: List[FeatureCreate] = []
    integrations: List[IntegrationCreate] = []
    design: Optional[DesignCreate] = None

class FeatureResponse(BaseModel):
    """Feature response model."""
    id: str
    text: str
    order_index: int
    status: Optional[str]
    created_at: datetime

class IntegrationResponse(BaseModel):
    """Integration response model."""
    id: str
    name: str
    enabled: bool
    config: Optional[Dict[str, Any]]
    enabled_at: Optional[datetime]
    created_at: datetime

class DesignResponse(BaseModel):
    """Design response model."""
    id: str
    theme: Optional[str]
    color_scheme: Optional[str]
    design_preferences: Optional[Dict[str, Any]]
    created_at: datetime

class ProjectResponse(BaseModel):
    """Full project response with all related data."""
    id: str
    user_id: str
    title: str
    description: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    last_accessed_at: Optional[datetime]
    features: List[FeatureResponse]
    integrations: List[IntegrationResponse]
    design: Optional[DesignResponse]

class ProjectListItem(BaseModel):
    """Summary project info for list view."""
    id: str
    title: str
    description: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    feature_count: int
    integration_count: int

class ProjectUpdate(BaseModel):
    """Request model for updating a project."""
    title: Optional[str] = None
    description: Optional[str] = None
    features: Optional[List[FeatureCreate]] = None
    integrations: Optional[List[IntegrationCreate]] = None
    design: Optional[DesignCreate] = None

# Helper Functions

# API Endpoints

@router.post("/projects", response_model=ProjectResponse)
async def create_project(project: ProjectCreate, user: AuthorizedUser):
    """
    Create a new project with features, integrations, and design preferences.
    
    This endpoint creates:
    - Main project record
    - Associated features
    - Associated integrations
    - Design preferences
    
    All operations are wrapped in a transaction for data consistency.
    """
    conn = await get_db_connection()
    try:
        # Start transaction
        async with conn.transaction():
            # Create main project
            project_id = await conn.fetchval(
                """
                INSERT INTO projects (user_id, title, description, status)
                VALUES ($1, $2, $3, 'active')
                RETURNING id
                """,
                user.sub,
                project.title,
                project.description
            )
            
            # Create features
            features = []
            for feature in project.features:
                feature_id = await conn.fetchval(
                    """
                    INSERT INTO project_features (project_id, feature_text, order_index, status)
                    VALUES ($1, $2, $3, 'active')
                    RETURNING id
                    """,
                    project_id,
                    feature.text,
                    feature.order_index
                )
                feature_data = await conn.fetchrow(
                    "SELECT * FROM project_features WHERE id = $1",
                    feature_id
                )
                features.append(FeatureResponse(
                    id=str(feature_data["id"]),
                    text=feature_data["feature_text"],
                    order_index=feature_data["order_index"],
                    status=feature_data["status"],
                    created_at=feature_data["created_at"]
                ))
            
            # Create integrations
            integrations = []
            for integration in project.integrations:
                integration_id = await conn.fetchval(
                    """
                    INSERT INTO project_integrations (project_id, integration_name, enabled, config)
                    VALUES ($1, $2, $3, $4)
                    RETURNING id
                    """,
                    project_id,
                    integration.name,
                    integration.enabled,
                    integration.config
                )
                integration_data = await conn.fetchrow(
                    "SELECT * FROM project_integrations WHERE id = $1",
                    integration_id
                )
                integrations.append(IntegrationResponse(
                    id=str(integration_data["id"]),
                    name=integration_data["integration_name"],
                    enabled=integration_data["enabled"],
                    config=integration_data["config"],
                    enabled_at=integration_data["enabled_at"],
                    created_at=integration_data["created_at"]
                ))
            
            # Create design
            design_response = None
            if project.design:
                design_id = await conn.fetchval(
                    """
                    INSERT INTO project_design (project_id, theme, color_scheme, design_preferences)
                    VALUES ($1, $2, $3, $4)
                    RETURNING id
                    """,
                    project_id,
                    project.design.theme,
                    project.design.color_scheme,
                    project.design.design_preferences
                )
                design_data = await conn.fetchrow(
                    "SELECT * FROM project_design WHERE id = $1",
                    design_id
                )
                design_response = DesignResponse(
                    id=str(design_data["id"]),
                    theme=design_data["theme"],
                    color_scheme=design_data["color_scheme"],
                    design_preferences=design_data["design_preferences"],
                    created_at=design_data["created_at"]
                )
            
            # Get the created project
            project_data = await conn.fetchrow(
                "SELECT * FROM projects WHERE id = $1",
                project_id
            )
            
            return ProjectResponse(
                id=str(project_data["id"]),
                user_id=project_data["user_id"],
                title=project_data["title"],
                description=project_data["description"],
                status=project_data["status"],
                created_at=project_data["created_at"],
                updated_at=project_data["updated_at"],
                last_accessed_at=project_data["last_accessed_at"],
                features=features,
                integrations=integrations,
                design=design_response
            )
    finally:
        await conn.close()


@router.get("/projects", response_model=List[ProjectListItem])
async def list_projects(user: AuthorizedUser):
    """
    List all projects for the authenticated user.
    
    Returns a summary view with counts of features and integrations.
    Only active projects are returned (soft-deleted projects are excluded).
    """
    conn = await get_db_connection()
    try:
        projects = await conn.fetch(
            """
            SELECT 
                p.*,
                COUNT(DISTINCT pf.id) as feature_count,
                COUNT(DISTINCT pi.id) as integration_count
            FROM projects p
            LEFT JOIN project_features pf ON p.id = pf.project_id
            LEFT JOIN project_integrations pi ON p.id = pi.project_id
            WHERE p.user_id = $1 AND p.status != 'deleted'
            GROUP BY p.id
            ORDER BY p.updated_at DESC
            """,
            user.sub
        )
        
        return [
            ProjectListItem(
                id=str(p["id"]),
                title=p["title"],
                description=p["description"],
                status=p["status"],
                created_at=p["created_at"],
                updated_at=p["updated_at"],
                feature_count=p["feature_count"],
                integration_count=p["integration_count"]
            )
            for p in projects
        ]
    finally:
        await conn.close()


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, user: AuthorizedUser):
    """
    Get full project details including all related entities.
    
    Returns:
    - Project info
    - All features
    - All integrations
    - Design preferences
    
    Also updates the last_accessed_at timestamp.
    """
    conn = await get_db_connection()
    try:
        # Get project and verify ownership
        project = await conn.fetchrow(
            "SELECT * FROM projects WHERE id = $1 AND user_id = $2",
            project_id,
            user.sub
        )
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Update last accessed
        await conn.execute(
            "UPDATE projects SET last_accessed_at = NOW() WHERE id = $1",
            project_id
        )
        
        # Get features
        feature_rows = await conn.fetch(
            "SELECT * FROM project_features WHERE project_id = $1 ORDER BY order_index",
            project_id
        )
        features = [
            FeatureResponse(
                id=str(f["id"]),
                text=f["feature_text"],
                order_index=f["order_index"],
                status=f["status"],
                created_at=f["created_at"]
            )
            for f in feature_rows
        ]
        
        # Get integrations
        integration_rows = await conn.fetch(
            "SELECT * FROM project_integrations WHERE project_id = $1 ORDER BY integration_name",
            project_id
        )
        integrations = [
            IntegrationResponse(
                id=str(i["id"]),
                name=i["integration_name"],
                enabled=i["enabled"],
                config=i["config"],
                enabled_at=i["enabled_at"],
                created_at=i["created_at"]
            )
            for i in integration_rows
        ]
        
        # Get design
        design_row = await conn.fetchrow(
            "SELECT * FROM project_design WHERE project_id = $1",
            project_id
        )
        design = None
        if design_row:
            design = DesignResponse(
                id=str(design_row["id"]),
                theme=design_row["theme"],
                color_scheme=design_row["color_scheme"],
                design_preferences=design_row["design_preferences"],
                created_at=design_row["created_at"]
            )
        
        return ProjectResponse(
            id=str(project["id"]),
            user_id=project["user_id"],
            title=project["title"],
            description=project["description"],
            status=project["status"],
            created_at=project["created_at"],
            updated_at=project["updated_at"],
            last_accessed_at=project["last_accessed_at"],
            features=features,
            integrations=integrations,
            design=design
        )
    finally:
        await conn.close()


@router.put("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: str, update: ProjectUpdate, user: AuthorizedUser):
    """
    Update a project and its related entities.
    
    Updates:
    - Project title/description if provided
    - Features (replaces all features if provided)
    - Integrations (upserts integrations if provided)
    - Design (upserts design if provided)
    
    All operations are wrapped in a transaction.
    """
    conn = await get_db_connection()
    try:
        async with conn.transaction():
            # Verify project exists and user owns it
            project = await conn.fetchrow(
                "SELECT * FROM projects WHERE id = $1 AND user_id = $2",
                project_id,
                user.sub
            )
            
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            
            # Update project fields if provided
            if update.title or update.description:
                await conn.execute(
                    """
                    UPDATE projects 
                    SET title = COALESCE($1, title),
                        description = COALESCE($2, description),
                        updated_at = NOW()
                    WHERE id = $3
                    """,
                    update.title,
                    update.description,
                    project_id
                )
            
            # Update features (replace all)
            if update.features is not None:
                # Delete existing features
                await conn.execute(
                    "DELETE FROM project_features WHERE project_id = $1",
                    project_id
                )
                
                # Create new features
                for feature in update.features:
                    await conn.execute(
                        """
                        INSERT INTO project_features (project_id, feature_text, order_index, status)
                        VALUES ($1, $2, $3, 'active')
                        """,
                        project_id,
                        feature.text,
                        feature.order_index
                    )
            
            # Update integrations (upsert)
            if update.integrations is not None:
                for integration in update.integrations:
                    # Check if integration exists
                    existing = await conn.fetchval(
                        "SELECT id FROM project_integrations WHERE project_id = $1 AND integration_name = $2",
                        project_id,
                        integration.name
                    )
                    
                    if existing:
                        # Update existing
                        await conn.execute(
                            """
                            UPDATE project_integrations
                            SET enabled = $1, config = $2, updated_at = NOW()
                            WHERE id = $3
                            """,
                            integration.enabled,
                            integration.config,
                            existing
                        )
                    else:
                        # Create new
                        await conn.execute(
                            """
                            INSERT INTO project_integrations (project_id, integration_name, enabled, config)
                            VALUES ($1, $2, $3, $4)
                            """,
                            project_id,
                            integration.name,
                            integration.enabled,
                            integration.config
                        )
            
            # Update design (upsert)
            if update.design is not None:
                existing_design = await conn.fetchval(
                    "SELECT id FROM project_design WHERE project_id = $1",
                    project_id
                )
                
                if existing_design:
                    # Update existing
                    await conn.execute(
                        """
                        UPDATE project_design
                        SET theme = $1, color_scheme = $2, design_preferences = $3, updated_at = NOW()
                        WHERE id = $4
                        """,
                        update.design.theme,
                        update.design.color_scheme,
                        update.design.design_preferences,
                        existing_design
                    )
                else:
                    # Create new
                    await conn.execute(
                        """
                        INSERT INTO project_design (project_id, theme, color_scheme, design_preferences)
                        VALUES ($1, $2, $3, $4)
                        """,
                        project_id,
                        update.design.theme,
                        update.design.color_scheme,
                        update.design.design_preferences
                    )
        
        # Return updated project (reuse get_project logic)
        return await get_project(project_id, user)
    finally:
        await conn.close()


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str, user: AuthorizedUser):
    """
    Soft delete a project.
    
    Sets the project status to 'deleted' instead of actually deleting the record.
    This allows for potential recovery and maintains referential integrity.
    """
    conn = await get_db_connection()
    try:
        result = await conn.fetchval(
            """
            UPDATE projects 
            SET status = 'deleted', updated_at = NOW()
            WHERE id = $1 AND user_id = $2
            RETURNING id
            """,
            project_id,
            user.sub
        )
        
        if not result:
            raise HTTPException(status_code=404, detail="Project not found")
        
        return {"success": True, "message": "Project deleted successfully"}
    finally:
        await conn.close()
