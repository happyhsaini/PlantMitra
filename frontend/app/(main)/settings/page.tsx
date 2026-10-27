"use client";

import { FormEvent, useState } from "react";
import { DisclaimerBanner } from "@/components/DisclaimerBanner";
import { useAuth } from "@/components/AuthProvider";
import { api, setSession, type User } from "@/lib/api";

export default function SettingsPage() {
  const { user, setUser, logout } = useAuth();
  const [displayName, setDisplayName] = useState(user?.display_name || "");
  const [privacy, setPrivacy] = useState<User["privacy"]>(user?.privacy || "public");
  const [message, setMessage] = useState("");

  if (!user) return null;

  async function onSave(e: FormEvent) {
    e.preventDefault();
    const updated = await api.updateMe({ display_name: displayName, privacy });
    const token = localStorage.getItem("plantmitra_token");
    if (token) setSession(token, updated);
    setUser(updated);
    setMessage("Saved.");
  }

  return (
    <div className="mx-auto max-w-xl space-y-5">
      <h1 className="text-2xl font-semibold text-leaf-800">Settings</h1>
      <form onSubmit={onSave} className="space-y-3 rounded-2xl bg-white p-5 shadow-soft">
        <label className="block text-sm">
          Display name
          <input className="mt-1 w-full rounded-xl border border-leaf-200 px-3 py-2" value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
        </label>
        <label className="block text-sm">
          Profile privacy
          <select className="mt-1 w-full rounded-xl border border-leaf-200 px-3 py-2" value={privacy} onChange={(e) => setPrivacy(e.target.value as User["privacy"])}>
            <option value="public">Public</option>
            <option value="friends_only">Friends only</option>
            <option value="private">Private</option>
          </select>
        </label>
        {message ? <p className="text-sm text-leaf-700">{message}</p> : null}
        <button className="w-full rounded-xl bg-leaf-600 py-2.5 font-medium text-white">Save settings</button>
      </form>
      <button type="button" onClick={logout} className="w-full rounded-xl border border-leaf-300 bg-white py-2 text-leaf-800">
        Log out
      </button>
      <DisclaimerBanner />
    </div>
  );
}
