"use client";
// 配置策略整頁 — 自由配 / 設定配 模式切換 + 結果呈現。
import React, { useEffect, useMemo, useState } from "react";
import { createAllocationApi, type AllocationApi } from "./api";
import { AllocationResult } from "./AllocationResult";
import { ConstraintEditor } from "./ConstraintEditor";
import { StrategyModeCards } from "./StrategyModeCards";
import {
  DEFAULT_CONSTRAINTS,
  type Allocation,
  type ClientInputs,
  type Constraint,
  type IndependentNeeds,
  type StrategyMode,
} from "./types";

interface Props {
  client: ClientInputs;
  api?: AllocationApi;
  baseUrl?: string;
  initialConstraints?: Constraint[];
  onNext?: (result: ViewModel) => void;
  nextLabel?: string;
}

export interface ViewModel {
  mode: StrategyMode;
  allocation: Allocation;
  needs?: IndependentNeeds | null;
  constraints: Constraint[];
  binding: string[];
  explanation?: string;
  feasible: boolean;
  error?: string | null;
}

export function AllocationStrategy({
  client,
  api,
  baseUrl = "/api/allocation",
  initialConstraints = DEFAULT_CONSTRAINTS,
  onNext,
  nextLabel = "查看退休規劃曲線 →",
}: Props) {
  const apiClient = useMemo(() => api ?? createAllocationApi(baseUrl), [api, baseUrl]);
  const [mode, setMode] = useState<StrategyMode>("free");
  const [constraints, setConstraints] = useState<Constraint[]>(initialConstraints);
  const [view, setView] = useState<ViewModel | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const constraintsKey = JSON.stringify(constraints);

  useEffect(() => {
    let ignore = false;

    (async () => {
      setLoading(true);
      setError(null);
      try {
        if (mode === "free") {
          const { needs, allocation } = await apiClient.estimate(client);
          if (ignore) return;
          setView({ mode, allocation, needs, constraints: [], binding: [], feasible: true });
        } else {
          const r = await apiClient.solve({ client, constraints });
          if (ignore) return;
          setView({
            mode,
            allocation: r.allocation,
            needs: r.needs,
            constraints,
            binding: r.binding,
            explanation: r.explanation,
            feasible: r.feasible,
            error: r.error,
          });
          if (!r.feasible && r.error) setError(r.error);
        }
      } catch (e) {
        if (!ignore) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!ignore) setLoading(false);
      }
    })();

    return () => { ignore = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, constraintsKey, client]);

  return (
    <div className="alloc-strategy">
      <header className="alloc-strategy__head">
        <div className="alloc-strategy__eyebrow">Allocation Strategy</div>
        <h2 className="alloc-strategy__title">選擇計算方式</h2>
        <p className="alloc-strategy__sub">
          不確定的話，選「讓系統幫我算」就好；有特定想法再切換到「我自己設條件」。
        </p>
      </header>

      <StrategyModeCards mode={mode} onChange={setMode} />

      <section className="alloc-card alloc-strategy__panel">
        <div className="alloc-strategy__panel-head">
          <div>
            <div className="alloc-strategy__eyebrow">
              {mode === "free" ? "系統估算配置" : "指定條件"}
            </div>
            <div className="alloc-strategy__panel-title">
              {mode === "free" ? "系統估算的 ABC 比例" : "在以下條件下求解"}
            </div>
          </div>
          {mode === "free" && <span className="alloc-chip">✦ 系統估算</span>}
          {loading && <span className="alloc-chip">計算中…</span>}
        </div>

        {error && <div className="alloc-error">⚠ {error}</div>}

        {mode === "cons" && (
          <ConstraintEditor constraints={constraints} onChange={setConstraints} />
        )}

        {view && view.feasible && (
          <AllocationResult
            allocation={view.allocation}
            needs={view.needs}
            constraints={mode === "cons" ? constraints : undefined}
            binding={view.binding}
            explanation={view.explanation}
          />
        )}

        {onNext && (
          <div className="alloc-strategy__actions">
            <button
              type="button"
              className="alloc-btn alloc-btn--primary"
              disabled={loading || !view || !view.feasible}
              onClick={() => view && onNext(view)}
            >
              {nextLabel}
            </button>
          </div>
        )}
      </section>
    </div>
  );
}

export default AllocationStrategy;
