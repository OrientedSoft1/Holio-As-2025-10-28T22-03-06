import { useState } from 'react';
import { apiClient } from 'app';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from 'sonner';
import { GitBranch, Upload, CheckCircle2, Loader2 } from 'lucide-react';
import { GitHubRepo } from 'types';

interface Props {
  projectId: string;
  projectName: string;
  files: Array<{ path: string; content: string }>;
  onSuccess?: (repoUrl: string) => void;
}

export function GitHubPushButton({ projectId, projectName, files, onSuccess }: Props) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [repos, setRepos] = useState<GitHubRepo[]>([]);
  const [loadingRepos, setLoadingRepos] = useState(false);
  
  // Form state
  const [mode, setMode] = useState<'new' | 'existing'>('new');
  const [repoName, setRepoName] = useState(projectName.toLowerCase().replace(/\s+/g, '-'));
  const [selectedRepo, setSelectedRepo] = useState<string>('');
  const [branch, setBranch] = useState('main');
  
  // Push state
  const [pushing, setPushing] = useState(false);
  const [pushProgress, setPushProgress] = useState<string[]>([]);
  const [pushComplete, setPushComplete] = useState(false);
  const [repoUrl, setRepoUrl] = useState<string>('');

  const handleOpen = async (isOpen: boolean) => {
    setOpen(isOpen);
    if (isOpen && repos.length === 0) {
      await fetchRepos();
    }
  };

  const fetchRepos = async () => {
    try {
      setLoadingRepos(true);
      const response = await apiClient.list_repositories({
        visibility: 'all',
        sort: 'updated',
        per_page: 50,
        page: 1
      });
      const data = await response.json();
      setRepos(data);
    } catch (error) {
      console.error('Failed to fetch repos:', error);
      toast.error('Failed to load repositories');
    } finally {
      setLoadingRepos(false);
    }
  };

  const handlePush = async () => {
    try {
      setPushing(true);
      setPushProgress([]);
      setPushComplete(false);
      
      let targetRepo = selectedRepo;
      let targetRepoUrl = '';

      // Step 1: Create repo if needed
      if (mode === 'new') {
        setPushProgress(prev => [...prev, `Creating repository ${repoName}...`]);
        
        const response = await apiClient.create_repository({
          name: repoName,
          description: `AI-generated app: ${projectName}`,
          private: false,
          auto_init: true,
          gitignore_template: undefined
        });
        
        const newRepo = await response.json();
        targetRepo = newRepo.name;
        targetRepoUrl = newRepo.html_url;
        
        setPushProgress(prev => [...prev, `✓ Repository created: ${newRepo.full_name}`]);
      } else {
        const repo = repos.find(r => r.name === selectedRepo);
        targetRepoUrl = repo?.html_url || '';
      }

      // Step 2: Push files
      setPushProgress(prev => [...prev, `Pushing ${files.length} files to ${targetRepo}...`]);
      
      const filesToPush = files.map(f => ({
        path: f.path,
        content: f.content,
        message: `Add ${f.path} from Riff AI Studio`
      }));

      const pushResponse = await apiClient.push_files({
        owner: 'OrientedSoft1', // TODO: Get from auth context
        repo: targetRepo,
        files: filesToPush,
        branch: branch
      });

      const commits = await pushResponse.json();
      
      setPushProgress(prev => [
        ...prev,
        `✓ Pushed ${commits.length} files successfully`
      ]);
      
      // Complete
      setPushComplete(true);
      setRepoUrl(targetRepoUrl);
      
      toast.success(
        <div>
          <p className="font-semibold">Project pushed to GitHub!</p>
          <p className="text-sm text-muted-foreground">{targetRepoUrl}</p>
        </div>
      );
      
      if (onSuccess) {
        onSuccess(targetRepoUrl);
      }
      
    } catch (error: any) {
      console.error('Failed to push to GitHub:', error);
      const errorMsg = error?.message || 'Failed to push to GitHub';
      toast.error(errorMsg);
      setPushProgress(prev => [...prev, `✗ Error: ${errorMsg}`]);
    } finally {
      setPushing(false);
    }
  };

  const handleClose = () => {
    if (!pushing) {
      setOpen(false);
      // Reset after animation
      setTimeout(() => {
        setPushProgress([]);
        setPushComplete(false);
        setRepoUrl('');
      }, 300);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpen}>
      <DialogTrigger asChild>
        <Button variant="outline">
          <GitBranch className="w-4 h-4 mr-2" />
          Push to GitHub
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Push to GitHub</DialogTitle>
          <DialogDescription>
            Deploy your project to a GitHub repository
          </DialogDescription>
        </DialogHeader>

        {pushProgress.length === 0 ? (
          <div className="space-y-4 py-4">
            {/* Mode Selection */}
            <div className="space-y-2">
              <Label>Repository</Label>
              <Select value={mode} onValueChange={(v: 'new' | 'existing') => setMode(v)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="new">Create new repository</SelectItem>
                  <SelectItem value="existing">Use existing repository</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {mode === 'new' ? (
              <div className="space-y-2">
                <Label htmlFor="repo-name">Repository Name</Label>
                <Input
                  id="repo-name"
                  value={repoName}
                  onChange={(e) => setRepoName(e.target.value)}
                  placeholder="my-riff-project"
                />
              </div>
            ) : (
              <div className="space-y-2">
                <Label htmlFor="existing-repo">Select Repository</Label>
                {loadingRepos ? (
                  <div className="flex items-center justify-center py-4">
                    <Loader2 className="w-4 h-4 animate-spin" />
                  </div>
                ) : (
                  <Select value={selectedRepo} onValueChange={setSelectedRepo}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select a repository" />
                    </SelectTrigger>
                    <SelectContent>
                      {repos.map((repo) => (
                        <SelectItem key={repo.id} value={repo.name}>
                          {repo.full_name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="branch">Branch</Label>
              <Input
                id="branch"
                value={branch}
                onChange={(e) => setBranch(e.target.value)}
                placeholder="main"
              />
            </div>

            <div className="rounded-md bg-muted p-3 text-sm">
              <p className="font-semibold mb-1">Files to push:</p>
              <ul className="text-muted-foreground space-y-0.5">
                {files.slice(0, 5).map((f, i) => (
                  <li key={i}>• {f.path}</li>
                ))}
                {files.length > 5 && (
                  <li>• ... and {files.length - 5} more files</li>
                )}
              </ul>
            </div>
          </div>
        ) : (
          <div className="py-4 space-y-3">
            {pushProgress.map((msg, i) => (
              <div key={i} className="flex items-start gap-2 text-sm">
                {msg.startsWith('✓') ? (
                  <CheckCircle2 className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" />
                ) : msg.startsWith('✗') ? (
                  <span className="text-red-500">✗</span>
                ) : (
                  <Loader2 className="w-4 h-4 animate-spin flex-shrink-0 mt-0.5" />
                )}
                <span className={msg.startsWith('✗') ? 'text-red-500' : ''}>
                  {msg.replace(/^[✓✗]\s*/, '')}
                </span>
              </div>
            ))}
          </div>
        )}

        <DialogFooter>
          {pushComplete ? (
            <>
              <Button variant="outline" onClick={handleClose}>
                Close
              </Button>
              <Button onClick={() => window.open(repoUrl, '_blank')}>
                View on GitHub
              </Button>
            </>
          ) : (
            <>
              <Button
                variant="outline"
                onClick={handleClose}
                disabled={pushing}
              >
                Cancel
              </Button>
              <Button
                onClick={handlePush}
                disabled={pushing || (mode === 'new' && !repoName) || (mode === 'existing' && !selectedRepo)}
              >
                {pushing ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Pushing...
                  </>
                ) : (
                  <>
                    <Upload className="w-4 h-4 mr-2" />
                    Push to GitHub
                  </>
                )}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
