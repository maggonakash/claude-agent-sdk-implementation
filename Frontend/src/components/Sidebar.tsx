import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Link, useNavigate, useParams } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Plus, MessageSquare, Cpu, Settings, ChevronLeft, ChevronRight,
  Loader2, MoreHorizontal, Pencil, Trash2
} from 'lucide-react';
import { useChatStore } from '../store/chatStore';
import { deleteSession, renameSession } from '../api/sessions';
import clsx from 'clsx';

export default function Sidebar() {
  const {
    chats,
    sidebarCollapsed,
    sessionList,
    sessionListHasMore,
    isLoadingSessions,
    setActiveChat,
    deleteLocalChat,
    removeSessionFromList,
    toggleSidebar,
    loadSessions,
    loadMoreSessions,
    updateChatTitle,
    refreshSessionInList,
  } = useChatStore();

  const navigate = useNavigate();
  const { chatId: activeChatId } = useParams<{ chatId: string }>();

  const [activeTab, setActiveTab] = useState<'chats' | 'agents'>('chats');
  const sentinelRef = useRef<HTMLDivElement>(null);

  // Delete modal state
  const [deleteTarget, setDeleteTarget] = useState<{ sessionId: string; title: string } | null>(null);

  useEffect(() => {
    loadSessions(true);
  }, []);

  useEffect(() => {
    if (!sentinelRef.current) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && sessionListHasMore && !isLoadingSessions) {
          loadMoreSessions();
        }
      },
      { threshold: 0.1 }
    );
    observer.observe(sentinelRef.current);
    return () => observer.disconnect();
  }, [sessionListHasMore, isLoadingSessions]);

  const handleSelectSession = (sessionId: string, title: string | null) => {
    navigate(`/c/${sessionId}`);
    const existing = chats.find((c) => c.sessionId === sessionId);
    if (existing) {
      setActiveChat(existing.id);
      return;
    }
    const now = new Date().toISOString();
    const newChatId = Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
    useChatStore.setState((state) => ({
      chats: [
        { id: newChatId, sessionId, title: title ?? 'New Chat', turns: [], createdAt: now, updatedAt: now },
        ...state.chats,
      ],
      activeChatId: newChatId,
      showArtifacts: false,
      artifactContent: '',
      artifactTitle: '',
    }));
  };

  const handleRename = async (sessionId: string, localChatId: string | undefined, newTitle: string) => {
    if (!newTitle.trim()) return;
    try {
      await renameSession(sessionId, newTitle.trim());
      refreshSessionInList(sessionId, newTitle.trim());
      if (localChatId) updateChatTitle(localChatId, newTitle.trim());
    } catch (e) {
      console.error('Failed to rename session:', e);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    try {
      await deleteSession(deleteTarget.sessionId);
    } catch (e) {
      console.error('Failed to delete session:', e);
    }
    removeSessionFromList(deleteTarget.sessionId);
    setDeleteTarget(null);
    // If we deleted the active chat, go home
    const wasActive = chats.find((c) => c.sessionId === deleteTarget.sessionId)?.id === activeChatId;
    if (wasActive) navigate('/');
  };

  if (sidebarCollapsed) {
    return (
      <div className="w-14 flex-shrink-0 bg-[#0e0e13] flex flex-col items-center py-4 gap-3 border-r border-[#252530]">
        <button
          onClick={toggleSidebar}
          className="w-9 h-9 flex items-center justify-center rounded-lg text-[#4a4a5a] hover:text-[#00a8e8] hover:bg-[#1a1a22] transition-colors"
        >
          <ChevronRight size={17} />
        </button>
        <button
          onClick={() => navigate('/')}
          className="w-9 h-9 flex items-center justify-center rounded-lg text-[#4a4a5a] hover:text-[#00a8e8] hover:bg-[#1a1a22] transition-colors"
          title="New Chat"
        >
          <Plus size={17} />
        </button>
      </div>
    );
  }

  return (
    <>
      <div className="w-[280px] flex-shrink-0 bg-[#0e0e13] flex flex-col border-r border-[#252530]">
        {/* Header */}
        <div className="flex items-center justify-between px-4 pt-5 pb-4">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-[#00a8e8] to-[#0077b8] flex items-center justify-center text-white text-sm font-bold flex-shrink-0 shadow-md shadow-[#00a8e8]/25">
              D
            </div>
            <div className="leading-tight">
              <span className="text-[#eeeef8] font-semibold text-[15px]">Doc Agent</span>
              <div className="text-[11px] text-[#00a8e8] font-medium leading-none mt-0.5">by TechChefz</div>
            </div>
          </div>
          <button
            onClick={toggleSidebar}
            className="w-7 h-7 flex items-center justify-center rounded-lg text-[#4a4a5a] hover:text-[#00a8e8] hover:bg-[#1a1a22] transition-colors"
          >
            <ChevronLeft size={15} />
          </button>
        </div>

        {/* New Chat Button */}
        <div className="px-3 pb-4">
          <button
            onClick={() => navigate('/')}
            className="w-full flex items-center gap-2.5 px-4 py-2.5 rounded-xl border border-[#252530] text-[#8a8aaa] hover:border-[#00a8e8]/50 hover:text-[#00a8e8] hover:bg-[#00a8e8]/5 text-sm font-medium transition-all"
          >
            <Plus size={16} />
            <span>New chat</span>
          </button>
        </div>

        {/* Nav Tabs */}
        <div className="px-3 pb-3 flex gap-1.5">
          <button
            onClick={() => setActiveTab('chats')}
            className={clsx(
              'flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-semibold transition-colors',
              activeTab === 'chats'
                ? 'bg-[#1e1e28] text-[#00a8e8] border border-[#00a8e8]/25'
                : 'text-[#4a4a5a] hover:text-[#8a8aaa] hover:bg-[#181820]'
            )}
          >
            <MessageSquare size={13} />
            Chats
          </button>
          <button
            onClick={() => setActiveTab('agents')}
            className={clsx(
              'flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-semibold transition-colors',
              activeTab === 'agents'
                ? 'bg-[#1e1e28] text-[#00a8e8] border border-[#00a8e8]/25'
                : 'text-[#4a4a5a] hover:text-[#8a8aaa] hover:bg-[#181820]'
            )}
          >
            <Cpu size={13} />
            Agents
          </button>
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto px-2 pb-2">
          {activeTab === 'chats' && (
            <>
              {/* Unsaved local chats */}
              {chats.filter((c) => !c.sessionId).map((chat) => (
                <ChatRow
                  key={chat.id}
                  id={chat.id}
                  title={chat.title}
                  isActive={chat.id === activeChatId}
                  href="/"
                  onClick={() => {}}
                  onDelete={() => deleteLocalChat(chat.id)}
                  isNew
                />
              ))}

              {chats.some((c) => !c.sessionId) && sessionList.length > 0 && (
                <div className="px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[#2e2e3e] mt-1">
                  Recent
                </div>
              )}

              {sessionList.length === 0 && !isLoadingSessions && (
                <div className="px-3 py-6 text-center text-[#2e2e3e] text-sm">
                  No chats yet
                </div>
              )}

              {sessionList.map((session) => {
                const localChat = chats.find((c) => c.sessionId === session.session_id);
                const isActive = !!activeChatId && (
                  activeChatId === session.session_id || localChat?.id === activeChatId
                );
                const displayTitle = session.title ?? 'New Chat';

                return (
                  <ChatRow
                    key={session.session_id}
                    id={session.session_id}
                    title={displayTitle}
                    isActive={isActive}
                    href={`/c/${session.session_id}`}
                    onClick={() => handleSelectSession(session.session_id, session.title)}
                    onRename={async (newTitle) => {
                      await handleRename(session.session_id, localChat?.id, newTitle);
                    }}
                    onDelete={() => setDeleteTarget({ sessionId: session.session_id, title: displayTitle })}
                  />
                );
              })}

              <div ref={sentinelRef} className="h-2" />

              {isLoadingSessions && (
                <div className="flex justify-center py-3">
                  <Loader2 size={14} className="spinner text-[#00a8e8]/40" />
                </div>
              )}
            </>
          )}

          {activeTab === 'agents' && (
            <div className="px-3 py-8 text-center text-[#2e2e3e] text-sm">
              Agent management coming soon
            </div>
          )}
        </div>

        {/* Settings */}
        <div className="p-3 border-t border-[#252530]">
          <button className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-[#4a4a5a] hover:text-[#8a8aaa] hover:bg-[#181820] text-sm transition-colors">
            <Settings size={15} />
            <span>Settings and more</span>
          </button>
        </div>
      </div>

      {/* Delete confirmation modal */}
      {deleteTarget && (
        <DeleteModal
          title={deleteTarget.title}
          onConfirm={handleDeleteConfirm}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </>
  );
}

// ── Delete Modal ───────────────────────────────────────────────────────────

function DeleteModal({ title, onConfirm, onCancel }: {
  title: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onCancel}
    >
      <div
        className="bg-[#18181f] border border-[#2e2e3a] rounded-2xl p-6 w-[360px] shadow-2xl shadow-black/50"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-[#eeeef8] font-semibold text-base mb-2">Delete conversation?</h3>
        <p className="text-[#a0a0b8] text-sm mb-6 leading-relaxed select-text">
          "<span className="text-[#d0d0e8] font-medium">{title}</span>" will be permanently deleted and cannot be recovered.
        </p>
        <div className="flex gap-2.5 justify-end">
          <button
            onClick={onCancel}
            className="px-4 py-2 rounded-xl text-sm font-medium text-[#8a8aaa] bg-[#222228] hover:bg-[#2a2a35] border border-[#2e2e3a] transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className="px-4 py-2 rounded-xl text-sm font-medium text-white bg-red-600 hover:bg-red-500 transition-colors shadow-sm shadow-red-900/40"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Chat Row ───────────────────────────────────────────────────────────────

interface ChatRowProps {
  id: string;
  title: string;
  isActive: boolean;
  href: string;
  isNew?: boolean;
  onClick: () => void;
  onDelete: () => void;
  onRename?: (newTitle: string) => Promise<void>;
}

function ChatRow({ id, title, isActive, href, isNew, onClick, onDelete, onRename }: ChatRowProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [menuPos, setMenuPos] = useState<{ top: number; left: number } | null>(null);
  const [renaming, setRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState(title);
  const btnRef = useRef<HTMLButtonElement>(null);
  const renameRef = useRef<HTMLInputElement>(null);

  // Close menu on outside click or scroll
  useEffect(() => {
    if (!menuOpen) return;
    const handler = (e: MouseEvent | Event) => {
      if (btnRef.current && !(e as MouseEvent).composedPath?.().includes(btnRef.current)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    document.addEventListener('scroll', handler, true);
    return () => {
      document.removeEventListener('mousedown', handler);
      document.removeEventListener('scroll', handler, true);
    };
  }, [menuOpen]);

  const openMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const rect = btnRef.current?.getBoundingClientRect();
    if (rect) {
      setMenuPos({ top: rect.bottom + 4, left: rect.right - 144 });
    }
    setMenuOpen((v) => !v);
  };

  // Focus rename input when it appears
  useEffect(() => {
    if (renaming) {
      setRenameValue(title);
      setTimeout(() => renameRef.current?.select(), 10);
    }
  }, [renaming]);

  const submitRename = async () => {
    setRenaming(false);
    if (renameValue.trim() && renameValue.trim() !== title && onRename) {
      await onRename(renameValue.trim());
    }
  };

  if (renaming) {
    return (
      <div className="px-2.5 py-1.5 rounded-xl mb-0.5">
        <input
          ref={renameRef}
          value={renameValue}
          onChange={(e) => setRenameValue(e.target.value)}
          onBlur={submitRename}
          onKeyDown={(e) => {
            if (e.key === 'Enter') submitRename();
            if (e.key === 'Escape') setRenaming(false);
          }}
          className="w-full bg-[#1e1e28] border border-[#00a8e8]/40 rounded-lg px-2.5 py-1.5 text-sm text-[#eeeef8] outline-none"
        />
      </div>
    );
  }

  return (
    <div className="relative group mb-0.5">
      <Link
        to={href}
        onClick={onClick}
        className={clsx(
          'flex items-center px-3 py-2.5 rounded-xl transition-all text-sm border-l-2',
          isActive
            ? 'bg-[#1e1e28] text-[#eeeef8] border-[#00a8e8]'
            : 'text-[#7a7a90] hover:bg-[#181820] hover:text-[#c0c0d8] border-transparent',
          // Reserve space for ... button on hover so title doesn't overlap
          'group-hover:pr-8'
        )}
      >
        {isNew && (
          <span className="mr-2 w-1.5 h-1.5 rounded-full bg-[#00a8e8] flex-shrink-0" />
        )}
        <span className="truncate flex-1 text-[13px] leading-5 [&_p]:inline [&_p]:m-0 [&_strong]:font-semibold [&_em]:italic">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{title}</ReactMarkdown>
        </span>
      </Link>

      {/* Vignette fade overlay — appears on hover, sits over the truncated text before the ... button */}
      <div
        className={clsx(
          'absolute right-7 top-0 h-full w-14 pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity',
          isActive
            ? 'bg-gradient-to-r from-transparent to-[#1e1e28]'
            : 'bg-gradient-to-r from-transparent to-[#181820]'
        )}
      />

      {/* ... button — absolutely positioned, shown on hover */}
      <button
        ref={btnRef}
        onClick={openMenu}
        className={clsx(
          'absolute right-2 top-1/2 -translate-y-1/2 w-6 h-6 flex items-center justify-center rounded-md transition-colors',
          menuOpen
            ? 'text-[#c0c0d8] bg-[#2a2a38]'
            : 'text-transparent group-hover:text-[#6a6a80] hover:!text-[#c0c0d8] hover:bg-[#2a2a38]'
        )}
        title="More options"
      >
        <MoreHorizontal size={14} />
      </button>

      {/* Dropdown rendered via portal to escape scroll container */}
      {menuOpen && menuPos && createPortal(
        <div
          style={{ position: 'fixed', top: menuPos.top, left: menuPos.left, zIndex: 9999 }}
          className="w-36 bg-[#18181f] border border-[#2e2e3a] rounded-xl shadow-2xl shadow-black/60 overflow-hidden py-1"
          onMouseDown={(e) => e.stopPropagation()}
        >
          {onRename && (
            <button
              onClick={() => { setMenuOpen(false); setRenaming(true); }}
              className="w-full flex items-center gap-2.5 px-3 py-2.5 text-sm text-[#c0c0d8] hover:bg-[#222230] transition-colors"
            >
              <Pencil size={13} className="text-[#6a6a80]" />
              Rename
            </button>
          )}
          <button
            onClick={() => { setMenuOpen(false); onDelete(); }}
            className="w-full flex items-center gap-2.5 px-3 py-2.5 text-sm text-red-400 hover:bg-red-950/40 transition-colors"
          >
            <Trash2 size={13} />
            Delete
          </button>
        </div>,
        document.body
      )}
    </div>
  );
}
