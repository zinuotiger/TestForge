/** API 请求封装 — 自动携带 Token + 401 自动刷新/跳转登录 */

const TOKEN_KEY = "testforge_access_token";
const REFRESH_KEY = "testforge_refresh_token";
const USER_KEY = "testforge_user";

export interface AuthUser {
  username: string;
  role: string;
  email?: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: AuthUser;
}

// ============ Token 存储 ============

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}

export function setTokens(access: string, refresh: string) {
  localStorage.setItem(TOKEN_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
  localStorage.removeItem(USER_KEY);
}

export function setUser(user: AuthUser) {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function getUser(): AuthUser | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function isLoggedIn(): boolean {
  return !!getToken();
}

// ============ 请求封装 ============

let isRefreshing = false;
let refreshPromise: Promise<boolean> | null = null;

async function refreshToken(): Promise<boolean> {
  const refresh = getRefreshToken();
  if (!refresh) return false;

  try {
    const res = await fetch("/api/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    localStorage.setItem(TOKEN_KEY, data.access_token);
    return true;
  } catch {
    return false;
  }
}

export async function apiFetch(
  url: string,
  options: RequestInit = {},
): Promise<Response> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  let response = await fetch(url, { ...options, headers });

  // 401 → 尝试刷新 token
  if (response.status === 401 && getToken()) {
    // 避免并发刷新
    if (!isRefreshing) {
      isRefreshing = true;
      refreshPromise = refreshToken();
    }
    const refreshed = await refreshPromise!;
    isRefreshing = false;
    refreshPromise = null;

    if (refreshed) {
      // 重新发送请求
      headers["Authorization"] = `Bearer ${getToken()}`;
      response = await fetch(url, { ...options, headers });
    } else {
      // 刷新失败 → 清除 token，跳转登录
      clearTokens();
      window.location.href = "/login";
    }
  }

  return response;
}

export async function apiJson<T = any>(
  url: string,
  options: RequestInit = {},
): Promise<T> {
  const res = await apiFetch(url, options);
  if (!res.ok) {
    const error = await res.json().catch(() => ({ error: { message: res.statusText } }));
    throw new Error(error.error?.message || `HTTP ${res.status}`);
  }
  return res.json();
}

// ============ 认证 API ============

export async function login(username: string, password: string): Promise<LoginResponse> {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `登录失败 (HTTP ${res.status})`);
  }
  const data: LoginResponse = await res.json();
  setTokens(data.access_token, data.refresh_token);
  setUser(data.user);
  return data;
}

export async function logout(): Promise<void> {
  try {
    await apiFetch("/api/auth/logout", { method: "POST" });
  } catch {
    // 忽略网络错误
  }
  clearTokens();
}

export async function fetchCurrentUser(): Promise<AuthUser & { permissions: string[] }> {
  return apiJson("/api/auth/me");
}
