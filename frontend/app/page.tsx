import Link from "next/link";

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 flex flex-col">
      <div className="flex-1 flex flex-col items-center justify-center px-4 py-16">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-900 mb-3">AI 保險顧問平台</h1>
          <p className="text-gray-500 text-lg">整合式金融保障規劃工具</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 w-full max-w-3xl">
          {/* Customer Portal */}
          <div className="bg-white rounded-2xl border border-blue-100 shadow-sm hover:shadow-md transition-shadow p-8 flex flex-col">
            <div className="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center mb-5">
              <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
            </div>
            <h2 className="text-xl font-semibold text-gray-900 mb-2">客戶入口</h2>
            <p className="text-gray-500 text-sm mb-6">一般民眾使用的 AI 保險諮詢服務</p>
            <ul className="space-y-2 text-sm text-gray-600 mb-8 flex-1">
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 bg-blue-400 rounded-full shrink-0" />
                AI 保險顧問對話
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 bg-blue-400 rounded-full shrink-0" />
                保險商品瀏覽
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 bg-blue-400 rounded-full shrink-0" />
                個人需求評估
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 bg-blue-400 rounded-full shrink-0" />
                理賠情境模擬
              </li>
            </ul>
            <Link
              href="/chat"
              className="w-full bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium py-3 rounded-xl text-center transition-colors"
            >
              進入客戶入口 →
            </Link>
          </div>

          {/* Advisor Portal */}
          <div className="bg-white rounded-2xl border border-emerald-100 shadow-sm hover:shadow-md transition-shadow p-8 flex flex-col">
            <div className="w-12 h-12 bg-emerald-100 rounded-xl flex items-center justify-center mb-5">
              <svg className="w-6 h-6 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
            </div>
            <h2 className="text-xl font-semibold text-gray-900 mb-2">業務員工具</h2>
            <p className="text-gray-500 text-sm mb-6">業務員使用的客戶管理與規劃後台</p>
            <ul className="space-y-2 text-sm text-gray-600 mb-8 flex-1">
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full shrink-0" />
                客戶資料建檔管理
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full shrink-0" />
                資產負債表填寫
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full shrink-0" />
                退休規劃問卷
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full shrink-0" />
                退休資產曲線試算
              </li>
            </ul>
            <Link
              href="/advisor"
              className="w-full bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium py-3 rounded-xl text-center transition-colors"
            >
              進入業務員工具 →
            </Link>
          </div>
        </div>

        <p className="mt-10 text-xs text-gray-400">
          本平台提供資訊參考，非正式保險建議，請諮詢合格業務員。
        </p>
      </div>
    </div>
  );
}
