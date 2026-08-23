"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  COVERAGE_LABELS,
  fetchPolicyPortfolio,
  formatMoney,
  getPoliciesByCompany,
  getPolicySummary,
  type CoverageKey,
  type PolicyPortfolio,
} from "@/lib/demo-policies";

type UploadKey = "diagnosis" | "receipt" | "detail";
type UploadedFiles = Record<UploadKey, File | null>;
type CompanyPolicyGroup = ReturnType<typeof getPoliciesByCompany>[number];
type Confidence = "高度符合" | "需保險公司確認";

type CompanyClaim = {
  company: string;
  total: number;
  items: Array<{ name: string; amount: number; confidence: Confidence; source_policy?: string }>;
};

type ClaimEstimate = {
  companies: CompanyClaim[];
  estimated_total: number;
  high_confidence_total: number;
  review_total: number;
  possible_denied_total: number;
  policy_count: number;
};

type ClaimDocumentExtraction = {
  diagnoses: string[];
  surgeries: string[];
  hospital_stay: {
    start_date: string;
    end_date: string;
    days: number | null;
  };
  medical_expense_total: number | null;
  self_pay_total: number | null;
  self_pay_items: string[];
  matched_signals: string[];
};

type ClaimDocumentResult = {
  key: UploadKey;
  title: string;
  filename: string;
  status: "parsed" | "needs_ocr" | "stored" | "unsupported";
  chars: number;
  preview: string;
  message: string;
  extracted?: ClaimDocumentExtraction;
};

const EMPTY_DOCUMENT_SUMMARY: ClaimDocumentExtraction = {
  diagnoses: [],
  surgeries: [],
  hospital_stay: { start_date: "", end_date: "", days: null },
  medical_expense_total: null,
  self_pay_total: null,
  self_pay_items: [],
  matched_signals: [],
};

const EMPTY_PORTFOLIO: PolicyPortfolio = {
  profile: null,
  policies: [],
  summary: getPolicySummary([]),
};

const UPLOADS: Array<{ key: UploadKey; title: string; text: string }> = [
  { key: "diagnosis", title: "診斷證明", text: "用來判斷疾病、手術名稱、住院期間與診療項目。" },
  { key: "receipt", title: "醫療收據", text: "用來辨識本次支出、健保與自費金額。" },
  { key: "detail", title: "醫療費用明細", text: "用來比對實支實付、手術與雜費項目。" },
];

const CLAIM_FACTORS: Partial<Record<CoverageKey, { factor: number; confidence: Confidence }>> = {
  daily: { factor: 6, confidence: "高度符合" },
  medical: { factor: 5000, confidence: "高度符合" },
  accident: { factor: 120, confidence: "高度符合" },
  critical: { factor: 500, confidence: "需保險公司確認" },
  cancer: { factor: 350, confidence: "需保險公司確認" },
};

