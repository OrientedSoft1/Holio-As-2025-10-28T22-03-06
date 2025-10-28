import { create } from 'zustand';
import { apiClient } from 'app';

/**
 * Message in the chat conversation
 */
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  metadata?: Record<string, any>;
}

/**
 * Task in the project
 */
export interface Task {
  id: string;
  project_id: string;
  title: string;
  description: string;
  status: 'todo' | 'in_progress' | 'done';
  priority: 'low' | 'medium' | 'high';
  order_index: number;
  created_at: string;
  updated_at: string;
  completed_at?: string;
  metadata?: Record<string, any>;
}

/**
 * File in the virtual file system
 */
export interface ProjectFile {
  id: string;
  project_id: string;
  file_path: string;
  file_content: string;
  file_type: string;
  version: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/**
 * Project metadata
 */
export interface Project {
  id: string;
  name: string;
  description?: string;
  user_id: string;
  created_at: string;
  updated_at: string;
  metadata?: Record<string, any>;
}

/**
 * Project statistics
 */
export interface ProjectStats {
  total_files: number;
  total_tasks: number;
  completed_tasks: number;
  total_lines: number;
}

/**
 * Workspace state interface
 */
interface WorkspaceState {
  // Project ID
  projectId: string | null;
  isProjectInitialized: boolean;
  initializeProject: () => Promise<void>;

  // Current project
  currentProject: Project | null;
  setCurrentProject: (project: Project | null) => void;

  // Chat messages
  messages: ChatMessage[];
  addMessage: (message: ChatMessage) => void;
  setMessages: (messages: ChatMessage[]) => void;
  clearMessages: () => void;

  // Tasks
  tasks: Task[];
  setTasks: (tasks: Task[]) => void;
  addTask: (task: Task) => void;
  updateTask: (taskId: string, updates: Partial<Task>) => void;
  removeTask: (taskId: string) => void;

  // Files
  files: ProjectFile[];
  setFiles: (files: ProjectFile[]) => void;
  addFile: (file: ProjectFile) => void;
  updateFile: (fileId: string, updates: Partial<ProjectFile>) => void;
  removeFile: (fileId: string) => void;

  // Selected items
  selectedFileId: string | null;
  setSelectedFileId: (fileId: string | null) => void;
  selectedTaskId: string | null;
  setSelectedTaskId: (taskId: string | null) => void;

  // Project stats
  stats: ProjectStats | null;
  setStats: (stats: ProjectStats) => void;

  // UI state
  isChatLoading: boolean;
  setIsChatLoading: (loading: boolean) => void;
  
  // Panel visibility
  showTaskBoard: boolean;
  showCodePreview: boolean;
  toggleTaskBoard: () => void;
  toggleCodePreview: () => void;
}

/**
 * Zustand store for workspace state
 * Manages the entire AI chat workspace including:
 * - Current project
 * - Chat messages
 * - Tasks
 * - Files
 * - Selected items
 * - UI state
 */
export const useWorkspaceStore = create<WorkspaceState>((set, get) => ({
  // Project ID
  projectId: null,
  isProjectInitialized: false,
  initializeProject: async () => {
    try {
      // Check localStorage first
      const storedProjectId = localStorage.getItem('riff_project_id');
      
      if (storedProjectId) {
        set({ projectId: storedProjectId, isProjectInitialized: true });
        return;
      }

      // Initialize project from backend
      const response = await apiClient.init_project();
      const data = await response.json();

      if (data.success) {
        const projectId = data.project_id;
        localStorage.setItem('riff_project_id', projectId);
        set({ 
          projectId, 
          isProjectInitialized: true,
          currentProject: {
            id: projectId,
            name: data.title,
            description: data.description,
            user_id: 'default-user',
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          }
        });
      }
    } catch (error) {
      console.error('Failed to initialize project:', error);
      set({ isProjectInitialized: false });
    }
  },

  // Current project
  currentProject: null,
  setCurrentProject: (project) => set({ currentProject: project }),

  // Chat messages
  messages: [],
  addMessage: (message) => set((state) => ({
    messages: [...state.messages, message],
  })),
  setMessages: (messages) => set({ messages }),
  clearMessages: () => set({ messages: [] }),

  // Tasks
  tasks: [],
  setTasks: (tasks) => set({ tasks }),
  addTask: (task) => set((state) => ({
    tasks: [...state.tasks, task],
  })),
  updateTask: (taskId, updates) => set((state) => ({
    tasks: state.tasks.map((task) =>
      task.id === taskId ? { ...task, ...updates } : task
    ),
  })),
  removeTask: (taskId) => set((state) => ({
    tasks: state.tasks.filter((task) => task.id !== taskId),
  })),

  // Files
  files: [],
  setFiles: (files) => set({ files }),
  addFile: (file) => set((state) => ({
    files: [...state.files, file],
  })),
  updateFile: (fileId, updates) => set((state) => ({
    files: state.files.map((file) =>
      file.id === fileId ? { ...file, ...updates } : file
    ),
  })),
  removeFile: (fileId) => set((state) => ({
    files: state.files.filter((file) => file.id !== fileId),
  })),

  // Selected items
  selectedFileId: null,
  setSelectedFileId: (fileId) => set({ selectedFileId: fileId }),
  selectedTaskId: null,
  setSelectedTaskId: (taskId) => set({ selectedTaskId: taskId }),

  // Project stats
  stats: null,
  setStats: (stats) => set({ stats }),

  // UI state
  isChatLoading: false,
  setIsChatLoading: (loading) => set({ isChatLoading: loading }),
  
  // Panel visibility
  showTaskBoard: true,
  showCodePreview: true,
  toggleTaskBoard: () => set((state) => ({ showTaskBoard: !state.showTaskBoard })),
  toggleCodePreview: () => set((state) => ({ showCodePreview: !state.showCodePreview })),
}));
