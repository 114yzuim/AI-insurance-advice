import { Suspense } from "react";
import PoliciesApp from "@/components/policies-app";

export const metadata = { title: "我的保單 | AI 保險顧問" };

export default function PoliciesPage() {
  return (
    <Suspense fallback={<div className="p-8 text-sm text-slate-400">載入保單資料...</div>}>
      <PoliciesApp />
    </Suspense>
  );
}
