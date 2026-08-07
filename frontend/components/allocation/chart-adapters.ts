import type { AccPoint } from "./chart-types";

export function toAccPoints(yearly: { age: number; assets_twd: number }[]): AccPoint[] {
  return yearly.map((p) => ({ y: p.age, v: Math.round(p.assets_twd / 10000) }));
}
