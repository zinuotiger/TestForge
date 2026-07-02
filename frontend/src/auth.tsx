/** AuthContext — 全局认证状态管理 */

import { createContext, useContext, useState, useEffect, ReactNode, useCallback } from "react";
import {
  AuthUser, login as apiLogin, logout as apiLogout,
  getToken, getUser, clearTokens, fetchCurrentUser,
} from "./api";

/**
 * 临时跳过登录开关
 * true  → 隐藏登录界面，使用模拟用户直接访问所有页面（用于网页测试）
 * false → 恢复正常登录流程
 */
const BYPASS_AUTH = true;

/** 跳过登录时使用的模拟用户 */
const MOCK_USER: AuthUser = {
  username: "dev_user",
  role: "admin",
  email: "dev@testforge.local",
};

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(
    BYPASS_AUTH ? MOCK_USER : getUser()
  );
  const [loading, setLoading] = useState(!BYPASS_AUTH);

  const refreshUser = useCallback(async () => {
    if (BYPASS_AUTH) {
      setUser(MOCK_USER);
      setLoading(false);
      return;
    }
    if (!getToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await fetchCurrentUser();
      setUser({ username: me.username, role: me.role, email: me.email });
    } catch {
      clearTokens();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  const login = useCallback(async (username: string, password: string) => {
    if (BYPASS_AUTH) {
      setUser(MOCK_USER);
      return;
    }
    const data = await apiLogin(username, password);
    setUser(data.user);
  }, []);

  const logout = useCallback(async () => {
    if (BYPASS_AUTH) {
      setUser(MOCK_USER);
      return;
    }
    await apiLogout();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        isAuthenticated: BYPASS_AUTH ? true : !!user,
        login,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth 必须在 AuthProvider 内使用");
  }
  return ctx;
}
