import React, { useState } from 'react';
import { API_URL } from 'app';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, RefreshCw, ExternalLink } from 'lucide-react';

export function PreviewPanel({ projectId }: { projectId: string }) {
  const [isBuilding, setIsBuilding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [buildLogs, setBuildLogs] = useState<string[]>([]);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  
  const buildPreview = async () => {
    setIsBuilding(true);
    setError(null);
    setBuildLogs([]);
    setPreviewUrl(null);

    try {
      console.log('[BUILD] Starting build for project:', projectId);
      const response = await fetch(`${API_URL}/preview/build/${projectId}`, {
        method: 'POST',
        credentials: 'include',
      });

      const data = await response.json();
      console.log('[BUILD] Response:', data);

      if (!response.ok) {
        setError(data.error || data.detail || 'Build failed');
        if (data.logs) {
          setBuildLogs(data.logs);
        }
        return;
      }

      if (data.success) {
        // Set preview URL after successful build - use relative path
        const url = `${API_URL}/preview/${projectId}`;
        console.log('[BUILD] Setting preview URL:', url);
        setPreviewUrl(url);
        if (data.logs) {
          setBuildLogs(data.logs);
        }
      } else {
        setError(data.message || 'Build failed');
        if (data.logs) {
          setBuildLogs(data.logs);
        }
      }
    } catch (err) {
      console.error('[BUILD] Error:', err);
      setError(`Network error: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setIsBuilding(false);
    }
  };

  const handleRefresh = () => {
    // Rebuild the preview
    buildPreview();
  };

  const openInNewTab = () => {
    if (previewUrl) {
      window.open(previewUrl, '_blank');
    }
  };

  return (
    <div className="flex flex-col h-full bg-gray-900">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-gray-800 border-b border-gray-700">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${previewUrl ? 'bg-green-500' : 'bg-yellow-500'}`} />
          <span className="text-sm text-gray-300">
            {previewUrl ? 'Live Preview' : 'Preview Ready'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {!previewUrl && (
            <Button
              onClick={buildPreview}
              disabled={isBuilding}
              className="bg-blue-600 hover:bg-blue-700 text-white"
              size="sm"
            >
              {isBuilding ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Building...
                </>
              ) : (
                '🔨 Build Preview'
              )}
            </Button>
          )}
          {previewUrl && (
            <>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleRefresh}
                disabled={isBuilding}
                className="text-gray-300 hover:text-white"
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                Rebuild
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={openInNewTab}
                className="text-gray-300 hover:text-white"
              >
                <ExternalLink className="w-4 h-4 mr-2" />
                Open in New Tab
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Preview Content */}
      <div className="flex-1 relative">
        {error && (
          <div className="p-4">
            <Alert className="bg-red-900/20 border-red-700 text-red-400">
              <AlertDescription>
                <div className="font-semibold mb-2">Build Failed</div>
                <div className="text-sm">{error}</div>
                {buildLogs.length > 0 && (
                  <details className="mt-3">
                    <summary className="cursor-pointer text-sm font-medium">View Build Logs</summary>
                    <pre className="mt-2 text-xs bg-black/30 p-3 rounded overflow-auto max-h-60">
                      {buildLogs.join('\n')}
                    </pre>
                  </details>
                )}
              </AlertDescription>
            </Alert>
          </div>
        )}

        {!previewUrl && !error && !isBuilding && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <div className="text-6xl mb-4">🔨</div>
              <h3 className="text-lg font-semibold text-gray-200 mb-2">Preview Not Built</h3>
              <p className="text-sm text-gray-400 mb-4">Click 'Build Preview' to see your app</p>
            </div>
          </div>
        )}

        {isBuilding && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <Loader2 className="w-12 h-12 text-blue-500 animate-spin mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-gray-200 mb-2">Building Preview...</h3>
              <p className="text-sm text-gray-400">This may take a few moments</p>
              {buildLogs.length > 0 && (
                <div className="mt-4 max-w-2xl mx-auto">
                  <details open>
                    <summary className="cursor-pointer text-sm font-medium text-gray-300">Build Logs</summary>
                    <pre className="mt-2 text-xs text-left bg-black/30 p-3 rounded overflow-auto max-h-40">
                      {buildLogs.join('\n')}
                    </pre>
                  </details>
                </div>
              )}
            </div>
          </div>
        )}

        {previewUrl && !isBuilding && (
          <iframe
            id="preview-iframe"
            src={previewUrl}
            className="w-full h-full border-0"
            title="App Preview"
            sandbox="allow-scripts allow-same-origin allow-forms"
          />
        )}
      </div>
    </div>
  );
}
