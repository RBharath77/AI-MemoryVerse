import { create } from "zustand";

export interface User {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_verified: boolean;
  is_superuser: boolean;
  profile?: {
    bio: string;
    avatar_url: string;
    ai_custom_instructions: string;
    preferences: Record<string, any>;
  };
}

interface AuthState {
  user: User | null;
  accessToken: string | null;
  activeWorkspaceId: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  setAuth: (user: User, token: string, workspaceId?: string) => void;
  setActiveWorkspace: (workspaceId: string) => void;
  updateUser: (user: Partial<User>) => void;
  logout: () => void;
  initialize: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  accessToken: null,
  activeWorkspaceId: null,
  isAuthenticated: false,
  isLoading: true,

  setAuth: (user, token, workspaceId) => {
    if (typeof window !== "undefined") {
      localStorage.setItem("access_token", token);
      if (workspaceId) {
        localStorage.setItem("active_workspace_id", workspaceId);
      }
      localStorage.setItem("auth_user", JSON.stringify(user));
    }
    set({
      user,
      accessToken: token,
      activeWorkspaceId: workspaceId || null,
      isAuthenticated: true,
      isLoading: false,
    });
  },

  setActiveWorkspace: (workspaceId) => {
    if (typeof window !== "undefined") {
      localStorage.setItem("active_workspace_id", workspaceId);
    }
    set({ activeWorkspaceId: workspaceId });
  },

  updateUser: (updatedFields) => {
    set((state) => {
      if (!state.user) return state;
      const updatedUser = { ...state.user, ...updatedFields };
      if (typeof window !== "undefined") {
        localStorage.setItem("auth_user", JSON.stringify(updatedUser));
      }
      return { user: updatedUser };
    });
  },

  logout: () => {
    if (typeof window !== "undefined") {
      localStorage.removeItem("access_token");
      localStorage.removeItem("active_workspace_id");
      localStorage.removeItem("auth_user");
    }
    set({
      user: null,
      accessToken: null,
      activeWorkspaceId: null,
      isAuthenticated: false,
      isLoading: false,
    });
  },

  initialize: () => {
    if (typeof window !== "undefined") {
      const token = localStorage.getItem("access_token");
      const workspaceId = localStorage.getItem("active_workspace_id");
      const savedUser = localStorage.getItem("auth_user");

      if (token && savedUser) {
        try {
          const user = JSON.parse(savedUser);
          set({
            user,
            accessToken: token,
            activeWorkspaceId: workspaceId,
            isAuthenticated: true,
            isLoading: false,
          });
          return;
        } catch {
          // ignore corrupted JSON
        }
      }
    }
    set({ isLoading: false });
  },
}));

