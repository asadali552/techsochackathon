const authBase = (import.meta.env.VITE_SUPABASE_URL ?? "").replace(/\/+$/, "");
const publicKey = import.meta.env.VITE_SUPABASE_ANON_KEY ?? "";

export const canSignIn = Boolean(authBase && publicKey);
export type Session = { token: string; expiresAt: number };

export async function signIn(email: string, password: string, signal: AbortSignal): Promise<Session> {
  if (!canSignIn) throw new Error("Sign-in has not been configured for this deployment.");

  const response = await fetch(`${authBase}/auth/v1/token?grant_type=password`, {
    method: "POST",
    headers: { apikey: publicKey, "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
    signal,
    redirect: "error",
  });
  if (!response.ok) {
    throw new Error(response.status === 400 || response.status === 401
      ? "Sign-in failed. Check your email and password."
      : "Sign-in is temporarily unavailable. Try again shortly.");
  }

  const data = await response.json();
  if (typeof data?.access_token !== "string" || !data.access_token
    || !Number.isFinite(data.expires_in) || data.expires_in <= 0 || data.user?.is_anonymous) {
    throw new Error("Sign in with a registered Supabase account.");
  }
  return { token: data.access_token, expiresAt: Date.now() + data.expires_in * 1000 };
}
