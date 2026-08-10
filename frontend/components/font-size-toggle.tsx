"use client";

import { useEffect, useState } from "react";

type FontSize = "small" | "medium" | "large";

const OPTIONS: { label: string; value: FontSize; scale: string }[] = [
  { label: "小", value: "small", scale: "100%" },
  { label: "中", value: "medium", scale: "112.5%" },
  { label: "大", value: "large", scale: "125%" },
];

function apply(size: FontSize) {
  const scale = OPTIONS.find((o) => o.value === size)?.scale ?? "100%";
  document.documentElement.style.fontSize = scale;
}

export default function FontSizeToggle() {
  const [size, setSize] = useState<FontSize>("small");

  useEffect(() => {
    window.setTimeout(() => {
      const saved = (localStorage.getItem("font-size") as FontSize | null) ?? "small";
      setSize(saved);
      apply(saved);
    }, 0);
  }, []);

  function handleClick(nextSize: FontSize) {
    setSize(nextSize);
    apply(nextSize);
    localStorage.setItem("font-size", nextSize);
  }

  return (
    <div className="flex shrink-0 items-center gap-1 rounded-full bg-slate-100 p-1" aria-label="字級切換">
      {OPTIONS.map((option) => (
        <button
          key={option.value}
          onClick={() => handleClick(option.value)}
          className={`h-8 w-8 rounded-full text-sm font-bold transition ${
            size === option.value
              ? "bg-white text-slate-900 shadow-sm"
              : "text-slate-400 hover:text-slate-700"
          }`}
          title={`字級：${option.label}`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
