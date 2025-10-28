import { Card } from '@/components/ui/card';
import { API_URL } from 'app';

export default function TestPreviewBuild() {
  // Use the actual project ID from database that has React files
  const projectId = '96c089f1-14bb-4a5d-b18f-1a1e1066453a';
  const previewUrl = `${API_URL}/preview/simple/${projectId}`;

  return (
    <div className="min-h-screen bg-gray-950 p-8">
      <div className="max-w-6xl mx-auto">
        <Card className="p-6 bg-gray-900 border-gray-800">
          <h1 className="text-2xl font-bold text-white mb-4">🔨 Test Preview Build</h1>
          
          <p className="text-gray-400 mb-4">Viser hardkoda counter app frå /preview/simple endpoint</p>
          
          <div className="mt-6">
            <h3 className="text-lg font-semibold text-white mb-2">Live Preview:</h3>
            <div className="border-2 border-gray-700 rounded-lg overflow-hidden" style={{ height: '600px' }}>
              <iframe
                src={previewUrl}
                className="w-full h-full bg-white"
                title="Preview"
                sandbox="allow-scripts allow-same-origin allow-forms"
              />
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
};
