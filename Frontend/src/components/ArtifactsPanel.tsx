import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import {
  X, Download, FileText, ArrowLeft, Loader2, Image as ImageIcon,
  Copy, CheckCheck, Layers,
} from 'lucide-react';
import hljs from '../lib/hljs';
import { useChatStore } from '../store/chatStore';
import { Artifact } from '../types';
import { fetchSessionArtifacts, getArtifactDownloadUrl, getArtifactPreviewUrl } from '../api/sessions';
import { apiFetch } from '../api/auth';
import { toast } from './Toast';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getExtension(filename: string): string {
  const parts = filename.split('.');
  return parts.length > 1 ? parts.pop()!.toUpperCase() : '';
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function isImageFile(mime: string): boolean {
  return mime.startsWith('image/');
}

function isTextLike(mime: string, filename: string): boolean {
  if (mime.startsWith('text/')) return true;
  const textExtensions = [
    'py', 'js', 'ts', 'tsx', 'jsx', 'json', 'xml', 'yaml', 'yml',
    'md', 'csv', 'html', 'css', 'scss', 'sh', 'bash', 'sql', 'log',
    'ini', 'toml', 'cfg', 'conf', 'env', 'gitignore', 'dockerfile',
    'txt', 'rst', 'r', 'rb', 'java', 'c', 'cpp', 'h', 'hpp', 'go',
    'rs', 'swift', 'kt', 'php', 'pl', 'lua', 'makefile',
  ];
  const ext = filename.split('.').pop()?.toLowerCase() ?? '';
  return textExtensions.includes(ext);
}

function isPdf(mime: string): boolean {
  return mime === 'application/pdf';
}

// Map file extension to highlight.js language identifier
function extToHljsLang(filename: string): string | undefined {
  const ext = filename.split('.').pop()?.toLowerCase() ?? '';
  const map: Record<string, string> = {
    py: 'python', js: 'javascript', ts: 'typescript', tsx: 'typescript',
    jsx: 'javascript', json: 'json', xml: 'xml', yaml: 'yaml', yml: 'yaml',
    md: 'markdown', html: 'html', css: 'css', scss: 'scss',
    sh: 'bash', bash: 'bash', sql: 'sql', r: 'r', rb: 'ruby',
    java: 'java', c: 'c', cpp: 'cpp', h: 'c', hpp: 'cpp',
    go: 'go', rs: 'rust', swift: 'swift', kt: 'kotlin',
    php: 'php', pl: 'perl', lua: 'lua', dockerfile: 'dockerfile',
    toml: 'ini', ini: 'ini', csv: 'plaintext', txt: 'plaintext',
    log: 'plaintext', env: 'bash', cfg: 'ini', conf: 'ini',
  };
  return map[ext];
}

async function downloadArtifact(sessionId: string, artifact: Artifact) {
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

// ===========================================================================
// List View (default)
// ===========================================================================

export default function ArtifactsPanel() {
  const { selectedArtifact, selectArtifact, setShowArtifacts, chats, activeChatId } = useChatStore();
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [loading, setLoading] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [page, setPage] = useState(1);

  const chat = chats.find((c) => c.id === activeChatId);
  const sessionId = chat?.sessionId ?? '';
  const fetchedSessionRef = useRef<string | null>(null);

  useEffect(() => {
    if (!sessionId || fetchedSessionRef.current === sessionId) return;
    fetchedSessionRef.current = sessionId;
    setLoading(true);
    setPage(1);
    fetchSessionArtifacts(sessionId, 1, 20)
      .then((data) => {
        setArtifacts(data.artifacts);
        setHasMore(data.has_more);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [sessionId]);

  // Merge only artifacts from the current (non-history) turns not yet in DB
  const streamArtifacts = chat?.turns
    .filter((t) => !t.fromHistory)
    .flatMap((t) => t.artifacts) ?? [];
  const dbIds = new Set(artifacts.map((a) => a.artifact_id));
  const mergedArtifacts = [
    ...artifacts,
    ...streamArtifacts.filter((a) => !dbIds.has(a.artifact_id)),
  ];

  const loadingRef = useRef(false);
  const observerRef = useRef<IntersectionObserver | null>(null);

  const loadMore = useCallback(async () => {
    if (!sessionId || !hasMore || loadingRef.current) return;
    loadingRef.current = true;
    setLoading(true);
    const nextPage = page + 1;
    try {
      const data = await fetchSessionArtifacts(sessionId, nextPage, 20);
      setArtifacts((prev) => [...prev, ...data.artifacts]);
      setHasMore(data.has_more);
      setPage(nextPage);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
      loadingRef.current = false;
    }
  }, [sessionId, hasMore, page]);

  const loadMoreRef = useCallback(
    (node: HTMLDivElement | null) => {
      if (observerRef.current) {
        observerRef.current.disconnect();
        observerRef.current = null;
      }
      if (!node || !hasMore) return;
      observerRef.current = new IntersectionObserver(
        (entries) => {
          if (entries[0].isIntersecting) loadMore();
        },
        { threshold: 0.1 }
      );
      observerRef.current.observe(node);
    },
    [hasMore, loadMore]
  );

  // If an artifact is selected, show the preview
  if (selectedArtifact) {
    return (
      <ArtifactPreview
        artifact={selectedArtifact}
        sessionId={sessionId}
        onBack={() => selectArtifact(null)}
        onClose={() => { selectArtifact(null); setShowArtifacts(false); }}
      />
    );
  }

  return (
    <div className="flex flex-col h-full bg-[#16161c]">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3.5 border-b border-[#2e2e3a] flex-shrink-0">
        <div className="flex items-center gap-2">
          <Layers size={16} className="text-[#00a8e8]" />
          <span className="text-sm font-semibold text-[#c0c0d0]">Artifacts</span>
        </div>
        <button
          onClick={() => setShowArtifacts(false)}
          className="p-2 rounded-lg text-[#7a7a8a] hover:text-[#e0e0f0] hover:bg-[#2a2a38] transition-colors"
        >
          <X size={16} />
        </button>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-1">
        {mergedArtifacts.length === 0 && !loading && (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-center px-4">
            <div className="w-12 h-12 rounded-xl bg-[#222228] border border-[#2e2e3a] flex items-center justify-center">
              <FileText size={20} className="text-[#3a3a4a]" />
            </div>
            <p className="text-sm text-[#5a5a6a]">No artifacts yet</p>
            <p className="text-xs text-[#3a3a4a]">Files created by the agent will appear here</p>
          </div>
        )}

        {mergedArtifacts.map((artifact) => (
          <div
            key={artifact.artifact_id}
            className="flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-[#222228] transition-colors cursor-pointer group"
            onClick={() => selectArtifact(artifact)}
          >
            <div className="w-10 h-10 rounded-lg bg-[#2a2a38] flex items-center justify-center flex-shrink-0">
              {isImageFile(artifact.mime_type)
                ? <ImageIcon size={16} className="text-[#9a9ab0]" />
                : <FileText size={16} className="text-[#9a9ab0]" />
              }
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm text-[#e0e0f0] truncate">{artifact.filename}</p>
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-[#5a5a6a] font-mono">{getExtension(artifact.filename)}</span>
                <span className="text-[11px] text-[#3a3a4a]">{formatFileSize(artifact.file_size)}</span>
              </div>
            </div>
            <button
              onClick={(e) => {
                e.stopPropagation();
                downloadArtifact(sessionId, artifact);
              }}
              className="p-2 rounded-lg text-[#5a5a6a] hover:text-[#00a8e8] hover:bg-[#2a2a38] transition-colors opacity-0 group-hover:opacity-100"
            >
              <Download size={16} />
            </button>
          </div>
        ))}

        {loading && (
          <div className="flex justify-center py-4">
            <Loader2 size={16} className="spinner text-[#00a8e8]/50" />
          </div>
        )}

        {hasMore && <div ref={loadMoreRef} className="h-4" />}
      </div>
    </div>
  );
}

// ===========================================================================
// Preview View
// ===========================================================================

interface ArtifactPreviewProps {
  artifact: Artifact;
  sessionId: string;
  onBack: () => void;
  onClose: () => void;
}

function ArtifactPreview({ artifact, sessionId, onBack, onClose }: ArtifactPreviewProps) {
  const [content, setContent] = useState<string | null>(null);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const previewUrl = getArtifactPreviewUrl(sessionId, artifact.artifact_id);
  const mime = artifact.mime_type;
  const isText = isTextLike(mime, artifact.filename);
  const canPreview = isText || isImageFile(mime) || isPdf(mime);

  // Text / Image / PDF loading
  useEffect(() => {
    if (!canPreview) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    setContent(null);
    setBlobUrl(null);

    apiFetch(previewUrl)
      .then(async (res) => {
        if (!res.ok) {
          if (res.status === 404) throw new Error('File no longer exists on disk.');
          throw new Error(`HTTP ${res.status}`);
        }
        if (isText) {
          setContent(await res.text());
        } else {
          const blob = await res.blob();
          setBlobUrl(URL.createObjectURL(blob));
        }
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));

    return () => {
      if (blobUrl) URL.revokeObjectURL(blobUrl);
    };
  }, [artifact.artifact_id]);

  // DOCX lazy-load
  const isDocx = artifact.filename.toLowerCase().endsWith('.docx');
  const docxContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isDocx || !docxContainerRef.current) return;

    setLoading(true);
    apiFetch(previewUrl)
      .then(async (res) => {
        if (!res.ok) throw new Error(res.status === 404 ? 'File no longer exists.' : `HTTP ${res.status}`);
        const blob = await res.blob();
        const { renderAsync } = await import('docx-preview');
        if (docxContainerRef.current) {
          await renderAsync(blob, docxContainerRef.current, undefined, {
            className: 'docx-preview',
            ignoreFonts: true,
            inWrapper: false,
            ignoreWidth: true,
            ignoreHeight: true,
          });
          // Post-process: Wingdings/Symbol bullets use Private Use Area
          // Unicode characters (e.g. \uF0B7) that don't render in standard
          // fonts.  For each injected <style>, replace the font AND swap PUA
          // content characters with standard bullet glyphs.
          const puaBulletMap: Record<string, string> = {
            '\uF0B7': '\u2022', // ● → •
            '\uF0A7': '\u25AA', // ■ → ▪
            '\uF0FC': '\u2713', // ✓ → ✓
            '\uF0D8': '\u25B6', // ▶ → ▶
            '\uF076': '\u2022', // bullet variant → •
            '\uF0A8': '\u25CB', // ○ → ○
            '\uF06E': '\u25AA', // small square → ▪
            '\uF02D': '\u2013', // dash → –
          };
          docxContainerRef.current.querySelectorAll('style').forEach((styleEl) => {
            let css = styleEl.textContent ?? '';
            // Remove Wingdings/Symbol font-family declarations entirely
            css = css.replace(/font-family\s*:[^;]*(?:Wingdings|Symbol)[^;]*;/gi, '');
            // Replace PUA characters in content: "..." values
            for (const [pua, replacement] of Object.entries(puaBulletMap)) {
              css = css.replaceAll(pua, replacement);
            }
            // Also replace escaped PUA hex references like \f0b7
            css = css.replace(/\\f0b7/gi, '\\2022');
            css = css.replace(/\\f0a7/gi, '\\25AA');
            css = css.replace(/\\f0fc/gi, '\\2713');
            css = css.replace(/\\f076/gi, '\\2022');
            css = css.replace(/\\f0a8/gi, '\\25CB');
            css = css.replace(/\\f06e/gi, '\\25AA');
            css = css.replace(/\\f02d/gi, '\\2013');
            styleEl.textContent = css;
          });
        }
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [artifact.artifact_id, isDocx]);

  // XLSX lazy-load
  const isXlsx = /\.xlsx?$/i.test(artifact.filename);
  const [sheetHtml, setSheetHtml] = useState<string | null>(null);

  useEffect(() => {
    if (!isXlsx) return;

    setLoading(true);
    apiFetch(previewUrl)
      .then(async (res) => {
        if (!res.ok) throw new Error(res.status === 404 ? 'File no longer exists.' : `HTTP ${res.status}`);
        const buf = await res.arrayBuffer();
        const XLSX = await import('xlsx');
        const wb = XLSX.read(buf, { type: 'array' });
        const firstSheet = wb.Sheets[wb.SheetNames[0]];
        if (firstSheet) {
          setSheetHtml(XLSX.utils.sheet_to_html(firstSheet));
        }
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [artifact.artifact_id, isXlsx]);

  // Syntax-highlighted code with line numbers
  const highlightedCode = useMemo(() => {
    if (content === null || !isText) return null;
    const lang = extToHljsLang(artifact.filename);
    try {
      if (lang && hljs.getLanguage(lang)) {
        return hljs.highlight(content, { language: lang }).value;
      }
      const auto = hljs.highlightAuto(content);
      return auto.value;
    } catch {
      return null;
    }
  }, [content, artifact.filename, isText]);

  const lineCount = content ? content.split('\n').length : 0;

  const handleCopy = async () => {
    if (!content) return;
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const ext = getExtension(artifact.filename);

  return (
    <div className="flex flex-col h-full bg-[#16161c]">
      {/* Header */}
      <div className="flex items-center px-3 py-[10.5px] border-b border-[#2e2e3a] flex-shrink-0 gap-0.5">
        <button
          onClick={onBack}
          className="p-2 rounded-lg text-[#7a7a8a] hover:text-[#e0e0f0] hover:bg-[#2a2a38] transition-colors flex-shrink-0"
        >
          <ArrowLeft size={16} />
        </button>
        <div className="flex-1 min-w-0 px-2">
          <p className="text-sm font-medium text-[#c0c0d0] truncate">{artifact.filename}</p>
          <p className="text-[11px] text-[#5a5a6a] font-mono">{ext} &middot; {formatFileSize(artifact.file_size)}</p>
        </div>
        {isText && content !== null && (
          <button
            onClick={handleCopy}
            className="p-2 rounded-lg text-[#7a7a8a] hover:text-[#00a8e8] hover:bg-[#2a2a38] transition-colors flex-shrink-0"
            title="Copy content"
          >
            {copied ? <CheckCheck size={16} className="text-green-400" /> : <Copy size={16} />}
          </button>
        )}
        <button
          onClick={() => downloadArtifact(sessionId, artifact)}
          className="p-2 rounded-lg text-[#7a7a8a] hover:text-[#00a8e8] hover:bg-[#2a2a38] transition-colors flex-shrink-0"
          title="Download"
        >
          <Download size={16} />
        </button>
        <button
          onClick={onClose}
          className="p-2 rounded-lg text-[#7a7a8a] hover:text-[#e0e0f0] hover:bg-[#2a2a38] transition-colors flex-shrink-0"
        >
          <X size={16} />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto artifact-preview-scroll">
        {loading && (
          <div className="flex items-center justify-center h-full">
            <Loader2 size={20} className="spinner text-[#00a8e8]/50" />
          </div>
        )}

        {error && (
          <div className="flex flex-col items-center justify-center h-full gap-2 px-6 text-center">
            <p className="text-sm text-red-400">Failed to load preview</p>
            <p className="text-xs text-[#5a5a6a]">{error}</p>
          </div>
        )}

        {/* Text / Code with syntax highlighting + line numbers */}
        {!loading && !error && content !== null && isText && (
          <div className="overflow-x-auto">
              <table className="w-full border-collapse">
                <tbody>
                  {content.split('\n').map((line, i) => (
                    <tr key={i} className="hover:bg-[#1a1a24]">
                      <td className="text-right select-none px-3 py-0 text-[11px] font-mono text-[#3a3a4a] border-r border-[#2a2a34] w-[1%] whitespace-nowrap align-top leading-[1.65rem]">
                        {i + 1}
                      </td>
                      <td className="px-4 py-0 text-[13px] font-mono leading-[1.65rem] whitespace-pre text-[#c0c0d0]">
                        {highlightedCode ? (
                          <span
                            dangerouslySetInnerHTML={{
                              __html: highlightedCode.split('\n')[i] ?? '',
                            }}
                          />
                        ) : (
                          line
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
        )}

        {/* Image */}
        {!loading && !error && isImageFile(mime) && blobUrl && (
          <div className="flex items-center justify-center p-6 h-full">
            <img
              src={blobUrl}
              alt={artifact.filename}
              className="max-w-full max-h-full object-contain rounded-lg"
            />
          </div>
        )}

        {/* PDF */}
        {!loading && !error && isPdf(mime) && blobUrl && (
          <iframe
            src={blobUrl}
            title={artifact.filename}
            className="w-full h-full border-0"
          />
        )}

        {/* DOCX */}
        {isDocx && !error && (
          <div ref={docxContainerRef} className="docx-container" />
        )}

        {/* XLSX */}
        {!loading && !error && sheetHtml && (
          <div
            className="px-4 py-4 xlsx-preview overflow-auto"
            dangerouslySetInnerHTML={{ __html: sheetHtml }}
          />
        )}

        {/* No preview (PPTX, etc.) */}
        {!loading && !error && !canPreview && !isDocx && !isXlsx && (
          <div className="flex flex-col items-center justify-center h-full gap-4 px-6 text-center">
            <div className="w-16 h-16 rounded-xl bg-[#222228] border border-[#2e2e3a] flex items-center justify-center">
              <FileText size={28} className="text-[#3a3a4a]" />
            </div>
            <p className="text-sm text-[#9a9ab0]">Preview not available for {ext} files</p>
            <button
              onClick={() => downloadArtifact(sessionId, artifact)}
              className="flex items-center gap-2 px-5 py-2.5 rounded-lg border border-[#3e3e4a] text-sm text-[#c0c0d0] hover:border-[#5a5a6a] hover:text-[#e0e0f0] transition-colors"
            >
              <Download size={15} />
              Download file
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
