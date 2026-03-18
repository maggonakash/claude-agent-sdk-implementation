import { useEffect, useRef, useCallback } from 'react';
import { useParams, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { useChatStore } from './store/chatStore';
import { useAuthStore } from './store/authStore';
import Sidebar from './components/Sidebar';
import ChatPanel from './components/ChatPanel';
import ArtifactsPanel from './components/ArtifactsPanel';
import ProtectedRoute from './components/ProtectedRoute';
import LoginPage from './pages/LoginPage';
import { toast } from './components/Toast';

function ChatLayout() {
  const { chatId: urlChatId } = useParams<{ chatId?: string }>();
  const { chats, showArtifacts, createChat, updateChatSession, pendingError, clearPendingError, artifactsPanelWidth, setArtifactsPanelWidth } = useChatStore();
  const navigate = useNavigate();

  // Try to find an existing chat by local id or sessionId
  const resolvedChat = urlChatId
    ? (chats.find((c) => c.id === urlChatId) ?? chats.find((c) => c.sessionId === urlChatId))
    : undefined;

  const chatId = resolvedChat?.id ?? null;

  // Consume pendingError: show toast then navigate without a page reload.
  // Must happen in the component (not the store) so React is still mounted when toast renders.
  useEffect(() => {
    if (!pendingError) return;
    toast.error(pendingError);
    clearPendingError();
    navigate('/', { replace: true });
  }, [pendingError]);

  // If the URL has a sessionId that isn't in the local store yet,
  // create a transient stub chat so ChatPanel calls loadHistoryForSession.
  // loadHistoryForSession will set pendingError on 403 (not your session)
  // or populate turns on 200 (your session loaded from API).
  useEffect(() => {
    if (!urlChatId || resolvedChat) return;
    const newChat = createChat();
    updateChatSession(newChat.id, urlChatId);
    navigate(`/c/${newChat.id}`, { replace: true });
  }, [urlChatId]);

  // Resizable artifacts sidebar
  const isResizing = useRef(false);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isResizing.current = true;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing.current) return;
      const newWidth = window.innerWidth - e.clientX;
      setArtifactsPanelWidth(newWidth);
    };

    const handleMouseUp = () => {
      isResizing.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
  }, [setArtifactsPanelWidth]);

  return (
    <div className="flex h-screen bg-[#1a1a1e] overflow-hidden">
      <Sidebar />

      <div className="flex flex-1 min-w-0 overflow-hidden">
        <div className={`flex flex-col flex-1 min-w-0 ${showArtifacts ? 'border-r border-[#2e2e3a]' : ''}`}>
          <ChatPanel chatId={chatId} />
        </div>

        {showArtifacts && (
          <div className="relative flex-shrink-0 bg-[#16161c] border-l border-[#2e2e3a]" style={{ width: artifactsPanelWidth }}>
            {/* Drag handle */}
            <div
              onMouseDown={handleMouseDown}
              className="absolute left-0 top-0 bottom-0 w-1 cursor-col-resize z-10 hover:bg-[#00a8e8]/30 active:bg-[#00a8e8]/50 transition-colors"
            />
            <ArtifactsPanel />
          </div>
        )}
      </div>
    </div>
  );
}

function LoginGuard() {
  const token = useAuthStore((s) => s.token);
  if (token) return <Navigate to="/" replace />;
  return <LoginPage />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginGuard />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <ChatLayout />
          </ProtectedRoute>
        }
      />
      <Route
        path="/c/:chatId"
        element={
          <ProtectedRoute>
            <ChatLayout />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
