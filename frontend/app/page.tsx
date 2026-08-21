import Link from "next/link";

const highlights = [
  { label: "8 張", value: "已建立保單" },
  { label: "5 家", value: "保險公司" },
  { label: "一輩子", value: "長期保單記憶" },
];

const coverageItems = [
  { title: "壽險保障", value: "1,500 萬", color: "bg-sky-100 text-sky-700" },
  { title: "癌症保障", value: "300 萬", color: "bg-rose-100 text-rose-700" },
  { title: "重大傷病", value: "200 萬", color: "bg-emerald-100 text-emerald-700" },
  { title: "實支實付", value: "40 萬", color: "bg-amber-100 text-amber-700" },
];

const flows = [
  { title: "我的保單", text: "集中管理主約、附約、保額與保費。" },
  { title: "保障健診", text: "用現有保障扣出真正缺口。" },
  { title: "理賠中心", text: "用文件與保單資料比對可申請項目。" },
];

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
            你的保單，AI 幫你記一輩子
          </h1>
          <p className="mt-5 max-w-xl text-lg leading-8 text-slate-600">
            把所有保單集中管理，從保障健診、保單條款到醫療理賠，需要的時候，AI 幫你找出真正能用的保障。
          </p>

          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link
              href="/policies"
              className="inline-flex items-center justify-center rounded-xl bg-slate-950 px-6 py-3 text-base font-semibold text-white shadow-lg shadow-slate-200 transition hover:-translate-y-0.5 hover:bg-slate-800"
            >
              + 建立我的保單資料
            </Link>
            <Link
              href="/claims"
              className="inline-flex items-center justify-center rounded-xl border border-slate-200 bg-white px-6 py-3 text-base font-semibold text-slate-800 transition hover:-translate-y-0.5 hover:border-teal-300 hover:text-teal-700"
            >
              前往理賠中心
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
              <div className="mb-5">
                <p className="text-sm font-semibold text-teal-700">個人保障總覽</p>
                <h2 className="mt-1 text-2xl font-bold leading-tight text-slate-950">
                  AI 先懂你的保單，再回答你的問題
                </h2>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  當保單、條款、家庭成員與理賠紀錄被整理成同一份 Insurance Profile，AI 才能給出真正個人化的下一步。
                </p>
              </div>

              <div className="grid gap-3">
                {coverageItems.map((item) => (
                  <VisualCard key={item.title} title={item.title} value={item.value} color={item.color} />
                ))}
              </div>

              <div className="mt-5 grid gap-3">
                {flows.map((flow, index) => (
                  <div key={flow.title} className="flex gap-3 rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-100">
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-slate-950 text-sm font-bold text-white">
                      {index + 1}
                    </span>
                    <div>
                      <h3 className="text-sm font-bold text-slate-950">{flow.title}</h3>
                      <p className="mt-1 text-sm leading-6 text-slate-500">{flow.text}</p>
                    </div>
                  </div>
                ))}
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
