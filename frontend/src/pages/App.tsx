import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

/**
 * Home page - redirects to AIChatWorkspace
 */
export default function App() {
  const navigate = useNavigate();

  useEffect(() => {
    navigate('/ai-chat-workspace');
  }, [navigate]);

  return null;
}
