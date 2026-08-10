"use client";

import { useEffect, useRef, useState } from "react";
import MarkdownContent from "./markdown-content";
import type { Message } from "./chat-app";

type SpeechRecognitionResultEvent = {
  results: {
    0: {
      0: {
        transcript: string;
      };
    };
  };
};

type SpeechRecognitionInstance = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: SpeechRecognitionResultEvent) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
  start: () => void;
  stop: () => void;
};

type SpeechRecognitionConstructor = new () => SpeechRecognitionInstance;
type SpeechWindow = Window &
  typeof globalThis & {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  };

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
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);

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
    const speechWindow = window as SpeechWindow;
    const SR = speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition;
    if (!SR) {
      alert("此瀏覽器不支援語音輸入，建議使用 Chrome 或 Edge。");
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
    recognition.onresult = (e) => {
      const transcript = e.results[0][0].transcript;
      setInput((prev) => (prev ? `${prev} ${transcript}` : transcript));
    };
    recognition.onend = () => setIsListening(false);
    recognition.onerror = () => setIsListening(false);
    recognition.start();
    recognitionRef.current = recognition;
    setIsListening(true);
  }

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="mx-auto flex max-w-5xl flex-col gap-4">
          {messages.map((msg, i) => (
            <div key={i} className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : "flex-row"}`}>
              {msg.role === "assistant" && (
                <div className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-teal-600 text-xs font-bold text-white">
                  AI
                </div>
              )}
              <div
                className={`max-w-[82%] rounded-3xl px-4 py-3 text-sm leading-7 shadow-sm ${
                  msg.role === "user"
                    ? "rounded-tr-md bg-slate-950 text-white"
                    : "rounded-tl-md border border-slate-200 bg-white text-slate-800"
                }`}
              >
                {msg.role === "user" ? msg.content : <MarkdownContent content={msg.content} />}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-teal-600 text-xs font-bold text-white">
                AI
              </div>
              <div className="rounded-3xl rounded-tl-md border border-slate-200 bg-white px-4 py-3 shadow-sm">
                <span className="flex items-center gap-1">
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:0ms]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:150ms]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:300ms]" />
                </span>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      <div className="border-t border-slate-200 bg-white/80 px-4 py-3 backdrop-blur">
        <p className="mx-auto mb-2 max-w-5xl text-center text-xs text-slate-400">
          AI 回覆僅供參考，實際投保、承保與理賠仍以保險公司條款與專業顧問說明為準。
        </p>
        <div className="mx-auto max-w-5xl rounded-3xl border border-slate-200 bg-white px-4 pb-3 pt-4 shadow-sm">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isListening ? "正在聆聽..." : "輸入問題，Enter 送出，Shift+Enter 換行"}
            rows={1}
            className="max-h-64 w-full resize-none overflow-y-auto text-sm leading-7 text-slate-800 placeholder:text-slate-400 focus:outline-none"
            onInput={(e) => {
              const el = e.currentTarget;
              el.style.height = "auto";
              el.style.height = `${el.scrollHeight}px`;
            }}
          />

          {file && (
            <div className="mt-2">
              <span className="inline-flex items-center gap-2 rounded-full bg-teal-50 px-3 py-1.5 text-xs font-medium text-teal-700">
                <PdfFileIcon />
                <span className="max-w-[240px] truncate">{file.name}</span>
                <button onClick={() => setFile(null)} className="font-bold hover:text-teal-900" title="移除檔案">
                  x
                </button>
              </span>
            </div>
          )}

          <div className="mt-2 flex items-center justify-between border-t border-slate-100 pt-2">
            <div className="flex items-center gap-1">
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={loading}
                title="上傳保單 PDF"
                className="rounded-xl p-2 text-slate-400 transition hover:bg-teal-50 hover:text-teal-700 disabled:opacity-40"
              >
                <PlusCircleIcon />
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,application/pdf"
                className="hidden"
                onChange={(e) => {
                  const nextFile = e.target.files?.[0];
                  if (nextFile) setFile(nextFile);
                  e.target.value = "";
                }}
              />

              <button
                onClick={toggleVoice}
                title={isListening ? "停止語音輸入" : "語音輸入"}
                className={`rounded-xl p-2 transition ${
                  isListening ? "animate-pulse bg-rose-50 text-rose-500" : "text-slate-400 hover:bg-teal-50 hover:text-teal-700"
                }`}
              >
                <MicIcon />
              </button>
            </div>

            <button
              onClick={handleSend}
              disabled={!input.trim() || loading}
              className="inline-flex items-center gap-2 rounded-xl bg-slate-950 px-5 py-2.5 text-sm font-bold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <SendIcon />
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

function SendIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
      <path d="M22 2L11 13" />
      <path d="M22 2L15 22L11 13L2 9L22 2Z" />
    </svg>
  );
}
