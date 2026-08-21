"use client";

import { useState, useEffect } from "react";
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  ResponsiveContainer, Tooltip,
} from "recharts";
import HealthCheckSidebar from "./health-check-sidebar";
import {
  COVERAGE_LABELS,
  COVERAGE_ORDER,
  fetchPolicyPortfolio,
  formatCoverage,
  getPolicySummary,
  type CoverageKey,
  type PolicySummary,
} from "@/lib/demo-policies";

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

const RECOMMENDATION_TO_COVERAGE: Record<string, CoverageKey> = {
  accident_coverage: "accident",
  medical_daily: "daily",
  disability_monthly: "ltc",
  cancer_coverage: "cancer",
  life_coverage: "life",
};

const DEFAULT_POLICY_SUMMARY = getPolicySummary();

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
  const [policySummary, setPolicySummary] = useState<PolicySummary>(DEFAULT_POLICY_SUMMARY);

  useEffect(() => {
    queueMicrotask(() => {
      try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (raw) setProfiles(JSON.parse(raw));
      } catch {}
    });
  }, []);

  useEffect(() => {
    if (profiles.length > 0) localStorage.setItem(STORAGE_KEY, JSON.stringify(profiles));
  }, [profiles]);

  useEffect(() => {
    let mounted = true;
    fetchPolicyPortfolio()
      .then((data) => {
        if (mounted) setPolicySummary(data.summary);
      })
      .catch(() => {
        if (mounted) setPolicySummary(DEFAULT_POLICY_SUMMARY);
      });
    return () => {
      mounted = false;
    };
  }, []);

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
      return <ProfileResultView profile={currentProfile} policySummary={policySummary} onNew={startSetup} />;
    }
    return <WelcomeView policySummary={policySummary} onNew={startSetup} />;
  })();

  return (
    <div className="flex h-full overflow-hidden bg-[#f7faf8]">
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

function WelcomeView({ policySummary, onNew }: { policySummary: PolicySummary; onNew: () => void }) {
  return (
    <div className="mx-auto max-w-6xl px-5 py-8 md:px-8">
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <section className="rounded-[2rem] bg-white p-6 shadow-xl shadow-teal-100/70 ring-1 ring-slate-100 md:p-8">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-teal-50 text-teal-700">
            <ClipboardIcon />
          </div>
          <p className="mt-6 text-sm font-bold text-teal-700">保障健診</p>
          <h1 className="mt-2 max-w-2xl text-3xl font-bold leading-tight text-slate-950 md:text-5xl">
            <span className="block">先看現有保障</span>
            <span className="block">再算真正缺口</span>
          </h1>
          <p className="mt-4 max-w-2xl text-base leading-7 text-slate-600">
            後續會從我的保單自動彙整身故、癌症、重大傷病、醫療、意外與長照保障，再結合家庭責任與預算評估缺口。
          </p>
          <button
            onClick={onNew}
            className="mt-7 rounded-xl bg-slate-950 px-6 py-3 text-sm font-bold text-white shadow-lg shadow-slate-200 transition hover:bg-slate-800"
          >
            開始保障健診
          </button>
        </section>

        <aside className="rounded-[2rem] border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-sm font-bold text-slate-950">健診會看哪些面向</h2>
          <div className="mt-4 space-y-3">
            <GuideCard title="既有保障" text="從已建立保單彙整各類保障額度。" />
            <GuideCard title="家庭責任" text="婚姻、扶養人數、房貸與重大債務。" />
            <GuideCard title="缺口排序" text="依收入、預算與風險排出補強順序。" />
          </div>
        </aside>
      </div>
      <div className="mt-6 grid gap-3 md:grid-cols-3">
        <GuideCard title="1. 匯入保單" text="建立每位家庭成員的 Insurance Profile。" />
        <GuideCard title="2. 補充需求" text="整理收入、責任、健康與預算。" />
        <GuideCard title="3. 產出缺口" text="用現有保障扣出需要補強的項目。" />
      </div>

      <section className="mt-6 rounded-[1.5rem] border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm font-bold text-teal-700">我的保障現況</p>
            <h2 className="mt-1 text-xl font-bold text-slate-950">
              已讀取 {policySummary.policyCount} 張保單、{policySummary.companyCount} 家保險公司
            </h2>
          </div>
          <p className="text-sm font-bold text-slate-500">
            年繳保費 {policySummary.premium.toLocaleString("zh-TW")} 元
          </p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
          {COVERAGE_ORDER.map((key) => (
            <div key={key} className="rounded-2xl bg-slate-50 p-4">
              <p className="text-xs font-bold text-slate-400">{COVERAGE_LABELS[key].label}</p>
              <p className="mt-2 text-lg font-bold leading-tight text-slate-900">
                {formatCoverage(key, policySummary.coverage[key])}
              </p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function GuideCard({ title, text }: { title: string; text: string }) {
  return (
    <div className="rounded-2xl bg-slate-50 p-4">
      <p className="text-sm font-bold text-slate-800">{title}</p>
      <p className="mt-1 text-sm leading-6 text-slate-500">{text}</p>
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
    <div className="mx-auto grid min-h-full max-w-5xl items-center gap-6 px-5 py-8 md:px-8 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div>
        <p className="text-sm font-bold text-teal-700">建立資料</p>
        <h1 className="mt-2 text-3xl font-bold text-slate-950">先設定這次要評估的人</h1>
        <p className="mt-3 max-w-xl text-base leading-7 text-slate-600">
          可以只評估自己，也可以一次建立家庭成員，後續結果會依照整體責任與預算一起整理。
        </p>

        <div className="mt-6 flex flex-col gap-6 rounded-[2rem] border border-slate-200 bg-white p-6 shadow-xl shadow-teal-100/70">
        <div>
          <label className="mb-2 block text-sm font-bold text-slate-700">資料名稱</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="例如：我的家庭、王先生"
            className="w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-800 outline-none transition placeholder:text-slate-300 focus:border-teal-300 focus:ring-4 focus:ring-teal-100"
          />
        </div>

        <div>
          <p className="mb-3 text-sm font-bold text-slate-700">這次要評估幾個人？</p>
          <div className="flex gap-2">
            {[1, 2, 3, 4].map((n) => (
              <button
                key={n}
                onClick={() => setCount(n)}
                className={`flex-1 rounded-2xl border py-3 text-sm font-bold transition ${
                  count === n
                    ? "border-slate-950 bg-slate-950 text-white"
                    : "border-slate-200 text-slate-600 hover:border-teal-300 hover:text-teal-700"
                }`}
              >
                {n} 人
              </button>
            ))}
          </div>
        </div>

        <button
          onClick={() => onConfirm(name, count)}
          className="w-full rounded-xl bg-slate-950 py-3 text-sm font-bold text-white transition hover:bg-slate-800"
        >
          開始填問卷
        </button>
      </div>

        <button onClick={onCancel} className="mt-4 text-sm font-bold text-slate-400 transition hover:text-slate-600">
          取消
        </button>
      </div>

      <aside className="rounded-[2rem] border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-sm font-bold text-slate-950">接下來會問</h2>
        <div className="mt-4 flex flex-wrap gap-2">
          {["年齡", "收入", "家庭責任", "債務", "健康", "保費預算"].map((item) => (
            <span key={item} className="rounded-full bg-slate-100 px-3 py-1.5 text-sm font-bold text-slate-600">
              {item}
            </span>
          ))}
        </div>
      </aside>
    </div>
  );
}

// ─── Assessing ────────────────────────────────────────────────────────────────

function AssessingView({ memberCount }: { memberCount: number }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 px-4 text-center text-slate-500">
      <SpinnerIcon />
      <p className="text-base font-bold text-slate-700">
        正在評估 {memberCount} 位成員的保障需求…
      </p>
      <p className="text-sm text-slate-400">考慮家庭脈絡進行分析，約需 10–20 秒</p>
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
      <div className="mx-auto flex min-h-full max-w-3xl flex-col justify-center px-5 py-8 md:px-8">
        <div className="mb-6">
          <p className="text-sm font-bold text-teal-700">
            第 {memberIndex + 1} 位 / 共 {totalMembers} 位
          </p>
          <h1 className="mt-2 text-3xl font-bold text-slate-950">請輸入姓名或關係</h1>
          <p className="mt-2 text-sm text-slate-500">方便之後區分每位成員的評估結果。</p>
        </div>
        <div className="rounded-[2rem] border border-slate-200 bg-white p-5 shadow-xl shadow-teal-100/70">
          <input
            autoFocus
            value={memberName}
            onChange={(e) => setMemberName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") { setMemberName((v) => v.trim() || defaultName); setNameStep(false); }
            }}
            placeholder={defaultName}
            className="mb-4 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-800 outline-none transition placeholder:text-slate-300 focus:border-teal-300 focus:ring-4 focus:ring-teal-100"
          />
          <button
            onClick={() => { setMemberName((v) => v.trim() || defaultName); setNameStep(false); }}
            className="w-full rounded-xl bg-slate-950 py-3 text-sm font-bold text-white transition hover:bg-slate-800"
          >
            下一步
          </button>
        </div>
        {error && <p className="mt-4 text-center text-sm text-red-500">{error}</p>}
      </div>
    );
  }

  const q = QUESTIONS[step];
  const isLastMember = memberIndex === totalMembers - 1;
  const isLastQuestion = step === QUESTIONS.length - 1;
  const progress = Math.round(((step + 1) / QUESTIONS.length) * 100);

  return (
    <div className="mx-auto grid min-h-full max-w-5xl items-center gap-6 px-5 py-8 md:px-8 lg:grid-cols-[minmax(0,1fr)_280px]">
      <section>
        <div className="mb-6">
        <p className="text-sm font-bold text-teal-700">
          {memberName}・第 {memberIndex + 1} 位 / 共 {totalMembers} 位
        </p>
        <h1 className="mt-2 text-3xl font-bold text-slate-950">保障需求評估</h1>
        {isLastMember && isLastQuestion && (
          <p className="mt-2 text-sm font-bold text-amber-600">填完後將送出所有成員資料進行評估</p>
        )}
      </div>

      <div className="mb-6">
        <div className="mb-2 flex justify-between text-xs font-bold text-slate-400">
          <span>第 {step + 1} / {QUESTIONS.length} 題</span>
          <span>{progress}%</span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-slate-200">
          <div
            className="h-full rounded-full bg-teal-500 transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      <div className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-xl shadow-teal-100/70">
        <p className="mb-5 text-xl font-bold text-slate-950">{q.question}</p>
        <div className="grid gap-2.5 sm:grid-cols-2">
          {q.options.map((opt) => (
            <button
              key={opt}
              onClick={() => handleOption(opt)}
              className="w-full rounded-2xl border border-slate-200 px-4 py-3 text-left text-sm font-bold text-slate-700 transition hover:border-teal-300 hover:bg-teal-50 hover:text-teal-800"
            >
              {opt}
            </button>
          ))}
        </div>
      </div>

      {step > 0 && (
        <button
          onClick={() => setStep(step - 1)}
          className="mt-4 flex items-center gap-1 text-sm font-bold text-slate-400 hover:text-slate-600"
        >
          <ChevronLeftIcon /> 上一題
        </button>
      )}
      </section>

      <aside className="rounded-[2rem] border border-slate-200 bg-white p-5 shadow-sm">
        <p className="text-sm font-bold text-slate-950">目前進度</p>
        <p className="mt-3 text-4xl font-bold text-teal-700">{progress}%</p>
        <p className="mt-2 text-sm leading-6 text-slate-500">
          回答會暫存在本頁，最後一位成員完成後才會送出評估。
        </p>
      </aside>
    </div>
  );
}

// ─── Profile Result ───────────────────────────────────────────────────────────

function ProfileResultView({
  profile,
  policySummary,
  onNew,
}: {
  profile: CustomerProfile;
  policySummary: PolicySummary;
  onNew: () => void;
}) {
  const [activeMember, setActiveMember] = useState(0);
  const member = profile.members[activeMember];

  return (
    <div className="mx-auto max-w-6xl px-5 py-8 md:px-8">
      <div className="mb-5 flex flex-col gap-4 rounded-[2rem] border border-slate-200 bg-white p-5 shadow-sm md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-sm font-bold text-teal-700">健檢結果</p>
          <h1 className="mt-1 text-2xl font-bold text-slate-950">{profile.name}</h1>
          <p className="mt-1 text-xs text-slate-400">
            {profile.members.length} 人・{new Date(profile.createdAt).toLocaleDateString("zh-TW")}
          </p>
        </div>
        <button
          onClick={onNew}
          className="inline-flex items-center justify-center gap-1.5 rounded-xl bg-slate-950 px-4 py-2 text-sm font-bold text-white transition hover:bg-slate-800"
        >
          <PlusSmIcon /> 建立新資料
        </button>
      </div>

      {/* Family summary */}
      {profile.familySummary && (
        <div className="mb-5 rounded-[1.5rem] border border-teal-100 bg-teal-50 p-4 text-sm leading-7 text-teal-900">
          <span className="font-bold">家庭整體摘要：</span>{profile.familySummary}
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
                  ? "border-slate-950 bg-slate-950 text-white"
                  : "border-slate-200 bg-white text-slate-600 hover:border-teal-300 hover:text-teal-700"
              }`}
            >
              {m.name}
            </button>
          ))}
        </div>
      )}

      {member && <MemberResultSection member={member} policySummary={policySummary} disclaimer={""} />}

      <p className="mt-5 text-center text-xs text-slate-400">
        本服務提供資訊參考，非正式保險建議，請諮詢合格業務員。
      </p>
    </div>
  );
}

function MemberResultSection({
  member,
  policySummary,
  disclaimer,
}: {
  member: MemberProfile;
  policySummary: PolicySummary;
  disclaimer: string;
}) {
  const { result } = member;
  const inBudget = result.items.filter((i) => i.within_budget);
  const deferred = result.items.filter((i) => !i.within_budget);
  const radarData = result.items.map((item) => ({
    subject: KEY_LABEL[item.key] ?? item.key,
    每月保費: item.monthly_premium_mid,
  }));

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
      <div className="space-y-5">
        <CoverageGapPanel items={result.items} policySummary={policySummary} />

        <div className="rounded-[1.5rem] border border-amber-200 bg-amber-50 p-4 text-sm leading-7 text-amber-900">
          <span className="font-bold">摘要：</span>{result.summary}
        </div>

        <div className="rounded-[1.5rem] border border-slate-200 bg-white p-4 text-sm leading-7 text-slate-700">
          <span className="font-bold">預算規劃：</span>{result.budget_note}
        </div>

      {inBudget.length > 0 && (
        <div>
          <h2 className="mb-3 text-xs font-bold uppercase text-slate-500">在預算內，建議優先投保</h2>
          <div className="flex flex-col gap-2.5">
            {inBudget.map((item) => <PriorityCard key={item.key} item={item} highlighted />)}
          </div>
        </div>
      )}

      {deferred.length > 0 && (
        <div>
          <h2 className="mb-3 text-xs font-bold uppercase text-slate-500">預算充裕後再補足</h2>
          <div className="flex flex-col gap-2.5">
            {deferred.map((item) => <PriorityCard key={item.key} item={item} highlighted={false} />)}
          </div>
        </div>
      )}
      </div>

      <aside className="space-y-5">
      <div className="rounded-[1.5rem] border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="mb-4 text-sm font-bold text-slate-700">每月保費分配（元/月）</h2>
        <div style={{ height: "16rem" }}>
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={radarData}>
              <PolarGrid />
              <PolarAngleAxis dataKey="subject" tick={{ fontSize: 12 }} />
              <Radar name="每月保費" dataKey="每月保費" stroke="#0f766e" fill="#14b8a6" fillOpacity={0.28} />
              <Tooltip formatter={(val) => `${Number(val ?? 0).toLocaleString()} 元/月`} />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {result.recommended_products?.length > 0 && (
        <ProductRecommendations products={result.recommended_products} />
      )}

      {disclaimer && <p className="text-xs text-gray-400 text-center">{disclaimer}</p>}
      </aside>
    </div>
  );
}

function CoverageGapPanel({ items, policySummary }: { items: RecommendationItem[]; policySummary: PolicySummary }) {
  const rows = items
    .map((item) => {
      const coverageKey = RECOMMENDATION_TO_COVERAGE[item.key];
      if (!coverageKey) return null;
      const existing = coverageKey === "ltc" ? policySummary.coverage[coverageKey] * 10000 : policySummary.coverage[coverageKey];
      const target = item.amount;
      const gap = Math.max(target - existing, 0);
      return {
        key: item.key,
        label: KEY_LABEL[item.key] ?? item.key,
        existing,
        target,
        gap,
        unit: item.unit,
        priority: item.priority,
      };
    })
    .filter((row): row is NonNullable<typeof row> => row !== null)
    .sort((a, b) => b.gap - a.gap || a.priority - b.priority);

  return (
    <section className="rounded-[1.5rem] border border-teal-100 bg-white p-4 shadow-sm">
      <div className="mb-3">
        <p className="text-sm font-bold text-teal-700">保單健診缺口</p>
        <h2 className="mt-1 text-xl font-bold text-slate-950">現有保障 - 建議保障</h2>
      </div>
      <div className="overflow-hidden rounded-2xl border border-slate-100">
        <div className="grid grid-cols-[1.1fr_1fr_1fr_1fr] bg-slate-50 px-3 py-2 text-xs font-bold text-slate-500">
          <span>保障項目</span>
          <span className="text-right">現有</span>
          <span className="text-right">建議</span>
          <span className="text-right">缺口</span>
        </div>
        {rows.map((row) => (
          <div key={row.key} className="grid grid-cols-[1.1fr_1fr_1fr_1fr] border-t border-slate-100 px-3 py-3 text-sm">
            <span className="font-bold text-slate-800">{row.label}</span>
            <span className="text-right text-slate-500">{formatGapValue(row.existing, row.unit)}</span>
            <span className="text-right text-slate-500">{formatGapValue(row.target, row.unit)}</span>
            <span className={`text-right font-bold ${row.gap > 0 ? "text-rose-600" : "text-emerald-700"}`}>
              {row.gap > 0 ? formatGapValue(row.gap, row.unit) : "已足額"}
            </span>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs leading-5 text-slate-400">
        目前先以示範保單資料計算；正式版會依每位家庭成員名下保單、主附約與條款欄位自動彙整。
      </p>
    </section>
  );
}

function formatGapValue(value: number, unit: string) {
  return `${value.toLocaleString("zh-TW")} ${unit}`;
}

function ProductRecommendations({ products }: { products: ProductCard[] }) {
  return (
    <div className="rounded-[1.5rem] border border-emerald-200 bg-emerald-50 p-4">
      <div className="mb-3 flex items-center gap-2">
        <StarIcon />
        <h2 className="text-sm font-bold text-emerald-800">資料庫推薦商品</h2>
      </div>
      <p className="mb-3 text-xs leading-5 text-emerald-700">根據此成員的需求評估，以下商品可能值得了解（僅供參考）</p>
      <div className="flex flex-col gap-2.5">
        {products.map((p) => (
          <div key={p.product_id} className="flex items-center justify-between gap-3 rounded-2xl border border-emerald-100 bg-white px-4 py-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-bold text-slate-800">{p.product_name}</p>
              <p className="mt-0.5 text-xs text-slate-500">{p.company}・{p.category}</p>
            </div>
            {p.source_url && (
              <a href={p.source_url} target="_blank" rel="noopener noreferrer" className="shrink-0 text-xs font-bold text-teal-700 hover:text-teal-900">
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
    <div className={`rounded-2xl border p-4 ${highlighted ? "border-teal-200 border-l-4 border-l-teal-500 bg-white" : "border-slate-200 bg-slate-50"}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2.5">
          <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${highlighted ? "bg-teal-600 text-white" : "bg-slate-300 text-slate-600"}`}>
            {item.priority}
          </span>
          <div className="min-w-0">
            <span className="text-sm font-bold text-slate-800">{KEY_LABEL[item.key] ?? item.key}</span>
            <p className="mt-0.5 text-xs leading-6 text-slate-500">{item.reason}</p>
          </div>
        </div>
        <div className="shrink-0 text-right">
          <p className="text-sm font-bold text-slate-800">{item.amount.toLocaleString()} {item.unit}</p>
          <p className="mt-0.5 text-xs text-slate-400">{item.premium_range}</p>
        </div>
      </div>
    </div>
  );
}

// ─── Icons ────────────────────────────────────────────────────────────────────

function SpinnerIcon() {
  return (
    <svg className="animate-spin text-teal-600" width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
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
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
      <rect x="8" y="2" width="8" height="4" rx="1" ry="1" />
    </svg>
  );
}
function StarIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#059669" strokeWidth="2.5">
      <polygon points="12,2 15.09,8.26 22,9.27 17,14.14 18.18,21.02 12,17.77 5.82,21.02 7,14.14 2,9.27 8.91,8.26" />
    </svg>
  );
}
