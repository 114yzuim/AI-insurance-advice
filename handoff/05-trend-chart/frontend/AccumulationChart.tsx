// AccumulationChart.tsx — 退休前累積 / 退休後提領 視覺曲線（移植自 O/ui.jsx）
// 退休標記線 retireAge 取代 O 寫死的 65，預設 65。

import type { AccPoint } from "../data/types";

export interface AccumulationChartProps {
  data: AccPoint[];
  color?: string;
  data2?: AccPoint[];
  color2?: string;
  height?: number;
  retireAge?: number;
}

export default function AccumulationChart({
  data,
  color = "var(--green-600)",
  color2,
  data2,
  height = 220,
  retireAge = 65,
}: AccumulationChartProps) {
  const w = 560, h = height, padL = 36, padR = 14, padT = 14, padB = 26;

  // 防呆：無資料（forward 尚未載入 / 失敗 / 客戶無財務資料）→ 顯示佔位，不畫 NaN 路徑。
  if (!data || data.length === 0) {
    return (
      <div
        style={{
          height,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--ink-3)",
          fontSize: 13,
        }}
      >
        尚無試算資料（請確認客戶財務資料）
      </div>
    );
  }

  const allVals = data.map((d) => d.v).concat(data2 ? data2.map((d) => d.v) : []);
  // maxV 至少為 1，避免資產全為 0 時除以 0 產生 NaN。
  const rawMax = Math.max(0, ...allVals);
  const maxV = (rawMax > 0 ? rawMax : 1) * 1.05;
  const minY = Math.min(...data.map((d) => d.y)), maxY = Math.max(...data.map((d) => d.y));
  const ySpan = maxY - minY || 1; // 避免單點時除以 0

  const sx = (y: number) => padL + ((y - minY) / ySpan) * (w - padL - padR);
  const sy = (v: number) => padT + (1 - v / maxV) * (h - padT - padB);

  const buildPath = (arr: AccPoint[]) =>
    arr.map((d, i) => `${i === 0 ? "M" : "L"}${sx(d.y)},${sy(d.v)}`).join(" ");
  const buildArea = (arr: AccPoint[]) =>
    `${buildPath(arr)} L${sx(arr[arr.length - 1].y)},${h - padB} L${sx(arr[0].y)},${h - padB} Z`;

  // Find peak (retirement age = max)
  const peak = data.reduce((p, d) => (d.v > p.v ? d : p), data[0]);

  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ display: "block" }}>
      {/* gridlines */}
      {[0, 0.5, 1].map((t) => (
        <g key={t}>
          <line
            x1={padL}
            y1={padT + t * (h - padT - padB)}
            x2={w - padR}
            y2={padT + t * (h - padT - padB)}
            stroke="var(--line)"
            strokeDasharray="2 4"
          />
          <text
            x={padL - 6}
            y={padT + t * (h - padT - padB) + 3}
            textAnchor="end"
            fontSize="10"
            fill="var(--ink-3)"
            fontFamily="var(--font-mono)"
          >
            {Math.round(maxV * (1 - t))}
          </text>
        </g>
      ))}
      {/* x-axis labels */}
      {data
        .filter((_, i) => i % 2 === 0)
        .map((d) => (
          <text
            key={d.y}
            x={sx(d.y)}
            y={h - 8}
            textAnchor="middle"
            fontSize="10"
            fill="var(--ink-3)"
            fontFamily="var(--font-mono)"
          >
            {d.y}
          </text>
        ))}

      {/* Retirement marker line */}
      <line
        x1={sx(retireAge)}
        x2={sx(retireAge)}
        y1={padT}
        y2={h - padB}
        stroke="var(--gold-500)"
        strokeDasharray="3 3"
        strokeWidth="1"
      />
      <text
        x={sx(retireAge) + 4}
        y={padT + 12}
        fontSize="10"
        fill="var(--gold-700)"
        fontFamily="var(--font-mono)"
        letterSpacing="0.04em"
      >
        {retireAge} 退休
      </text>

      {/* Comparison fill (modeII) */}
      {data2 && (
        <>
          <path d={buildArea(data2)} fill={color2} opacity="0.10" />
          <path d={buildPath(data2)} fill="none" stroke={color2} strokeWidth="1.5" strokeDasharray="4 3" />
        </>
      )}

      {/* Primary fill */}
      <path d={buildArea(data)} fill={color} opacity="0.14" />
      <path d={buildPath(data)} fill="none" stroke={color} strokeWidth="2" />

      {/* Peak dot */}
      <circle cx={sx(peak.y)} cy={sy(peak.v)} r="4" fill={color} />
      <circle cx={sx(peak.y)} cy={sy(peak.v)} r="8" fill={color} opacity="0.15" />
      <text
        x={sx(peak.y)}
        y={sy(peak.v) - 12}
        textAnchor="middle"
        fontSize="11"
        fontWeight="600"
        fill={color}
        fontFamily="var(--font-mono)"
      >
        {peak.v}萬
      </text>

      <text x={padL} y={padT - 2} fontSize="10" fill="var(--ink-3)" letterSpacing="0.08em">
        資產累積（萬元）
      </text>
    </svg>
  );
}
