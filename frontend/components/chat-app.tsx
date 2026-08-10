"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ChatInterface from "./chat-interface";
import ChatLanding from "./chat-landing";
import ChatSidebar from "./chat-sidebar";

export interface Message {
  role: "user" | "assistant";
  content: string;
}

export interface Conversation {
  id: string;
  title: string;
  createdAt: number;
  messages: Message[];
  starred?: boolean;
}

const STORAGE_KEY = "insurance_conversations";
const NEW_CHAT_TITLE = "新的諮詢";

function makeConversation(): Conversation {
  return {
    id: Date.now().toString(),
    title: NEW_CHAT_TITLE,
    createdAt: Date.now(),
    messages: [],
  };
}

export default function ChatApp({ initMessage }: { initMessage?: string }) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentId, setCurrentId] = useState("");
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const initSentRef = useRef(false);

  useEffect(() => {
    window.setTimeout(() => {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        try {
          const parsed: Conversation[] = JSON.parse(raw);
          if (parsed.length > 0) {
            setConversations(parsed);
            setCurrentId(parsed[0].id);
            return;
          }
        } catch {
          localStorage.removeItem(STORAGE_KEY);
        }
      }
      const conv = makeConversation();
      setConversations([conv]);
      setCurrentId(conv.id);
    }, 0);
  }, []);

  useEffect(() => {
    if (conversations.length > 0) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
    }
  }, [conversations]);

  function handleNew() {
    const conv = makeConversation();
    setConversations((prev) => [conv, ...prev]);
    setCurrentId(conv.id);
  }

  function handleDelete(id: string) {
    const next = conversations.filter((c) => c.id !== id);
    if (next.length === 0) {
      const conv = makeConversation();
      setConversations([conv]);
      setCurrentId(conv.id);
      return;
    }
    setConversations(next);
    if (currentId === id) setCurrentId(next[0].id);
  }

  const current = conversations.find((c) => c.id === currentId);
  const messages = useMemo(() => current?.messages ?? [], [current?.messages]);

  function handleRename(id: string, title: string) {
    setConversations((prev) =>
      prev.map((c) => (c.id === id ? { ...c, title } : c))
    );
  }

  function handleStar(id: string) {
    setConversations((prev) =>
      prev.map((c) => (c.id === id ? { ...c, starred: !c.starred } : c))
    );
  }

  const handleSend = useCallback(async (text: string, file?: File) => {
    const userMsg: Message = { role: "user", content: text };
    const history = messages.map((m) => ({ role: m.role, content: m.content }));
    const withUser = [...messages, userMsg];

    setConversations((prev) =>
      prev.map((c) =>
        c.id === currentId
          ? {
              ...c,
              messages: withUser,
              title: c.title === NEW_CHAT_TITLE ? text.slice(0, 28) : c.title,
            }
          : c
      )
    );

    setLoading(true);
    try {
      let data;
      if (file) {
        const formData = new FormData();
        formData.append("message", text);
        formData.append("history", JSON.stringify(history));
        formData.append("file", file);
        const res = await fetch("/api/chat/upload", { method: "POST", body: formData });
        data = await res.json();
      } else {
        const res = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: text, history }),
        });
        data = await res.json();
      }

      setConversations((prev) =>
        prev.map((c) =>
          c.id === currentId
            ? { ...c, messages: [...withUser, { role: "assistant", content: data.reply }] }
            : c
        )
      );
    } catch {
      setConversations((prev) =>
        prev.map((c) =>
          c.id === currentId
            ? {
                ...c,
                messages: [
                  ...withUser,
                  { role: "assistant", content: "抱歉，暫時無法取得回覆。請稍後再試，或換個方式描述你的問題。" },
                ],
              }
            : c
        )
      );
    } finally {
      setLoading(false);
    }
  }, [currentId, messages]);

  useEffect(() => {
    if (!initMessage || initSentRef.current || !currentId) return;
    initSentRef.current = true;
    void handleSend(initMessage);
  }, [currentId, handleSend, initMessage]);

  const isLanding = messages.length === 0;

  return (
    <div className="flex h-full overflow-hidden bg-[#f7faf8]">
      <ChatSidebar
        conversations={conversations}
        currentId={currentId}
        open={sidebarOpen}
        onNew={handleNew}
        onSelect={setCurrentId}
        onDelete={handleDelete}
        onRename={handleRename}
        onStar={handleStar}
        onToggle={() => setSidebarOpen((v) => !v)}
      />
      {isLanding ? (
        <ChatLanding onSend={handleSend} loading={loading} />
      ) : (
        <ChatInterface messages={messages} loading={loading} onSend={handleSend} />
      )}
    </div>
  );
}
