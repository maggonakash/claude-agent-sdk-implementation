import { useState } from 'react';
import { createPortal } from 'react-dom';
import { ThumbsUp, ThumbsDown, Loader2, X } from 'lucide-react';
import clsx from 'clsx';
import { setMessageLike } from '../api/feedback';

interface FeedbackModalProps {
  messageId: string;
  initialSentiment: 'liked' | 'disliked';
  onClose: () => void;
  onSubmitted: (sentiment: 'liked' | 'disliked') => void;
}

export default function FeedbackModal({
  messageId,
  initialSentiment,
  onClose,
  onSubmitted,
}: FeedbackModalProps) {
  const [sentiment, setSentiment] = useState<'liked' | 'disliked'>(initialSentiment);
  const [description, setDescription] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    setLoading(true);
    setError(null);
    try {
      await setMessageLike(messageId, sentiment === 'liked', description);
      onSubmitted(sentiment);
      onClose();
    } catch {
      setError('Failed to submit feedback. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-[#18181f] border border-[#2e2e3a] rounded-2xl p-5 w-[380px] shadow-2xl shadow-black/50"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-[#eeeef8]">Share your feedback</h3>
          <button
            onClick={onClose}
            className="w-6 h-6 flex items-center justify-center rounded-md text-[#5a5a6a] hover:text-[#9a9ab0] hover:bg-[#222228] transition-colors"
          >
            <X size={14} />
          </button>
        </div>

        {/* Sentiment toggle */}
        <div className="flex gap-2 mb-4">
          <button
            onClick={() => setSentiment('liked')}
            className={clsx(
              'flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-medium border transition-all',
              sentiment === 'liked'
                ? 'bg-green-950/50 border-green-700/50 text-green-400'
                : 'border-[#2e2e3a] text-[#5a5a6a] hover:border-[#3e3e4a] hover:text-[#9a9ab0]'
            )}
          >
            <ThumbsUp size={15} />
            Helpful
          </button>
          <button
            onClick={() => setSentiment('disliked')}
            className={clsx(
              'flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-medium border transition-all',
              sentiment === 'disliked'
                ? 'bg-red-950/50 border-red-700/50 text-red-400'
                : 'border-[#2e2e3a] text-[#5a5a6a] hover:border-[#3e3e4a] hover:text-[#9a9ab0]'
            )}
          >
            <ThumbsDown size={15} />
            Not helpful
          </button>
        </div>

        {/* Description */}
        <div className="mb-4">
          <label className="block text-xs font-medium text-[#6a6a80] mb-1.5">
            Tell us more <span className="text-[#3a3a4a] font-normal">(optional)</span>
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder={
              sentiment === 'liked'
                ? 'What did you find helpful?'
                : 'What could be improved?'
            }
            rows={3}
            className="w-full bg-[#111118] border border-[#252530] rounded-xl px-3.5 py-2.5 text-sm text-[#eeeef8] placeholder-[#3a3a4a] outline-none focus:border-[#00a8e8]/40 transition-all resize-none"
          />
        </div>

        {/* Error */}
        {error && (
          <p className="text-xs text-red-400 mb-3">{error}</p>
        )}

        {/* Actions */}
        <div className="flex gap-2 justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl text-sm font-medium text-[#8a8aaa] bg-[#222228] hover:bg-[#2a2a35] border border-[#2e2e3a] transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={loading}
            className="px-4 py-2 rounded-xl text-sm font-medium text-white bg-[#00a8e8] hover:bg-[#0090cc] disabled:opacity-50 transition-colors flex items-center gap-2 shadow-sm shadow-[#00a8e8]/20"
          >
            {loading && <Loader2 size={13} className="spinner" />}
            Submit
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}
