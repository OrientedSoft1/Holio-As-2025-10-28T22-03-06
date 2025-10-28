import { useState, useEffect } from 'react';
import { AlertCircle, X, CheckCircle, ChevronDown, ChevronUp } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { apiClient } from 'app';
import type { ErrorResponse, ErrorDetail } from 'types';

interface Props {
  projectId: string;
}

/**
 * ErrorPanel - Shows build/runtime errors detected in the project
 * Displays error counts, details, and allows the AI to see and fix them
 */
export function ErrorPanel({ projectId }: Props) {
  const [errors, setErrors] = useState<ErrorDetail[]>([]);
  const [summary, setSummary] = useState<ErrorResponse['summary'] | null>(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadErrors();
    // Poll for errors every 10 seconds
    const interval = setInterval(loadErrors, 10000);
    return () => clearInterval(interval);
  }, [projectId]);

  const loadErrors = async () => {
    try {
      const response = await apiClient.get_open_errors({ projectId });
      const data = await response.json();
      
      setErrors(data.errors || []);
      setSummary(data.summary || null);
      
      // Auto-expand if there are new errors
      if (data.errors && data.errors.length > 0 && !isExpanded) {
        setIsExpanded(true);
      }
    } catch (error) {
      console.error('Failed to load errors:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleResolveError = async (errorId: string) => {
    try {
      await apiClient.resolve_error({ errorId });
      await loadErrors();
    } catch (error) {
      console.error('Failed to resolve error:', error);
    }
  };

  const openErrorCount = summary?.open_errors || 0;
  const hasErrors = openErrorCount > 0;

  if (!hasErrors && !isExpanded) {
    return (
      <div className="p-2 flex items-center gap-2 text-sm text-muted-foreground">
        <CheckCircle className="h-4 w-4 text-green-500" />
        <span>No errors detected</span>
      </div>
    );
  }

  return (
    <div className="border-t border-border">
      {/* Error Summary Bar */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-muted/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          {hasErrors ? (
            <AlertCircle className="h-5 w-5 text-destructive" />
          ) : (
            <CheckCircle className="h-5 w-5 text-green-500" />
          )}
          <div className="flex items-center gap-2">
            <span className="font-semibold text-sm">
              {hasErrors ? `${openErrorCount} Error${openErrorCount > 1 ? 's' : ''}` : 'No Errors'}
            </span>
            {summary && (
              <div className="flex gap-1">
                {summary.build_errors > 0 && (
                  <Badge variant="destructive" className="text-xs">
                    {summary.build_errors} Build
                  </Badge>
                )}
                {summary.runtime_errors > 0 && (
                  <Badge variant="destructive" className="text-xs">
                    {summary.runtime_errors} Runtime
                  </Badge>
                )}
                {summary.api_errors > 0 && (
                  <Badge variant="destructive" className="text-xs">
                    {summary.api_errors} API
                  </Badge>
                )}
              </div>
            )}
          </div>
        </div>
        {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
      </button>

      {/* Error Details Panel */}
      {isExpanded && (
        <div className="border-t border-border bg-muted/20">
          <ScrollArea className="h-64">
            <div className="p-4 space-y-3">
              {errors.length === 0 ? (
                <div className="text-center py-8 text-sm text-muted-foreground">
                  <CheckCircle className="h-8 w-8 text-green-500 mx-auto mb-2" />
                  <p>All errors resolved! 🎉</p>
                </div>
              ) : (
                errors.map((error) => (
                  <Card key={error.id} className="border-destructive/50">
                    <CardHeader className="pb-2">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <Badge variant="outline" className="text-xs">
                              {error.error_type}
                            </Badge>
                            {error.file_path && (
                              <span className="text-xs font-mono text-muted-foreground">
                                {error.file_path}
                                {error.line_number && `:${error.line_number}`}
                              </span>
                            )}
                          </div>
                          <CardTitle className="text-sm font-medium text-destructive">
                            {error.message}
                          </CardTitle>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleResolveError(error.id)}
                          className="h-6 w-6 p-0"
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      </div>
                    </CardHeader>
                    {error.code_snippet && (
                      <CardContent className="pt-0">
                        <pre className="text-xs bg-background/50 p-2 rounded overflow-x-auto border border-border">
                          <code>{error.code_snippet}</code>
                        </pre>
                      </CardContent>
                    )}
                    {error.stack_trace && (
                      <CardContent className="pt-2">
                        <details className="text-xs">
                          <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                            Stack trace
                          </summary>
                          <pre className="mt-2 text-xs bg-background/50 p-2 rounded overflow-x-auto border border-border">
                            <code>{error.stack_trace}</code>
                          </pre>
                        </details>
                      </CardContent>
                    )}
                  </Card>
                ))
              )}
            </div>
          </ScrollArea>
        </div>
      )}
    </div>
  );
}
