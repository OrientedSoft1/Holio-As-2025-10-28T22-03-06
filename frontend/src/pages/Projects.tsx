import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Folder, Calendar, Trash2, Loader2 } from "lucide-react";
import { apiClient } from "app";
import { ProjectListItem } from "types";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { GitHubPushButton } from "components/GitHubPushButton";
import { toast } from "sonner";
import { useUser } from "@stackframe/react";

export default function Projects() {
  const user = useUser();
  const navigate = useNavigate();
  const [projects, setProjects] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!user) {
      console.log("User not authenticated, redirecting to sign-in");
      navigate("/auth/sign-in");
    }
  }, [user, navigate]);

  // Load projects on mount
  useEffect(() => {
    loadProjects();
  }, []);

  const loadProjects = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiClient.list_projects();
      const data = await response.json();
      setProjects(data);
    } catch (err) {
      console.error("Failed to load projects:", err);
      setError("Failed to load projects. Please try again.");
      toast.error("Failed to load projects");
    } finally {
      setLoading(false);
    }
  };

  const handleCreateProject = async () => {
    try {
      const response = await apiClient.create_project({
        title: "Untitled Project",
        description: "",
        features: [],
        integrations: [],
      });
      const newProject = await response.json();
      toast.success("Project created");
      // Navigate to the editor with the new project ID
      navigate(`/?projectId=${newProject.id}`);
    } catch (err) {
      console.error("Failed to create project:", err);
      toast.error("Failed to create project");
    }
  };

  const handleDeleteProject = async (projectId: string, title: string) => {
    if (!confirm(`Are you sure you want to delete "${title}"?`)) {
      return;
    }

    try {
      setDeletingId(projectId);
      await apiClient.delete_project({ projectId });
      toast.success("Project deleted");
      // Reload the list
      await loadProjects();
    } catch (err) {
      console.error("Failed to delete project:", err);
      toast.error("Failed to delete project");
    } finally {
      setDeletingId(null);
    }
  };

  const handleOpenProject = (projectId: string) => {
    navigate(`/?projectId=${projectId}`);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-center space-y-4">
          <Loader2 className="w-8 h-8 animate-spin mx-auto text-muted-foreground" />
          <p className="text-sm text-muted-foreground">Loading projects...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-center space-y-4 max-w-md">
          <div className="w-16 h-16 mx-auto bg-destructive/10 rounded-lg flex items-center justify-center">
            <Folder className="w-8 h-8 text-destructive" />
          </div>
          <div>
            <h3 className="text-lg font-medium text-foreground mb-2">Failed to Load Projects</h3>
            <p className="text-sm text-muted-foreground mb-4">{error}</p>
            <Button onClick={loadProjects}>Try Again</Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card">
        <div className="px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-semibold text-foreground">Projects</h1>
              <p className="text-sm text-muted-foreground mt-1">
                Manage your AI-powered applications
              </p>
            </div>
            <Button onClick={handleCreateProject} className="flex items-center gap-2">
              <Plus className="w-4 h-4" />
              New Project
            </Button>
          </div>
        </div>
      </header>

      {/* Content */}
      <div className="p-6">
        {projects.length === 0 ? (
          <div className="flex items-center justify-center" style={{ minHeight: "calc(100vh - 200px)" }}>
            <div className="text-center space-y-4 max-w-md">
              <div className="w-16 h-16 mx-auto bg-muted rounded-lg flex items-center justify-center">
                <Folder className="w-8 h-8 text-muted-foreground" />
              </div>
              <div>
                <h3 className="text-lg font-medium text-foreground mb-2">No Projects Yet</h3>
                <p className="text-sm text-muted-foreground mb-4">
                  Create your first project to start building with AI
                </p>
                <Button onClick={handleCreateProject} className="flex items-center gap-2">
                  <Plus className="w-4 h-4" />
                  Create Project
                </Button>
              </div>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {projects.map((project) => (
              <Card
                key={project.id}
                className="p-6 hover:border-primary/50 transition-colors cursor-pointer group"
                onClick={() => handleOpenProject(project.id)}
              >
                <div className="space-y-4">
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <h3 className="text-lg font-semibold text-foreground truncate">
                        {project.title}
                      </h3>
                      {project.description && (
                        <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
                          {project.description}
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-4 text-xs text-muted-foreground">
                    <div className="flex items-center gap-1">
                      <Calendar className="w-3 h-3" />
                      {formatDate(project.created_at)}
                    </div>
                    <div>{project.feature_count} features</div>
                    <div>{project.integration_count} integrations</div>
                  </div>

                  <div className="flex items-center justify-between pt-2 border-t border-border">
                    <span className="text-xs font-medium text-muted-foreground uppercase">
                      {project.status}
                    </span>
                    <div className="flex items-center gap-2">
                      <GitHubPushButton projectId={project.id} variant="ghost" size="sm" />
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteProject(project.id, project.title);
                        }}
                        disabled={deletingId === project.id}
                        className="opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        {deletingId === project.id ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Trash2 className="w-4 h-4" />
                        )}
                      </Button>
                    </div>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
