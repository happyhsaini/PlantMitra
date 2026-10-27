"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { DisclaimerBanner } from "@/components/DisclaimerBanner";
import { useAuth } from "@/components/AuthProvider";
import { api, setSession } from "@/lib/api";

export default function SignupPage() {
  const router = useRouter();
  const { setUser } = useAuth();
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = await api.signup({
        display_name: displayName,
        email: email || undefined,
        phone: phone || undefined,
        password,
      });
      setSession(res.access_token, res.user);
      setUser(res.user);
      router.push("/home");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Signup failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,#eef6ea_0%,#fffcf6_45%)] px-4 py-10">
      <div className="mx-auto w-full max-w-md">
        <div className="mb-6 text-center">
          <h1 className="text-2xl font-semibold text-leaf-800">Join PlantMitra</h1>
          <p className="mt-1 text-sm text-leaf-700">Use email or phone plus a password.</p>
        </div>
        <form onSubmit={onSubmit} className="rounded-2xl bg-white p-6 shadow-soft">
          <label className="mb-3 block text-sm">
            Display name
            <input
              className="mt-1 w-full rounded-xl border border-leaf-200 px-3 py-2"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              required
            />
          </label>
          <label className="mb-3 block text-sm">
            Email (optional if phone is set)
            <input
              type="email"
              className="mt-1 w-full rounded-xl border border-leaf-200 px-3 py-2"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          <label className="mb-3 block text-sm">
            Phone (optional if email is set)
            <input
              className="mt-1 w-full rounded-xl border border-leaf-200 px-3 py-2"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+91…"
            />
          </label>
          <label className="mb-4 block text-sm">
            Password (min 8 characters)
            <input
              type="password"
              className="mt-1 w-full rounded-xl border border-leaf-200 px-3 py-2"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={8}
              required
            />
          </label>
          {error ? <p className="mb-3 text-sm text-red-700">{error}</p> : null}
          <button disabled={busy} className="w-full rounded-xl bg-leaf-600 py-2.5 font-medium text-white">
            {busy ? "Creating…" : "Create account"}
          </button>
          <p className="mt-4 text-center text-sm text-leaf-700">
            Already have an account?{" "}
            <Link href="/login" className="font-semibold underline">
              Log in
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
