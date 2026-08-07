"use client";
// 自由配 / 設定配 兩張選擇卡。
import React from "react";
import type { StrategyMode } from "./types";

interface Props {
  mode: StrategyMode;
  onChange: (mode: StrategyMode) => void;
}

const CARDS: { mode: StrategyMode; tag: string; eng: string; desc: string; foot: string }[] = [
  {
    mode: "free",
    tag: "讓系統幫我算",
    eng: "AI 自動建議",
    desc: "系統根據您的年齡、退休年齡與風險偏好，自動估算儲蓄投資、保險保障、醫療長照三類的建議比例。不需手動設定任何條件。",
    foot: "適合剛開始規劃、不確定從哪裡下手的用戶",
  },
  {
    mode: "cons",
    tag: "我自己設條件",
    eng: "手動設定限制",
    desc: "您指定規則，例如「保險至少佔 25%」或「一定要含醫療保障」，系統在這些條件下算出最合適的配置。",
    foot: "適合已有想法、想確認方案可行性的用戶",
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
              {selected ? `✓ 已選擇 · ${card.foot}` : card.foot}
            </div>
          </button>
        );
      })}
    </div>
  );
}

export default StrategyModeCards;
