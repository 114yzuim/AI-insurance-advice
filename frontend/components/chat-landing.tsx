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
    title: "我的保障",
    description: "根據保單整理可用保障",
    prompt: "請根據我的保單資料，幫我整理目前有哪些保障可以使用。",
    icon: "shield",
    accent: "bg-teal-100 text-teal-700",
  },
  {
    title: "保單解讀",
    description: "整理條款重點與限制",
    prompt: "我想上傳保單 PDF，請幫我整理重點、限制與注意事項。",
    icon: "file",
    accent: "bg-sky-100 text-sky-700",
  },
  {
    title: "預算分配",
    description: "安排保費使用順序",
    prompt: "如果我每月保費預算有限，應該先安排哪些保障？",
    icon: "wallet",
    accent: "bg-amber-100 text-amber-700",
  },
  {
    title: "理賠準備",
    description: "確認流程與必備文件",
    prompt: "請告訴我申請理賠通常需要準備哪些文件與流程。",
    icon: "claim",
    accent: "bg-rose-100 text-rose-700",
  },
];

const SUMMARY_STEPS = [
  "讀取我的保單",
  "比對保障與條款",
  "整理下一步行動",
];

const TOPICS = ["醫療險", "失能險", "壽險", "保費預算", "除外責任", "理賠文件"];

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
      <div className="w-full px-4 py-6 sm:px-6 lg:px-8">
        <div className="mx-auto grid w-full max-w-[1360px] gap-5 xl:grid-cols-[minmax(0,1fr)_310px]">
          <section className="min-w-0">
            <div className="max-w-4xl">
              <p className="text-sm font-bold text-teal-700">AI 保險顧問</p>
              <h1 className="mt-3 text-3xl font-bold leading-tight text-slate-950 md:text-4xl xl:text-5xl">
                <span className="block">問我任何關於</span>
                <span className="block">我的保障的問題</span>
              </h1>
              <p className="mt-4 max-w-3xl text-base leading-7 text-slate-600">
                未來 AI 會讀取你的保單資料回答問題。現在可先上傳保單或描述需求，系統會整理條款重點與下一步。
              </p>
            </div>

            <div className="mt-6 rounded-[1.75rem] border border-slate-200 bg-white p-4 shadow-xl shadow-teal-100/70">
              <div className="rounded-[1.25rem] border border-slate-100 bg-slate-50/70 p-4">
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
                  className="max-h-56 min-h-32 w-full resize-none bg-transparent text-base leading-7 text-slate-800 placeholder:text-slate-400 focus:outline-none"
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

                <div className="mt-3 flex items-center justify-between border-t border-slate-200 pt-3">
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      disabled={loading}
                      title="上傳保單 PDF"
                      className="rounded-xl p-2 text-slate-500 transition hover:bg-white hover:text-teal-700 disabled:opacity-40"
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
                          : "text-slate-500 hover:bg-white hover:text-teal-700"
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
            </div>

            <div className="mt-5 grid gap-3 sm:grid-cols-2 2xl:grid-cols-4">
              {TASKS.map((task) => (
                <button
                  key={task.title}
                  onClick={() => handleSend(task.prompt)}
                  disabled={loading}
                  className="group flex min-h-28 items-start gap-3 rounded-3xl border border-slate-200 bg-white p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-teal-200 hover:shadow-md disabled:opacity-40"
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
          </section>

          <aside className="min-w-0">
            <div className="rounded-[1.75rem] border border-slate-200 bg-white p-4 shadow-sm xl:sticky xl:top-24">
              <section>
                <div className="flex items-center justify-between gap-3">
                  <h2 className="text-sm font-bold text-slate-950">使用流程</h2>
                  <span className="rounded-full bg-teal-50 px-2.5 py-1 text-xs font-bold text-teal-700">
                    3 步
                  </span>
                </div>
                <div className="mt-3 space-y-2.5">
                  {SUMMARY_STEPS.map((step, index) => (
                    <div key={step} className="flex items-center gap-2.5">
                      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-teal-50 text-xs font-bold text-teal-700">
                        {index + 1}
                      </span>
                      <span className="text-sm font-medium leading-5 text-slate-600">{step}</span>
                    </div>
                  ))}
                </div>
              </section>

              <div className="my-4 h-px bg-slate-100" />

              <section>
                <h2 className="text-sm font-bold text-slate-950">常見問題方向</h2>
                <div className="mt-3 flex flex-wrap gap-2">
                  {TOPICS.map((topic) => (
                    <span key={topic} className="rounded-full bg-slate-100 px-3 py-1.5 text-sm font-medium text-slate-600">
                      {topic}
                    </span>
                  ))}
                </div>
              </section>
            </div>
          </aside>
        </div>
      </div>
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
