import { useParams, Routes, Route, Navigate } from 'react-router-dom';
import { useChatStore } from './store/chatStore';
import Sidebar from './components/Sidebar';
import ChatPanel from './components/ChatPanel';
import ArtifactsPanel from './components/ArtifactsPanel';

function ChatLayout() {
  const { chatId: urlChatId } = useParams<{ chatId?: string }>();
  const { chats, showArtifacts } = useChatStore();

  // Resolve chat: look up by local id first, then by sessionId (for /c/{session_id} URLs)
  const resolvedChat = urlChatId
    ? (chats.find((c) => c.id === urlChatId) ?? chats.find((c) => c.sessionId === urlChatId))
    : undefined;

  // Pass local chat id to ChatPanel (null = new chat mode)
  const chatId = resolvedChat?.id ?? null;

  return (
    <div className="flex h-screen bg-[#1a1a1e] overflow-hidden">
      <Sidebar />

      <div className="flex flex-1 min-w-0 overflow-hidden">
        <div className={`flex flex-col flex-1 min-w-0 ${showArtifacts ? 'border-r border-[#2e2e3a]' : ''}`}>
          <ChatPanel chatId={chatId} />
        </div>

        {showArtifacts && (
          <div className="w-[480px] flex-shrink-0 bg-[#16161c] border-l border-[#2e2e3a]">
            <ArtifactsPanel />
          </div>
        )}
      </div>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<ChatLayout />} />
      <Route path="/c/:chatId" element={<ChatLayout />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
