import { useState } from 'react';
import { apiClient } from 'app';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { toast } from 'sonner';

/**
 * Test page for verifying AI Agent Toolkit endpoints
 * This is a development/testing page to ensure all AI tools work correctly
 */
export default function TestAgentTools() {
  const [projectId] = useState(() => crypto.randomUUID());
  const [taskId, setTaskId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<string[]>([]);

  const addResult = (message: string) => {
    setResults(prev => [...prev, `${new Date().toLocaleTimeString()}: ${message}`]);
  };

  const testTaskCreation = async () => {
    setLoading(true);
    try {
      const response = await apiClient.create_task({
        project_id: projectId,
        title: 'Test Task from Agent Tools',
        description: 'This is a test task created to verify the AI agent toolkit',
        priority: 'medium',
        order_index: 0,
      });

      const data = await response.json();
      if (data.success) {
        const newTaskId = data.data.task_id;
        setTaskId(newTaskId);
        addResult(`✓ Task created: ${newTaskId}`);
        toast.success('Task created successfully');
      }
    } catch (error) {
      addResult(`✗ Failed to create task: ${error}`);
      toast.error('Failed to create task');
    } finally {
      setLoading(false);
    }
  };

  const testTaskList = async () => {
    setLoading(true);
    try {
      const response = await apiClient.list_tasks({ projectId });
      const data = await response.json();
      addResult(`✓ Found ${data.tasks?.length || 0} task(s)`);
      toast.success(`Found ${data.tasks?.length || 0} tasks`);
    } catch (error) {
      addResult(`✗ Failed to list tasks: ${error}`);
      toast.error('Failed to list tasks');
    } finally {
      setLoading(false);
    }
  };

  const testTaskUpdate = async () => {
    if (!taskId) {
      toast.error('Create a task first');
      return;
    }

    setLoading(true);
    try {
      const response = await apiClient.update_task({
        task_id: taskId,
        status: 'in_progress',
      });

      const data = await response.json();
      if (data.success) {
        addResult(`✓ Task updated to in_progress`);
        toast.success('Task updated successfully');
      }
    } catch (error) {
      addResult(`✗ Failed to update task: ${error}`);
      toast.error('Failed to update task');
    } finally {
      setLoading(false);
    }
  };

  const testFileCreation = async () => {
    setLoading(true);
    try {
      const response = await apiClient.create_file({
        project_id: projectId,
        file_path: 'test/example.py',
        file_content: '# Test file\nprint("Hello from AI agent!")\n',
        file_type: 'python',
      });

      const data = await response.json();
      if (data.success) {
        addResult(`✓ File created: ${data.data.file_path}`);
        toast.success('File created successfully');
      }
    } catch (error) {
      addResult(`✗ Failed to create file: ${error}`);
      toast.error('Failed to create file');
    } finally {
      setLoading(false);
    }
  };

  const testFileRead = async () => {
    setLoading(true);
    try {
      const response = await apiClient.read_files({ projectId });
      const data = await response.json();
      addResult(`✓ Found ${data.files?.length || 0} file(s)`);
      toast.success(`Found ${data.files?.length || 0} files`);
    } catch (error) {
      addResult(`✗ Failed to read files: ${error}`);
      toast.error('Failed to read files');
    } finally {
      setLoading(false);
    }
  };

  const testProjectStats = async () => {
    setLoading(true);
    try {
      const response = await apiClient.get_project_stats({ projectId });
      const data = await response.json();
      addResult(`✓ Project stats: ${data.total_files} files, ${data.total_tasks} tasks`);
      toast.success('Project stats retrieved');
    } catch (error) {
      addResult(`✗ Failed to get project stats: ${error}`);
      toast.error('Failed to get stats');
    } finally {
      setLoading(false);
    }
  };

  const clearResults = () => {
    setResults([]);
  };

  return (
    <div className="min-h-screen bg-background p-8">
      <div className="max-w-4xl mx-auto space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-foreground">AI Agent Toolkit Test</h1>
          <p className="text-muted-foreground mt-2">
            Test page for verifying all AI agent endpoints are working correctly
          </p>
          <p className="text-sm text-muted-foreground mt-1">
            Project ID: <code className="bg-muted px-2 py-1 rounded">{projectId}</code>
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card>
            <CardHeader>
              <CardTitle>Task Management</CardTitle>
              <CardDescription>Test task CRUD operations</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              <Button
                onClick={testTaskCreation}
                disabled={loading}
                className="w-full"
              >
                Create Task
              </Button>
              <Button
                onClick={testTaskList}
                disabled={loading}
                variant="outline"
                className="w-full"
              >
                List Tasks
              </Button>
              <Button
                onClick={testTaskUpdate}
                disabled={loading || !taskId}
                variant="outline"
                className="w-full"
              >
                Update Task Status
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>File System</CardTitle>
              <CardDescription>Test file operations</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              <Button
                onClick={testFileCreation}
                disabled={loading}
                className="w-full"
              >
                Create File
              </Button>
              <Button
                onClick={testFileRead}
                disabled={loading}
                variant="outline"
                className="w-full"
              >
                Read Files
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Project Tools</CardTitle>
              <CardDescription>Test project utilities</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              <Button
                onClick={testProjectStats}
                disabled={loading}
                className="w-full"
              >
                Get Project Stats
              </Button>
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Test Results</CardTitle>
                <CardDescription>Logs from endpoint tests</CardDescription>
              </div>
              <Button onClick={clearResults} variant="outline" size="sm">
                Clear
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="bg-muted rounded-lg p-4 max-h-96 overflow-y-auto">
              {results.length === 0 ? (
                <p className="text-muted-foreground text-sm">No results yet. Run some tests!</p>
              ) : (
                <div className="space-y-1 font-mono text-sm">
                  {results.map((result, i) => (
                    <div key={i} className="text-foreground">
                      {result}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
