// 自由配 / 設定配 兩張選擇卡。對應原型 AllocScreen 上半部。
import React from "react";
import type { StrategyMode } from "./types";

interface Props {
  mode: StrategyMode;
  onChange: (mode: StrategyMode) => void;
}

const CARDS: { mode: StrategyMode; tag: string; eng: string; desc: string }[] = [
  {
    mode: "free",
    tag: "自由配",
    eng: "Free Allocation",
    desc: "系統依客戶資產 / 年期 / 需求自行估算 ABC 比例,作為一個基準起點。",
  },
  {
    mode: "cons",
    tag: "設定配",
    eng: "Constrained Allocation",
    desc: "保經先指定條件——保險佔比下限、必含醫療、特定上限——再讓系統在這個籠子裡求解。",
  },
];

export function StrategyModeCards({ mode, onChange }: Props) {
  return (
    <div className="alloc-mode-cards">
      {CARDS.map((card) => {
        const selected = mode === card.mode;
        return (
          <button
            key={card.mode}
            type="button"
            className={`alloc-card alloc-mode-card${selected ? " is-selected" : ""}`}
            aria-pressed={selected}
            onClick={() => onChange(card.mode)}
          >
            <div className="alloc-mode-card__head">
              <span className="alloc-mode-card__tag">{card.tag}</span>
              <span className="alloc-mode-card__eng">{card.eng}</span>
            </div>
            <p className="alloc-mode-card__desc">{card.desc}</p>
            <div className="alloc-mode-card__foot">
              {selected ? "✓ 已選擇" : "點擊選擇"}
            </div>
          </button>
        );
      })}
    </div>
  );
}

export default StrategyModeCards;
