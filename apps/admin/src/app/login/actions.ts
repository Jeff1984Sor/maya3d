"use server";

import { redirect } from "next/navigation";
import { attemptLogin, logout, type LoginResult } from "@/lib/auth";

export async function login(_prev: LoginResult, form: FormData): Promise<LoginResult> {
  const result = await attemptLogin(String(form.get("password") ?? ""));
  if (result.error) return result;
  const next = String(form.get("next") ?? "/");
  redirect(next.startsWith("/") && !next.startsWith("//") ? next : "/");
}

export async function signOut(): Promise<void> {
  await logout();
  redirect("/login");
}