export default function ClaimsApp() {
  const searchParams = useSearchParams();
  const profileId = searchParams.get("profile_id") ?? "demo-user";
  const ownerName = searchParams.get("owner_name") ?? "客戶";
  const clientId = searchParams.get("client_id");
  const [files, setFiles] = useState<UploadedFiles>({ diagnosis: null, receipt: null, detail: null });
  const [scenario, setScenario] = useState("");
  const [phase, setPhase] = useState<"input" | "analyzing" | "result">("input");
  const [documentResults, setDocumentResults] = useState<ClaimDocumentResult[]>([]);
  const [documentSummary, setDocumentSummary] = useState<ClaimDocumentExtraction>(EMPTY_DOCUMENT_SUMMARY);
  const [documentError, setDocumentError] = useState("");
  const [claimEstimate, setClaimEstimate] = useState<ClaimEstimate | null>(null);
  const [portfolio, setPortfolio] = useState<PolicyPortfolio>(EMPTY_PORTFOLIO);

  useEffect(() => {
    let mounted = true;
    fetchPolicyPortfolio(profileId)
      .then((data) => {
        if (mounted) setPortfolio(data);
      })
      .catch(() => {
        if (mounted) setPortfolio(EMPTY_PORTFOLIO);
      });
    return () => {
      mounted = false;
    };
  }, [profileId]);

  const policySummary = portfolio.summary;
  const companies = useMemo(() => getPoliciesByCompany(portfolio.policies), [portfolio.policies]);
  const uploadedCount = Object.values(files).filter(Boolean).length;
  const policyHref = `/policies?profile_id=${encodeURIComponent(profileId)}&owner_name=${encodeURIComponent(ownerName)}&relation=${encodeURIComponent("本人")}`;

  function setFile(key: UploadKey, file: File | null) {
    setFiles((prev) => ({ ...prev, [key]: file }));
  }

  async function analyze() {
    setPhase("analyzing");
    setDocumentError("");
    try {
      if (uploadedCount > 0) {
        const formData = new FormData();
        Object.entries(files).forEach(([key, file]) => {
          if (file) formData.append(key, file);
        });
        const res = await fetch("/api/claims/documents", { method: "POST", body: formData });
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();
        setDocumentResults(data.documents ?? []);
        setDocumentSummary(data.summary ?? EMPTY_DOCUMENT_SUMMARY);
      } else {
        setDocumentResults([]);
        setDocumentSummary(EMPTY_DOCUMENT_SUMMARY);
      }
      const estimateRes = await fetch("/api/claims/estimate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile_id: profileId, scenario }),
      });
      setClaimEstimate(estimateRes.ok ? await estimateRes.json() : null);
    } catch {
      setDocumentError("文件解析或理賠估算失敗，請稍後再試。");
      setClaimEstimate(null);
    } finally {
      window.setTimeout(() => setPhase("result"), 500);
    }
  }

  if (phase === "analyzing") {
    return (
      <div className="flex min-h-full items-center justify-center bg-[#f7faf8] px-5 text-center">
        <div>
          <SpinnerIcon />
          <h1 className="mt-5 text-2xl font-bold text-slate-950">AI 正在比對理賠資料</h1>
          <p className="mt-3 text-sm leading-6 text-slate-500">
            正在解析文件，並比對 {ownerName} 目前系統中的 {policySummary.policyCount} 張保單。
          </p>
        </div>
      </div>
    );
  }

  if (phase === "result") {
    return (
      <ClaimResultView
        ownerName={ownerName}
        scenario={scenario}
        companies={companies}
        estimate={claimEstimate}
        documents={documentResults}
        documentSummary={documentSummary}
        documentError={documentError}
        onReset={() => setPhase("input")}
      />
    );
  }

  return (
    <div className="min-h-full bg-[#f7faf8] px-5 py-8 text-slate-900 md:px-8">
      <div className="mx-auto max-w-7xl">
        <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-bold text-teal-700">理賠服務中心</p>
            <h1 className="mt-2 text-3xl font-bold leading-tight text-slate-950 md:text-5xl">
              {ownerName} 的理賠試算
            </h1>
            <p className="mt-3 max-w-3xl text-base leading-7 text-slate-600">
              上傳診斷證明、收據與醫療明細後，系統會依此客戶現有保單比對可能理賠項目、預估金額與應備文件。
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {clientId && (
              <Link
                href={`/advisor/clients/${clientId}`}
                className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-bold text-slate-700 transition hover:border-amber-300 hover:text-amber-700"
              >
                返回客戶 360
              </Link>
            )}
            <Link
              href={policyHref}
              className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-bold text-slate-700 transition hover:border-teal-300 hover:text-teal-700"
            >
              編輯保單
            </Link>
          </div>
        </div>

        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
          <section className="rounded-[1.5rem] border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-4">
              <h2 className="text-xl font-bold text-slate-950">上傳理賠文件</h2>
              <p className="mt-1 text-sm text-slate-500">第一版會先保存並擷取可讀文字，後續可接 OCR 與醫療費用自動辨識。</p>
            </div>

            <div className="grid gap-3 md:grid-cols-3">
              {UPLOADS.map((upload) => (
                <UploadCard
                  key={upload.key}
                  title={upload.title}
                  text={upload.text}
                  file={files[upload.key]}
                  onChange={(file) => setFile(upload.key, file)}
                />
              ))}
            </div>

            <label className="mt-5 block text-sm font-bold text-slate-700">事故或疾病補充說明</label>
            <textarea
              value={scenario}
              onChange={(e) => setScenario(e.target.value)}
              rows={5}
              placeholder="例如：因疾病住院 6 天，期間有手術與自費醫材，想確認哪些保單可能可以申請。"
              className="mt-3 w-full resize-none rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-7 text-slate-800 outline-none transition placeholder:text-slate-300 focus:border-teal-300 focus:ring-4 focus:ring-teal-100"
            />

            <button
              onClick={analyze}
              disabled={uploadedCount === 0 && !scenario.trim()}
              className="mt-5 w-full rounded-xl bg-slate-950 px-5 py-3 text-sm font-bold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40"
            >
              開始理賠比對
            </button>
          </section>

          <aside className="space-y-4">
            <section className="rounded-[1.5rem] border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-sm font-bold text-slate-950">客戶保單摘要</h2>
              <p className="mt-2 text-2xl font-bold text-teal-700">{policySummary.policyCount} 張</p>
              <p className="mt-1 text-sm text-slate-500">{policySummary.companyCount} 家保險公司</p>
              <div className="mt-4 space-y-2">
                {companies.length === 0 && (
                  <div className="rounded-xl border border-dashed border-slate-200 px-3 py-5 text-center text-sm text-slate-400">
                    尚未建立保單資料
                  </div>
                )}
                {companies.map((group) => (
                  <div key={group.company} className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2">
                    <span className="text-sm font-bold text-slate-700">{group.company}</span>
                    <span className="text-sm text-slate-500">{group.policies.length} 張</span>
                  </div>
                ))}
              </div>
            </section>

            <section className="rounded-[1.5rem] border border-amber-200 bg-amber-50 p-5">
              <h2 className="text-sm font-bold text-amber-900">理賠前置條件</h2>
              <div className="mt-3 grid gap-2 text-sm leading-6 text-amber-900">
                <p>需先建立客戶既有保單。</p>
                <p>診斷證明、收據、費用明細越完整，判讀越準。</p>
                <p>預估金額仍需以保險公司核定與條款為準。</p>
              </div>
            </section>
          </aside>
        </div>
      </div>
    </div>
  );
}

