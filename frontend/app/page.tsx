import Link from "next/link";

const highlights = [
  { label: "商品查詢", value: "先找商品，再決定是否建立保單" },
  { label: "AI 推薦", value: "依客戶條件比較合適方案" },
  { label: "全流程串接", value: "保單管理與理賠中心都可回查商品" },
];

const modules = [
  {
    title: "查看商品清單",
    text: "瀏覽已收錄的保險商品，依保險公司、商品類別或關鍵字搜尋，也可勾選商品請 AI 協助比較。",
    href: "/products",
    primary: true,
  },
  {
    title: "建立與管理保單",
    text: "已確認商品或已有客戶資料時，可直接建立保單、上傳文件並整理保障缺口。",
    href: "/policies",
  },
  {
    title: "理賠中心",
    text: "處理理賠資料、文件與預估結果；仍可從導覽列回到商品查詢與推薦。",
    href: "/claims",
  },
];

const recommendationSteps = [
  "輸入客戶年齡、預算、保障目標或指定公司",
  "查詢商品並加入比較清單",
  "請 AI 產出推薦理由、注意事項與下一步建議",
];

export default function Home() {
  return (
    <div className="min-h-full bg-[#f7faf8] text-slate-900">
      <section className="mx-auto grid min-h-full w-full max-w-6xl grid-cols-1 gap-10 px-5 py-8 md:grid-cols-[1.05fr_0.95fr] md:px-8 md:py-12">
        <div className="flex flex-col justify-center">
          <div className="mb-6 inline-flex w-fit items-center gap-2 rounded-full border border-teal-200 bg-white px-3 py-1.5 text-sm font-medium text-teal-700 shadow-sm">
            <span className="h-2 w-2 rounded-full bg-emerald-400" />
            AI 保險顧問系統
          </div>

          <h1 className="max-w-2xl text-4xl font-bold leading-tight tracking-normal text-slate-950 md:text-6xl">
            先看有哪些商品，再找到適合你的保險
          </h1>
          <p className="mt-5 max-w-xl text-lg leading-8 text-slate-600">
            點擊「查看商品清單」，即可瀏覽已收錄的保險商品，依公司、類別或關鍵字快速查找。找到感興趣的商品後，還能請 AI 依你的需求協助比較。
          </p>

          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link
              href="/products"
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-teal-700 px-6 py-3 text-base font-semibold text-white shadow-lg shadow-teal-100 transition hover:-translate-y-0.5 hover:bg-teal-800 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-teal-700"
            >
              查看商品清單
              <span aria-hidden="true">→</span>
            </Link>
            <Link
              href="/policies"
              className="inline-flex items-center justify-center rounded-xl border border-slate-200 bg-white px-6 py-3 text-base font-semibold text-slate-800 transition hover:-translate-y-0.5 hover:border-teal-300 hover:text-teal-700"
            >
              建立保單
            </Link>
            <Link
              href="/claims"
              className="inline-flex items-center justify-center rounded-xl border border-slate-200 bg-white px-6 py-3 text-base font-semibold text-slate-800 transition hover:-translate-y-0.5 hover:border-teal-300 hover:text-teal-700"
            >
              理賠中心
            </Link>
          </div>

          <div className="mt-10 grid max-w-xl grid-cols-1 gap-3 sm:grid-cols-3">
            {highlights.map((item) => (
              <div key={item.label} className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-100">
                <p className="text-xl font-bold text-teal-700">{item.label}</p>
                <p className="mt-1 text-sm leading-5 text-slate-500">{item.value}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="flex items-center">
          <div className="w-full rounded-[2rem] border border-white bg-white/80 p-4 shadow-2xl shadow-teal-100 backdrop-blur">
            <div className="rounded-[1.5rem] bg-[#eaf7f1] p-5">
              <div className="mb-5">
                <p className="text-sm font-semibold text-teal-700">首頁主要工作區</p>
                <h2 className="mt-1 text-2xl font-bold leading-tight text-slate-950">
                  商品檢索、推薦、保單與理賠分流
                </h2>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  使用者不需要先進入理賠中心才能看商品資料。商品查詢與推薦是第一層功能，其他模組則保留給已確定的保單建立或理賠處理情境。
                </p>
              </div>

              <div className="grid gap-3">
                {modules.map((module) => (
                  <Link
                    key={module.title}
                    href={module.href}
                    className={`block rounded-2xl p-4 shadow-sm ring-1 transition hover:-translate-y-0.5 ${
                      module.primary
                        ? "bg-slate-950 text-white ring-slate-950"
                        : "bg-white text-slate-900 ring-slate-100 hover:ring-teal-200"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <h3 className="text-base font-bold">{module.title}</h3>
                      <span className={module.primary ? "text-teal-200" : "text-teal-700"}>前往</span>
                    </div>
                    <p className={`mt-2 text-sm leading-6 ${module.primary ? "text-slate-200" : "text-slate-500"}`}>
                      {module.text}
                    </p>
                  </Link>
                ))}
              </div>

              <div className="mt-5 rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-100">
                <h3 className="text-sm font-bold text-slate-950">推薦流程</h3>
                <div className="mt-3 grid gap-3">
                  {recommendationSteps.map((step, index) => (
                    <div key={step} className="flex gap-3">
                      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-teal-100 text-sm font-bold text-teal-700">
                        {index + 1}
                      </span>
                      <p className="text-sm leading-6 text-slate-600">{step}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
