import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function MarkdownContent({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        p: ({ children }) => <p className="mb-2.5 last:mb-0">{children}</p>,

        strong: ({ children }) => (
          <strong className="font-semibold text-gray-900">{children}</strong>
        ),
        em: ({ children }) => (
          <em className="italic text-gray-500">{children}</em>
        ),

        ul: ({ children }) => (
          <ul className="mt-1 mb-2.5 space-y-1 last:mb-0">{children}</ul>
        ),
        ol: ({ children }) => (
          <ol className="mt-1 mb-2.5 space-y-1 last:mb-0">{children}</ol>
        ),
        li: ({ children }) => (
          <li className="flex gap-2 items-start">
            <span className="mt-0.5 shrink-0 text-blue-500 text-xs">●</span>
            <span className="flex-1">{children}</span>
          </li>
        ),

        /* 表格 */
        table: ({ children }) => (
          <div className="overflow-x-auto my-3">
            <table className="w-full text-sm border-collapse rounded-lg overflow-hidden">
              {children}
            </table>
          </div>
        ),
        thead: ({ children }) => (
          <thead className="bg-blue-50 text-gray-700">{children}</thead>
        ),
        tbody: ({ children }) => (
          <tbody className="divide-y divide-gray-100">{children}</tbody>
        ),
        tr: ({ children }) => <tr className="hover:bg-gray-50 transition-colors">{children}</tr>,
        th: ({ children }) => (
          <th className="px-4 py-2.5 text-left font-semibold text-xs border border-gray-200 whitespace-nowrap">
            {children}
          </th>
        ),
        td: ({ children }) => (
          <td className="px-4 py-2.5 text-gray-700 border border-gray-200">
            {children}
          </td>
        ),

        /* 標題降級為粗體段落，避免字級過大 */
        h1: ({ children }) => (
          <p className="font-semibold text-gray-900 text-base mt-4 mb-1.5 first:mt-0">{children}</p>
        ),
        h2: ({ children }) => (
          <p className="font-semibold text-gray-900 mt-4 mb-1.5 first:mt-0">{children}</p>
        ),
        h3: ({ children }) => (
          <p className="font-semibold text-gray-800 mt-3 mb-1 first:mt-0">{children}</p>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
