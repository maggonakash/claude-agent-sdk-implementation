import { useState } from 'react';
import {
  ChevronDown, ChevronRight, Check, AlertCircle, FileText,
  Copy, CheckCheck, Loader2, ThumbsUp, ThumbsDown, Download,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useChatStore } from '../store/chatStore';
import { Artifact, ConversationTurn, TurnSegment } from '../types';
import { getArtifactDownloadUrl } from '../api/sessions';
import { apiFetch } from '../api/auth';
import FeedbackModal from './FeedbackModal';
import { markdownComponents } from './MarkdownComponents';
import { toast } from './Toast';
import clsx from 'clsx';

interface TurnItemProps {
  turn: ConversationTurn;
  chatId: string;       // local store ID (for store actions)
  sessionId: string;   // MongoDB session_id (for API calls)
  isActive: boolean;
}

function getExtension(filename: string): string {
  const parts = filename.split('.');
  return parts.length > 1 ? parts.pop()!.toUpperCase() : '';
}

async function handleDownload(sessionId: string, artifact: Artifact) {
  try {
    const url = getArtifactDownloadUrl(sessionId, artifact.artifact_id);
    const res = await apiFetch(url);
    if (!res.ok) {
      toast.error(
        res.status === 404
          ? `File "${artifact.filename}" no longer exists.`
          : `Download failed (${res.status}).`
      );
      return;
    }
    const blob = await res.blob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = artifact.filename;
    a.click();
    URL.revokeObjectURL(a.href);
  } catch {
    toast.error('Download failed. Please try again.');
  }
}

