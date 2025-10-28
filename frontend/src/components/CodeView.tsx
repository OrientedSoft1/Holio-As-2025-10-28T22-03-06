import { useState, useEffect } from 'react';
import { apiClient } from 'app';
import { toast } from 'sonner';
import { FileTree } from 'components/FileTree';
import { CodeEditor, detectLanguage } from 'components/CodeEditor';
import { Loader2, FileCode } from 'lucide-react';
import type { ProjectFile } from 'utils/workspaceStore';

interface Props {
  projectId: string;
}

/**
 * Code view component with file tree and Monaco editor
 * Displays project files in a tree structure and allows viewing code
 */
export const CodeView = ({ projectId }: Props) => {
  const [files, setFiles] = useState<ProjectFile[]>([]);
  const [selectedFileId, setSelectedFileId] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<ProjectFile | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingFile, setLoadingFile] = useState(false);

  // Load all files on mount
  useEffect(() => {
    loadFiles();
  }, [projectId]);

  const loadFiles = async () => {
    try {
      setLoading(true);
      const response = await apiClient.read_files({ projectId });
      const data = await response.json();
      
      if (data.success && data.files) {
        setFiles(data.files);
        
        // Auto-select first file if none selected
        if (data.files.length > 0 && !selectedFileId) {
          handleFileClick(data.files[0].id);
        }
      }
    } catch (err) {
      console.error('Failed to load files:', err);
      toast.error('Failed to load files');
    } finally {
      setLoading(false);
    }
  };

  const handleFileClick = async (fileId: string) => {
    try {
      setLoadingFile(true);
      setSelectedFileId(fileId);
      
      // Find file in current files list
      const file = files.find(f => f.id === fileId);
      if (file) {
        setSelectedFile(file);
      }
    } catch (err) {
      console.error('Failed to load file:', err);
      toast.error('Failed to load file');
    } finally {
      setLoadingFile(false);
    }
  };

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center space-y-4">
          <Loader2 className="w-8 h-8 animate-spin mx-auto text-muted-foreground" />
          <p className="text-sm text-muted-foreground">Loading files...</p>
        </div>
      </div>
    );
  }

  if (files.length === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="w-16 h-16 mx-auto bg-muted rounded-lg flex items-center justify-center">
            <FileCode className="w-8 h-8 text-muted-foreground" />
          </div>
          <div>
            <h3 className="text-lg font-medium text-foreground mb-2">No Code Yet</h3>
            <p className="text-sm text-muted-foreground">
              Chat with AI to generate code for your project
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex gap-4">
      {/* File Tree - Left Sidebar */}
      <div className="w-64 flex-shrink-0">
        <FileTree
          files={files}
          selectedFileId={selectedFileId}
          onFileClick={handleFileClick}
        />
      </div>

      {/* Code Editor - Main Area */}
      <div className="flex-1 flex flex-col">
        {selectedFile ? (
          <>
            {/* File Header */}
            <div className="px-4 py-2 bg-card border border-border rounded-t-md flex items-center justify-between">
              <span className="text-sm font-mono text-muted-foreground">
                {selectedFile.file_path}
              </span>
              <span className="text-xs text-muted-foreground">
                {selectedFile.language || detectLanguage(selectedFile.file_path)}
              </span>
            </div>

            {/* Editor */}
            <div className="flex-1 rounded-b-md overflow-hidden">
              {loadingFile ? (
                <div className="h-full flex items-center justify-center bg-card">
                  <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
                </div>
              ) : (
                <CodeEditor
                  code={selectedFile.file_content}
                  language={selectedFile.language || detectLanguage(selectedFile.file_path)}
                  readOnly={true}
                />
              )}
            </div>
          </>
        ) : (
          <div className="h-full flex items-center justify-center bg-card border border-border rounded-md">
            <p className="text-sm text-muted-foreground">
              Select a file to view its code
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
