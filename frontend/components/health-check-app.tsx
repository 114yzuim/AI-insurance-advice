"use client";

import { useState, useEffect } from "react";
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  ResponsiveContainer, Tooltip,
} from "recharts";
import HealthCheckSidebar from "./health-check-sidebar";

// ─── Types ────────────────────────────────────────────────────────────────────

interface RecommendationItem {
  key: string;
  priority: number;
  amount: number;
  unit: string;
  premium_range: string;
  monthly_premium_mid: number;
  within_budget: boolean;
  reason: string;
}

interface ProductCard {
  product_id: string;
  product_name: string;
  company: string;
  category: string;
  source_url: string;
}

interface MemberResult {
  name: string;
  items: RecommendationItem[];
  budget_note: string;
  summary: string;
  recommended_products: ProductCard[];
}

interface MemberInput {
  name: string;
  answers: Record<string, string>;
}

interface MemberProfile {
  id: string;
  name: string;
  answers: Record<string, string>;
  result: MemberResult;
}

export interface CustomerProfile {
  id: string;
  name: string;
  createdAt: number;
  totalMembers: number;
  familySummary: string;
  members: MemberProfile[];
}

// ─── Constants ────────────────────────────────────────────────────────────────

const STORAGE_KEY = "insurance_customer_profiles";

const QUESTIONS = [
  { id: "age",      question: "幾歲？",                   options: ["20–30 歲", "31–40 歲", "41–50 歲", "51 歲以上"] },
  { id: "marital",  question: "婚姻狀況？",               options: ["單身", "已婚 / 有伴侶"] },
  { id: "children", question: "有需要扶養的小孩嗎？",     options: ["沒有", "1 個", "2 個以上"] },
  { id: "income",   question: "每月收入大約是多少？",     options: ["3 萬以下", "3–5 萬", "5–10 萬", "10 萬以上"] },
  { id: "job",      question: "工作性質？",               options: ["辦公室 / 內勤", "需外出或現場作業", "高危險行業（工地、高空、漁業等）"] },
  { id: "debt",     question: "目前有房貸或重大債務嗎？", options: ["有", "沒有"] },
  { id: "health",   question: "健康狀況如何？",           options: ["良好", "有慢性病或特定病史"] },
  { id: "budget",   question: "每月能用於保險的預算？",   options: ["1,000 元以下", "1,000–2,000 元", "2,000–4,000 元", "4,000 元以上"] },
];

const KEY_LABEL: Record<string, string> = {
  accident_coverage:  "意外險",
  medical_daily:      "醫療日額",
  disability_monthly: "失能保障",
  cancer_coverage:    "癌症險",
  life_coverage:      "壽險",
};

// ─── Root ─────────────────────────────────────────────────────────────────────

type Phase = "browse" | "setup" | "questionnaire" | "assessing";

