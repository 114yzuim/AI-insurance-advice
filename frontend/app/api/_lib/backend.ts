const backendUrl = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

export const BACKEND = backendUrl.replace(/\/$/, "");
