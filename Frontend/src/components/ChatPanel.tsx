import { useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Layers, Loader2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useChatStore } from '../store/chatStore';
import { createSession, renameSession } from '../api/sessions';
import { parseSSEStream } from '../utils/stream';
import { AgentStep, TurnSegment, ConversationTurn } from '../types';
import { apiFetch, ForbiddenError } from '../api/auth';
import TurnItem from './TurnItem';
import InputArea from './InputArea';


interface ChatPanelProps {
  chatId: string | null; // null = new chat (no session yet)
}

function generateId() {
  return Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
}

export default function ChatPanel({ chatId }: ChatPanelProps) {
  const {
    chats, showArtifacts, setShowArtifacts, setArtifact,
    createChat, updateChatSession, updateChatTitle,
    addTurn, updateTurn,
    addSegment, addStepToSegment, updateStepInSegment, appendTextToSegment, updateSegment,
    loadMoreHistory, loadHistoryForSession, historyHasMoreMap, isLoadingHistory,
    loadSessions,
  } = useChatStore();

  const navigate = useNavigate();
  const chat = chats.find((c) => c.id === chatId);

  // Derive streaming state from the store — survives component remount after navigation
  const isStreaming = chat?.turns.some((t) => t.isStreaming) ?? false;
  const streamingTurns = chat?.turns.filter((t) => t.isStreaming) ?? [];
  const activeTurnId = streamingTurns[streamingTurns.length - 1]?.id ?? null;

  const feedRef = useRef<HTMLDivElement>(null);
  const topSentinelRef = useRef<HTMLDivElement>(null);
  const prevScrollHeightRef = useRef<number>(0);

  const scrollToBottom = useCallback(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, []);

  useEffect(() => {
    if (!isStreaming) return;
    scrollToBottom();
  }, [chat?.turns.length]);

  useEffect(() => {
    setTimeout(scrollToBottom, 100);
  }, [chatId]);

  // Fetch history fresh every time the active chat changes (route-driven)
  useEffect(() => {
    if (!chatId) return;
    const sessionId = useChatStore.getState().chats.find((c) => c.id === chatId)?.sessionId;
    if (!sessionId) return;
    const streaming = useChatStore.getState().chats
      .find((c) => c.id === chatId)?.turns.some((t) => t.isStreaming);
    if (streaming) return;
    loadHistoryForSession(chatId, sessionId);
  }, [chatId]);

  // Upward infinite scroll for history
  useEffect(() => {
    if (!topSentinelRef.current || !chat?.sessionId) return;
    const sessionId = chat.sessionId;
    const hasMore = historyHasMoreMap[sessionId] ?? false;

    const observer = new IntersectionObserver(
      async (entries) => {
        if (entries[0].isIntersecting && hasMore && !isLoadingHistory) {
          if (feedRef.current) {
            prevScrollHeightRef.current = feedRef.current.scrollHeight;
          }
          await loadMoreHistory(chatId!, sessionId);
          requestAnimationFrame(() => {
            if (feedRef.current) {
              const diff = feedRef.current.scrollHeight - prevScrollHeightRef.current;
              feedRef.current.scrollTop = diff;
            }
          });
        }
      },
      { threshold: 0.1, root: feedRef.current }
    );
    observer.observe(topSentinelRef.current);
    return () => observer.disconnect();
  }, [chatId, chat?.sessionId, historyHasMoreMap, isLoadingHistory]);

  const handleSend = async (instruction: string, files: File[]) => {
    if (!instruction.trim() || isStreaming) return;

    let currentChatId = chatId;
    let sessionId = chat?.sessionId ?? null;

    if (!currentChatId) {
      // New chat: pre-create session to get real UUID immediately
      try {
        const { session_id } = await createSession();
        sessionId = session_id;
        await renameSession(session_id, instruction.slice(0, 80).trim());
      } catch (e) {
        console.error('Failed to pre-create session:', e);
      }

      const newChat = createChat();
      currentChatId = newChat.id;

      if (sessionId) {
        updateChatSession(currentChatId, sessionId);
      }
    }

    const turnId = generateId();
    const now = new Date();

    const newTurn: ConversationTurn = {
      id: turnId,
      userMessage: instruction,
      userFiles: files.map((f) => f.name),
      segments: [],
      isStreaming: true,
      streamPhase: 'steps',
      filesCreated: [],
      timestamp: now,
    };

    addTurn(currentChatId, newTurn);

    const currentChat = useChatStore.getState().chats.find((c) => c.id === currentChatId);
    const onlyHistoryTurns = currentChat?.turns.every((t) => t.fromHistory) ?? true;
    if (onlyHistoryTurns || !currentChat || currentChat.turns.length === 0) {
      updateChatTitle(currentChatId, instruction.slice(0, 60));
    }

    // Navigate to the real session URL immediately (before streaming starts)
    if (sessionId && !chatId) {
      navigate(`/c/${sessionId}`, { replace: true });
      loadSessions(true);
    }

    try {
      const formData = new FormData();
      formData.append('instruction', instruction);
      if (sessionId) {
        formData.append('session_id', sessionId);
      }
      for (const file of files) {
        formData.append('files', file);
      }

      const response = await apiFetch('/agent/stream', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errText = await response.text();
        updateTurn(currentChatId, turnId, {
          isStreaming: false,
          streamPhase: 'done',
          error: `HTTP ${response.status}: ${errText}`,
        });
        return;
      }

      // currentSegmentId tracks which segment we're writing into
      let currentSegmentId: string | null = null;
      let currentStepId: string | null = null;

      const getOrCreateSegment = (): string => {
        if (currentSegmentId) return currentSegmentId;
        const seg: TurnSegment = {
          id: generateId(),
          steps: [],
          stepsCollapsed: false,
          text: '',
        };
        addSegment(currentChatId!, turnId, seg);
        currentSegmentId = seg.id;
        return seg.id;
      };

      const getAllText = (): string => {
        const turn = useChatStore.getState().chats
          .find((c) => c.id === currentChatId)?.turns
          .find((t) => t.id === turnId);
        return turn?.segments.map((s) => s.text).filter(Boolean).join('\n\n') ?? '';
      };

      for await (const event of parseSSEStream(response)) {
        switch (event.type) {
          case 'session_start':
            if (event.session_id) {
              updateChatSession(currentChatId!, event.session_id);
            }
            break;

          case 'message_created':
            if (event.message_id) {
              updateTurn(currentChatId!, turnId, { messageId: event.message_id });
            }
            break;

          case 'status': {
            const segId = getOrCreateSegment();
            const stepId = generateId();
            const step: AgentStep = {
              id: stepId,
              type: 'status',
              text: event.message ?? '',
              completed: true,
              turn: event.turn,
              maxTurns: event.max_turns,
            };
            addStepToSegment(currentChatId!, turnId, segId, step);
            if (event.turn !== undefined) {
              updateTurn(currentChatId!, turnId, {
                currentTurn: event.turn,
                maxTurns: event.max_turns,
              });
            }
            scrollToBottom();
            break;
          }

          case 'tool_start': {
            // If the current segment already has text, start a fresh segment for this new round
            const currentSeg = currentSegmentId
              ? useChatStore.getState().chats
                  .find((c) => c.id === currentChatId)?.turns
                  .find((t) => t.id === turnId)?.segments
                  .find((s) => s.id === currentSegmentId)
              : null;

            if (!currentSegmentId || (currentSeg && currentSeg.text.length > 0)) {
              const seg: TurnSegment = {
                id: generateId(),
                steps: [],
                stepsCollapsed: false,
                text: '',
              };
              addSegment(currentChatId!, turnId, seg);
              currentSegmentId = seg.id;
            }

            currentStepId = generateId();
            const step: AgentStep = {
              id: currentStepId,
              type: 'tool',
              text: `Using ${event.tool}`,
              tool: event.tool,
              completed: false,
            };
            addStepToSegment(currentChatId!, turnId, currentSegmentId!, step);
            scrollToBottom();
            break;
          }

          case 'tool_end': {
            if (currentStepId && currentSegmentId) {
              updateStepInSegment(currentChatId!, turnId, currentSegmentId, currentStepId, {
                completed: true,
                summary: event.summary,
                text: event.summary ? `${event.tool}: ${event.summary}` : `${event.tool}`,
              });
              currentStepId = null;
            }
            scrollToBottom();
            break;
          }

          case 'text_delta': {
            if (event.text) {
              const segId = getOrCreateSegment();
              appendTextToSegment(currentChatId!, turnId, segId, event.text);
              updateTurn(currentChatId!, turnId, { streamPhase: 'text' });
              const allText = getAllText();
              const title = useChatStore.getState().chats.find((c) => c.id === currentChatId)?.title;
              setArtifact(title ?? 'Output', allText);
              scrollToBottom();
            }
            break;
          }

          case 'result': {
            updateTurn(currentChatId!, turnId, {
              result: {
                status: 'success',
                text: event.result ?? '',
                turnsUsed: event.turns_used,
                costUsd: event.cost_usd,
              },
            });
            if (event.result) {
              const allText = getAllText();
              const title = useChatStore.getState().chats.find((c) => c.id === currentChatId)?.title;
              setArtifact(title ?? 'Result', allText || event.result);
            }
            scrollToBottom();
            break;
          }

          case 'error': {
            updateTurn(currentChatId!, turnId, { error: event.message });
            scrollToBottom();
            break;
          }

          case 'files': {
            if (event.files_modified?.length) {
              updateTurn(currentChatId!, turnId, { filesCreated: event.files_modified });
              scrollToBottom();
            }
            break;
          }

          case 'done': {
            // Auto-collapse any segment with more than 4 steps
            const finalTurn = useChatStore.getState().chats
              .find((c) => c.id === currentChatId)?.turns
              .find((t) => t.id === turnId);
            finalTurn?.segments.forEach((seg) => {
              if (seg.steps.length > 4) {
                updateSegment(currentChatId!, turnId, seg.id, { stepsCollapsed: true });
              }
            });

            updateTurn(currentChatId!, turnId, { isStreaming: false, streamPhase: 'done' });
            loadSessions(true);
            scrollToBottom();
            break;
          }
        }
      }
    } catch (err: unknown) {
      if (err instanceof ForbiddenError) {
        updateTurn(currentChatId!, turnId, {
          isStreaming: false,
          streamPhase: 'done',
          error: 'Access denied — this session belongs to another account.',
        });
        return;
      }
      const message = err instanceof Error ? err.message : 'Unknown error';
      updateTurn(currentChatId!, turnId, {
        isStreaming: false,
        streamPhase: 'done',
        error: `Stream error: ${message}`,
      });
    }
  };

  const chatTitle = chat?.title ?? 'New Chat';
  const sessionId = chat?.sessionId ?? null;
  const hasMoreHistory = sessionId ? (historyHasMoreMap[sessionId] ?? false) : false;

  return (
    <div className="flex flex-col h-full bg-[#1a1a1e]">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3.5 border-b border-[#2e2e3a] flex-shrink-0">
        <h1 className="text-sm font-semibold text-[#c0c0d0] max-w-lg line-clamp-1 prose-agent [&_p]:inline [&_p]:m-0">
          {chatTitle === 'New Chat' ? '' : (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{chatTitle}</ReactMarkdown>
          )}
        </h1>
        <button
          onClick={() => setShowArtifacts(!showArtifacts)}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
            showArtifacts
              ? 'bg-[#00a8e8]/10 text-[#00a8e8] border border-[#00a8e8]/20'
              : 'text-[#5a5a6a] hover:bg-[#222228] hover:text-[#9a9ab0]'
          }`}
        >
          <Layers size={14} />
          Artifacts
        </button>
      </div>

      {/* Message Feed */}
      <div ref={feedRef} className="flex-1 overflow-y-auto">
        {(!chat || chat.turns.length === 0) ? (
          <EmptyState />
        ) : (
          <div className="max-w-3xl mx-auto px-6 py-8 space-y-6">
            <div ref={topSentinelRef} className="h-1" />

            {isLoadingHistory && (
              <div className="flex justify-center py-2">
                <Loader2 size={15} className="spinner text-[#00a8e8]/50" />
              </div>
            )}

            {hasMoreHistory && !isLoadingHistory && (
              <div className="text-center">
                <button
                  onClick={() => sessionId && chatId && loadMoreHistory(chatId, sessionId)}
                  className="text-xs text-[#5a5a6a] hover:text-[#00a8e8] transition-colors"
                >
                  Load older messages
                </button>
              </div>
            )}

            {chat.turns.map((turn) => (
              <TurnItem
                key={turn.id}
                turn={turn}
                chatId={chatId!}
                sessionId={sessionId ?? ''}
                isActive={turn.id === activeTurnId}
              />
            ))}
          </div>
        )}
      </div>

      {/* Input */}
      <InputArea
        onSend={handleSend}
        isStreaming={isStreaming}
        sessionId={sessionId}
      />
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-5 text-center px-6">
      <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-[#00a8e8] to-[#0077a8] flex items-center justify-center shadow-lg shadow-[#00a8e8]/20">
        <span className="text-white text-2xl font-bold">D</span>
      </div>
      <div className="space-y-2">
        <h2 className="text-xl font-semibold text-[#e0e0f0]">Doc Agent</h2>
        <p className="text-sm text-[#5a5a6a] max-w-xs leading-relaxed">
          Upload documents and give instructions. Watch the agent work in real-time.
        </p>
      </div>
      <div className="flex flex-wrap gap-2 justify-center mt-1">
        {['Summarize this document', 'Extract key data', 'Reformat the presentation'].map((hint) => (
          <span key={hint} className="px-3 py-1.5 bg-[#222228] rounded-full text-xs text-[#5a5a6a] border border-[#2e2e3a]">
            {hint}
          </span>
        ))}
      </div>
    </div>
  );
}