export default function HealthCheckApp() {
  const [profiles, setProfiles] = useState<CustomerProfile[]>([]);
  const [currentProfileId, setCurrentProfileId] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>("browse");
  const [draftName, setDraftName] = useState("");
  const [draftTotal, setDraftTotal] = useState(1);
  const [draftInputs, setDraftInputs] = useState<MemberInput[]>([]);  // collected answers, no results yet
  const [assessError, setAssessError] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(true);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) setProfiles(JSON.parse(raw));
    } catch {}
  }, []);

  useEffect(() => {
    if (profiles.length > 0) localStorage.setItem(STORAGE_KEY, JSON.stringify(profiles));
  }, [profiles]);

  function startSetup() {
    setPhase("setup");
    setCurrentProfileId(null);
    setDraftInputs([]);
    setAssessError("");
  }

  function handleSetupConfirm(name: string, total: number) {
    setDraftName(name || "顧客資料");
    setDraftTotal(total);
    setDraftInputs([]);
    setPhase("questionnaire");
  }

  async function handleMemberDone(input: MemberInput) {
    const allInputs = [...draftInputs, input];

    if (allInputs.length < draftTotal) {
      setDraftInputs(allInputs);
      return;
    }

    // All members filled — submit all at once
    setPhase("assessing");
    setAssessError("");

    try {
      const res = await fetch("/api/needs-assessment", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ members: allInputs }),
      });
      if (!res.ok) throw new Error();
      const data = await res.json();

      const members: MemberProfile[] = allInputs.map((inp, i) => ({
        id: `${Date.now()}-${i}`,
        name: inp.name,
        answers: inp.answers,
        result: data.members[i] ?? {
          name: inp.name, items: [], budget_note: "", summary: "", recommended_products: [],
        },
      }));

      const profile: CustomerProfile = {
        id: Date.now().toString(),
        name: draftName,
        createdAt: Date.now(),
        totalMembers: draftTotal,
        familySummary: data.family_summary ?? "",
        members,
      };

      setProfiles((prev) => [profile, ...prev]);
      setCurrentProfileId(profile.id);
      setPhase("browse");
      setDraftInputs([]);
    } catch {
      setAssessError("評估失敗，請確認後端已啟動並重試。");
      setDraftInputs(allInputs);  // preserve filled data
      setPhase("questionnaire");  // go back so user can retry
    }
  }

  function handleDelete(id: string) {
    const updated = profiles.filter((p) => p.id !== id);
    setProfiles(updated);
    if (updated.length === 0) localStorage.removeItem(STORAGE_KEY);
    if (currentProfileId === id) { setCurrentProfileId(null); setPhase("browse"); }
  }

  function handleRename(id: string, name: string) {
    setProfiles((prev) => prev.map((p) => (p.id === id ? { ...p, name } : p)));
  }

  const currentProfile = profiles.find((p) => p.id === currentProfileId);

  const mainContent = (() => {
    if (phase === "setup") {
      return <SetupView onConfirm={handleSetupConfirm} onCancel={() => setPhase("browse")} />;
    }
    if (phase === "assessing") {
      return <AssessingView memberCount={draftTotal} />;
    }
    if (phase === "questionnaire") {
      return (
        <QuestionnaireView
          key={draftInputs.length}   // remount on each member to reset internal state
          memberIndex={draftInputs.length}
          totalMembers={draftTotal}
          error={assessError}
          onMemberDone={handleMemberDone}
        />
      );
    }
    if (currentProfile) {
      return <ProfileResultView profile={currentProfile} onNew={startSetup} />;
    }
    return <WelcomeView onNew={startSetup} />;
  })();

  return (
    <div className="flex h-full overflow-hidden bg-gray-50">
      <HealthCheckSidebar
        profiles={profiles}
        currentId={currentProfileId}
        open={sidebarOpen}
        onNew={startSetup}
        onSelect={(id) => { setCurrentProfileId(id); setPhase("browse"); }}
        onDelete={handleDelete}
        onRename={handleRename}
        onToggle={() => setSidebarOpen((v) => !v)}
      />
      <div className="flex-1 min-w-0 overflow-y-auto">{mainContent}</div>
    </div>
  );
}

// ─── Welcome ──────────────────────────────────────────────────────────────────

function WelcomeView({ onNew }: { onNew: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center px-6 py-12">
      <div className="w-16 h-16 bg-blue-100 rounded-2xl flex items-center justify-center mb-5">
        <ClipboardIcon />
      </div>
      <h1 className="text-xl font-semibold text-gray-800 mb-2">保障需求評估</h1>
      <p className="text-sm text-gray-500 max-w-xs leading-relaxed mb-6">
        建立顧客資料，填完所有成員問卷後，AI 一次分析整個家庭的保障需求
      </p>
      <button
        onClick={onNew}
        className="px-6 py-2.5 bg-blue-700 text-white rounded-xl text-sm font-medium hover:bg-blue-800 transition-colors"
      >
        建立顧客資料
      </button>
    </div>
  );
}

// ─── Setup ────────────────────────────────────────────────────────────────────

