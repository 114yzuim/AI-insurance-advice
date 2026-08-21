"use client";

import { FormEvent, ReactNode, useEffect, useMemo, useRef, useState } from "react";
import {
  COVERAGE_LABELS,
  COVERAGE_ORDER,
  DEMO_POLICIES,
  fetchInsuranceProfiles,
  fetchPolicyPortfolio,
  formatCoverage,
  formatMoney,
  getPoliciesByCompany,
  getPolicySummary,
  type CoverageKey,
  type InsuranceProfile,
  type Policy,
  type PolicyPortfolio,
} from "@/lib/demo-policies";

const INPUT_CLASS =
  "w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800 outline-none transition placeholder:text-slate-300 focus:border-teal-300 focus:ring-4 focus:ring-teal-100";

type PolicyFormState = {
  id?: string;
  company: string;
  name: string;
  policyNo: string;
  role: Policy["role"];
  status: Policy["status"];
  annualPremium: string;
  effectiveDate: string;
  coverages: Record<CoverageKey, string>;
  ridersText: string;
};

function makeEmptyCoverages() {
  return COVERAGE_ORDER.reduce((acc, key) => {
    acc[key] = "";
    return acc;
  }, {} as Record<CoverageKey, string>);
}

function makeEmptyForm(): PolicyFormState {
  return {
    company: "",
    name: "",
    policyNo: "",
    role: "主約",
    status: "有效",
    annualPremium: "",
    effectiveDate: "",
    coverages: makeEmptyCoverages(),
    ridersText: "",
  };
}

