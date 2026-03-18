import { useState, useRef, useCallback } from 'react';
import { Paperclip, ArrowUp, X, FileText, Loader2 } from 'lucide-react';
import clsx from 'clsx';

interface InputAreaProps {
  onSend: (instruction: string, files: File[]) => void;
  isStreaming: boolean;
  sessionId: string | null;
}

const ALLOWED_EXTENSIONS = ['.pptx', '.docx', '.xlsx', '.pdf', '.jpeg', '.jpg', '.png'];

export default function InputArea({ onSend, isStreaming, sessionId }: InputAreaProps) {
  const [text, setText] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSend = useCallback(() => {
    const trimmed = text.trim();
    if (!trimmed || isStreaming) return;
    onSend(trimmed, files);
    setText('');
    setFiles([]);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }, [text, files, isStreaming, onSend]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value);
    const el = e.target;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 180) + 'px';
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newFiles = Array.from(e.target.files ?? []);
    setFiles((prev) => [...prev, ...newFiles]);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const dropped = Array.from(e.dataTransfer.files).filter((f) =>
      ALLOWED_EXTENSIONS.some((ext) => f.name.toLowerCase().endsWith(ext))
    );
    if (dropped.length) setFiles((prev) => [...prev, ...dropped]);
  };

  const canSend = text.trim().length > 0 && !isStreaming;

  return (
    <div
      className="flex-shrink-0 bg-[#1a1a1e] px-4 pb-5 pt-3"
      onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
    >
      {/* File Attachments */}
      {files.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2 max-w-3xl mx-auto">
          {files.map((file, i) => (
            <div
              key={i}
              className="flex items-center gap-1.5 px-2.5 py-1 bg-[#002a40] border border-[#00a8e8]/30 rounded-lg text-xs text-[#00a8e8]"
            >
              <FileText size={11} />
              <span className="max-w-[140px] truncate">{file.name}</span>
              <button
                onClick={() => removeFile(i)}
                className="text-[#00a8e8]/50 hover:text-[#00a8e8] ml-0.5"
              >
                <X size={11} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Input Box */}
      <div className={clsx(
        'max-w-3xl mx-auto border rounded-2xl bg-[#222228] transition-all',
        isDragging
          ? 'border-[#00a8e8] shadow-lg shadow-[#00a8e8]/10'
          : 'border-[#2e2e3a] hover:border-[#3e3e4a] focus-within:border-[#00a8e8]/50 focus-within:shadow-sm focus-within:shadow-[#00a8e8]/10'
      )}>
        <div className="flex items-end gap-2 px-3 py-2">
          {/* Attach Button */}
          <label className="flex-shrink-0 cursor-pointer p-1.5 rounded-lg text-[#5a5a6a] hover:text-[#00a8e8] hover:bg-[#2a2a38] transition-colors mb-0.5">
            <Paperclip size={17} />
            <input
              ref={fileInputRef}
              type="file"
              accept=".pptx,.docx,.xlsx,.pdf,.jpeg,.jpg,.png"
              multiple
              hidden
              onChange={handleFileChange}
            />
          </label>

          {/* Text Input */}
          <textarea
            ref={textareaRef}
            value={text}
            onChange={handleTextChange}
            onKeyDown={handleKeyDown}
            placeholder={isStreaming ? 'Agent is working…' : 'How can I assist you today?'}
            disabled={isStreaming}
            rows={1}
            className="flex-1 resize-none bg-transparent text-sm text-[#e0e0f0] placeholder-[#4a4a5a] outline-none leading-relaxed py-1.5 disabled:opacity-50 min-h-[38px] max-h-[180px]"
          />

          {/* Send Button */}
          <button
            onClick={handleSend}
            disabled={!canSend}
            className={clsx(
              'flex-shrink-0 w-9 h-9 rounded-xl flex items-center justify-center transition-all mb-0.5',
              canSend
                ? 'bg-[#00a8e8] text-white hover:bg-[#0090cc] shadow-sm shadow-[#00a8e8]/30'
                : 'bg-[#2a2a38] text-[#4a4a5a] cursor-not-allowed'
            )}
          >
            {isStreaming ? (
              <Loader2 size={15} className="spinner" />
            ) : (
              <ArrowUp size={15} />
            )}
          </button>
        </div>

        {/* Bottom row */}
        <div className="flex items-center gap-2 px-4 pb-2.5">
          <span className="text-[11px] text-[#3a3a4a] font-mono">
            {sessionId ? `Session: ${sessionId.slice(0, 8)}…` : 'New session'}
          </span>
          <span className="flex-1" />
          <span className="text-[11px] text-[#3a3a4a]">
            Shift+Enter for newline
          </span>
        </div>
      </div>
    </div>
  );
}
