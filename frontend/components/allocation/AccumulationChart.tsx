"use client";
import { useState } from "react";
import type { AccPoint } from "./chart-types";

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
  color = "#059669",
  color2,
  data2,
  height = 220,
  retireAge = 65,
}: AccumulationChartProps) {
  const w = 560, h = height, padL = 36, padR = 14, padT = 14, padB = 26;

  const [tooltip, setTooltip] = useState<{
    svgX: number;
    svgY: number;
    age: number;
    v1: number;
    v2?: number;
  } | null>(null);

  if (!data || data.length === 0) {
    return (
      <div
        style={{
          height,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#9ca3af",
          fontSize: 13,
        }}
      >
        尚無試算資料
      </div>
    );
  }

  const allVals = data.map((d) => d.v).concat(data2 ? data2.map((d) => d.v) : []);
  const rawMax = Math.max(0, ...allVals);
  const maxV = (rawMax > 0 ? rawMax : 1) * 1.05;
  const minY = Math.min(...data.map((d) => d.y)), maxY = Math.max(...data.map((d) => d.y));
  const ySpan = maxY - minY || 1;

  const sx = (y: number) => padL + ((y - minY) / ySpan) * (w - padL - padR);
  const sy = (v: number) => padT + (1 - v / maxV) * (h - padT - padB);

  const buildPath = (arr: AccPoint[]) =>
    arr.map((d, i) => `${i === 0 ? "M" : "L"}${sx(d.y)},${sy(d.v)}`).join(" ");
  const buildArea = (arr: AccPoint[]) =>
    `${buildPath(arr)} L${sx(arr[arr.length - 1].y)},${h - padB} L${sx(arr[0].y)},${h - padB} Z`;

  const peak = data.reduce((p, d) => (d.v > p.v ? d : p), data[0]);

  const nearest = (arr: AccPoint[], age: number) =>
    arr.reduce((prev, curr) =>
      Math.abs(curr.y - age) < Math.abs(prev.y - age) ? curr : prev
    );

  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const svgX = ((e.clientX - rect.left) / rect.width) * w;
    if (svgX < padL || svgX > w - padR) { setTooltip(null); return; }

    const age = minY + ((svgX - padL) / (w - padL - padR)) * ySpan;
    const pt1 = nearest(data, age);
    const pt2 = data2 && data2.length > 0 ? nearest(data2, pt1.y) : undefined;

    setTooltip({ svgX: sx(pt1.y), svgY: sy(pt1.v), age: pt1.y, v1: pt1.v, v2: pt2?.v });
  };

  // Tooltip box dimensions
  const hasTwo = !!(data2 && color2);
  const ttW = 108, ttH = hasTwo ? 50 : 38;

  return (
    <svg
      width="100%"
      viewBox={`0 0 ${w} ${h}`}
      preserveAspectRatio="none"
      style={{ display: "block", cursor: "crosshair" }}
      onMouseMove={handleMouseMove}
      onMouseLeave={() => setTooltip(null)}
    >
      <defs>
        <filter id="tt-shadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="1" stdDeviation="2" floodOpacity="0.13" />
        </filter>
      </defs>

      {/* grid lines + y labels */}
      {[0, 0.5, 1].map((t) => (
        <g key={t}>
          <line
            x1={padL} y1={padT + t * (h - padT - padB)}
            x2={w - padR} y2={padT + t * (h - padT - padB)}
            stroke="#e5e7eb" strokeDasharray="2 4"
          />
          <text
            x={padL - 6} y={padT + t * (h - padT - padB) + 3}
            textAnchor="end" fontSize="10" fill="#9ca3af" fontFamily="monospace"
          >
            {Math.round(maxV * (1 - t))}
          </text>
        </g>
      ))}

      {/* x-axis age labels */}
      {data.filter((_, i) => i % 2 === 0).map((d) => (
        <text
          key={d.y} x={sx(d.y)} y={h - 8}
          textAnchor="middle" fontSize="10" fill="#9ca3af" fontFamily="monospace"
        >
          {d.y}
        </text>
      ))}

      {/* retirement vertical line */}
      <line
        x1={sx(retireAge)} x2={sx(retireAge)} y1={padT} y2={h - padB}
        stroke="#d97706" strokeDasharray="3 3" strokeWidth="1"
      />
      <text
        x={sx(retireAge) + 4} y={padT + 12}
        fontSize="10" fill="#b45309" fontFamily="monospace" letterSpacing="0.04em"
      >
        {retireAge} 退休
      </text>

      {/* data2 area + line */}
      {data2 && color2 && (
        <>
          <path d={buildArea(data2)} fill={color2} opacity="0.10" />
          <path d={buildPath(data2)} fill="none" stroke={color2} strokeWidth="1.5" strokeDasharray="4 3" />
        </>
      )}

      {/* main area + line */}
      <path d={buildArea(data)} fill={color} opacity="0.14" />
      <path d={buildPath(data)} fill="none" stroke={color} strokeWidth="2" />

      {/* peak marker */}
      <circle cx={sx(peak.y)} cy={sy(peak.v)} r="4" fill={color} />
      <circle cx={sx(peak.y)} cy={sy(peak.v)} r="8" fill={color} opacity="0.15" />
      <text
        x={sx(peak.y)} y={sy(peak.v) - 12}
        textAnchor="middle" fontSize="11" fontWeight="600" fill={color} fontFamily="monospace"
      >
        {peak.v}萬
      </text>

      {/* y-axis label */}
      <text x={padL} y={padT - 2} fontSize="10" fill="#9ca3af" letterSpacing="0.08em">
        資產累積（萬元）
      </text>

      {/* hover tooltip */}
      {tooltip && (() => {
        const flipLeft = tooltip.svgX + ttW + 14 > w - padR;
        const ttX = flipLeft ? tooltip.svgX - ttW - 8 : tooltip.svgX + 8;
        const ttY = Math.max(padT, Math.min(tooltip.svgY - ttH / 2, h - padB - ttH));
        const pt2svgY = tooltip.v2 !== undefined ? sy(tooltip.v2) : null;

        return (
          <g>
            {/* crosshair vertical line */}
            <line
              x1={tooltip.svgX} y1={padT}
              x2={tooltip.svgX} y2={h - padB}
              stroke="#9ca3af" strokeWidth="1" strokeDasharray="2 3"
            />
            {/* dot on main line */}
            <circle
              cx={tooltip.svgX} cy={tooltip.svgY}
              r="5" fill={color} stroke="white" strokeWidth="2"
            />
            {/* dot on data2 line */}
            {data2 && color2 && pt2svgY !== null && (
              <circle
                cx={tooltip.svgX} cy={pt2svgY}
                r="5" fill={color2} stroke="white" strokeWidth="2"
              />
            )}
            {/* tooltip box */}
            <g transform={`translate(${ttX},${ttY})`}>
              <rect
                x={0} y={0} width={ttW} height={ttH}
                rx={5} ry={5}
                fill="white" stroke="#e5e7eb" strokeWidth="1"
                filter="url(#tt-shadow)"
              />
              <text x={8} y={14} fontSize="10" fontFamily="monospace" fontWeight="700" fill="#374151">
                {tooltip.age} 歲
              </text>
              <text x={8} y={28} fontSize="10" fontFamily="monospace" fill={color}>
                ● {tooltip.v1.toLocaleString()} 萬元
              </text>
              {hasTwo && tooltip.v2 !== undefined && (
                <text x={8} y={42} fontSize="10" fontFamily="monospace" fill={color2}>
                  ● {tooltip.v2.toLocaleString()} 萬元
                </text>
              )}
            </g>
          </g>
        );
      })()}
    </svg>
  );
}
