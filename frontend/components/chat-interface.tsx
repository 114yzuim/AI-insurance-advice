"use client";

import { useState, useRef, useEffect } from "react";
import MarkdownContent from "./markdown-content";
import type { Message } from "./chat-app";

interface Props {
  messages: Message[];
  loading: boolean;
  onSend: (text: string, file?: File) => void;
}

export default function ChatInterface({ messages, loading, onSend }: Props) {
  const [input, setInput] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [isListening, setIsListening] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  function handleSend() {
    const text = input.trim();
    if (!text || loading) return;
    onSend(text, file ?? undefined);
    setInput("");
    setFile(null);
    if (inputRef.current) inputRef.current.style.height = "auto";
    inputRef.current?.focus();
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function toggleVoice() {
    const SR =
      (window as any).SpeechRecognition ||
      (window as any).webkitSpeechRecognition;
    if (!SR) {
      alert("你的瀏覽器不支援語音輸入，請使用 Chrome 或 Edge。");
      return;
    }
    if (isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
      return;
    }
    const recognition = new SR();
    recognition.lang = "zh-TW";
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.onresult = (e: any) => {
      const transcript = e.results[0][0].transcript;
      setInput((prev) => (prev ? prev + " " + transcript : transcript));
    };
    recognition.onend = () => setIsListening(false);
    recognition.onerror = () => setIsListening(false);
    recognition.start();
    recognitionRef.current = recognition;
    setIsListening(true);
  }

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-2xl mx-auto flex flex-col gap-4">
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : "flex-row"}`}
            >
              {msg.role === "assistant" && (
                <div className="w-8 h-8 rounded-full bg-blue-700 text-white text-xs flex items-center justify-center shrink-0 mt-1">
                  AI
                </div>
              )}
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                  msg.role === "user"
                    ? "bg-blue-700 text-white rounded-tr-sm whitespace-pre-wrap"
                    : "bg-white border border-gray-200 text-gray-800 rounded-tl-sm"
                }`}
              >
                {msg.role === "user" ? (
                  msg.content
                ) : (
                  <MarkdownContent content={msg.content} />
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-full bg-blue-700 text-white text-xs flex items-center justify-center shrink-0">
                AI
              </div>
              <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-3">
                <span className="flex gap-1 items-center">
                  <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:0ms]" />
                  <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:150ms]" />
                  <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:300ms]" />
                </span>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Input area */}
      <div className="border-t border-gray-200 bg-gray-50 px-4 py-3">
        <div className="max-w-2xl mx-auto bg-white rounded-2xl border border-gray-200 shadow-sm px-4 pt-4 pb-3">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              isListening
                ? "正在聆聽..."
                : "輸入你的問題... (Enter 送出，Shift+Enter 換行)"
            }
            rows={1}
            className="w-full resize-none text-sm text-gray-800 placeholder-gray-400 focus:outline-none leading-relaxed max-h-64 overflow-y-auto"
            onInput={(e) => {
              const el = e.currentTarget;
              el.style.height = "auto";
              el.style.height = `${el.scrollHeight}px`;
            }}
          />

          {/* File chip */}
          {file && (
            <div className="mt-2">
              <span className="inline-flex items-center gap-1.5 text-xs bg-blue-50 text-blue-700 px-2.5 py-1 rounded-full">
                <PdfFileIcon />
                <span className="max-w-[240px] truncate">{file.name}</span>
                <button
                  onClick={() => setFile(null)}
                  className="ml-0.5 leading-none hover:text-blue-900"
                >
                  ×
                </button>
              </span>
            </div>
          )}

          <div className="flex items-center justify-between mt-2 pt-2 border-t border-gray-100">
            <div className="flex items-center gap-0.5">
              {/* File upload */}
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={loading}
                title="上傳保單 PDF"
                className="p-2 rounded-lg text-gray-400 hover:text-blue-700 hover:bg-blue-50 transition-colors disabled:opacity-40"
              >
                <PlusCircleIcon />
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,application/pdf"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) setFile(f);
                  e.target.value = "";
                }}
              />

              {/* Voice */}
              <button
                onClick={toggleVoice}
                title={isListening ? "停止錄音" : "語音輸入"}
                className={`p-2 rounded-lg transition-colors ${
                  isListening
                    ? "text-red-500 bg-red-50 animate-pulse"
                    : "text-gray-400 hover:text-blue-700 hover:bg-blue-50"
                }`}
              >
                <MicIcon />
              </button>
            </div>

            <button
              onClick={handleSend}
              disabled={!input.trim() || loading}
              className="flex items-center gap-1.5 px-4 py-2 bg-blue-700 text-white rounded-xl text-sm font-medium hover:bg-blue-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              送出
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function PlusCircleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="16" />
      <line x1="8" y1="12" x2="16" y2="12" />
    </svg>
  );
}
function PdfFileIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14,2 14,8 20,8" />
    </svg>
  );
}
function MicIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" y1="19" x2="12" y2="23" />
      <line x1="8" y1="23" x2="16" y2="23" />
    </svg>
  );
}
