// 設定配條件編輯:每條約束可開關 + 改數值。
import React from "react";
import type { Constraint } from "./types";

interface Props {
  constraints: Constraint[];
  onChange: (next: Constraint[]) => void;
}

const UNIT: Record<Constraint["kind"], string> = {
  floor: "%",
  cap: "%",
  must_include: "%",
  liquidity: " 個月",
};

const PREFIX: Record<Constraint["kind"], string> = {
  floor: "≥ ",
  cap: "≤ ",
  must_include: "≥ ",
  liquidity: "≥ ",
};

export function ConstraintEditor({ constraints, onChange }: Props) {
  const update = (id: string, patch: Partial<Constraint>) =>
    onChange(constraints.map((c) => (c.id === id ? { ...c, ...patch } : c)));

  return (
    <div className="alloc-constraints">
      {constraints.map((c) => (
        <div
          key={c.id}
          className={`alloc-constraint${c.active ? " is-active" : ""}`}
        >
          <label className="alloc-constraint__label">
            <input
              type="checkbox"
              checked={c.active}
              onChange={(e) => update(c.id, { active: e.target.checked })}
            />
            <span className="alloc-constraint__dot" aria-hidden />
            {c.label}
          </label>
          <span className="alloc-constraint__value">
            {c.kind === "must_include" && c.value <= 0 ? (
              "是"
            ) : (
              <>
                {PREFIX[c.kind]}
                <input
                  type="number"
                  className="alloc-constraint__input"
                  value={c.value}
                  min={0}
                  disabled={!c.active}
                  onChange={(e) =>
                    update(c.id, { value: Number(e.target.value) })
                  }
                />
                {UNIT[c.kind]}
              </>
            )}
          </span>
        </div>
      ))}
    </div>
  );
}

export default ConstraintEditor;
