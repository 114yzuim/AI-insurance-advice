// 型別化 API client。對應 backend/allocation/router.py。

import type {
  AllocationResult,
  ClientInputs,
  EstimateResponse,
  SolveRequest,
} from "./types";

export interface AllocationApi {
  estimate(client: ClientInputs): Promise<EstimateResponse>;
  solve(req: SolveRequest): Promise<AllocationResult>;
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`POST ${url} failed: ${res.status} ${detail}`);
  }
  return (await res.json()) as T;
}

export function createAllocationApi(baseUrl = "/api/allocation"): AllocationApi {
  const base = baseUrl.replace(/\/$/, "");
  return {
    estimate: (client) => postJson<EstimateResponse>(`${base}/estimate`, client),
    solve: (req) => postJson<AllocationResult>(`${base}/solve`, req),
  };
}

export const allocationApi = createAllocationApi();
