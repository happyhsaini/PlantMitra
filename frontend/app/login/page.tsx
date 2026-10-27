"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { DisclaimerBanner } from "@/components/DisclaimerBanner";
import { useAuth } from "@/components/AuthProvider";
import { api, setSession } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const { setUser } = useAuth();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = await api.login(identifier, password);
      setSession(res.access_token, res.user);
      setUser(res.user);
      router.push("/home");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,#eef6ea_0%,#fffcf6_45%)] px-4 py-10">
      <div className="mx-auto w-full max-w-md">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 grid h-14 w-14 place-items-center rounded-full bg-leaf-600 text-2xl text-white">
            🌿
          </div>
          <h1 className="text-2xl font-semibold text-leaf-800">PlantMitra</h1>
          <p className="mt-1 text-sm text-leaf-700">
            Identification of Different Medicinal Plants through Image Processing
          </p>
        </div>
        <form onSubmit={onSubmit} className="rounded-2xl bg-white p-6 shadow-soft">
          <h2 className="mb-4 text-lg font-semibold text-leaf-800">Log in</h2>
          <label className="mb-3 block text-sm text-leaf-800">
            Email or phone
            <input
              className="mt-1 w-full rounded-xl border border-leaf-200 px-3 py-2 outline-none focus:border-leaf-500"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              autoComplete="username"
              required
            />
          </label>
          <label className="mb-4 block text-sm text-leaf-800">
            Password
            <input
              type="password"
              className="mt-1 w-full rounded-xl border border-leaf-200 px-3 py-2 outline-none focus:border-leaf-500"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </label>
          {error ? <p className="mb-3 text-sm text-red-700">{error}</p> : null}
          <button
            disabled={busy}
            className="w-full rounded-xl bg-leaf-600 py-2.5 font-medium text-white disabled:opacity-60"
          >
            {busy ? "Signing in…" : "Sign in"}
          </button>
          <p className="mt-4 text-center text-sm text-leaf-700">
            New here?{" "}
            <Link href="/signup" className="font-semibold text-leaf-800 underline">
              Create an account
            </Link>
          </p>
        </form>
        <div className="mt-4">
          <DisclaimerBanner />
        </div>
      </div>
    </div>
  );
}