export default function PoliciesApp() {
  const [activeCompany, setActiveCompany] = useState("全部");
  const [activeProfileId, setActiveProfileId] = useState("demo-user");
  const [profiles, setProfiles] = useState<InsuranceProfile[]>([]);
  const [portfolio, setPortfolio] = useState<PolicyPortfolio>(() => ({
    profile: null,
    policies: DEMO_POLICIES,
    summary: getPolicySummary(DEMO_POLICIES),
  }));
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState<PolicyFormState>(() => makeEmptyForm());
  const [formError, setFormError] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<Policy | null>(null);
  const uploadInputRef = useRef<HTMLInputElement | null>(null);

  async function reloadPolicies(profileId = activeProfileId) {
    setLoading(true);
    try {
      setPortfolio(await fetchPolicyPortfolio(profileId));
    } catch {
      setPortfolio({
        profile: null,
        policies: DEMO_POLICIES,
        summary: getPolicySummary(DEMO_POLICIES),
      });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let mounted = true;
    queueMicrotask(() => {
      fetchInsuranceProfiles()
        .then((data) => {
          if (mounted) setProfiles(data);
        })
        .catch(() => {
          if (mounted) {
            setProfiles([{ id: "demo-user", owner_name: "預設客戶", relation: "本人", policy_count: DEMO_POLICIES.length }]);
          }
        });

      fetchPolicyPortfolio("demo-user")
        .then((data) => {
          if (mounted) setPortfolio(data);
        })
        .catch(() => {
          if (mounted) {
            setPortfolio({
              profile: null,
              policies: DEMO_POLICIES,
              summary: getPolicySummary(DEMO_POLICIES),
            });
          }
        })
        .finally(() => {
          if (mounted) setLoading(false);
        });
    });
    return () => {
      mounted = false;
    };
  }, []);

  const totals = portfolio.summary;
  const companies = useMemo(() => getPoliciesByCompany(portfolio.policies), [portfolio.policies]);
  const visibleCompanies =
    activeCompany === "全部" ? companies : companies.filter((item) => item.company === activeCompany);

  function openCreateForm() {
    setForm(makeEmptyForm());
    setFormError("");
    setFormOpen(true);
  }

  async function reloadProfiles() {
    try {
      setProfiles(await fetchInsuranceProfiles());
    } catch {
      setProfiles([{ id: "demo-user", owner_name: "預設客戶", relation: "本人", policy_count: portfolio.policies.length }]);
    }
  }

  async function handleProfileSelect(profileId: string) {
    setActiveProfileId(profileId);
    setActiveCompany("全部");
    await reloadPolicies(profileId);
  }

  async function handleCreateProfile() {
    const ownerName = window.prompt("請輸入家庭成員姓名");
    if (!ownerName?.trim()) return;
    const relation = window.prompt("請輸入關係，例如：配偶、小孩、爸爸、媽媽", "家人") || "家人";
    try {
      const res = await fetch("/api/policies/profiles", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          owner_name: ownerName.trim(),
          relation: relation.trim() || "家人",
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const profile = await res.json();
      await reloadProfiles();
      await handleProfileSelect(profile.id);
    } catch {
      setFormError("新增家庭成員失敗，請稍後再試。");
    }
  }

  function openEditForm(policy: Policy) {
    setForm(policyToForm(policy));
    setFormError("");
    setFormOpen(true);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!form.company.trim() || !form.name.trim()) {
      setFormError("請至少填寫保險公司與保單名稱。");
      return;
    }

    setSaving(true);
    setFormError("");
    try {
      const res = await fetch(form.id ? `/api/policies/${form.id}` : "/api/policies", {
        method: form.id ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formToPayload(form, activeProfileId)),
      });
      if (!res.ok) throw new Error(await res.text());
      setFormOpen(false);
      await reloadProfiles();
      await reloadPolicies();
    } catch {
      setFormError("儲存失敗，請確認後端服務是否啟動。");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    setSaving(true);
    try {
      const res = await fetch(`/api/policies/${deleteTarget.id}`, { method: "DELETE" });
      if (!res.ok) throw new Error(await res.text());
      setDeleteTarget(null);
      await reloadProfiles();
      await reloadPolicies();
    } catch {
      setFormError("刪除失敗，請稍後再試。");
    } finally {
      setSaving(false);
    }
  }

  async function handleUpload(file: File | null) {
    if (!file) return;
    setUploading(true);
    setFormError("");
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("profile_id", activeProfileId);
      const res = await fetch("/api/policies/upload", { method: "POST", body: formData });
      if (!res.ok) throw new Error(await res.text());
      await reloadProfiles();
      await reloadPolicies();
    } catch {
      setFormError("上傳失敗，請確認檔案格式或後端服務。");
    } finally {
      setUploading(false);
      if (uploadInputRef.current) uploadInputRef.current.value = "";
    }
  }

  return (
    <div className="min-h-full bg-[#f7faf8] px-5 py-8 text-slate-900 md:px-8">
      <div className="mx-auto max-w-7xl">
        <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-bold text-teal-700">我的保單</p>
            <h1 className="mt-2 text-3xl font-bold leading-tight text-slate-950 md:text-5xl">
              {portfolio.profile?.owner_name ?? "我的"}的保障總覽
            </h1>
            <p className="mt-3 max-w-3xl text-base leading-7 text-slate-600">
              把所有保單集中在同一個地方，AI 之後會用這份資料協助健診、理賠與個人化問答。
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={openCreateForm}
              className="rounded-xl bg-slate-950 px-4 py-2.5 text-sm font-bold text-white transition hover:bg-slate-800"
            >
              + 建立保單
            </button>
            <button
              onClick={() => uploadInputRef.current?.click()}
              disabled={uploading}
              className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-bold text-slate-700 transition hover:border-teal-300 hover:text-teal-700 disabled:opacity-50"
            >
              {uploading ? "上傳中..." : "上傳 PDF"}
            </button>
            <input
              ref={uploadInputRef}
              type="file"
              accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/*"
              className="hidden"
              onChange={(event) => void handleUpload(event.target.files?.[0] ?? null)}
            />
          </div>
        </div>

        {formError && !formOpen && (
          <div className="mb-4 rounded-xl border border-rose-100 bg-rose-50 px-4 py-3 text-sm font-bold text-rose-600">
            {formError}
          </div>
        )}

        <section className="grid gap-3 md:grid-cols-4">
          <SummaryTile label="已建立保單" value={`${totals.policyCount} 張`} />
          <SummaryTile label="保險公司" value={`${totals.companyCount} 家`} />
          <SummaryTile label="年繳保費" value={formatMoney(totals.premium)} />
          <SummaryTile label="待補資料" value={`${totals.incomplete} 張`} tone="amber" />
        </section>

        <section className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
          {COVERAGE_ORDER.map((key) => (
            <CoverageTile
              key={key}
              label={COVERAGE_LABELS[key].label}
              value={formatCoverage(key, totals.coverage[key])}
            />
          ))}
        </section>

        <div className="mt-7 grid gap-5 lg:grid-cols-[260px_minmax(0,1fr)]">
          <aside className="h-fit rounded-[1.5rem] border border-slate-200 bg-white p-4 shadow-sm">
            <div className="border-b border-slate-100 pb-4">
              <div className="flex items-center justify-between">
                <p className="text-sm font-bold text-slate-950">家庭成員</p>
                <button onClick={handleCreateProfile} className="text-xs font-bold text-teal-700 hover:text-teal-900">
                  + 新增
                </button>
              </div>
              <div className="mt-3 flex flex-col gap-1.5">
                {profiles.map((profile) => (
                  <CompanyButton
                    key={profile.id}
                    active={activeProfileId === profile.id}
                    name={`${profile.owner_name ?? "家庭成員"}｜${profile.relation ?? "家人"}`}
                    count={profile.policy_count ?? 0}
                    onClick={() => void handleProfileSelect(profile.id)}
                  />
                ))}
              </div>
            </div>
            <p className="mt-4 text-sm font-bold text-slate-950">保險公司</p>
            <div className="mt-3 flex flex-col gap-1.5">
              <CompanyButton
                active={activeCompany === "全部"}
                name="全部"
                count={portfolio.policies.length}
                onClick={() => setActiveCompany("全部")}
              />
              {companies.map((item) => (
                <CompanyButton
                  key={item.company}
                  active={activeCompany === item.company}
                  name={item.company}
                  count={item.policies.length}
                  onClick={() => setActiveCompany(item.company)}
                />
              ))}
            </div>
          </aside>

          <main className="space-y-4">
            {loading && (
              <div className="rounded-[1.5rem] border border-slate-200 bg-white p-5 text-sm font-bold text-slate-500 shadow-sm">
                正在讀取保單資料...
              </div>
            )}
            {!loading && visibleCompanies.length === 0 && (
              <div className="rounded-[1.5rem] border border-dashed border-slate-300 bg-white p-8 text-center">
                <p className="text-sm font-bold text-slate-500">目前沒有保單資料</p>
                <button onClick={openCreateForm} className="mt-4 text-sm font-bold text-teal-700 hover:text-teal-900">
                  建立第一張保單
                </button>
              </div>
            )}
            {visibleCompanies.map((group) => (
              <section key={group.company} className="rounded-[1.5rem] border border-slate-200 bg-white p-5 shadow-sm">
                <div className="mb-4 flex flex-col gap-2 border-b border-slate-100 pb-4 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <h2 className="text-xl font-bold text-slate-950">{group.company}</h2>
                    <p className="mt-1 text-sm text-slate-500">
                      {group.policies.length} 張保單・年繳 {formatMoney(group.annualPremium)}
                    </p>
                  </div>
                  <button className="w-fit rounded-xl border border-slate-200 px-3 py-2 text-sm font-bold text-slate-600 transition hover:border-teal-300 hover:text-teal-700">
                    查看公司保障
                  </button>
                </div>

                <div className="grid gap-3">
                  {group.policies.map((policy) => (
                    <PolicyRow
                      key={policy.id}
                      policy={policy}
                      onEdit={() => openEditForm(policy)}
                      onDelete={() => setDeleteTarget(policy)}
                    />
                  ))}
                </div>
              </section>
            ))}
          </main>
        </div>
      </div>

      {formOpen && (
        <PolicyFormDrawer
          form={form}
          error={formError}
          saving={saving}
          onClose={() => setFormOpen(false)}
          onSubmit={handleSubmit}
          onChange={setForm}
        />
      )}

      {deleteTarget && (
        <ConfirmDialog
          policy={deleteTarget}
          saving={saving}
          onCancel={() => setDeleteTarget(null)}
          onConfirm={handleDelete}
        />
      )}
    </div>
  );
}

function SummaryTile({ label, value, tone = "teal" }: { label: string; value: string; tone?: "teal" | "amber" }) {
  return (
    <div className="rounded-[1.25rem] border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-sm font-bold text-slate-500">{label}</p>
      <p className={`mt-2 text-2xl font-bold ${tone === "amber" ? "text-amber-600" : "text-teal-700"}`}>{value}</p>
    </div>
  );
}

function CoverageTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[1.25rem] border border-teal-100 bg-white p-4 shadow-sm">
      <p className="text-sm font-bold text-slate-500">{label}</p>
      <p className="mt-2 min-h-8 text-xl font-bold leading-tight text-slate-950">{value}</p>
    </div>
  );
}

function CompanyButton({
  active,
  name,
  count,
  onClick,
}: {
  active: boolean;
  name: string;
  count: number;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center justify-between rounded-xl px-3 py-2.5 text-left text-sm font-bold transition ${
        active ? "bg-slate-950 text-white" : "text-slate-600 hover:bg-slate-50 hover:text-slate-950"
      }`}
    >
      <span>{name}</span>
      <span className={active ? "text-slate-300" : "text-slate-400"}>{count}</span>
    </button>
  );
}

function PolicyRow({
  policy,
  onEdit,
  onDelete,
}: {
  policy: Policy;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const coverageItems = COVERAGE_ORDER.filter((key) => policy.coverages[key]).map((key) => ({
    key,
    label: COVERAGE_LABELS[key].label,
    value: formatCoverage(key, policy.coverages[key] ?? 0),
  }));

  return (
    <article className="rounded-2xl border border-slate-100 bg-slate-50/70 p-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-lg bg-white px-2 py-1 text-xs font-bold text-slate-500 ring-1 ring-slate-200">
              {policy.role}
            </span>
            <span
              className={`rounded-lg px-2 py-1 text-xs font-bold ${
                policy.status === "有效" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"
              }`}
            >
              {policy.status}
            </span>
          </div>
          <h3 className="mt-2 truncate text-base font-bold text-slate-950">{policy.name}</h3>
          <p className="mt-1 text-sm text-slate-500">
            保單號碼 {policy.policyNo || "待補"}・生效日 {policy.effectiveDate || "待補"}
          </p>
          {policy.riders.length > 0 && (
            <p className="mt-2 text-sm leading-6 text-slate-500">
              附加：{policy.riders.join("、")}
            </p>
          )}
        </div>
        <div className="shrink-0 text-left md:text-right">
          <p className="text-xs font-bold text-slate-400">年繳保費</p>
          <p className="mt-1 text-lg font-bold text-slate-900">{formatMoney(policy.annualPremium)}</p>
          <div className="mt-3 flex gap-2 md:justify-end">
            <button
              onClick={onEdit}
              className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold text-slate-600 transition hover:border-teal-300 hover:text-teal-700"
            >
              編輯
            </button>
            <button
              onClick={onDelete}
              className="rounded-lg border border-rose-100 bg-white px-3 py-1.5 text-xs font-bold text-rose-500 transition hover:border-rose-200 hover:bg-rose-50"
            >
              刪除
            </button>
          </div>
        </div>
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {coverageItems.map((item) => (
          <div key={item.key} className="rounded-xl bg-white px-3 py-2 ring-1 ring-slate-100">
            <p className="text-xs font-bold text-slate-400">{item.label}</p>
            <p className="mt-1 text-sm font-bold text-slate-800">{item.value}</p>
          </div>
        ))}
      </div>
    </article>
  );
}

function PolicyFormDrawer({
  form,
  error,
  saving,
  onClose,
  onSubmit,
  onChange,
}: {
  form: PolicyFormState;
  error: string;
  saving: boolean;
  onClose: () => void;
  onSubmit: (event: FormEvent) => void;
  onChange: (next: PolicyFormState) => void;
}) {
  return (
    <div className="fixed inset-0 z-50 bg-slate-950/35">
      <div className="ml-auto flex h-full w-full max-w-2xl flex-col bg-white shadow-2xl">
        <div className="border-b border-slate-200 px-5 py-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-bold text-teal-700">{form.id ? "編輯保單" : "建立保單"}</p>
              <h2 className="mt-1 text-xl font-bold text-slate-950">
                {form.id ? "更新保單資料" : "新增一張保單"}
              </h2>
            </div>
            <button onClick={onClose} className="rounded-full px-3 py-2 text-sm font-bold text-slate-400 hover:bg-slate-100">
              關閉
            </button>
          </div>
        </div>

        <form onSubmit={onSubmit} className="flex-1 overflow-y-auto px-5 py-5">
          {error && <div className="mb-4 rounded-xl bg-rose-50 px-4 py-3 text-sm font-bold text-rose-600">{error}</div>}

          <div className="grid gap-4 md:grid-cols-2">
            <Field label="保險公司">
              <input
                value={form.company}
                onChange={(e) => onChange({ ...form, company: e.target.value })}
                className={INPUT_CLASS}
                placeholder="例如：國泰人壽"
              />
            </Field>
            <Field label="保單名稱">
              <input
                value={form.name}
                onChange={(e) => onChange({ ...form, name: e.target.value })}
                className={INPUT_CLASS}
                placeholder="例如：住院醫療健康保險"
              />
            </Field>
            <Field label="保單號碼">
              <input
                value={form.policyNo}
                onChange={(e) => onChange({ ...form, policyNo: e.target.value })}
                className={INPUT_CLASS}
                placeholder="可先留空"
              />
            </Field>
            <Field label="生效日">
              <input
                value={form.effectiveDate}
                onChange={(e) => onChange({ ...form, effectiveDate: e.target.value })}
                className={INPUT_CLASS}
                placeholder="YYYY/MM/DD"
              />
            </Field>
            <Field label="主約 / 附約">
              <select
                value={form.role}
                onChange={(e) => onChange({ ...form, role: e.target.value as Policy["role"] })}
                className={INPUT_CLASS}
              >
                <option value="主約">主約</option>
                <option value="附約">附約</option>
              </select>
            </Field>
            <Field label="資料狀態">
              <select
                value={form.status}
                onChange={(e) => onChange({ ...form, status: e.target.value as Policy["status"] })}
                className={INPUT_CLASS}
              >
                <option value="有效">有效</option>
                <option value="待補資料">待補資料</option>
              </select>
            </Field>
            <Field label="年繳保費">
              <input
                type="number"
                min={0}
                value={form.annualPremium}
                onChange={(e) => onChange({ ...form, annualPremium: e.target.value })}
                className={`${INPUT_CLASS} text-right tabular-nums`}
                placeholder="0"
              />
            </Field>
          </div>

          <div className="mt-6">
            <p className="text-sm font-bold text-slate-800">保障額度</p>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              {COVERAGE_ORDER.map((key) => (
                <Field key={key} label={`${COVERAGE_LABELS[key].label}（${COVERAGE_LABELS[key].unit}）`}>
                  <input
                    type="number"
                    min={0}
                    value={form.coverages[key]}
                    onChange={(e) =>
                      onChange({
                        ...form,
                        coverages: { ...form.coverages, [key]: e.target.value },
                      })
                    }
                    className={`${INPUT_CLASS} text-right tabular-nums`}
                    placeholder="0"
                  />
                </Field>
              ))}
            </div>
          </div>

          <Field label="附約 / 備註" className="mt-6">
            <textarea
              value={form.ridersText}
              onChange={(e) => onChange({ ...form, ridersText: e.target.value })}
              rows={4}
              className={`${INPUT_CLASS} resize-none`}
              placeholder="一行一個附約名稱，或用逗號分隔"
            />
          </Field>

          <div className="sticky bottom-0 -mx-5 mt-6 border-t border-slate-200 bg-white px-5 py-4">
            <div className="flex gap-3">
              <button
                type="submit"
                disabled={saving}
                className="flex-1 rounded-xl bg-slate-950 py-3 text-sm font-bold text-white transition hover:bg-slate-800 disabled:opacity-50"
              >
                {saving ? "儲存中..." : "儲存保單"}
              </button>
              <button
                type="button"
                onClick={onClose}
                className="rounded-xl border border-slate-200 px-5 py-3 text-sm font-bold text-slate-600 hover:bg-slate-50"
              >
                取消
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}

function Field({
  label,
  className = "",
  children,
}: {
  label: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <label className={`block ${className}`}>
      <span className="mb-2 block text-sm font-bold text-slate-700">{label}</span>
      {children}
    </label>
  );
}

function ConfirmDialog({
  policy,
  saving,
  onCancel,
  onConfirm,
}: {
  policy: Policy;
  saving: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/40 px-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-5 shadow-2xl">
        <p className="text-sm font-bold text-rose-600">刪除保單</p>
        <h2 className="mt-2 text-xl font-bold text-slate-950">確定刪除「{policy.name}」？</h2>
        <p className="mt-2 text-sm leading-6 text-slate-500">
          刪除後這張保單不會再進入保障健診、理賠比對與 AI 顧問回答。
        </p>
        <div className="mt-5 flex gap-3">
          <button
            onClick={onConfirm}
            disabled={saving}
            className="flex-1 rounded-xl bg-rose-600 py-3 text-sm font-bold text-white hover:bg-rose-700 disabled:opacity-50"
          >
            {saving ? "刪除中..." : "確認刪除"}
          </button>
          <button
            onClick={onCancel}
            className="flex-1 rounded-xl border border-slate-200 py-3 text-sm font-bold text-slate-600 hover:bg-slate-50"
          >
            取消
          </button>
        </div>
      </div>
    </div>
  );
}

function policyToForm(policy: Policy): PolicyFormState {
  return {
    id: policy.id,
    company: policy.company,
    name: policy.name,
    policyNo: policy.policyNo,
    role: policy.role,
    status: policy.status,
    annualPremium: String(policy.annualPremium || ""),
    effectiveDate: policy.effectiveDate,
    coverages: COVERAGE_ORDER.reduce((acc, key) => {
      acc[key] = policy.coverages[key] ? String(policy.coverages[key]) : "";
      return acc;
    }, {} as Record<CoverageKey, string>),
    ridersText: policy.riders.join("\n"),
  };
}

function formToPayload(form: PolicyFormState, profileId: string) {
  const coverages = COVERAGE_ORDER.reduce((acc, key) => {
    const value = Number(form.coverages[key]);
    if (value > 0) acc[key] = value;
    return acc;
  }, {} as Partial<Record<CoverageKey, number>>);

  return {
    profile_id: profileId,
    company_name: form.company.trim(),
    policy_name: form.name.trim(),
    policy_no: form.policyNo.trim(),
    role: form.role,
    status: form.status,
    annual_premium: Number(form.annualPremium) || 0,
    effective_date: form.effectiveDate.trim(),
    coverages,
    riders: form.ridersText
      .split(/[\n,，、]/)
      .map((item) => item.trim())
      .filter(Boolean),
  };
}
