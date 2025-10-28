import { useState, useEffect } from 'react';
import { apiClient } from 'app';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { toast } from 'sonner';
import { GitHubRepo } from 'types';
import { GitBranch, Lock, Globe, Plus, ExternalLink, RefreshCw, Upload, Folder, Loader2, Code } from 'lucide-react';
import type { ProjectFile } from "types";

export default function GitHub() {
  const [repos, setRepos] = useState<GitHubRepo[]>([]);
  const [projectFiles, setProjectFiles] = useState<ProjectFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [pushingProject, setPushingProject] = useState(false);
  const [rateLimit, setRateLimit] = useState<{ remaining: number; limit: number } | null>(null);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [creatingRepo, setCreatingRepo] = useState(false);
  const [deployingProject, setDeployingProject] = useState(false);
  const [newRepoName, setNewRepoName] = useState("");
  const [newRepoDescription, setNewRepoDescription] = useState("");
  
  // Create repo form state
  const [repoName, setRepoName] = useState('');
  const [repoDescription, setRepoDescription] = useState('');
  const [isPrivate, setIsPrivate] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);

  // Fetch repos on mount
  useEffect(() => {
    fetchRepos();
    fetchRateLimit();
    loadProjectFiles();
  }, []);

  const fetchRateLimit = async () => {
    try {
      const response = await apiClient.get_rate_limit();
      const data = await response.json();
      setRateLimit(data);
    } catch (error) {
      console.error('Failed to fetch rate limit:', error);
    }
  };

  const fetchRepos = async () => {
    try {
      setLoading(true);
      const response = await apiClient.list_repositories({
        visibility: 'all',
        sort: 'updated',
        per_page: 30,
        page: 1
      });
      const data = await response.json();
      setRepos(data);
    } catch (error) {
      console.error('Failed to fetch repos:', error);
      toast.error('Failed to load repositories');
    } finally {
      setLoading(false);
    }
  };

  const loadProjectFiles = async () => {
    setLoadingFiles(true);
    try {
      const response = await apiClient.get_project_files();
      const files = await response.json();
      setProjectFiles(files);
      console.log(`Loaded ${files.length} project files`);
    } catch (error) {
      console.error("Failed to load project files:", error);
      toast.error("Failed to load project files");
    } finally {
      setLoadingFiles(false);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchRepos();
    await fetchRateLimit();
    setRefreshing(false);
    toast.success('Repositories refreshed');
  };

  const handleCreateRepo = async () => {
    if (!repoName.trim()) {
      toast.error('Repository name is required');
      return;
    }

    try {
      setCreating(true);
      const response = await apiClient.create_repository({
        name: repoName,
        description: repoDescription || undefined,
        private: isPrivate,
        auto_init: true,
        gitignore_template: undefined
      });
      
      const newRepo = await response.json();
      
      toast.success(
        <div>
          <p className="font-semibold">Repository created!</p>
          <p className="text-sm text-muted-foreground">{newRepo.full_name}</p>
        </div>
      );
      
      // Reset form
      setRepoName('');
      setRepoDescription('');
      setIsPrivate(false);
      setDialogOpen(false);
      
      // Refresh repos list
      await fetchRepos();
      await fetchRateLimit();
    } catch (error: any) {
      console.error('Failed to create repo:', error);
      const errorMsg = error?.message || 'Failed to create repository';
      toast.error(errorMsg);
    } finally {
      setCreating(false);
    }
  };

  const handlePushEntireProject = async () => {
    try {
      setPushingProject(true);
      
      // Generate unique repo name with timestamp
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
      const repoName = `Holio-As-${timestamp}`;
      
      // Step 1: Create the repository
      toast.info(`Creating repository "${repoName}"...`);
      const createResponse = await apiClient.create_repository({
        name: repoName,
        description: 'Full Riff AI Studio project - AI-powered app builder',
        private: false,
        auto_init: false,
        gitignore_template: undefined
      });
      
      const newRepo = await createResponse.json();
      const owner = newRepo.full_name.split('/')[0];
      
      toast.success('Repository created!');
      
      // Step 2: Use real project files from backend
      if (projectFiles.length === 0) {
        toast.error('No project files loaded. Please refresh the page.');
        return;
      }
      
      toast.info(`Preparing ${projectFiles.length} project files...`);
      
      // Step 3: Push all files in batch
      toast.info(`Pushing ${projectFiles.length} files to GitHub...`);
      
      const pushResponse = await apiClient.push_files({
        owner,
        repo: repoName,
        files: projectFiles.map(f => ({
          path: f.path,
          content: f.content,
          message: undefined
        })),
        branch: 'main',
        update_existing: true
      });
      
      await pushResponse.json();
      
      toast.success(
        <div>
          <p className="font-semibold">Project deployed to GitHub! 🚀</p>
          <p className="text-sm text-muted-foreground">{newRepo.html_url}</p>
        </div>,
        { duration: 5000 }
      );
      
      // Refresh repos list
      await fetchRepos();
      await fetchRateLimit();
      
      // Open the repo in a new tab
      window.open(newRepo.html_url, '_blank');
      
    } catch (error: any) {
      console.error('Failed to push project:', error);
      toast.error(error?.message || 'Failed to push project to GitHub');
    } finally {
      setPushingProject(false);
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    }).format(date);
  };

  return (
    <div className="min-h-screen bg-background p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-2">
            <h1 className="text-4xl font-bold">GitHub Integration</h1>
            <div className="flex items-center gap-3">
              {rateLimit && (
                <Badge variant="outline" className="text-sm">
                  API: {rateLimit.remaining}/{rateLimit.limit}
                </Badge>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={handleRefresh}
                disabled={refreshing}
              >
                <RefreshCw className={`w-4 h-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
              <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
                <DialogTrigger asChild>
                  <Button>
                    <Plus className="w-4 h-4 mr-2" />
                    Create Repository
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Create New Repository</DialogTitle>
                    <DialogDescription>
                      Create a new GitHub repository for your project
                    </DialogDescription>
                  </DialogHeader>
                  <div className="space-y-4 py-4">
                    <div className="space-y-2">
                      <Label htmlFor="repo-name">Repository Name *</Label>
                      <Input
                        id="repo-name"
                        placeholder="my-awesome-app"
                        value={repoName}
                        onChange={(e) => setRepoName(e.target.value)}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="repo-desc">Description</Label>
                      <Input
                        id="repo-desc"
                        placeholder="An AI-generated app built with Riff"
                        value={repoDescription}
                        onChange={(e) => setRepoDescription(e.target.value)}
                      />
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="space-y-0.5">
                        <Label htmlFor="private">Private Repository</Label>
                        <p className="text-sm text-muted-foreground">
                          Only you and collaborators can see this
                        </p>
                      </div>
                      <Switch
                        id="private"
                        checked={isPrivate}
                        onCheckedChange={setIsPrivate}
                      />
                    </div>
                  </div>
                  <DialogFooter>
                    <Button
                      variant="outline"
                      onClick={() => setDialogOpen(false)}
                      disabled={creating}
                    >
                      Cancel
                    </Button>
                    <Button onClick={handleCreateRepo} disabled={creating}>
                      {creating ? 'Creating...' : 'Create Repository'}
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </div>
          </div>
          <p className="text-muted-foreground">
            Manage your GitHub repositories and deploy your Riff projects
          </p>
        </div>

        {/* Push Entire Project Section */}
        <Card className="mb-6 border-2 border-primary/20 bg-gradient-to-br from-primary/5 to-background">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-2xl flex items-center gap-2">
                  <Folder className="w-6 h-6" />
                  Deploy Full Riff Project
                </CardTitle>
                <CardDescription className="mt-2">
                  Push the entire Riff AI Studio codebase to a new GitHub repository
                </CardDescription>
              </div>
              <Button
                size="lg"
                onClick={handlePushEntireProject}
                disabled={pushingProject}
                className="gap-2"
              >
                {pushingProject ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    Deploying...
                  </>
                ) : (
                  <>
                    <Upload className="w-4 h-4" />
                    Push to "Holio As"
                  </>
                )}
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <p className="text-muted-foreground">Repository Name</p>
                <p className="font-semibold">Holio-As</p>
              </div>
              <div>
                <p className="text-muted-foreground">Visibility</p>
                <p className="font-semibold flex items-center gap-1">
                  <Globe className="w-3 h-3" /> Public
                </p>
              </div>
              <div>
                <p className="text-muted-foreground">Files</p>
                <p className="font-semibold">~20 files</p>
              </div>
              <div>
                <p className="text-muted-foreground">Structure</p>
                <p className="font-semibold">Frontend + Backend</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Repositories Grid */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <Card key={i}>
                <CardHeader>
                  <Skeleton className="h-6 w-3/4" />
                  <Skeleton className="h-4 w-full mt-2" />
                </CardHeader>
                <CardContent>
                  <Skeleton className="h-4 w-1/2" />
                </CardContent>
              </Card>
            ))}
          </div>
        ) : repos.length === 0 ? (
          <Card className="p-12 text-center">
            <GitBranch className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
            <h3 className="text-lg font-semibold mb-2">No repositories yet</h3>
            <p className="text-muted-foreground mb-4">
              Create your first repository to get started
            </p>
            <Button onClick={() => setDialogOpen(true)}>
              <Plus className="w-4 h-4 mr-2" />
              Create Repository
            </Button>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {repos.map((repo) => (
              <Card key={repo.id} className="hover:shadow-lg transition-shadow">
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <CardTitle className="text-lg truncate">
                        {repo.name}
                      </CardTitle>
                      <CardDescription className="text-xs mt-1">
                        {repo.full_name}
                      </CardDescription>
                    </div>
                    {repo.private ? (
                      <Lock className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                    ) : (
                      <Globe className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                    )}
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  {repo.description && (
                    <p className="text-sm text-muted-foreground line-clamp-2">
                      {repo.description}
                    </p>
                  )}
                  
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <div className="flex items-center gap-2">
                      <GitBranch className="w-3 h-3" />
                      <span>{repo.default_branch}</span>
                    </div>
                    <span>Updated {formatDate(repo.updated_at)}</span>
                  </div>

                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      className="flex-1"
                      onClick={() => window.open(repo.html_url, '_blank')}
                    >
                      <ExternalLink className="w-3 h-3 mr-2" />
                      View on GitHub
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
