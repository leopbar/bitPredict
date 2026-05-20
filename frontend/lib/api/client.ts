const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "dev-secret-key";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public data?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  auth = true,
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(auth && { "X-API-Key": API_KEY }),
    ...(options.headers as Record<string, string>),
  };

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let data: unknown;
    try {
      data = await response.json();
    } catch {
      data = null;
    }
    const message =
      typeof data === "object" && data !== null && "detail" in data
        ? String((data as { detail: unknown }).detail)
        : `HTTP ${response.status}`;
    throw new ApiError(response.status, message, data);
  }

  if (response.status === 204) return undefined as T;

  return response.json() as Promise<T>;
}

export const apiClient = {
  get: <T>(path: string, auth = true) => request<T>(path, { method: "GET" }, auth),
  post: <T>(path: string, body?: unknown, auth = true) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }, auth),
  put: <T>(path: string, body?: unknown, auth = true) =>
    request<T>(path, { method: "PUT", body: body ? JSON.stringify(body) : undefined }, auth),
  delete: <T>(path: string, auth = true) => request<T>(path, { method: "DELETE" }, auth),

  downloadBlob: async (path: string, filename: string): Promise<void> => {
    const response = await fetch(`${API_URL}${path}`, {
      headers: { "X-API-Key": API_KEY },
    });
    if (!response.ok) throw new ApiError(response.status, `HTTP ${response.status}`);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  },
};
