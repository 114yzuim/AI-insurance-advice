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

type TaskCard = {
  title: string;
  description: string;
  prompt: string;
  icon: "shield" | "file" | "wallet" | "claim";
  accent: string;
};

const TASKS: TaskCard[] = [
  {
    title: "保障盤點",
    description: "用年齡、家庭與工作狀況，找出優先補強項目。",
    prompt: "請用白話幫我評估目前最需要補強哪些保險保障。",
    icon: "shield",
    accent: "bg-teal-100 text-teal-700",
  },
  {
    title: "保單解讀",
    description: "上傳 PDF 後，整理條款重點、限制與注意事項。",
    prompt: "我想上傳保單 PDF，請幫我整理重點、限制與注意事項。",
    icon: "file",
    accent: "bg-sky-100 text-sky-700",
  },
  {
    title: "預算分配",
    description: "把有限保費拆成醫療、意外、失能與壽險順序。",
    prompt: "如果我每月保費預算有限，應該先安排哪些保障？",
    icon: "wallet",
    accent: "bg-amber-100 text-amber-700",
  },
  {
    title: "理賠準備",
    description: "釐清情境、可能適用保障，以及應準備的文件。",
    prompt: "請告訴我申請理賠通常需要準備哪些文件與流程。",
    icon: "claim",
    accent: "bg-rose-100 text-rose-700",
  },
];

const SUMMARY_STEPS = [
  "描述問題或上傳保單",
  "AI 先整理重點與疑問",
  "依照風險與預算排下一步",
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
    <div className="flex flex-1 overflow-y-auto bg-[#f7faf8]">
      <div className="w-full px-4 py-6 sm:px-6 lg:px-8 xl:px-10">
        <div className="mx-auto grid w-full max-w-[1540px] gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
          <section className="min-w-0">
            <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
              <div className="min-w-0">
                <p className="text-sm font-bold text-teal-700">AI 保險諮詢</p>
                <h1 className="mt-3 max-w-4xl text-3xl font-bold leading-tight text-slate-950 md:text-4xl xl:text-5xl">
                  <span className="block">把保險問題說出來</span>
                  <span className="block">我幫你整理下一步</span>
                </h1>
                <p className="mt-4 max-w-3xl text-base leading-7 text-slate-600">
                  適合用來問保障缺口、看懂保單、整理預算分配，也可以先把理賠情境講清楚。
                </p>
              </div>

              <div className="rounded-3xl border border-teal-100 bg-white p-4 shadow-sm">
                <p className="text-sm font-bold text-slate-900">使用流程</p>
                <div className="mt-4 space-y-3">
                  {SUMMARY_STEPS.map((step, index) => (
                    <div key={step} className="flex items-center gap-3">
                      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-teal-50 text-xs font-bold text-teal-700">
                        {index + 1}
                      </span>
                      <span className="text-sm font-medium text-slate-600">{step}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="mt-6 grid gap-5 2xl:grid-cols-[minmax(0,1fr)_390px]">
              <div className="rounded-[2rem] border border-slate-200 bg-white p-4 shadow-xl shadow-teal-100/70">
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
                  rows={7}
                  className="max-h-72 min-h-44 w-full resize-none text-base leading-7 text-slate-800 placeholder:text-slate-400 focus:outline-none"
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

              <div className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-1">
                {TASKS.map((task) => (
                  <button
                    key={task.title}
                    onClick={() => handleSend(task.prompt)}
                    disabled={loading}
                    className="group flex min-h-32 items-start gap-3 rounded-3xl border border-slate-200 bg-white p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-teal-200 hover:shadow-md disabled:opacity-40"
                  >
                    <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl ${task.accent}`}>
                      <TaskIcon name={task.icon} />
                    </span>
                    <span className="min-w-0">
                      <span className="block text-base font-bold text-slate-950">{task.title}</span>
                      <span className="mt-1 block text-sm leading-6 text-slate-500">{task.description}</span>
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </section>

          <aside className="hidden xl:flex min-w-0 flex-col gap-4">
            <div className="rounded-[2rem] bg-slate-950 p-5 text-white shadow-xl shadow-slate-200">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-bold text-teal-200">諮詢後會整理成</p>
                  <h2 className="mt-1 text-2xl font-bold">清楚的保障路徑</h2>
                </div>
                <span className="rounded-2xl bg-teal-400 px-3 py-2 text-sm font-bold text-slate-950">AI</span>
              </div>

              <div className="mt-6 grid grid-cols-3 gap-2">
                <VisualBar label="問題" height="h-20" color="bg-teal-300" />
                <VisualBar label="缺口" height="h-28" color="bg-amber-300" />
                <VisualBar label="行動" height="h-16" color="bg-sky-300" />
              </div>

              <div className="mt-6 space-y-3">
                {["風險排序", "條款重點", "預算提醒"].map((item) => (
                  <div key={item} className="flex items-center justify-between rounded-2xl bg-white/10 px-4 py-3">
                    <span className="text-sm font-medium text-slate-100">{item}</span>
                    <CheckIcon />
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-[2rem] border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-sm font-bold text-slate-900">常見問題方向</p>
              <div className="mt-4 flex flex-wrap gap-2">
                {["醫療險", "失能險", "壽險", "保費預算", "除外責任", "理賠文件"].map((topic) => (
                  <span key={topic} className="rounded-full bg-slate-100 px-3 py-1.5 text-sm font-medium text-slate-600">
                    {topic}
                  </span>
                ))}
              </div>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}

function VisualBar({ label, height, color }: { label: string; height: string; color: string }) {
  return (
    <div className="flex flex-col justify-end rounded-2xl bg-white/10 p-2">
      <div className={`rounded-xl ${height} ${color}`} />
      <p className="mt-2 text-center text-xs font-bold text-slate-200">{label}</p>
    </div>
  );
}

function TaskIcon({ name }: { name: TaskCard["icon"] }) {
  if (name === "file") return <FileIcon />;
  if (name === "wallet") return <WalletIcon />;
  if (name === "claim") return <ClaimIcon />;
  return <ShieldIcon />;
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

function ShieldIcon() {
  return (
    <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}

function FileIcon() {
  return (
    <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14,2 14,8 20,8" />
      <line x1="8" y1="13" x2="16" y2="13" />
      <line x1="8" y1="17" x2="14" y2="17" />
    </svg>
  );
}

function WalletIcon() {
  return (
    <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M20 7H5a2 2 0 0 1 0-4h13" />
      <path d="M20 7v14H4a2 2 0 0 1-2-2V5" />
      <path d="M16 13h4" />
    </svg>
  );
}

function ClaimIcon() {
  return (
    <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M9 11l3 3L22 4" />
      <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="text-teal-300">
      <polyline points="20,6 9,17 4,12" />
    </svg>
  );
}
