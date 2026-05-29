"use client";

import { useState, useRef, useEffect } from "react";
import MarkdownContent from "./markdown-content";

interface Product {
  product_id: string;
  product_name: string;
  company: string;
  category: string;
}

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface ProductChatPanelProps {
  selected: Product[];
  onDeselect: (id: string) => void;
}

export default function ProductChatPanel({ selected, onDeselect }: ProductChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function handleSend() {
    const text = input.trim();
    if (!text || loading || selected.length === 0) return;
    setInput("");

    const userMsg: Message = { role: "user", content: text };
    const history = messages.map((m) => ({ role: m.role, content: m.content }));
    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setLoading(true);

    const productContext =
      `【用戶已選取的保險商品（供顧問參考背景資訊，根據用戶問題自然回應即可）】\n` +
      selected.map((p, i) => `${i + 1}. ${p.product_name}（${p.company}，${p.category}）`).join("\n") +
      `\n\n顧問回應提示：在介紹商品特性時，如有助於用戶理解，可適時提及該類保障的常見限制或條件（例如年齡、職業、等待期、除外事項等），以及哪類消費者情境較可能需要這類保障。不要主動推薦或比較哪家較好，保持資訊提供的立場。`;

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, history, product_context: productContext }),
      });
      const data = await res.json();
      setMessages([...newMessages, { role: "assistant", content: data.reply }]);
    } catch {
      setMessages([...newMessages, { role: "assistant", content: "抱歉，發生錯誤，請稍後再試。" }]);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="h-full flex flex-col bg-white">
      {/* Header */}
      <div className="shrink-0 px-4 py-3 border-b border-gray-200 bg-gray-50 flex items-start justify-between">
        <div>
          <p className="text-sm font-semibold text-gray-700">AI 商品詢問</p>
          <p className="text-xs text-gray-400 mt-0.5">
            {selected.length === 0 ? "請先勾選商品" : `已選 ${selected.length} 個商品`}
          </p>
        </div>
        {messages.length > 0 && (
          <button
            onClick={() => setMessages([])}
            title="清除對話紀錄"
            className="text-xs text-gray-400 hover:text-red-500 transition-colors mt-0.5"
          >
            清除
          </button>
        )}
      </div>

      {/* Selected product chips */}
      {selected.length > 0 && (
        <div className="shrink-0 px-3 py-2 border-b border-gray-100 flex flex-wrap gap-1.5 max-h-28 overflow-y-auto">
          {selected.map((p) => (
            <span
              key={p.product_id}
              className="inline-flex items-center gap-1 text-xs bg-blue-50 text-blue-700 border border-blue-200 rounded-full px-2.5 py-1"
            >
              <span className="max-w-[120px] truncate">{p.product_name}</span>
              <button
                onClick={() => onDeselect(p.product_id)}
                className="text-blue-400 hover:text-blue-700 leading-none"
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 min-h-0 overflow-y-auto px-4 py-4 flex flex-col gap-3">
        {selected.length === 0 && messages.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center text-center gap-3 text-gray-400">
            <div className="w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center text-2xl">
              💬
            </div>
            <p className="text-sm">勾選左側商品後<br />即可詢問 AI 相關問題</p>
          </div>
        ) : messages.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center text-center gap-2 text-gray-400">
            <p className="text-sm">已選好商品，可以開始詢問</p>
            <p className="text-xs text-gray-300">例如：這些商品有什麼差異？</p>
          </div>
        ) : (
          messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-[85%] text-xs leading-relaxed rounded-2xl px-3.5 py-2.5 ${
                  m.role === "user"
                    ? "bg-blue-600 text-white rounded-br-sm whitespace-pre-wrap"
                    : "bg-gray-100 text-gray-800 rounded-bl-sm"
                }`}
              >
                {m.role === "user" ? m.content : <MarkdownContent content={m.content} />}
              </div>
            </div>
          ))
        )}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-2xl rounded-bl-sm px-3.5 py-2.5">
              <div className="flex gap-1 items-center h-4">
                <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:0ms]" />
                <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:150ms]" />
                <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:300ms]" />
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="shrink-0 border-t border-gray-200 px-3 py-3 bg-white">
        <div className="flex gap-2 items-end">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={selected.length === 0 ? "請先勾選商品…" : "輸入問題，Enter 送出"}
            disabled={selected.length === 0 || loading}
            rows={2}
            className="flex-1 resize-none text-xs text-gray-800 placeholder-gray-400 border border-gray-200 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-300 disabled:bg-gray-50 disabled:text-gray-400"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || selected.length === 0 || loading}
            className="shrink-0 w-9 h-9 bg-blue-600 text-white rounded-xl flex items-center justify-center hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </button>
        </div>
        <p className="text-[10px] text-gray-300 mt-1.5 text-center">
          本服務提供資訊參考，非正式保險建議
        </p>
      </div>
    </div>
  );
}
