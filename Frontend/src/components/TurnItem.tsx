import { useState } from 'react';
import {
  ChevronDown, ChevronRight, Check, AlertCircle, FileText,
  Copy, CheckCheck, Loader2,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useChatStore } from '../store/chatStore';
import { ConversationTurn } from '../types';
import clsx from 'clsx';

interface TurnItemProps {
  turn: ConversationTurn;
  chatId: string;
  isActive: boolean;
}

export default function TurnItem({ turn, chatId, isActive }: TurnItemProps) {
  const { toggleStepsCollapsed } = useChatStore();
  const [copied, setCopied] = useState(false);
  const [copiedText, setCopiedText] = useState(false);

  const handleCopyUser = async () => {
    await navigator.clipboard.writeText(turn.userMessage);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleCopyText = async () => {
    await navigator.clipboard.writeText(turn.agentText);
    setCopiedText(true);
    setTimeout(() => setCopiedText(false), 2000);
  };

  const stepCount = turn.steps.length;
  const hasSteps = stepCount > 0;
  const hasText = turn.agentText.length > 0;
  const hasResult = !!turn.result;
  const hasError = !!turn.error;
  const hasFiles = turn.filesCreated.length > 0;

  return (
    <div className="animate-[slideUp_0.2s_ease-out] space-y-3">
      {/* User Message */}
      <div className="group relative">
        <div className="bg-[#222228] border border-[#2e2e3a] rounded-2xl px-5 py-4">
          <div className="prose-agent text-sm text-[#e0e0f0] leading-relaxed">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
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
        <button
          onClick={handleCopyUser}
          className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded text-[#5a5a6a] hover:text-[#00a8e8] hover:bg-[#2a2a38]"
        >
          {copied ? <CheckCheck size={13} className="text-[#00a8e8]" /> : <Copy size={13} />}
        </button>
      </div>

      {/* Agent Response */}
      <div className="pl-2 space-y-2">

        {/* Steps Section */}
        {hasSteps && (
          <div className="border border-[#2e2e3a] rounded-xl overflow-hidden bg-[#1e1e24]">
            <button
              onClick={() => toggleStepsCollapsed(chatId, turn.id)}
              className="w-full flex items-center gap-2 px-4 py-2.5 text-xs text-[#5a5a6a] hover:text-[#9a9ab0] hover:bg-[#252530] transition-colors"
            >
              {turn.stepsCollapsed ? (
                <ChevronRight size={13} className="text-[#00a8e8]" />
              ) : (
                <ChevronDown size={13} className="text-[#00a8e8]" />
              )}
              <span className="font-medium text-[#b0b0c0]">
                {turn.stepsCollapsed
                  ? `${stepCount} step${stepCount !== 1 ? 's' : ''}`
                  : 'Less steps'}
              </span>
              {turn.isStreaming && !turn.stepsCollapsed && (
                <Loader2 size={12} className="ml-auto spinner text-[#00a8e8]" />
              )}
              {turn.currentTurn !== undefined && turn.maxTurns !== undefined && (
                <span className="ml-auto text-[11px] text-[#8a8a9a] font-mono">
                  {turn.currentTurn}/{turn.maxTurns}
                </span>
              )}
            </button>

            {!turn.stepsCollapsed && (
              <div className="px-4 pb-3 space-y-1.5 border-t border-[#2e2e3a]">
                {turn.steps.map((step) => (
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
        )}

        {/* Streaming dots */}
        {turn.isStreaming && !hasText && (
          <div className="flex items-center gap-2 px-2 py-1.5">
            <div className="flex gap-1">
              <span className="stream-dot w-1.5 h-1.5 rounded-full bg-[#00a8e8] inline-block" />
              <span className="stream-dot w-1.5 h-1.5 rounded-full bg-[#00a8e8] inline-block" />
              <span className="stream-dot w-1.5 h-1.5 rounded-full bg-[#00a8e8] inline-block" />
            </div>
          </div>
        )}

        {/* Agent Text Output */}
        {hasText && (
          <div className="group relative bg-[#1e1e26] border border-[#2e2e3a] rounded-xl px-5 py-4">
            <div className="prose-agent">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {turn.agentText}
              </ReactMarkdown>
              {turn.isStreaming && turn.streamPhase === 'text' && (
                <span className="typing-cursor" />
              )}
            </div>
            {!turn.isStreaming && (
              <button
                onClick={handleCopyText}
                className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded text-[#5a5a6a] hover:text-[#00a8e8] hover:bg-[#2a2a38]"
              >
                {copiedText ? <CheckCheck size={13} className="text-[#00a8e8]" /> : <Copy size={13} />}
              </button>
            )}
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

        {/* Files Created */}
        {hasFiles && (
          <div className="px-4 py-3 bg-[#1e1e26] border border-[#2e2e3a] rounded-xl">
            <p className="text-xs font-medium text-[#5a5a6a] mb-1.5">Files created</p>
            <div className="space-y-1">
              {turn.filesCreated.map((file) => {
                const name = file.split('/').pop() ?? file;
                return (
                  <div key={file} className="flex items-center gap-1.5">
                    <FileText size={11} className="text-[#00a8e8] flex-shrink-0" />
                    <span className="text-xs font-mono text-[#9a9ab0] truncate">{name}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
