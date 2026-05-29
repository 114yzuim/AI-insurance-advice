"use client";

import { useState, useRef } from "react";

interface Props {
  onSend: (text: string, file?: File) => void;
  loading: boolean;
}

const SUGGESTIONS = [
  { icon: <ShieldIcon />, label: "保險觀念", prompt: "壽險和意外險有什麼差別？" },
  { icon: <DocIcon />, label: "保單解析", prompt: "怎麼看懂保單條款？" },
  { icon: <CheckIcon />, label: "需求評估", prompt: "我該如何評估自己需要哪些保障？" },
  { icon: <ClockIcon />, label: "理賠流程", prompt: "保險理賠的流程是什麼？" },
];

export default function ChatLanding({ onSend, loading }: Props) {
  const [input, setInput] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [isListening, setIsListening] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<any>(null);

  function handleSend(text?: string) {
    const msg = (text ?? input).trim();
    if (!msg || loading) return;
    onSend(msg, file ?? undefined);
    setInput("");
    setFile(null);
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
    <div className="flex flex-col flex-1 items-center justify-center px-4 bg-gray-50">
      <div className="mb-8 text-center">
        <h1 className="text-3xl font-semibold text-gray-800">
          有什麼保險問題，盡管問我
        </h1>
      </div>

      {/* Input box */}
      <div className="w-full max-w-2xl bg-white rounded-2xl border border-gray-200 shadow-sm px-4 pt-4 pb-3">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          placeholder={isListening ? "正在聆聽..." : "輸入你的問題... (Enter 送出)"}
          rows={3}
          className="w-full resize-none text-sm text-gray-800 placeholder-gray-400 focus:outline-none leading-relaxed"
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
              disabled={loading}
              title={isListening ? "停止錄音" : "語音輸入"}
              className={`p-2 rounded-lg transition-colors disabled:opacity-40 ${
                isListening
                  ? "text-red-500 bg-red-50 animate-pulse"
                  : "text-gray-400 hover:text-blue-700 hover:bg-blue-50"
              }`}
            >
              <MicIcon />
            </button>
          </div>

          <button
            onClick={() => handleSend()}
            disabled={!input.trim() || loading}
            className="flex items-center gap-1.5 px-4 py-2 bg-blue-700 text-white rounded-xl text-sm font-medium hover:bg-blue-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            <SendIcon />
            送出
          </button>
        </div>
      </div>

      {/* Suggestion chips */}
      <div className="flex flex-wrap gap-2 mt-5 justify-center max-w-lg">
        {SUGGESTIONS.map((s) => (
          <button
            key={s.label}
            onClick={() => handleSend(s.prompt)}
            disabled={loading}
            className="flex items-center gap-1.5 px-4 py-2 rounded-full border border-gray-200 bg-white text-sm text-gray-600 hover:bg-gray-50 hover:border-blue-200 hover:text-blue-700 disabled:opacity-40 transition-colors"
          >
            {s.icon}
            {s.label}
          </button>
        ))}
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
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
      <path d="M22 2L11 13" /><path d="M22 2L15 22L11 13L2 9L22 2Z" />
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
function ShieldIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}
function DocIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14,2 14,8 20,8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" />
    </svg>
  );
}
function CheckIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="9,11 12,14 22,4" />
      <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
    </svg>
  );
}
function ClockIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" /><polyline points="12,6 12,12 16,14" />
    </svg>
  );
}
