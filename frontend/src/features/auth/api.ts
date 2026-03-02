import { API_BASE_URL, ApiUnauthorizedError } from "@/features/api/client";

export type AuthSession = {
  authenticated: true;
  username: string;
};

async function parseJsonSafe(res: Response) {
  const text = await res.text();
  try {
    return text ? JSON.parse(text) : null;
  } catch {
    return { raw: text };
  }
}

export async function getAuthSession(): Promise<AuthSession> {
  const res = await fetch(`${API_BASE_URL}/auth/session`, {
    cache: "no-store",
    credentials: "include",
  });

  if (res.status === 401) {
    throw new ApiUnauthorizedError("unauthenticated");
  }

  if (!res.ok) {
    throw new Error(`GET /auth/session -> ${res.status}`);
  }

  return res.json();
}

export async function loginAdmin(username: string, password: string): Promise<AuthSession> {
  const res = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    credentials: "include",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ username, password }),
  });

  if (res.status === 401) {
    throw new ApiUnauthorizedError("invalid_credentials");
  }

  if (!res.ok) {
    const body = await parseJsonSafe(res);
    throw new Error(`POST /auth/login -> ${res.status} ${JSON.stringify(body)}`);
  }

  return res.json();
}

export async function logoutAdmin(): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/auth/logout`, {
    method: "POST",
    credentials: "include",
  });

  if (!res.ok && res.status !== 204) {
    throw new Error(`POST /auth/logout -> ${res.status}`);
  }
}
