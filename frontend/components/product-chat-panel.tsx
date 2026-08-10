"use client";

import { useEffect, useRef, useState } from "react";
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
      setMessages([...newMessages, { role: "assistant", content: "抱歉，暫時無法取得回覆，請稍後再試。" }]);
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
    <aside className="flex h-full flex-col bg-white">
      <div className="shrink-0 border-b border-slate-100 px-4 py-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm font-bold text-teal-700">AI 商品詢問</p>
            <h2 className="mt-1 text-lg font-bold text-slate-950">
              {selected.length === 0 ? "先勾選商品" : `已選 ${selected.length} 張商品`}
            </h2>
          </div>
          {messages.length > 0 && (
            <button
              onClick={() => setMessages([])}
              title="清除對話紀錄"
              className="rounded-full px-2.5 py-1 text-xs font-bold text-slate-400 transition hover:bg-rose-50 hover:text-rose-500"
            >
              清除
            </button>
          )}
        </div>
      </div>

      {selected.length > 0 && (
        <div className="shrink-0 border-b border-slate-100 px-3 py-3">
          <div className="flex max-h-32 flex-wrap gap-1.5 overflow-y-auto">
            {selected.map((p) => (
              <span
                key={p.product_id}
                className="inline-flex items-center gap-1 rounded-full border border-teal-100 bg-teal-50 px-2.5 py-1 text-xs font-bold text-teal-700"
              >
                <span className="max-w-[130px] truncate">{p.product_name}</span>
                <button
                  onClick={() => onDeselect(p.product_id)}
                  className="leading-none text-teal-400 hover:text-teal-800"
                  title="移除商品"
                >
                  x
                </button>
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-4 py-4">
        {selected.length === 0 && messages.length === 0 ? (
          <EmptyState
            title="勾選商品後詢問 AI"
            description="例如條款限制、保障差異、適合情境，都可以放在這裡問。"
          />
        ) : messages.length === 0 ? (
          <EmptyState
            title="可以開始詢問"
            description="試著問：這些商品的保障差異在哪裡？"
          />
        ) : (
          messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-[88%] rounded-2xl px-3.5 py-2.5 text-xs leading-6 ${
                  m.role === "user"
                    ? "rounded-br-md bg-slate-950 text-white"
                    : "rounded-bl-md bg-slate-100 text-slate-800"
                }`}
              >
                {m.role === "user" ? m.content : <MarkdownContent content={m.content} />}
              </div>
            </div>
          ))
        )}

        {loading && (
          <div className="flex justify-start">
            <div className="rounded-2xl rounded-bl-md bg-slate-100 px-3.5 py-2.5">
              <div className="flex h-4 items-center gap-1">
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:0ms]" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:150ms]" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:300ms]" />
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="shrink-0 border-t border-slate-100 bg-white px-3 py-3">
        <div className="flex items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={selected.length === 0 ? "請先勾選商品..." : "輸入問題，Enter 送出"}
            disabled={selected.length === 0 || loading}
            rows={2}
            className="flex-1 resize-none rounded-2xl border border-slate-200 px-3 py-2 text-xs leading-5 text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-teal-300 focus:ring-4 focus:ring-teal-100 disabled:bg-slate-50 disabled:text-slate-400"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || selected.length === 0 || loading}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-slate-950 text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40"
            title="送出"
          >
            <SendIcon />
          </button>
        </div>
        <p className="mt-2 text-center text-[10px] text-slate-300">
          AI 回覆僅供資訊參考
        </p>
      </div>
    </aside>
  );
}

function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center rounded-3xl border border-dashed border-slate-200 bg-slate-50 px-4 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-teal-700 shadow-sm">
        <MessageIcon />
      </div>
      <p className="mt-3 text-sm font-bold text-slate-700">{title}</p>
      <p className="mt-1 max-w-52 text-xs leading-5 text-slate-400">{description}</p>
    </div>
  );
}

function MessageIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4z" />
    </svg>
  );
}

function SendIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
      <path d="M22 2L11 13" />
      <path d="M22 2L15 22L11 13L2 9L22 2Z" />
    </svg>
  );
}
