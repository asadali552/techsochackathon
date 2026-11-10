import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ command, mode }) => {
  const envDir = "..";
  if (command === "build") {
    const env = loadEnv(mode, envDir, ["VITE_", "VERCEL"]);
    const key = env.VITE_SUPABASE_ANON_KEY;
    if (key?.startsWith("sb_secret_")) {
      throw new Error("VITE_SUPABASE_ANON_KEY must be a public Supabase key.");
    }
    if (key?.startsWith("eyJ")) {
      let role: string | undefined;
      try {
        role = JSON.parse(atob(key.split(".")[1].replace(/-/g, "+").replace(/_/g, "/"))).role;
      } catch {
        throw new Error("VITE_SUPABASE_ANON_KEY is not a valid legacy Supabase key.");
      }
      if (role !== "anon") {
        throw new Error("VITE_SUPABASE_ANON_KEY must be a public Supabase key.");
      }
    }
    if (env.VERCEL === "1" && (!env.VITE_API_URL?.startsWith("https://")
        || !env.VITE_SUPABASE_URL?.startsWith("https://") || !key)) {
      throw new Error("Set VITE_API_URL and VITE_SUPABASE_URL to HTTPS origins and provide the public Supabase key.");
    }
  }
  return { plugins: [react()], envDir, server: { port: 5173 } };
});
