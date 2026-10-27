"use client";

import { DisclaimerBanner } from "@/components/DisclaimerBanner";

export function CaringMeter({
  score,
  badge,
}: {
  score: number;
  badge: "Low" | "Medium" | "High" | "Excellent";
}) {
  const clamped = Math.max(0, Math.min(100, score));
  return (
    <section className="rounded-2xl border border-leaf-100 bg-white p-5 shadow-soft">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-leaf-800">Plant caring rate</h2>
        <span className="rounded-full bg-leaf-100 px-3 py-1 text-xs font-semibold text-leaf-800">{badge}</span>
      </div>
      <div className="h-4 overflow-hidden rounded-full bg-leaf-100">
        <div className="h-full rounded-full bg-leaf-600 transition-all" style={{ width: `${clamped}%` }} />
      </div>
      <p className="mt-2 text-sm text-leaf-700">
        {clamped}/100 — placeholder until daily photos, watering check-ins, and feedback are added.
      </p>
      <DisclaimerBanner compact />
    </section>
  );
}
