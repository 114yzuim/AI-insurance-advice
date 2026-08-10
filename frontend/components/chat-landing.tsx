"use client";

import { useRef, useState } from "react";

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
  onSend: (text: string, file?: File) => void;
  loading: boolean;
}

const SUGGESTIONS = [
  { label: "我需要哪些保障？", prompt: "請用白話幫我評估目前最需要補強哪些保險保障。" },
  { label: "幫我看保單", prompt: "我想上傳保單 PDF，請幫我整理重點、限制與注意事項。" },
  { label: "預算怎麼分配？", prompt: "如果我每月保費預算有限，應該先安排哪些保障？" },
  { label: "理賠要準備什麼？", prompt: "請告訴我申請理賠通常需要準備哪些文件與流程。" },
];

export default function ChatLanding({ onSend, loading }: Props) {
  const [input, setInput] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [isListening, setIsListening] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);

  function handleSend(text?: string) {
    const msg = (text ?? input).trim();
    if (!msg || loading) return;
    onSend(msg, file ?? undefined);
    setInput("");
    setFile(null);
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
    <div className="flex flex-1 flex-col items-center justify-center bg-[#f7faf8] px-4 py-10">
      <div className="mb-7 max-w-2xl text-center">
        <p className="mb-3 text-sm font-bold text-teal-700">AI 保險諮詢</p>
        <h1 className="text-3xl font-bold leading-tight text-slate-950 md:text-4xl">
          把保險問題說出來，我幫你整理成下一步
        </h1>
      </div>

      <div className="w-full max-w-2xl rounded-3xl border border-slate-200 bg-white p-4 shadow-xl shadow-teal-100/70">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          placeholder={isListening ? "正在聆聽..." : "輸入你的保險問題，或上傳 PDF 保單..."}
          rows={4}
          className="max-h-56 w-full resize-none text-base leading-7 text-slate-800 placeholder:text-slate-400 focus:outline-none"
          onInput={(e) => {
            const el = e.currentTarget;
            el.style.height = "auto";
            el.style.height = `${el.scrollHeight}px`;
          }}
        />

        {file && (
          <div className="mt-2">
            <span className="inline-flex items-center gap-2 rounded-full bg-teal-50 px-3 py-1.5 text-sm font-medium text-teal-700">
              <PdfFileIcon />
              <span className="max-w-[240px] truncate">{file.name}</span>
              <button onClick={() => setFile(null)} className="font-bold hover:text-teal-900" title="移除檔案">
                x
              </button>
            </span>
          </div>
        )}

        <div className="mt-3 flex items-center justify-between border-t border-slate-100 pt-3">
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
              disabled={loading}
              title={isListening ? "停止語音輸入" : "語音輸入"}
              className={`rounded-xl p-2 transition disabled:opacity-40 ${
                isListening
                  ? "animate-pulse bg-rose-50 text-rose-500"
                  : "text-slate-400 hover:bg-teal-50 hover:text-teal-700"
              }`}
            >
              <MicIcon />
            </button>
          </div>

          <button
            onClick={() => handleSend()}
            disabled={!input.trim() || loading}
            className="inline-flex items-center gap-2 rounded-xl bg-slate-950 px-5 py-2.5 text-sm font-bold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <SendIcon />
            送出
          </button>
        </div>
      </div>

      <div className="mt-5 flex max-w-2xl flex-wrap justify-center gap-2">
        {SUGGESTIONS.map((suggestion) => (
          <button
            key={suggestion.label}
            onClick={() => handleSend(suggestion.prompt)}
            disabled={loading}
            className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-600 transition hover:border-teal-300 hover:text-teal-700 disabled:opacity-40"
          >
            {suggestion.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function PlusCircleIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="16" />
      <line x1="8" y1="12" x2="16" y2="12" />
    </svg>
  );
}

function MicIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
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

function PdfFileIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14,2 14,8 20,8" />
    </svg>
  );
}
