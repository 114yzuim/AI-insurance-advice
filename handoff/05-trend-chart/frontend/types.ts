/* ───────────────────────────────────────────────────────────────
   05-trend-chart — frontend types
   Sliced from the live app's src/pages/Studio/data/types.ts.
   AccumulationChart.tsx renders an array of AccPoint.
   ─────────────────────────────────────────────────────────────── */

/** 資產累積曲線單點。y=歲，v=萬（新台幣萬元）。 */
export interface AccPoint {
  y: number;
  v: number;
}