function SetupView({
  onConfirm,
  onCancel,
}: {
  onConfirm: (name: string, total: number) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState("");
  const [count, setCount] = useState(1);

  return (
    <div className="max-w-md mx-auto px-4 py-12">
      <div className="mb-8 text-center">
        <h1 className="text-2xl font-semibold text-gray-800 mb-1">建立顧客資料</h1>
        <p className="text-sm text-gray-400">填完所有成員問卷後，AI 一次評估整個家庭</p>
      </div>

      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 flex flex-col gap-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">資料名稱(個人、家庭)</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="例如：我的家庭、王先生"
            className="w-full px-4 py-2.5 rounded-xl border border-gray-200 text-sm text-gray-800 focus:outline-none focus:border-blue-400 placeholder-gray-300"
          />
        </div>

        <div>
          <p className="text-sm font-medium text-gray-700 mb-3">這次要評估幾個人？</p>
          <div className="flex gap-2">
            {[1, 2, 3, 4].map((n) => (
              <button
                key={n}
                onClick={() => setCount(n)}
                className={`flex-1 py-2.5 rounded-xl border text-sm font-medium transition-colors ${
                  count === n
                    ? "bg-blue-700 text-white border-blue-700"
                    : "border-gray-200 text-gray-600 hover:border-blue-300 hover:text-blue-700"
                }`}
              >
                {n} 人
              </button>
            ))}
          </div>
        </div>

        <button
          onClick={() => onConfirm(name, count)}
          className="w-full py-3 bg-blue-700 text-white rounded-xl font-medium text-sm hover:bg-blue-800 transition-colors"
        >
          開始填問卷
        </button>
      </div>

      <button onClick={onCancel} className="mt-4 w-full text-sm text-gray-400 hover:text-gray-600 text-center">
        取消
      </button>
    </div>
  );
}

// ─── Assessing ────────────────────────────────────────────────────────────────

function AssessingView({ memberCount }: { memberCount: number }) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4 text-gray-500 px-4 text-center">
      <SpinnerIcon />
      <p className="text-base font-medium text-gray-700">
        正在評估 {memberCount} 位成員的保障需求…
      </p>
      <p className="text-sm text-gray-400">考慮家庭脈絡進行分析，約需 10–20 秒</p>
    </div>
  );
}

// ─── Questionnaire ────────────────────────────────────────────────────────────

function QuestionnaireView({
  memberIndex,
  totalMembers,
  error,
  onMemberDone,
}: {
  memberIndex: number;
  totalMembers: number;
  error: string;
  onMemberDone: (input: MemberInput) => void;
}) {
  const [nameStep, setNameStep] = useState(true);
  const [memberName, setMemberName] = useState("");
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});

  const defaultName =
    memberIndex === 0 ? "本人" : (["配偶", "小孩", "父母"][memberIndex - 1] ?? `成員 ${memberIndex + 1}`);

  function handleOption(option: string) {
    const q = QUESTIONS[step];
    const next = { ...answers, [q.id]: option };
    setAnswers(next);

    if (step < QUESTIONS.length - 1) {
      setStep(step + 1);
      return;
    }

    // Last question — hand off to parent (no API call here)
    onMemberDone({ name: memberName || defaultName, answers: next });
  }

  if (nameStep) {
    return (
      <div className="max-w-xl mx-auto px-4 py-12">
        <div className="mb-8 text-center">
          <p className="text-xs text-blue-600 font-medium mb-1">
            第 {memberIndex + 1} 位 / 共 {totalMembers} 位
          </p>
          <h1 className="text-2xl font-semibold text-gray-800 mb-1">請輸入姓名或關係</h1>
          <p className="text-sm text-gray-400">方便之後區分各人的評估結果</p>
        </div>
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6">
          <input
            autoFocus
            value={memberName}
            onChange={(e) => setMemberName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") { setMemberName((v) => v.trim() || defaultName); setNameStep(false); }
            }}
            placeholder={defaultName}
            className="w-full px-4 py-3 rounded-xl border border-gray-200 text-sm text-gray-800 focus:outline-none focus:border-blue-400 placeholder-gray-300 mb-4"
          />
          <button
            onClick={() => { setMemberName((v) => v.trim() || defaultName); setNameStep(false); }}
            className="w-full py-3 bg-blue-700 text-white rounded-xl font-medium text-sm hover:bg-blue-800 transition-colors"
          >
            下一步
          </button>
        </div>
        {error && <p className="mt-4 text-sm text-red-500 text-center">{error}</p>}
      </div>
    );
  }

  const q = QUESTIONS[step];
  const isLastMember = memberIndex === totalMembers - 1;
  const isLastQuestion = step === QUESTIONS.length - 1;
  const progress = Math.round((step / QUESTIONS.length) * 100);

  return (
    <div className="max-w-xl mx-auto px-4 py-12">
      <div className="mb-8 text-center">
        <p className="text-xs text-blue-600 font-medium mb-1">
          {memberName}・第 {memberIndex + 1} 位 / 共 {totalMembers} 位
        </p>
        <h1 className="text-2xl font-semibold text-gray-800 mb-1">保障需求評估</h1>
        {isLastMember && isLastQuestion && (
          <p className="text-xs text-amber-600 mt-1">填完後將送出所有成員資料進行評估</p>
        )}
      </div>

      <div className="mb-6">
        <div className="flex justify-between text-xs text-gray-400 mb-1.5">
          <span>第 {step + 1} / {QUESTIONS.length} 題</span>
          <span>{progress}%</span>
        </div>
        <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
          <div
            className="h-full bg-blue-600 rounded-full transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6">
        <p className="text-base font-medium text-gray-800 mb-5">{q.question}</p>
        <div className="flex flex-col gap-2.5">
          {q.options.map((opt) => (
            <button
              key={opt}
              onClick={() => handleOption(opt)}
              className="w-full text-left px-4 py-3 rounded-xl border border-gray-200 text-sm text-gray-700 hover:border-blue-400 hover:bg-blue-50 hover:text-blue-700 transition-colors"
            >
              {opt}
            </button>
          ))}
        </div>
      </div>

      {step > 0 && (
        <button
          onClick={() => setStep(step - 1)}
          className="mt-4 text-sm text-gray-400 hover:text-gray-600 flex items-center gap-1"
        >
          <ChevronLeftIcon /> 上一題
        </button>
      )}
    </div>
  );
}

