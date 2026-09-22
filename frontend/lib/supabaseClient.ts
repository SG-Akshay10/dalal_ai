import { createClient, SupabaseClient } from "@supabase/supabase-js";

/**
 * Lazily creates the public Supabase client (anon key).
 * Safe to use in browser-side code.
 */
export function getSupabaseClient(): SupabaseClient {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) throw new Error("Missing NEXT_PUBLIC_SUPABASE_URL or NEXT_PUBLIC_SUPABASE_ANON_KEY");
  return createClient(url, key);
}

/**
 * Lazily creates the admin Supabase client (service_role key).
 * SERVER-SIDE ONLY — never expose this to the browser.
 */
export function getSupabaseAdmin(): SupabaseClient {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) throw new Error("Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY");
  return createClient(url, key);
}

// Convenience singleton exports for use in components / server code.
// These will throw at runtime (not build time) if env vars are missing.
let _supabase: SupabaseClient | null = null;
let _supabaseAdmin: SupabaseClient | null = null;

export function supabaseClient(): SupabaseClient {
  if (!_supabase) _supabase = getSupabaseClient();
  return _supabase;
}

export function supabaseAdmin(): SupabaseClient {
  if (!_supabaseAdmin) _supabaseAdmin = getSupabaseAdmin();
  return _supabaseAdmin;
}
