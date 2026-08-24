export type ApiError = { error: { code: string; message: string; request_id: string } };

function csrfToken(): string | undefined {
  if (typeof document === "undefined") return undefined;
  const raw = document.cookie.split("; ").find((c) => c.startsWith("pc_csrf="));
  return raw ? decodeURIComponent(raw.split("=").slice(1).join("=")) : undefined;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const csrf = csrfToken();
  if (csrf && !headers.has("X-CSRF-Token")) headers.set("X-CSRF-Token", csrf);
  const res = await fetch(path, { ...init, headers, credentials: "include" });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const err = data as ApiError;
    throw new Error(err?.error?.message || `Request failed (${res.status})`);
  }
  return data as T;
}

export type Account = {
  id: string;
  email: string;
  status: string;
  role: string;
  display_name: string | null;
  age_verification_status: string;
  balance: number;
  policy_versions: Record<string, string>;
};