export default function TurnItem({ turn, chatId, sessionId, isActive }: TurnItemProps) {
  const { toggleSegmentStepsCollapsed, updateTurn, selectArtifact } = useChatStore();
  const [copied, setCopied] = useState(false);
  const [copiedText, setCopiedText] = useState(false);
  const [feedbackModal, setFeedbackModal] = useState<'liked' | 'disliked' | null>(null);

  const handleCopyUser = async () => {
    await navigator.clipboard.writeText(turn.userMessage);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleCopyText = async () => {
    const allText = turn.segments.map((s) => s.text).filter(Boolean).join('\n\n');
    await navigator.clipboard.writeText(allText);
    setCopiedText(true);
    setTimeout(() => setCopiedText(false), 2000);
  };

  const hasError = !!turn.error;
  const hasArtifacts = turn.artifacts.length > 0;
  const hasResult = !!turn.result;
  const lastSegIdx = turn.segments.length - 1;

  return (
    <div className="animate-[slideUp_0.2s_ease-out] space-y-3">
      {/* User Message */}
      <div>
        <div className="bg-[#222228] border border-[#2e2e3a] rounded-2xl px-5 py-4">
          <div className="prose-agent text-sm text-[#e0e0f0] leading-relaxed">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
              {turn.userMessage}
            </ReactMarkdown>
          </div>
          {turn.userFiles.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2.5">
              {turn.userFiles.map((f) => (
                <span
                  key={f}
                  className="flex items-center gap-1 px-2 py-0.5 bg-[#2a2a38] border border-[#3a3a4a] rounded text-xs text-[#00a8e8]"
                >
                  <FileText size={11} />
                  {f}
                </span>
              ))}
            </div>
          )}
        </div>
        {/* Copy button below user bubble */}
        <div className="flex items-center gap-1 mt-1.5 pl-1">
          <button
            onClick={handleCopyUser}
            className="p-1.5 rounded-lg text-[#7a7a9a] hover:text-[#00a8e8] hover:bg-[#2a2a38] transition-colors"
            title="Copy message"
          >
            {copied ? <CheckCheck size={14} className="text-[#00a8e8]" /> : <Copy size={14} />}
          </button>
        </div>
      </div>

      {/* Agent Response — ordered segments */}
      <div className="pl-2 space-y-2">

        {turn.segments.map((segment, segIdx) => {
          const isLastSeg = segIdx === lastSegIdx;
          const isStreamingSeg = isActive && isLastSeg;
          const hasSteps = segment.steps.length > 0;
          const hasText = segment.text.length > 0;

          return (
            <div key={segment.id} className="space-y-2">
              {/* Steps block for this segment */}
              {hasSteps && (
                <SegmentSteps
                  segment={segment}
                  chatId={chatId}
                  turnId={turn.id}
                  isStreaming={isStreamingSeg}
                  currentTurn={turn.currentTurn}
                  maxTurns={turn.maxTurns}
                  onToggle={() => toggleSegmentStepsCollapsed(chatId, turn.id, segment.id)}
                />
              )}

              {/* Streaming dots — only on last segment, only when no text yet */}
              {isStreamingSeg && !hasText && (
                <div className="flex items-center gap-2 px-2 py-1.5">
                  <div className="flex gap-1">
                    <span className="stream-dot w-1.5 h-1.5 rounded-full bg-[#00a8e8] inline-block" />
                    <span className="stream-dot w-1.5 h-1.5 rounded-full bg-[#00a8e8] inline-block" />
                    <span className="stream-dot w-1.5 h-1.5 rounded-full bg-[#00a8e8] inline-block" />
                  </div>
                </div>
              )}

              {/* Text output for this segment */}
              {hasText && (
                <div>
                  <div className="bg-[#1e1e26] border border-[#2e2e3a] rounded-xl px-5 py-4">
                    <div className="prose-agent">
                      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                        {segment.text}
                      </ReactMarkdown>
                      {isStreamingSeg && turn.streamPhase === 'text' && (
                        <span className="typing-cursor" />
                      )}
                    </div>
                  </div>
                  {/* Action buttons — always visible below last segment after streaming */}
                  {isLastSeg && !turn.isStreaming && (
                    <div className="flex items-center gap-0.5 mt-1.5 pl-1">
                      <button
                        onClick={handleCopyText}
                        className="p-1.5 rounded-lg text-[#7a7a9a] hover:text-[#00a8e8] hover:bg-[#2a2a38] transition-colors"
                        title="Copy response"
                      >
                        {copiedText ? <CheckCheck size={14} className="text-[#00a8e8]" /> : <Copy size={14} />}
                      </button>
                      <button
                        onClick={() => setFeedbackModal('liked')}
                        className={clsx(
                          'p-1.5 rounded-lg transition-colors',
                          turn.feedbackSentiment === 'liked'
                            ? 'text-green-400'
                            : 'text-[#7a7a9a] hover:text-green-400 hover:bg-[#2a2a38]'
                        )}
                        title="Helpful"
                      >
                        <ThumbsUp size={14} />
                      </button>
                      <button
                        onClick={() => setFeedbackModal('disliked')}
                        className={clsx(
                          'p-1.5 rounded-lg transition-colors',
                          turn.feedbackSentiment === 'disliked'
                            ? 'text-red-400'
                            : 'text-[#7a7a9a] hover:text-red-400 hover:bg-[#2a2a38]'
                        )}
                        title="Not helpful"
                      >
                        <ThumbsDown size={14} />
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}

        {/* Streaming dots when no segments yet */}
        {isActive && turn.segments.length === 0 && (
          <div className="flex items-center gap-2 px-2 py-1.5">
            <div className="flex gap-1">
              <span className="stream-dot w-1.5 h-1.5 rounded-full bg-[#00a8e8] inline-block" />
              <span className="stream-dot w-1.5 h-1.5 rounded-full bg-[#00a8e8] inline-block" />
              <span className="stream-dot w-1.5 h-1.5 rounded-full bg-[#00a8e8] inline-block" />
            </div>
          </div>
        )}

        {/* Result Summary */}
        {hasResult && turn.result && (
          <div className="flex items-center gap-3 px-4 py-2.5 bg-[#0d2a1a] border border-[#1a4a2a] rounded-xl">
            <div className="w-5 h-5 rounded-full bg-[#1a4a2a] flex items-center justify-center flex-shrink-0">
              <Check size={11} className="text-[#39e75f]" />
            </div>
            <div className="flex-1 min-w-0">
              <span className="text-xs font-medium text-[#39e75f]">Complete</span>
              {(turn.result.turnsUsed || turn.result.costUsd) && (
                <div className="flex gap-3 mt-0.5">
                  {turn.result.turnsUsed && (
                    <span className="text-[11px] text-[#6ecf8a] font-mono">
                      {turn.result.turnsUsed} turns
                    </span>
                  )}
                  {turn.result.costUsd && (
                    <span className="text-[11px] text-[#6ecf8a] font-mono">
                      ${turn.result.costUsd.toFixed(4)}
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Error */}
        {hasError && (
          <div className="flex items-start gap-2.5 px-4 py-3 bg-[#2a0d0d] border border-[#4a1a1a] rounded-xl">
            <AlertCircle size={14} className="text-red-400 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-red-300 leading-relaxed">{turn.error}</p>
          </div>
        )}

        {/* Artifacts */}
        {hasArtifacts && (
          <div className="space-y-2">
            {turn.artifacts.map((artifact) => (
              <div
                key={artifact.artifact_id}
                className="flex items-center gap-3 px-4 py-3 bg-[#1e1e26] border border-[#2e2e3a] rounded-xl hover:border-[#3e3e4a] transition-colors cursor-pointer"
                onClick={() => selectArtifact(artifact)}
              >
                <div className="w-9 h-9 rounded-lg bg-[#2a2a38] flex items-center justify-center flex-shrink-0">
                  <FileText size={16} className="text-[#9a9ab0]" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-[#e0e0f0] truncate">{artifact.filename}</p>
                  <p className="text-[11px] text-[#5a5a6a] font-mono">{getExtension(artifact.filename)}</p>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDownload(sessionId, artifact);
                  }}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#3e3e4a] text-xs text-[#9a9ab0] hover:text-[#e0e0f0] hover:border-[#5a5a6a] transition-colors flex-shrink-0"
                >
                  <Download size={13} />
                  Download
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Feedback modal */}
      {feedbackModal && turn.messageId && (
        <FeedbackModal
          messageId={turn.messageId}
          initialSentiment={feedbackModal}
          onClose={() => setFeedbackModal(null)}
          onSubmitted={(sentiment) => {
            updateTurn(chatId, turn.id, { feedbackSentiment: sentiment });
          }}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Steps block for a single segment
// ---------------------------------------------------------------------------
interface SegmentStepsProps {
  segment: TurnSegment;
  chatId: string;
  turnId: string;
  isStreaming: boolean;
  currentTurn?: number;
  maxTurns?: number;
  onToggle: () => void;
}

function SegmentSteps({ segment, isStreaming, currentTurn, maxTurns, onToggle }: SegmentStepsProps) {
  const stepCount = segment.steps.length;

  return (
    <div className="border border-[#2e2e3a] rounded-xl overflow-hidden bg-[#1e1e24]">
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-2 px-4 py-2.5 text-xs text-[#5a5a6a] hover:text-[#9a9ab0] hover:bg-[#252530] transition-colors"
      >
        {segment.stepsCollapsed ? (
          <ChevronRight size={13} className="text-[#00a8e8]" />
        ) : (
          <ChevronDown size={13} className="text-[#00a8e8]" />
        )}
        <span className="font-medium text-[#b0b0c0]">
          {segment.stepsCollapsed
            ? `${stepCount} step${stepCount !== 1 ? 's' : ''}`
            : 'Less steps'}
        </span>
        {isStreaming && !segment.stepsCollapsed && (
          <Loader2 size={12} className="ml-auto spinner text-[#00a8e8]" />
        )}
        {isStreaming && currentTurn !== undefined && maxTurns !== undefined && (
          <span className="ml-auto text-[11px] text-[#8a8a9a] font-mono">
            {currentTurn}/{maxTurns}
          </span>
        )}
      </button>

      {!segment.stepsCollapsed && (
        <div className="px-4 pb-3 space-y-1.5 border-t border-[#2e2e3a]">
          {segment.steps.map((step) => (
            <div key={step.id} className="flex items-start gap-2 py-1">
              {step.type === 'tool' ? (
                <>
                  <div className={clsx(
                    'flex-shrink-0 mt-0.5 w-4 h-4 rounded flex items-center justify-center',
                    step.completed
                      ? 'bg-[#003a18] text-[#39e75f]'
                      : 'bg-[#002a40] text-[#00a8e8]'
                  )}>
                    {step.completed ? (
                      <Check size={9} />
                    ) : (
                      <Loader2 size={9} className="spinner" />
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <span className="text-xs text-[#00a8e8] font-medium font-mono">
                      {step.tool}
                    </span>
                    {step.summary && (
                      <span className="text-xs text-[#7a7a8a] ml-2 truncate">
                        {step.summary.length > 80 ? step.summary.slice(0, 80) + '…' : step.summary}
                      </span>
                    )}
                  </div>
                </>
              ) : step.type === 'error' ? (
                <>
                  <AlertCircle size={13} className="flex-shrink-0 mt-0.5 text-red-400" />
                  <p className="text-xs text-red-400">{step.text}</p>
                </>
              ) : (
                <>
                  <div className="flex-shrink-0 mt-2 w-1.5 h-1.5 rounded-full bg-[#5a5a6a]" />
                  <p className="text-xs text-[#9a9ab0] leading-relaxed">{step.text}</p>
                </>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
