import { useState, useCallback, useMemo, type ComponentPropsWithoutRef } from 'react';
import { Copy, CheckCheck, Code2 } from 'lucide-react';
import hljs from '../lib/hljs';

/**
 * Custom ReactMarkdown component overrides for prose-agent.
 * - `pre`/`code`: syntax-highlighted code blocks with language label + copy button
 * - `table`: wraps in a scrollable container to prevent overflow
 */

const LANG_DISPLAY: Record<string, string> = {
  python: 'Python', javascript: 'JavaScript', typescript: 'TypeScript',
  json: 'JSON', xml: 'XML', html: 'HTML', yaml: 'YAML', yml: 'YAML',
  markdown: 'Markdown', css: 'CSS', scss: 'SCSS', bash: 'Bash', sh: 'Shell',
  sql: 'SQL', java: 'Java', c: 'C', cpp: 'C++', go: 'Go', rust: 'Rust',
  ruby: 'Ruby', php: 'PHP', swift: 'Swift', kotlin: 'Kotlin',
  dockerfile: 'Dockerfile', ini: 'INI', toml: 'TOML', plaintext: 'Text',
  jsx: 'JSX', tsx: 'TSX', r: 'R', lua: 'Lua', perl: 'Perl',
};

function extractText(node: React.ReactNode): string {
  if (typeof node === 'string') return node;
  if (typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(extractText).join('');
  if (node && typeof node === 'object' && 'props' in node) {
    return extractText((node as React.ReactElement).props.children);
  }
  return '';
}

function extractLang(children: React.ReactNode): string | null {
  if (!children || typeof children !== 'object') return null;
  const child = Array.isArray(children) ? children[0] : children;
  if (child && typeof child === 'object' && 'props' in child) {
    const className: string = (child as React.ReactElement).props.className ?? '';
    const match = className.match(/language-(\w+)/);
    return match ? match[1] : null;
  }
  return null;
}

function PreBlock({ children, ...props }: ComponentPropsWithoutRef<'pre'>) {
  const [copied, setCopied] = useState(false);
  const text = extractText(children);
  const lang = extractLang(children);
  const displayLang = lang ? (LANG_DISPLAY[lang] ?? lang) : null;

  const handleCopy = useCallback(async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [text]);

  const highlighted = useMemo(() => {
    if (!text) return null;
    try {
      if (lang && hljs.getLanguage(lang)) {
        return hljs.highlight(text, { language: lang }).value;
      }
      const auto = hljs.highlightAuto(text);
      return auto.value;
    } catch {
      return null;
    }
  }, [text, lang]);

  return (
    <div className="group rounded-xl overflow-hidden border border-[#2e2e3a] bg-[#16161c] mb-3">
      {/* Header bar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-[#2e2e3a] bg-[#1a1a22]">
        <div className="flex items-center gap-2 text-[12px] text-[#9a9ab0]">
          <Code2 size={14} className="text-[#5a5a6a]" />
          {displayLang && <span className="font-medium">{displayLang}</span>}
        </div>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 px-2 py-0.5 rounded text-[11px] text-[#7a7a8a] hover:text-[#e0e0f0] transition-colors"
        >
          {copied
            ? <><CheckCheck size={12} className="text-green-400" /> Copied</>
            : <><Copy size={12} /></>
          }
        </button>
      </div>
      {/* Code body */}
      {highlighted ? (
        <pre className="!m-0 !border-0 !rounded-none" {...props}>
          <code
            className="hljs !bg-transparent"
            dangerouslySetInnerHTML={{ __html: highlighted }}
          />
        </pre>
      ) : (
        <pre className="!m-0 !border-0 !rounded-none" {...props}>{children}</pre>
      )}
    </div>
  );
}

function TableWrap({ children, ...props }: ComponentPropsWithoutRef<'table'>) {
  return (
    <div className="table-wrap">
      <table {...props}>{children}</table>
    </div>
  );
}

export const markdownComponents = {
  pre: PreBlock,
  table: TableWrap,
};
