export const API_BASE_URL =
  process.env.NEXT_PUBLIC_BACKEND_BASE_URL || "http://localhost:8000";

export class ApiUnauthorizedError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ApiUnauthorizedError";
  }
}

async function parseJsonSafe(res: Response) {
  const text = await res.text();
  try {
    return text ? JSON.parse(text) : null;
  } catch {
    return { raw: text };
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    cache: "no-store",
    credentials: "include",
  });
  if (!res.ok) {
    const body = await parseJsonSafe(res);
    if (res.status === 401) {
      throw new ApiUnauthorizedError(`GET ${path} -> ${res.status}`);
    }
    throw new Error(`GET ${path} -> ${res.status} ${JSON.stringify(body)}`);
  }
  return res.json();
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    credentials: "include",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    const payload = await parseJsonSafe(res);
    if (res.status === 401) {
      throw new ApiUnauthorizedError(`POST ${path} -> ${res.status}`);
    }
    throw new Error(`POST ${path} -> ${res.status} ${JSON.stringify(payload)}`);
  }
  return res.json();
}

export async function apiPatch<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    credentials: "include",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    const payload = await parseJsonSafe(res);
    if (res.status === 401) {
      throw new ApiUnauthorizedError(`PATCH ${path} -> ${res.status}`);
    }
    throw new Error(`PATCH ${path} -> ${res.status} ${JSON.stringify(payload)}`);
  }
  return res.json();
}
