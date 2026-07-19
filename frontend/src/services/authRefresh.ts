const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

/**
 * In-flight refresh promise — only one refresh at a time.
 * If multiple requests hit a 401 simultaneously, they all wait on the same
 * refresh attempt instead of hammering the refresh endpoint.
 */
let refreshPromise: Promise<string | null> | null = null;

/**
 * Attempt to refresh the access token using the stored refresh token.
 *
 * - The refresh endpoint is `/users/token/refresh/` (Django simplejwt).
 * - On success the new access token is saved to localStorage and returned.
 * - On failure (no refresh token, network error, expired refresh token)
 *   localStorage auth keys are cleared and `null` is returned so the
 *   caller can dispatch a Redux logout.
 * - If a refresh is already in progress, subsequent callers wait for it.
 *
 * NOTE: this function does NOT touch Redux state to avoid a circular
 * dependency between api.ts <-> authRefresh.ts <-> store.ts <-> api.ts.
 * Callers are responsible for dispatching `logout()` when this returns null.
 *
 * @returns The new access token, or `null` if refresh failed.
 */
export async function refreshAccessToken(): Promise<string | null> {
  if (refreshPromise) {
    return refreshPromise;
  }

  refreshPromise = (async () => {
    try {
      const refreshToken = localStorage.getItem("refresh_token");
      if (!refreshToken) {
        clearAuthStorage();
        return null;
      }

      const response = await fetch(`${API_BASE_URL}/users/token/refresh/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh: refreshToken }),
      });

      if (!response.ok) {
        clearAuthStorage();
        return null;
      }

      const data = (await response.json()) as { access?: string };
      const newToken = data.access;

      if (newToken) {
        localStorage.setItem("access_token", newToken);
        return newToken;
      }

      clearAuthStorage();
      return null;
    } catch {
      clearAuthStorage();
      return null;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

/** Clear auth-related items from localStorage. */
function clearAuthStorage(): void {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  localStorage.removeItem("user");
}