// ─── Profile Result ───────────────────────────────────────────────────────────

function ProfileResultView({
  profile,
  onNew,
}: {
  profile: CustomerProfile;
  onNew: () => void;
}) {
  const [activeMember, setActiveMember] = useState(0);
  const member = profile.members[activeMember];

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-xl font-semibold text-gray-800">{profile.name}</h1>
          <p className="text-xs text-gray-400 mt-0.5">
            {profile.members.length} 人・{new Date(profile.createdAt).toLocaleDateString("zh-TW")}
          </p>
        </div>
        <button
          onClick={onNew}
          className="flex items-center gap-1.5 px-4 py-2 bg-blue-700 text-white rounded-xl text-sm font-medium hover:bg-blue-800 transition-colors"
        >
          <PlusSmIcon /> 建立新資料
        </button>
      </div>

      {/* Family summary */}
      {profile.familySummary && (
        <div className="bg-blue-50 border border-blue-200 rounded-2xl p-4 mb-5 text-sm text-blue-900 leading-relaxed">
          <span className="font-medium">家庭整體摘要：</span>{profile.familySummary}
        </div>
      )}

      {/* Member tabs */}
      {profile.members.length > 1 && (
        <div className="flex gap-2 mb-5 overflow-x-auto pb-1">
          {profile.members.map((m, i) => (
            <button
              key={m.id}
              onClick={() => setActiveMember(i)}
              className={`shrink-0 px-4 py-2 rounded-xl text-sm font-medium border transition-colors ${
                i === activeMember
                  ? "bg-blue-700 text-white border-blue-700"
                  : "border-gray-200 text-gray-600 hover:border-blue-300"
              }`}
            >
              {m.name}
            </button>
          ))}
        </div>
      )}

      {member && <MemberResultSection member={member} disclaimer={""} />}

      <p className="text-xs text-gray-400 text-center mt-4">
        本服務提供資訊參考，非正式保險建議，請諮詢合格業務員。
      </p>
    </div>
  );
}