function ClaimResultView({
  ownerName,
  scenario,
  companies,
  estimate,
  documents,
  documentSummary,
  documentError,
  onReset,
}: {
  ownerName: string;
  scenario: string;
  companies: CompanyPolicyGroup[];
  estimate: ClaimEstimate | null;
  documents: ClaimDocumentResult[];
  documentSummary: ClaimDocumentExtraction;
  documentError: string;
  onReset: () => void;
}) {
  const fallbackClaims = buildClaimEstimate(companies);
  const companyClaims = estimate?.companies ?? fallbackClaims;
  const estimatedTotal = estimate?.estimated_total ?? companyClaims.reduce((sum, company) => sum + company.total, 0);
  const highConfidenceTotal =
    estimate?.high_confidence_total ??
    companyClaims.reduce(
      (sum, company) =>
        sum + company.items.filter((item) => item.confidence === "高度符合").reduce((itemSum, item) => itemSum + item.amount, 0),
      0,
    );
  const reviewTotal = estimate?.review_total ?? estimatedTotal - highConfidenceTotal;
  const requiredDocuments = buildRequiredDocuments(companyClaims.length);
  const medicalExpenseLabel = documentSummary.medical_expense_total
    ? formatMoney(documentSummary.medical_expense_total)
    : "待文件辨識";

  return (
    <div className="min-h-full bg-[#f7faf8] px-5 py-8 text-slate-900 md:px-8">
      <div className="mx-auto max-w-7xl">
        <div className="mb-5 flex flex-col gap-4 rounded-[1.5rem] border border-slate-200 bg-white p-5 shadow-sm lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-sm font-bold text-teal-700">理賠比對結果</p>
            <h1 className="mt-1 text-3xl font-bold text-slate-950">{ownerName} 的預估理賠</h1>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-500">
              <span className="font-bold text-slate-700">補充說明：</span>{scenario || "未填寫"}
            </p>
          </div>
          <button
            onClick={onReset}
            className="w-fit rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-600 transition hover:bg-slate-50"
          >
            重新分析
          </button>
        </div>

        <section className="grid gap-3 md:grid-cols-3">
          <MetricCard label="本次醫療費用" value={medicalExpenseLabel} tone="text-slate-950" />
          <MetricCard label="AI 預估可申請理賠" value={formatMoney(estimatedTotal)} tone="text-teal-700" />
          <MetricCard label="涉及保險公司" value={`${companyClaims.length} 家`} tone="text-amber-600" />
        </section>

        <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
          <main className="space-y-4">
            {documents.length > 0 && (
              <>
                <DocumentSummaryPanel summary={documentSummary} />
                <DocumentParsePanel documents={documents} documentError={documentError} />
              </>
            )}
            {documentError && documents.length === 0 && (
              <section className="rounded-[1.5rem] border border-rose-200 bg-rose-50 p-5 text-sm font-bold text-rose-700">
                {documentError}
              </section>
            )}

            {companyClaims.length === 0 && (
              <section className="rounded-[1.5rem] border border-dashed border-slate-300 bg-white p-8 text-center">
                <p className="text-sm font-bold text-slate-500">目前沒有可比對的保障項目</p>
                <p className="mt-2 text-sm text-slate-400">請先補齊客戶保單，或確認本次事故是否與現有保障相關。</p>
              </section>
            )}

            {companyClaims.map((company) => (
              <section key={company.company} className="rounded-[1.5rem] border border-slate-200 bg-white p-5 shadow-sm">
                <div className="mb-4 flex items-center justify-between border-b border-slate-100 pb-3">
                  <h2 className="text-xl font-bold text-slate-950">{company.company}</h2>
                  <p className="text-lg font-bold tabular-nums text-teal-700">{formatMoney(company.total)}</p>
                </div>
                <div className="space-y-2">
                  {company.items.map((item) => (
                    <div key={`${item.name}-${item.source_policy}`} className="grid grid-cols-[1fr_auto_auto] items-center gap-3 rounded-2xl bg-slate-50 px-4 py-3 text-sm">
                      <span className="font-bold text-slate-800">{item.name}</span>
                      <span className={`rounded-lg px-2 py-1 text-xs font-bold ${item.confidence === "高度符合" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>
                        {item.confidence}
                      </span>
                      <span className="font-bold tabular-nums text-slate-950">{formatMoney(item.amount)}</span>
                      {item.source_policy && (
                        <span className="col-span-3 text-xs text-slate-400">
                          來源保單：{item.source_policy}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </section>
            ))}
          </main>

          <aside className="space-y-4">
            <section className="rounded-[1.5rem] border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-sm font-bold text-slate-950">AI 理賠判讀</h2>
              <div className="mt-3 grid gap-2">
                <ConfidenceRow label="高度符合" value={highConfidenceTotal} tone="green" />
                <ConfidenceRow label="需保險公司確認" value={reviewTotal} tone="amber" />
                <ConfidenceRow label="可能不符合" value={0} tone="gray" />
              </div>
            </section>

            <section className="rounded-[1.5rem] border border-sky-200 bg-sky-50 p-5">
              <h2 className="text-sm font-bold text-sky-900">現在需要準備</h2>
              <div className="mt-3 space-y-2">
                {requiredDocuments.map((doc) => (
                  <div key={doc.name} className="flex items-center justify-between rounded-xl bg-white px-3 py-2">
                    <span className="text-sm font-bold text-slate-700">{doc.name}</span>
                    <span className="text-sm font-bold text-sky-700">x {doc.count}</span>
                  </div>
                ))}
              </div>
            </section>
          </aside>
        </div>

        <p className="mt-5 text-center text-xs text-slate-400">
          理賠估算僅供顧問服務前置判讀，實際結果仍以保險公司審核、條款、診斷證明與收據文件為準。
        </p>
      </div>
    </div>
  );
}

function DocumentParsePanel({
  documents,
  documentError,
}: {
  documents: ClaimDocumentResult[];
  documentError: string;
}) {
  return (
    <section className="rounded-[1.5rem] border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4">
        <p className="text-sm font-bold text-teal-700">文件解析結果</p>
        <h2 className="mt-1 text-xl font-bold text-slate-950">已收到 {documents.length} 份文件</h2>
        {documentError && <p className="mt-2 text-sm font-bold text-rose-600">{documentError}</p>}
      </div>
      <div className="grid gap-3">
        {documents.map((doc) => (
          <div key={`${doc.key}-${doc.filename}`} className="rounded-2xl bg-slate-50 p-4">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm font-bold text-slate-900">{doc.title}</p>
                <p className="mt-0.5 text-xs text-slate-400">{doc.filename}</p>
              </div>
              <span className={`w-fit rounded-lg px-2 py-1 text-xs font-bold ${doc.status === "parsed" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>
                {doc.status === "parsed" ? `已讀取 ${doc.chars.toLocaleString("zh-TW")} 字` : doc.message}
              </span>
            </div>
            {doc.preview && (
              <p className="mt-3 line-clamp-3 whitespace-pre-wrap text-xs leading-5 text-slate-500">
                {doc.preview}
              </p>
            )}
            {doc.extracted?.matched_signals && doc.extracted.matched_signals.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {doc.extracted.matched_signals.map((signal) => (
                  <span key={signal} className="rounded-lg bg-white px-2 py-1 text-xs font-bold text-teal-700 ring-1 ring-teal-100">
                    {signal}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

function DocumentSummaryPanel({ summary }: { summary: ClaimDocumentExtraction }) {
  const stay = summary.hospital_stay;
  const stayText =
    stay.days || stay.start_date || stay.end_date
      ? [stay.start_date && stay.end_date ? `${stay.start_date} - ${stay.end_date}` : "", stay.days ? `${stay.days} 天` : ""]
          .filter(Boolean)
          .join(" / ")
      : "待辨識";
  const rows = [
    { label: "診斷疾病", value: summary.diagnoses.length ? summary.diagnoses.join("、") : "待辨識" },
    { label: "住院期間", value: stayText },
    { label: "手術名稱", value: summary.surgeries.length ? summary.surgeries.join("、") : "待辨識" },
    {
      label: "自費金額",
      value: summary.self_pay_total ? formatMoney(summary.self_pay_total) : "待辨識",
    },
  ];

  return (
    <section className="rounded-[1.5rem] border border-teal-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-sm font-bold text-teal-700">AI 文件判讀摘要</p>
          <h2 className="mt-1 text-xl font-bold text-slate-950">理賠文件已轉成可比對欄位</h2>
        </div>
        <span className="w-fit rounded-lg bg-teal-50 px-2.5 py-1 text-xs font-bold text-teal-700">
          {summary.matched_signals.length ? `${summary.matched_signals.length} 項訊號` : "待補文件"}
        </span>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        {rows.map((row) => (
          <div key={row.label} className="rounded-2xl bg-slate-50 p-4">
            <p className="text-xs font-bold text-slate-400">{row.label}</p>
            <p className="mt-2 text-sm font-bold leading-6 text-slate-900">{row.value}</p>
          </div>
        ))}
      </div>

      {summary.self_pay_items.length > 0 && (
        <div className="mt-4 rounded-2xl bg-amber-50 p-4">
          <p className="text-xs font-bold text-amber-700">自費或需確認項目</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {summary.self_pay_items.map((item) => (
              <span key={item} className="rounded-lg bg-white px-2.5 py-1 text-xs font-bold text-amber-800 ring-1 ring-amber-100">
                {item}
              </span>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function buildClaimEstimate(companies: CompanyPolicyGroup[]): CompanyClaim[] {
  return companies
    .map((group) => {
      const items = group.policies.flatMap((policy) =>
        Object.entries(policy.coverages).flatMap(([key, amount]) => {
          const coverageKey = key as CoverageKey;
          const rule = CLAIM_FACTORS[coverageKey];
          if (!rule || !amount) return [];
          return [
            {
              name: COVERAGE_LABELS[coverageKey].label,
              amount: Math.round(amount * rule.factor),
              confidence: rule.confidence,
              source_policy: policy.name,
            },
          ];
        }),
      );
      return {
        company: group.company,
        total: items.reduce((sum, item) => sum + item.amount, 0),
        items,
      };
    })
    .filter((company) => company.total > 0);
}

function buildRequiredDocuments(companyCount: number) {
  return [
    { name: "診斷證明", count: Math.max(1, companyCount || 1) },
    { name: "收據正本", count: 1 },
    { name: "醫療費用明細", count: 1 },
    { name: "理賠申請書", count: Math.max(1, companyCount || 1) },
  ];
}

function UploadCard({
  title,
  text,
  file,
  onChange,
}: {
  title: string;
  text: string;
  file: File | null;
  onChange: (file: File | null) => void;
}) {
  return (
    <label className="flex min-h-44 cursor-pointer flex-col justify-between rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-4 transition hover:border-teal-300 hover:bg-teal-50/40">
      <span>
        <span className="block text-base font-bold text-slate-950">+ {title}</span>
        <span className="mt-2 block text-sm leading-6 text-slate-500">{text}</span>
      </span>
      <span className="mt-4 block truncate rounded-xl bg-white px-3 py-2 text-sm font-bold text-slate-600 ring-1 ring-slate-100">
        {file ? file.name : "選擇檔案"}
      </span>
      <input
        type="file"
        accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/*"
        className="hidden"
        onChange={(event) => onChange(event.target.files?.[0] ?? null)}
      />
    </label>
  );
}

function MetricCard({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className="rounded-[1.25rem] border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-sm font-bold text-slate-500">{label}</p>
      <p className={`mt-2 text-3xl font-bold tabular-nums ${tone}`}>{value}</p>
    </div>
  );
}

function ConfidenceRow({ label, value, tone }: { label: string; value: number; tone: "green" | "amber" | "gray" }) {
  const styles = {
    green: "bg-emerald-100 text-emerald-700",
    amber: "bg-amber-100 text-amber-700",
    gray: "bg-slate-100 text-slate-500",
  };
  return (
    <div className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2">
      <span className={`rounded-lg px-2 py-1 text-xs font-bold ${styles[tone]}`}>{label}</span>
      <span className="text-sm font-bold tabular-nums text-slate-900">{formatMoney(value)}</span>
    </div>
  );
}

function SpinnerIcon() {
  return (
    <svg className="mx-auto animate-spin text-teal-600" width="42" height="42" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
    </svg>
  );
}
