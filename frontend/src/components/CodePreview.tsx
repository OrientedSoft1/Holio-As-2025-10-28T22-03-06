import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { FileCode } from 'lucide-react';
import { CodeHighlight } from 'components/CodeHighlight';
import type { ProjectFile } from 'utils/workspaceStore';

interface Props {
  file: ProjectFile | null;
}

/**
 * Get language for syntax highlighting based on file extension
 */
const getLanguageFromPath = (path: string): string => {
  const ext = path.split('.').pop()?.toLowerCase();
  const languageMap: Record<string, string> = {
    ts: 'typescript',
    tsx: 'typescript',
    js: 'javascript',
    jsx: 'javascript',
    py: 'python',
    json: 'json',
    css: 'css',
    scss: 'scss',
    html: 'html',
    md: 'markdown',
    yaml: 'yaml',
    yml: 'yaml',
    sql: 'sql',
    sh: 'bash',
  };
  return languageMap[ext || ''] || 'text';
};

/**
 * Code preview component
 * Displays file content with syntax highlighting
 */
export const CodePreview = ({ file }: Props) => {
  if (!file) {
    return (
      <Card className="h-full border-border flex items-center justify-center">
        <CardContent className="text-center py-8">
          <FileCode className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
          <p className="text-sm text-muted-foreground">
            Select a file to view its contents
          </p>
        </CardContent>
      </Card>
    );
  }

  const language = getLanguageFromPath(file.file_path);
  const lineCount = file.file_content.split('\n').length;

  return (
    <Card className="h-full border-border flex flex-col">
      <CardHeader className="pb-3 border-b border-border">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-mono">{file.file_path}</CardTitle>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-xs">
              {language}
            </Badge>
            <Badge variant="outline" className="text-xs">
              v{file.version}
            </Badge>
            <Badge variant="outline" className="text-xs">
              {lineCount} lines
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex-1 p-0 overflow-auto">
        <div className="text-sm">
          <CodeHighlight
            code={file.file_content}
            language={language}
            showLineNumbers
            className="m-0 rounded-none"
          />
        </div>
      </CardContent>
    </Card>
  );
};
