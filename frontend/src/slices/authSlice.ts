import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

export interface AuthUser {
  id: number;
  username: string;
  email: string;
  phone?: string;
  role: string;
}

interface AuthState {
  token: string | null;
  refreshToken: string | null;
  user: AuthUser | null;
  isAuthenticated: boolean;
}

function loadToken(): string | null {
  try {
    return localStorage.getItem("access_token");
  } catch {
    return null;
  }
}

function loadRefreshToken(): string | null {
  try {
    return localStorage.getItem("refresh_token");
  } catch {
    return null;
  }
}

function loadUser(): AuthUser | null {
  try {
    const raw = localStorage.getItem("user");
    if (!raw) return null;
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

const initialState: AuthState = {
  token: loadToken(),
  refreshToken: loadRefreshToken(),
  user: loadUser(),
  isAuthenticated: Boolean(loadToken()),
};

const authSlice = createSlice({
  name: "auth",
  initialState,
  reducers: {
    setCredentials(
      state,
      action: PayloadAction<{
        access: string;
        refresh?: string;
        user?: AuthUser;
      }>,
    ) {
      // Clear ALL chat-related localStorage keys on login/register to prevent data leakage
      const allKeys = Object.keys(localStorage);
      allKeys.forEach(key => {
        if (key.startsWith('resto-chat') || key.startsWith('resto-active-conversation')) {
          localStorage.removeItem(key);
        }
      });

      state.token = action.payload.access;
      state.isAuthenticated = true;
      localStorage.setItem("access_token", action.payload.access);

      if (action.payload.refresh) {
        state.refreshToken = action.payload.refresh;
        localStorage.setItem("refresh_token", action.payload.refresh);
      }

      if (action.payload.user) {
        state.user = action.payload.user;
        localStorage.setItem("user", JSON.stringify(action.payload.user));
      }
    },
    setUser(state, action: PayloadAction<AuthUser>) {
      state.user = action.payload;
      localStorage.setItem("user", JSON.stringify(action.payload));
    },
    logout(state) {
      // Clear ALL chat-related localStorage keys
      const allKeys = Object.keys(localStorage);
      allKeys.forEach(key => {
        if (key.startsWith('resto-chat') || key.startsWith('resto-active-conversation')) {
          localStorage.removeItem(key);
        }
      });
      
      state.token = null;
      state.refreshToken = null;
      state.user = null;
      state.isAuthenticated = false;
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      localStorage.removeItem("user");
    },
  },
});

export const { setCredentials, setUser, logout } = authSlice.actions;
export default authSlice.reducer;
