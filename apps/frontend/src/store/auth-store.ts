"use client";

import { create } from "zustand";
import type { TokenPair, User } from "@/types";

// ---------------------------------------------------------------------------
// Auth store — access token kept in memory only (never persisted to storage).
//
// The refresh token is stored as an httpOnly cookie by the backend
// (_set_refresh_cookie in api/routes/auth.py).  The browser sends it
// automatically on requests to /api/v1/auth/* due to credentials: "include".
// We never read or write the refresh token in JavaScript so it is invisible
// to XSS payloads.
//
// Access tokens are short-lived (15 min default) and live only in this Zustand
// store.  They are lost on page reload; rehydrate() recovers the session by
// calling /api/v1/auth/refresh which reads the httpOnly cookie.
// ---------------------------------------------------------------------------

interface AuthState {
  accessToken: string | null;
  user: User | null;
  isRestoring: boolean;
  setSession: (tokens: TokenPair) => void;
  logout: () => Promise<void>;
  rehydrate: () => Promise<void>;
  refresh: () => Promise<boolean>;
}

export const useAuthStore = create<AuthState>()((set, get) => ({
  accessToken: null,
  user: null,
  isRestoring: false,

  setSession: (tokens) => {
    // Never write refresh_token to JS-accessible storage.
    // The httpOnly cookie was already set by the server response.
    set({
      accessToken: tokens.access_token,
      user: tokens.user ?? get().user,
      isRestoring: false,
    });
  },

  logout: async () => {
    // Call the backend logout endpoint so the refresh-token cookie is
    // deleted server-side and the refresh token is revoked in the DB.
    // We intentionally swallow errors here: if the network is down or
    // the token is already expired, we still want the client state cleared.
    try {
      const { api } = await import("@/lib/api");
      await api.logout();
    } catch {
      // Ignore — proceed to clear local state regardless.
    }
    set({ accessToken: null, user: null, isRestoring: false });
  },

  rehydrate: async () => {
    if (typeof window === "undefined") return;
    set({ isRestoring: true });
    try {
      const { api } = await import("@/lib/api");
      // Refresh relies solely on the httpOnly cookie (credentials: "include").
      // No token argument needed or accepted.
      const tokens = await api.refresh();
      get().setSession(tokens);
    } catch {
      await get().logout();
    }
  },

  refresh: async () => {
    set({ isRestoring: true });
    try {
      const { api } = await import("@/lib/api");
      const tokens = await api.refresh();
      get().setSession(tokens);
      return true;
    } catch {
      await get().logout();
      return false;
    }
  },
}));

