import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ChevronRight, File, Folder } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ProjectFile } from 'utils/workspaceStore';

interface Props {
  files: ProjectFile[];
  selectedFileId: string | null;
  onFileClick: (fileId: string) => void;
}

interface FileNode {
  name: string;
  path: string;
  type: 'file' | 'folder';
  children?: FileNode[];
  file?: ProjectFile;
}

/**
 * Build a tree structure from flat file list
 */
const buildFileTree = (files: ProjectFile[]): FileNode[] => {
  const root: FileNode[] = [];
  const folders = new Map<string, FileNode>();

  // Sort files by path
  const sortedFiles = [...files].sort((a, b) => a.file_path.localeCompare(b.file_path));

  for (const file of sortedFiles) {
    const parts = file.file_path.split('/');
    let currentLevel = root;
    let currentPath = '';

    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      currentPath += (currentPath ? '/' : '') + part;
      const isLastPart = i === parts.length - 1;

      if (isLastPart) {
        // It's a file
        currentLevel.push({
          name: part,
          path: currentPath,
          type: 'file',
          file,
        });
      } else {
        // It's a folder
        let folder = folders.get(currentPath);
        if (!folder) {
          folder = {
            name: part,
            path: currentPath,
            type: 'folder',
            children: [],
          };
          folders.set(currentPath, folder);
          currentLevel.push(folder);
        }
        currentLevel = folder.children!;
      }
    }
  }

  return root;
};

/**
 * Recursive tree node component
 */
const TreeNode = ({
  node,
  selectedFileId,
  onFileClick,
  depth = 0,
}: {
  node: FileNode;
  selectedFileId: string | null;
  onFileClick: (fileId: string) => void;
  depth?: number;
}) => {
  const [isOpen, setIsOpen] = useState(true);
  const isFile = node.type === 'file';
  const isSelected = isFile && node.file?.id === selectedFileId;

  return (
    <div>
      <div
        onClick={() => {
          if (isFile && node.file) {
            onFileClick(node.file.id);
          } else {
            setIsOpen(!isOpen);
          }
        }}
        className={cn(
          'flex items-center gap-2 py-1.5 px-2 rounded text-sm cursor-pointer transition-colors hover:bg-accent',
          isSelected && 'bg-accent border-l-2 border-primary',
        )}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
      >
        {!isFile && (
          <ChevronRight
            className={cn(
              'h-4 w-4 transition-transform text-muted-foreground',
              isOpen && 'rotate-90',
            )}
          />
        )}
        {isFile ? (
          <File className="h-4 w-4 text-blue-500" />
        ) : (
          <Folder className="h-4 w-4 text-yellow-500" />
        )}
        <span className="truncate">{node.name}</span>
      </div>
      {!isFile && isOpen && node.children && (
        <div>
          {node.children.map((child) => (
            <TreeNode
              key={child.path}
              node={child}
              selectedFileId={selectedFileId}
              onFileClick={onFileClick}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
};

/**
 * File tree component
 * Displays a hierarchical view of project files
 */
export const FileTree = ({ files, selectedFileId, onFileClick }: Props) => {
  const activeFiles = files.filter((f) => f.is_active);
  const tree = buildFileTree(activeFiles);

  return (
    <Card className="h-full border-border">
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-semibold">Files</CardTitle>
      </CardHeader>
      <CardContent>
        {tree.length === 0 ? (
          <div className="text-center py-8 text-sm text-muted-foreground">
            No files yet. Start building to generate code!
          </div>
        ) : (
          <div className="space-y-0.5">
            {tree.map((node) => (
              <TreeNode
                key={node.path}
                node={node}
                selectedFileId={selectedFileId}
                onFileClick={onFileClick}
              />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};
