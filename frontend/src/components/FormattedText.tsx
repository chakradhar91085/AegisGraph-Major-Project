import { Fragment } from 'react';

// Renders the small Markdown subset the LLM produces (``` code blocks, # headings,
// **bold**, `code`, * bullets) as React elements. Never injects raw HTML.
export function FormattedText({ text }: { text: string }) {
  // Splitting on fence markers puts code-block contents at the odd indices.
  const blocks = text.split(/```[a-zA-Z]*\n?/);
  return (
    <>
      {blocks.map((block, i) =>
        i % 2 === 1 ? (
          <pre key={i} className="my-2 p-3 bg-slate-950 border border-slate-800 rounded-md text-xs font-mono overflow-x-auto whitespace-pre-wrap">
            {block.trimEnd()}
          </pre>
        ) : (
          <Fragment key={i}>
            {block.split('\n').map((line, j, lines) => (
              <Fragment key={j}>
                {formatLine(line)}
                {j < lines.length - 1 && '\n'}
              </Fragment>
            ))}
          </Fragment>
        )
      )}
    </>
  );
}

function formatLine(line: string) {
  const heading = line.match(/^#{1,6}\s+(.*)$/);
  if (heading) return <strong className="text-slate-50">{formatInline(heading[1])}</strong>;
  return formatInline(line.replace(/^(\s*)[*-]\s+/, '$1• '));
}

function formatInline(text: string) {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, i) => {
    if (part.length > 4 && part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className="text-slate-50">{part.slice(2, -2)}</strong>;
    }
    if (part.length > 2 && part.startsWith('`') && part.endsWith('`')) {
      return <code key={i} className="px-1 bg-slate-800 rounded text-xs font-mono">{part.slice(1, -1)}</code>;
    }
    return part;
  });
}
