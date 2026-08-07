// adapters.ts — extracted from src/pages/Studio/data/adapters.ts (toAccPoints only).
// Converts the simulator /forward endpoint's `yearly_assets` (assets_twd, in NT$)
// into the {y: 歲, v: 萬} shape the <AccumulationChart> SVG expects.

import type { AccPoint } from "./types";

/** simulator forward 的 yearly_assets（assets_twd 元）→ 圖用 {y:歲, v:萬}。 */
export function toAccPoints(
  yearly: { age: number; assets_twd: number }[],
): AccPoint[] {
  return yearly.map((p) => ({ y: p.age, v: Math.round(p.assets_twd / 10000) }));
}
