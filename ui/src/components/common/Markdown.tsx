// A deliberately small markdown renderer for operator-facing text the agents author —
// intents, briefs, deliverable documents (live-run findings F6/F7). Dependency-free and
// XSS-safe by construction: it never touches innerHTML — every construct becomes a React
// element, unknown syntax falls through as plain text. Covers the working subset (headings,
// lists, blockquotes, fenced code, hr, bold/italic/inline code, http(s) links); anything
// fancier renders as its literal source, which is the honest fallback for a preview.
import React from "react";

// ---------------------------------------------------------------- inline spans
const INLINE = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*\s][^*]*\*|\[[^\]]+\]\(https?:\/\/[^\s)]+\))/g;

function renderInline(text: string): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  let last = 0;
  let key = 0;
  for (const m of text.matchAll(INLINE)) {
    if (m.index! > last) out.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("`")) {
      out.push(
        <code key={key++} className="rounded bg-surface-2 px-1 font-mono text-[0.9em]">
          {tok.slice(1, -1)}
        </code>,
      );
    } else if (tok.startsWith("**")) {
      out.push(<strong key={key++}>{tok.slice(2, -2)}</strong>);
    } else if (tok.startsWith("*")) {
      out.push(<em key={key++}>{tok.slice(1, -1)}</em>);
    } else {
      const label = tok.slice(1, tok.indexOf("]"));
      const href = tok.slice(tok.indexOf("(") + 1, -1);
      out.push(
        <a key={key++} href={href} target="_blank" rel="noopener noreferrer"
           className="text-accent underline">
          {label}
        </a>,
      );
    }
    last = m.index! + tok.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

// ---------------------------------------------------------------- block parsing
const HEADING_CLASS: Record<number, string> = {
  1: "text-base font-semibold text-ink mt-2 mb-1",
  2: "text-sm font-semibold text-ink mt-2 mb-1",
  3: "text-[13px] font-semibold text-ink mt-1.5 mb-0.5",
  4: "text-xs font-semibold text-ink mt-1 mb-0.5",
};

export function Markdown({ text, className }: { text: string; className?: string }) {
  const lines = text.replace(/\r\n/g, "\n").split("\n");
  const blocks: React.ReactNode[] = [];
  let key = 0;
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      i += 1;
      continue;
    }
    if (line.startsWith("```")) {
      const code: string[] = [];
      i += 1;
      while (i < lines.length && !lines[i].startsWith("```")) code.push(lines[i++]);
      i += 1; // closing fence (or EOF)
      blocks.push(
        <pre key={key++}
             className="my-1 overflow-x-auto rounded bg-surface-2 p-2 font-mono text-[0.9em]">
          {code.join("\n")}
        </pre>,
      );
      continue;
    }
    const h = /^(#{1,4})\s+(.*)$/.exec(line);
    if (h) {
      const level = h[1].length;
      blocks.push(
        <div key={key++} className={HEADING_CLASS[level]}>{renderInline(h[2])}</div>,
      );
      i += 1;
      continue;
    }
    if (/^(-{3,}|\*{3,})$/.test(line.trim())) {
      blocks.push(<hr key={key++} className="my-2 border-border" />);
      i += 1;
      continue;
    }
    if (/^\s*[-*]\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i]))
        items.push(lines[i++].replace(/^\s*[-*]\s+/, ""));
      blocks.push(
        <ul key={key++} className="my-1 list-disc pl-5">
          {items.map((it, j) => <li key={j}>{renderInline(it)}</li>)}
        </ul>,
      );
      continue;
    }
    if (/^\s*\d+[.)]\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*\d+[.)]\s+/.test(lines[i]))
        items.push(lines[i++].replace(/^\s*\d+[.)]\s+/, ""));
      blocks.push(
        <ol key={key++} className="my-1 list-decimal pl-5">
          {items.map((it, j) => <li key={j}>{renderInline(it)}</li>)}
        </ol>,
      );
      continue;
    }
    if (line.startsWith(">")) {
      const quote: string[] = [];
      while (i < lines.length && lines[i].startsWith(">"))
        quote.push(lines[i++].replace(/^>\s?/, ""));
      blocks.push(
        <blockquote key={key++}
                    className="my-1 border-l-2 border-border pl-2 text-ink-muted">
          {renderInline(quote.join(" "))}
        </blockquote>,
      );
      continue;
    }
    // Paragraph: consecutive plain lines join.
    const para: string[] = [line];
    i += 1;
    while (
      i < lines.length && lines[i].trim() &&
      !/^(#{1,4}\s|```|\s*[-*]\s|\s*\d+[.)]\s|>|(-{3,}|\*{3,})$)/.test(lines[i])
    )
      para.push(lines[i++]);
    blocks.push(<p key={key++} className="my-1">{renderInline(para.join(" "))}</p>);
  }
  return <div className={className}>{blocks}</div>;
}
