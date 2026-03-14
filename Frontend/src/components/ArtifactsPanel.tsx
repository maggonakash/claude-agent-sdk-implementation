import { useState } from 'react';
import {
  X, Download, Copy, CheckCheck, Code2, Eye, ChevronDown
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useChatStore } from '../store/chatStore';

export default function ArtifactsPanel() {
  const { artifactTitle, artifactContent, setShowArtifacts } = useChatStore();
  const [viewMode, setViewMode] = useState<'preview' | 'code'>('preview');
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    if (!artifactContent) return;
    await navigator.clipboard.writeText(artifactContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    if (!artifactContent) return;
    const blob = new Blob([artifactContent], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${artifactTitle.replace(/\s+/g, '-').toLowerCase() || 'output'}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const hasContent = !!artifactContent;
  const displayTitle = artifactTitle || 'Output';
  const truncatedTitle = displayTitle.length > 40
    ? displayTitle.slice(0, 40) + '…'
    : displayTitle;

  return (
    <div className="flex flex-col h-full bg-[#16161c]">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[#2e2e3a] flex-shrink-0">
        <div className="flex items-center gap-1 flex-1 min-w-0">
          <span className="text-xs font-medium text-[#c0c0d0] truncate" title={displayTitle}>
            {truncatedTitle}
          </span>
          {hasContent && (
            <ChevronDown size={12} className="text-[#5a5a6a] flex-shrink-0" />
          )}
        </div>

        {/* View Toggle */}
        <div className="flex items-center bg-[#222228] rounded-lg p-0.5 border border-[#2e2e3a] flex-shrink-0">
          <button
            onClick={() => setViewMode('code')}
            className={`flex items-center gap-1 px-2 py-1 rounded-md text-xs transition-colors ${
              viewMode === 'code'
                ? 'bg-[#2e2e3a] text-[#00a8e8]'
                : 'text-[#5a5a6a] hover:text-[#9a9ab0]'
            }`}
          >
            <Code2 size={12} />
          </button>
          <button
            onClick={() => setViewMode('preview')}
            className={`flex items-center gap-1 px-2 py-1 rounded-md text-xs transition-colors ${
              viewMode === 'preview'
                ? 'bg-[#2e2e3a] text-[#00a8e8]'
                : 'text-[#5a5a6a] hover:text-[#9a9ab0]'
            }`}
          >
            <Eye size={12} />
          </button>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-1 flex-shrink-0">
          <button
            onClick={handleCopy}
            disabled={!hasContent}
            className="p-1.5 rounded-lg text-[#5a5a6a] hover:text-[#00a8e8] hover:bg-[#2a2a38] transition-colors disabled:opacity-30"
            title="Copy"
          >
            {copied ? <CheckCheck size={14} className="text-[#39e75f]" /> : <Copy size={14} />}
          </button>
          <button
            onClick={handleDownload}
            disabled={!hasContent}
            className="p-1.5 rounded-lg text-[#5a5a6a] hover:text-[#00a8e8] hover:bg-[#2a2a38] transition-colors disabled:opacity-30"
            title="Download"
          >
            <Download size={14} />
          </button>
          <button
            onClick={() => setShowArtifacts(false)}
            className="p-1.5 rounded-lg text-[#5a5a6a] hover:text-[#e0e0f0] hover:bg-[#2a2a38] transition-colors"
            title="Close"
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {!hasContent ? (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-center px-6">
            <div className="w-12 h-12 rounded-xl bg-[#222228] border border-[#2e2e3a] flex items-center justify-center">
              <Eye size={20} className="text-[#3a3a4a]" />
            </div>
            <div>
              <p className="text-sm font-medium text-[#5a5a6a]">No artifact yet</p>
              <p className="text-xs text-[#3a3a4a] mt-1">
                Results will appear here as the agent works
              </p>
            </div>
          </div>
        ) : viewMode === 'preview' ? (
          <div className="px-6 py-5">
            <div className="prose-agent">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {artifactContent}
              </ReactMarkdown>
            </div>
          </div>
        ) : (
          <div className="px-4 py-4">
            <pre className="text-xs font-mono text-[#9a9ab0] whitespace-pre-wrap leading-relaxed bg-[#111116] rounded-xl p-4 border border-[#2e2e3a] overflow-x-auto">
              {artifactContent}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
