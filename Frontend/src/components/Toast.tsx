/**
 * Minimal toast notification system.
 * Usage:
 *   import { toast } from './Toast';
 *   toast.error('Something went wrong');
 *   toast.info('Redirecting…');
 *
 * Mount <ToastContainer /> once at the app root.
 */
import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { AlertCircle, Info, CheckCircle, X } from 'lucide-react';

type ToastType = 'error' | 'info' | 'success';

interface ToastItem {
  id: number;
  type: ToastType;
  message: string;
}

// Global mutable list + subscriber pattern so toast() works outside React
let _toasts: ToastItem[] = [];
let _idCounter = 0;
let _listeners: Array<(toasts: ToastItem[]) => void> = [];

function publish() {
  _listeners.forEach((fn) => fn([..._toasts]));
}

function addToast(type: ToastType, message: string, duration = 4000) {
  const id = ++_idCounter;
  _toasts = [..._toasts, { id, type, message }];
  publish();
  setTimeout(() => removeToast(id), duration);
}

function removeToast(id: number) {
  _toasts = _toasts.filter((t) => t.id !== id);
  publish();
}

/** Call from anywhere — no React context needed. */
export const toast = {
  error: (msg: string, duration?: number) => addToast('error', msg, duration),
  info: (msg: string, duration?: number) => addToast('info', msg, duration),
  success: (msg: string, duration?: number) => addToast('success', msg, duration),
};

const icons: Record<ToastType, React.ReactNode> = {
  error: <AlertCircle size={15} className="flex-shrink-0 text-red-400" />,
  info:  <Info size={15} className="flex-shrink-0 text-[#00a8e8]" />,
  success: <CheckCircle size={15} className="flex-shrink-0 text-green-400" />,
};

const styles: Record<ToastType, string> = {
  error:   'bg-[#1e1014] border-red-800/50 text-red-200',
  info:    'bg-[#0d1a24] border-[#00a8e8]/30 text-[#b0d8f0]',
  success: 'bg-[#0d1a10] border-green-800/40 text-green-200',
};

export function ToastContainer() {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  useEffect(() => {
    const listener = (t: ToastItem[]) => setToasts(t);
    _listeners.push(listener);
    return () => { _listeners = _listeners.filter((l) => l !== listener); };
  }, []);

  if (toasts.length === 0) return null;

  return createPortal(
    <div className="fixed bottom-5 right-5 z-[9999] flex flex-col gap-2 pointer-events-none">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`pointer-events-auto flex items-start gap-2.5 px-4 py-3 rounded-xl border shadow-2xl shadow-black/60 text-sm max-w-[340px] animate-[slideUp_0.2s_ease-out] ${styles[t.type]}`}
        >
          {icons[t.type]}
          <span className="flex-1 leading-snug">{t.message}</span>
          <button
            onClick={() => removeToast(t.id)}
            className="flex-shrink-0 opacity-50 hover:opacity-100 transition-opacity mt-px"
          >
            <X size={13} />
          </button>
        </div>
      ))}
    </div>,
    document.body,
  );
}
