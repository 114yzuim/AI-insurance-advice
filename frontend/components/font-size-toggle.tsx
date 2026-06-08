"use client";

import { useState, useEffect } from "react";

type FontSize = "small" | "medium" | "large";

const OPTIONS: { label: string; value: FontSize; scale: string }[] = [
  { label: "小", value: "small", scale: "112.5%" },
  { label: "中", value: "medium", scale: "131.25%" },
  { label: "大", value: "large", scale: "175%" },
];

function apply(size: FontSize) {
  const scale = OPTIONS.find((o) => o.value === size)?.scale ?? "100%";
  document.documentElement.style.fontSize = scale;
}

export default function FontSizeToggle() {
  const [size, setSize] = useState<FontSize>("small");

  useEffect(() => {
    const saved = (localStorage.getItem("font-size") as FontSize) ?? "small";
    setSize(saved);
    apply(saved);
  }, []);

  function handleClick(s: FontSize) {
    setSize(s);
    apply(s);
    localStorage.setItem("font-size", s);
  }

  return (
    <div className="flex items-center gap-0.5 bg-gray-100 rounded-lg p-0.5">
      {OPTIONS.map((o) => (
        <button
          key={o.value}
          onClick={() => handleClick(o.value)}
          className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
            size === o.value
              ? "bg-white text-gray-800 shadow-sm"
              : "text-gray-400 hover:text-gray-600"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