function MemberResultSection({ member, disclaimer }: { member: MemberProfile; disclaimer: string }) {
  const { result } = member;
  const inBudget = result.items.filter((i) => i.within_budget);
  const deferred = result.items.filter((i) => !i.within_budget);
  const radarData = result.items.map((item) => ({
    subject: KEY_LABEL[item.key] ?? item.key,
    每月保費: item.monthly_premium_mid,
  }));

  return (
    <div className="flex flex-col gap-4">
      <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 text-sm text-amber-900 leading-relaxed">
        <span className="font-medium">摘要：</span>{result.summary}
      </div>

      <div className="bg-gray-50 border border-gray-200 rounded-2xl p-4 text-sm text-gray-700 leading-relaxed">
        <span className="font-medium">預算規劃：</span>{result.budget_note}
      </div>

      {inBudget.length > 0 && (
        <div>
          <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">在預算內，建議優先投保</h2>
          <div className="flex flex-col gap-2.5">
            {inBudget.map((item) => <PriorityCard key={item.key} item={item} highlighted />)}
          </div>
        </div>
      )}

      {deferred.length > 0 && (
        <div>
          <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">預算充裕後再補足</h2>
          <div className="flex flex-col gap-2.5">
            {deferred.map((item) => <PriorityCard key={item.key} item={item} highlighted={false} />)}
          </div>
        </div>
      )}

      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6">
        <h2 className="text-sm font-medium text-gray-500 mb-4">每月保費分配（元/月）</h2>
        <div style={{ height: "16rem" }}>
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={radarData}>
              <PolarGrid />
              <PolarAngleAxis dataKey="subject" tick={{ fontSize: 12 }} />
              <Radar name="每月保費" dataKey="每月保費" stroke="#1d4ed8" fill="#3b82f6" fillOpacity={0.3} />
              <Tooltip formatter={(val) => `${Number(val ?? 0).toLocaleString()} 元/月`} />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {result.recommended_products?.length > 0 && (
        <ProductRecommendations products={result.recommended_products} />
      )}

      {disclaimer && <p className="text-xs text-gray-400 text-center">{disclaimer}</p>}
    </div>
  );
}

function ProductRecommendations({ products }: { products: ProductCard[] }) {
  return (
    <div className="bg-green-50 border border-green-200 rounded-2xl p-4">
      <div className="flex items-center gap-2 mb-3">
        <StarIcon />
        <h2 className="text-sm font-semibold text-green-800">資料庫推薦商品</h2>
      </div>
      <p className="text-xs text-green-700 mb-3">根據此成員的需求評估，以下商品可能值得了解（僅供參考）</p>
      <div className="flex flex-col gap-2.5">
        {products.map((p) => (
          <div key={p.product_id} className="bg-white rounded-xl border border-green-100 px-4 py-3 flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="text-sm font-medium text-gray-800 truncate">{p.product_name}</p>
              <p className="text-xs text-gray-500 mt-0.5">{p.company}・{p.category}</p>
            </div>
            {p.source_url && (
              <a href={p.source_url} target="_blank" rel="noopener noreferrer" className="shrink-0 text-xs text-blue-600 hover:text-blue-800 font-medium">
                查看 →
              </a>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function PriorityCard({ item, highlighted }: { item: RecommendationItem; highlighted: boolean }) {
  return (
    <div className={`rounded-xl border p-4 ${highlighted ? "bg-white border-blue-200 border-l-4 border-l-blue-500" : "bg-gray-50 border-gray-200"}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <span className={`shrink-0 w-6 h-6 rounded-full text-xs font-bold flex items-center justify-center ${highlighted ? "bg-blue-600 text-white" : "bg-gray-300 text-gray-600"}`}>
            {item.priority}
          </span>
          <div className="min-w-0">
            <span className="text-sm font-medium text-gray-800">{KEY_LABEL[item.key] ?? item.key}</span>
            <p className="text-xs text-gray-500 mt-0.5 leading-relaxed">{item.reason}</p>
          </div>
        </div>
        <div className="shrink-0 text-right">
          <p className="text-sm font-semibold text-gray-800">{item.amount.toLocaleString()} {item.unit}</p>
          <p className="text-xs text-gray-400 mt-0.5">{item.premium_range}</p>
        </div>
      </div>
    </div>
  );
}

// ─── Icons ────────────────────────────────────────────────────────────────────

function SpinnerIcon() {
  return (
    <svg className="animate-spin text-blue-600" width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
    </svg>
  );
}
function PlusSmIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
      <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}
function ChevronLeftIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="15,18 9,12 15,6" />
    </svg>
  );
}
function ClipboardIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="1.8">
      <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
      <rect x="8" y="2" width="8" height="4" rx="1" ry="1" />
    </svg>
  );
}
function StarIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2.5">
      <polygon points="12,2 15.09,8.26 22,9.27 17,14.14 18.18,21.02 12,17.77 5.82,21.02 7,14.14 2,9.27 8.91,8.26" />
    </svg>
  );
}
