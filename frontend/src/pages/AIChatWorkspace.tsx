import { useEffect, useState } from 'react';
import { useWorkspaceStore } from 'utils/workspaceStore';
import { ChatHistory } from 'components/ChatHistory';
import { ChatInput } from 'components/ChatInput';
import { TaskBoard } from 'components/TaskBoard';
import { FileTree } from 'components/FileTree';
import { CodePreview } from 'components/CodePreview';
import { PreviewPanel } from 'components/PreviewPanel';
import { ErrorPanel } from 'components/ErrorPanel';
import { GitHubPushButton } from 'components/GitHubPushButton';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { LayoutGrid, Code, ListTodo, Settings, Eye } from 'lucide-react';
import { apiClient, API_URL } from 'app';
import type { ChatMessage } from 'utils/workspaceStore';

/**
 * Main AI Chat Workspace
 * The primary interface where users build apps through conversation
 */
export default function AIChatWorkspace() {
  const [activeTab, setActiveTab] = useState<'tasks' | 'files' | 'preview'>('preview');
  const [availableProjects, setAvailableProjects] = useState<Array<{id: string; title: string}>>([]);

  const {
    projectId,
    isProjectInitialized,
    initializeProject,
    messages,
    addMessage,
    setMessages,
    tasks,
    setTasks,
    files,
    setFiles,
    selectedFileId,
    setSelectedFileId,
    selectedTaskId,
    setSelectedTaskId,
    stats,
    setStats,
    isChatLoading,
    setIsChatLoading,
  } = useWorkspaceStore();

  // Initialize project on mount
  useEffect(() => {
    initializeProject();
    loadProjects();
  }, []);

  // Load initial data when project is initialized
  useEffect(() => {
    if (!isProjectInitialized || !projectId) return;
    
    loadChatHistory();
    loadTasks();
    loadFiles();
    loadStats();
  }, [projectId, isProjectInitialized]);

  const loadChatHistory = async () => {
    try {
      const response = await apiClient.get_chat_history({ projectId });
      const data = await response.json();
      setMessages(data.messages || []);
    } catch (error) {
      console.error('Failed to load chat history:', error);
    }
  };

  const loadTasks = async () => {
    try {
      const response = await apiClient.list_tasks({ projectId });
      const data = await response.json();
      setTasks(data.tasks || []);
    } catch (error) {
      console.error('Failed to load tasks:', error);
    }
  };

  const loadFiles = async () => {
    try {
      const response = await apiClient.read_files({ projectId });
      const data = await response.json();
      setFiles(data.files || []);
    } catch (error) {
      console.error('Failed to load files:', error);
    }
  };

  const loadStats = async () => {
    try {
      const response = await apiClient.get_project_stats({ projectId });
      const data = await response.json();
      setStats(data);
    } catch (error) {
      console.error('Failed to load stats:', error);
    }
  };

  const loadProjects = async () => {
    try {
      const response = await apiClient.list_projects();
      const data = await response.json();
      setAvailableProjects(data);
    } catch (error) {
      console.error('Failed to load projects:', error);
    }
  };

  const handleProjectChange = (newProjectId: string) => {
    localStorage.setItem('riff_project_id', newProjectId);
    window.location.reload();
  };

  const handleSendMessage = async (content: string) => {
    // Add user message immediately
    const userMessage: ChatMessage = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
    };
    addMessage(userMessage);

    // Start loading state
    setIsChatLoading(true);
    
    try {
      // Create a placeholder message for the AI response that we'll update
      const aiMessageId = `msg-${Date.now() + 1}`;
      const aiMessage: ChatMessage = {
        id: aiMessageId,
        role: 'assistant',
        content: '',
        timestamp: new Date().toISOString(),
      };
      addMessage(aiMessage);

      // Call streaming endpoint
      const response = await fetch(`${API_URL}/ai-tools/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          project_id: projectId,
          role: 'user',
          content,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to get AI response');
      }

      // Read the stream
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let accumulatedContent = '';

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          
          if (done) break;
          
          // Decode chunk and add to accumulated content
          const chunk = decoder.decode(value, { stream: true });
          accumulatedContent += chunk;
          
          // Update the AI message in the store using setter function
          setMessages(
            useWorkspaceStore.getState().messages.map((msg) =>
              msg.id === aiMessageId
                ? { ...msg, content: accumulatedContent }
                : msg
            )
          );
        }
      }

      // Reload data to see any updates from tool execution
      await Promise.all([
        loadTasks(),
        loadFiles(),
        loadStats(),
      ]);
    } catch (error) {
      console.error('Failed to send message:', error);
      // Add error message
      const errorMessage: ChatMessage = {
        id: `msg-error-${Date.now()}`,
        role: 'assistant',
        content: 'Sorry, something went wrong. Please try again.',
        timestamp: new Date().toISOString(),
      };
      addMessage(errorMessage);
    } finally {
      setIsChatLoading(false);
    }
  };

  const selectedFile = files.find((f) => f.id === selectedFileId) || null;

  return (
    <div className="h-screen flex flex-col bg-background">
      {/* Header */}
      <header className="border-b border-border px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h1 className="text-2xl font-bold text-foreground">Riff AI Studio</h1>
            <Select value={projectId || ''} onValueChange={handleProjectChange}>
              <SelectTrigger className="w-[250px]">
                <SelectValue placeholder="Select project" />
              </SelectTrigger>
              <SelectContent>
                {availableProjects.map((project) => (
                  <SelectItem key={project.id} value={project.id}>
                    {project.title || 'Untitled Project'}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center gap-4">
            {stats && (
              <div className="flex items-center gap-4 text-sm text-muted-foreground">
                <Badge variant="secondary">{stats.file_count} files</Badge>
                <Badge variant="secondary">{stats.task_count} tasks</Badge>
              </div>
            )}
            {projectId && <GitHubPushButton projectId={projectId} />}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Pane - Chat */}
        <div className="w-1/2 flex flex-col border-r border-border">
          <ChatHistory messages={messages} isLoading={isChatLoading} />
          <div className="border-t border-border p-4">
            <ChatInput 
              onSend={handleSendMessage} 
              disabled={isChatLoading || !isProjectInitialized}
              placeholder={isProjectInitialized ? "Describe your app idea or ask for changes..." : "Initializing project..."}
            />
          </div>
        </div>

        {/* Right Pane - Tabs */}
        <div className="flex-1 flex flex-col">
          <Tabs value={activeTab} onValueChange={(val) => setActiveTab(val as 'tasks' | 'files' | 'preview')} className="flex-1 flex flex-col">
            <TabsList className="w-full rounded-none border-b border-border h-12 bg-muted/30">
              <TabsTrigger value="preview" className="flex-1">
                <Eye className="h-4 w-4 mr-2" />
                Preview
              </TabsTrigger>
              <TabsTrigger value="tasks" className="flex-1">
                <ListTodo className="h-4 w-4 mr-2" />
                Tasks
              </TabsTrigger>
              <TabsTrigger value="files" className="flex-1">
                <Code className="h-4 w-4 mr-2" />
                Files
              </TabsTrigger>
            </TabsList>
            
            <TabsContent value="preview" className="flex-1 m-0 overflow-hidden">
              {(() => {
                console.log('[AIChatWorkspace] Preview tab rendering, projectId:', projectId);
                console.log('[AIChatWorkspace] projectId truthy check:', !!projectId);
                if (!projectId) {
                  console.warn('[AIChatWorkspace] projectId is falsy, PreviewPanel will NOT render!');
                  return <div className="p-8 text-center text-muted-foreground">Project not initialized</div>;
                }
                return <PreviewPanel projectId={projectId} />;
              })()}
            </TabsContent>

            <TabsContent value="tasks" className="flex-1 m-0 overflow-auto p-4">
              {projectId && <TaskBoard projectId={projectId} />}
            </TabsContent>

            <TabsContent value="files" className="flex-1 m-0 overflow-hidden">
              <div className="h-full flex">
                <div className="w-80 border-r border-border overflow-auto">
                  <FileTree 
                    files={files}
                    selectedFileId={selectedFileId}
                    onFileClick={setSelectedFileId}
                  />
                </div>
                <div className="flex-1 overflow-hidden">
                  <CodePreview file={files.find(f => f.id === selectedFileId) || null} />
                </div>
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
}
