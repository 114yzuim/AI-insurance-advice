import { Suspense } from "react";
import ClaimsApp from "@/components/claims-app";

export const metadata = { title: "理賠服務中心 | AI 保險顧問" };

export default function ClaimsPage() {
  return (
    <Suspense fallback={<div className="p-8 text-sm text-slate-400">載入理賠服務...</div>}>
      <ClaimsApp />
    </Suspense>
  );
}
