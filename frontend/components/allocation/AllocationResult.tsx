"use client";
// 配置結果呈現:甜甜圈 + 長條 + 約束狀態 + (可選)Layer 1 個別需求。
import React, { useState } from "react";
import {
  BUCKET_META,
  type Allocation,
  type Bucket,
  type Constraint,
  type IndependentNeeds,
} from "./types";

interface Props {
  allocation: Allocation;
  needs?: IndependentNeeds | null;
  constraints?: Constraint[];
  binding?: string[];
  explanation?: string;
}

const BUCKETS: Bucket[] = ["A", "B", "C"];
const key = (b: Bucket) => b.toLowerCase() as "a" | "b" | "c";

function Donut({ allocation }: { allocation: Allocation }) {
  const r = 54;
  const sw = 18;
  const circ = 2 * Math.PI * r;
  let offset = 0;
  return (
    <svg viewBox="0 0 140 140" width={150} height={150} className="alloc-donut">
      <g transform="rotate(-90 70 70)">
        {BUCKETS.map((b) => {
          const len = (allocation[key(b)] / 100) * circ;
          const node = (
            <circle
              key={b}
              cx={70}
              cy={70}
              r={r}
              fill="none"
              stroke={BUCKET_META[b].cssVar}
              strokeWidth={sw}
              strokeDasharray={`${len} ${circ - len}`}
              strokeDashoffset={-offset}
            />
          );
          offset += len;
          return node;
        })}
      </g>
      <text x={70} y={66} textAnchor="middle" className="alloc-donut__big">
        100%
      </text>
      <text x={70} y={86} textAnchor="middle" className="alloc-donut__small">
        ABC 配置
      </text>
    </svg>
  );
}

export function AllocationResult({
  allocation,
  needs,
  constraints,
  binding = [],
  explanation,
}: Props) {
  const [showNeeds, setShowNeeds] = useState(false);
  const activeConstraints = (constraints ?? []).filter((c) => c.active);

  return (
    <div className="alloc-result">
      <div className="alloc-result__body">
        <Donut allocation={allocation} />

        <div className="alloc-bars">
          {BUCKETS.map((b) => {
            const meta = BUCKET_META[b];
            const pct = allocation[key(b)];
            return (
              <div key={b} className="alloc-bar">
                <div className="alloc-bar__head">
                  <span className="alloc-bar__name">
                    <span
                      className="alloc-bar__chip"
                      style={{ background: meta.cssVar }}
                    >
                      {b}
                    </span>
                    {meta.label}
                  </span>
                  <span className="alloc-bar__sub">{meta.sub}</span>
                  <span className="alloc-bar__pct">{pct}%</span>
                </div>
                <div className="alloc-bar__track">
                  <div
                    className="alloc-bar__fill"
                    style={{ width: `${pct}%`, background: meta.cssVar }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {activeConstraints.length > 0 && (
        <div className="alloc-binding">
          {activeConstraints.map((c) => (
            <span
              key={c.id}
              className={`alloc-binding__tag${
                binding.includes(c.id) ? " is-binding" : ""
              }`}
            >
              {c.label}
              {c.bucket && c.value > 0 ? `（${c.value}%）` : ""}
            </span>
          ))}
        </div>
      )}

      {explanation && <p className="alloc-result__note">{explanation}</p>}

      {needs && (
        <div className="alloc-needs">
          <button
            type="button"
            className="alloc-needs__toggle"
            onClick={() => setShowNeeds((s) => !s)}
          >
            {showNeeds ? "▾" : "▸"} 個別分析（純算各桶需求,不加總 100）
          </button>
          {showNeeds && (
            <div className="alloc-needs__grid">
              {BUCKETS.map((b) => (
                <div key={b} className="alloc-needs__item">
                  <span className="alloc-needs__bucket">{b}</span>
                  <span className="alloc-needs__num">
                    {needs[key(b)].toFixed(1)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default AllocationResult;
