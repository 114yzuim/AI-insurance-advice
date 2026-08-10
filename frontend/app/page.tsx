import Link from "next/link";

const highlights = [
  { label: "3 分鐘", value: "快速理解保障缺口" },
  { label: "AI", value: "整理保單與需求" },
  { label: "清楚", value: "用白話說明下一步" },
];

const customerFeatures = ["AI 保險問答", "商品條款整理", "保障健檢", "理賠文件協助"];
const advisorFeatures = ["客戶資料管理", "資產負債盤點", "問卷需求分析", "退休配置試算"];

export default function Home() {
  return (
    <div className="min-h-full bg-[#f7faf8] text-slate-900">
      <section className="mx-auto grid min-h-full w-full max-w-6xl grid-cols-1 gap-10 px-5 py-8 md:grid-cols-[1.05fr_0.95fr] md:px-8 md:py-12">
        <div className="flex flex-col justify-center">
          <div className="mb-6 inline-flex w-fit items-center gap-2 rounded-full border border-teal-200 bg-white px-3 py-1.5 text-sm font-medium text-teal-700 shadow-sm">
            <span className="h-2 w-2 rounded-full bg-emerald-400" />
            AI 保險顧問平台
          </div>

          <h1 className="max-w-2xl text-4xl font-bold leading-tight tracking-normal text-slate-950 md:text-6xl">
            讓保險規劃變得好懂、好問、好決定
          </h1>
          <p className="mt-5 max-w-xl text-lg leading-8 text-slate-600">
            從保單解讀、保障健檢到顧問工作台，把複雜資料整理成清楚建議，讓使用者知道現在最該處理什麼。
          </p>

          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link
              href="/chat"
              className="inline-flex items-center justify-center rounded-xl bg-slate-950 px-6 py-3 text-base font-semibold text-white shadow-lg shadow-slate-200 transition hover:-translate-y-0.5 hover:bg-slate-800"
            >
              開始 AI 諮詢
            </Link>
            <Link
              href="/health-check"
              className="inline-flex items-center justify-center rounded-xl border border-slate-200 bg-white px-6 py-3 text-base font-semibold text-slate-800 transition hover:-translate-y-0.5 hover:border-teal-300 hover:text-teal-700"
            >
              做保障健檢
            </Link>
          </div>

          <div className="mt-10 grid max-w-xl grid-cols-3 gap-3">
            {highlights.map((item) => (
              <div key={item.label} className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-100">
                <p className="text-2xl font-bold text-teal-700">{item.label}</p>
                <p className="mt-1 text-sm leading-5 text-slate-500">{item.value}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="flex items-center">
          <div className="w-full rounded-[2rem] border border-white bg-white/80 p-4 shadow-2xl shadow-teal-100 backdrop-blur">
            <div className="rounded-[1.5rem] bg-[#eaf7f1] p-5">
              <div className="mb-5 flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold text-teal-700">今日規劃重點</p>
                  <h2 className="mt-1 text-2xl font-bold text-slate-950">先補強醫療與失能風險</h2>
                </div>
                <div className="rounded-2xl bg-amber-300 px-3 py-2 text-sm font-bold text-amber-950">
                  優先
                </div>
              </div>

              <div className="grid gap-3">
                <VisualCard title="保障缺口" value="72%" color="bg-rose-100 text-rose-700" />
                <VisualCard title="預算可行性" value="良好" color="bg-emerald-100 text-emerald-700" />
                <VisualCard title="下一步" value="比較 3 張保單" color="bg-sky-100 text-sky-700" />
              </div>

              <div className="mt-5 grid grid-cols-2 gap-3">
                <PortalCard
                  title="一般使用者"
                  description="問問題、看商品、做健檢。"
                  href="/chat"
                  features={customerFeatures}
                  accent="bg-teal-500"
                />
                <PortalCard
                  title="保險顧問"
                  description="管理客戶與產出建議。"
                  href="/advisor"
                  features={advisorFeatures}
                  accent="bg-amber-400"
                />
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

function VisualCard({ title, value, color }: { title: string; value: string; color: string }) {
  return (
    <div className="flex items-center justify-between rounded-2xl bg-white p-4 shadow-sm">
      <span className="text-sm font-medium text-slate-500">{title}</span>
      <span className={`rounded-full px-3 py-1 text-sm font-bold ${color}`}>{value}</span>
    </div>
  );
}

function PortalCard({
  title,
  description,
  href,
  features,
  accent,
}: {
  title: string;
  description: string;
  href: string;
  features: string[];
  accent: string;
}) {
  return (
    <Link href={href} className="group rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-100 transition hover:-translate-y-1 hover:shadow-md">
      <span className={`mb-4 block h-2 w-12 rounded-full ${accent}`} />
      <h3 className="text-lg font-bold text-slate-950">{title}</h3>
      <p className="mt-1 text-sm leading-6 text-slate-500">{description}</p>
      <ul className="mt-4 space-y-2">
        {features.slice(0, 3).map((feature) => (
          <li key={feature} className="flex items-center gap-2 text-sm text-slate-600">
            <span className="h-1.5 w-1.5 rounded-full bg-slate-300" />
            {feature}
          </li>
        ))}
      </ul>
      <p className="mt-5 text-sm font-semibold text-teal-700">進入服務</p>
    </Link>
  );
}
