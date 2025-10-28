import { Editor } from '@monaco-editor/react';
import { useTheme } from '@/hooks/use-theme';
import { Card } from '@/components/ui/card';
import { Loader2 } from 'lucide-react';

interface Props {
  code: string;
  language: string;
  readOnly?: boolean;
  onChange?: (value: string | undefined) => void;
}

/**
 * Detect language from file path
 */
export const detectLanguage = (filePath: string): string => {
  const ext = filePath.split('.').pop()?.toLowerCase();
  
  const languageMap: Record<string, string> = {
    'py': 'python',
    'js': 'javascript',
    'jsx': 'javascript',
    'ts': 'typescript',
    'tsx': 'typescript',
    'html': 'html',
    'css': 'css',
    'scss': 'scss',
    'json': 'json',
    'md': 'markdown',
    'yaml': 'yaml',
    'yml': 'yaml',
    'sql': 'sql',
    'sh': 'shell',
    'bash': 'shell',
  };
  
  return languageMap[ext || ''] || 'plaintext';
};

/**
 * Monaco code editor component
 * Supports syntax highlighting, themes, and optional editing
 */
export const CodeEditor = ({ code, language, readOnly = true, onChange }: Props) => {
  const { theme } = useTheme();
  
  // Map our theme to Monaco theme
  const monacoTheme = theme === 'light' ? 'light' : 'vs-dark';
  
  return (
    <Card className="h-full border-border overflow-hidden">
      <Editor
        height="100%"
        language={language}
        value={code}
        theme={monacoTheme}
        onChange={onChange}
        options={{
          readOnly,
          minimap: { enabled: true },
          fontSize: 14,
          lineNumbers: 'on',
          roundedSelection: false,
          scrollBeyondLastLine: false,
          automaticLayout: true,
          tabSize: 2,
          wordWrap: 'off',
          folding: true,
          renderLineHighlight: 'all',
          cursorBlinking: 'smooth',
          smoothScrolling: true,
          padding: { top: 16, bottom: 16 },
        }}
        loading={
          <div className="h-full flex items-center justify-center bg-background">
            <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
          </div>
        }
      />
    </Card>
  );
};
