"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { CharacterAvatar } from "@/components/CharacterAvatar";
import { DisclaimerBanner } from "@/components/DisclaimerBanner";
import { useAuth } from "@/components/AuthProvider";

const NAV = [
  { href: "/home", label: "Home" },
  { href: "/map", label: "Map" },
  { href: "/explore", label: "Explore" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/character", label: "Character" },
  { href: "/settings", label: "Settings" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, logout, loading } = useAuth();

  if (loading) {
    return (
      <div className="grid min-h-screen place-items-center bg-leaf-50 text-leaf-800">
        Loading PlantMitra…
      </div>
    );
  }

  if (pathname === "/home") return <>{children}</>;

  if (!user) {
    return (
      <div className="grid min-h-screen place-items-center bg-leaf-50 p-6">
        <div className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-soft">
          <p className="mb-3 text-leaf-800">Please sign in to continue.</p>
          <Link href="/login" className="block rounded-xl bg-leaf-600 py-2 text-center font-medium text-white">
            Go to login
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-cream-50 md:grid md:grid-cols-[240px_1fr]">
      <aside className="hidden border-r border-leaf-100 bg-[#eef6ea] p-4 md:flex md:flex-col">
        <div className="mb-6 flex items-center gap-2 text-leaf-800">
          <span className="text-2xl">🌿</span>
          <div>
            <p className="font-semibold leading-tight">PlantMitra</p>
            <p className="text-[11px] text-leaf-700">Medicinal plant companion</p>
          </div>
        </div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-leaf-700">Navigation</p>
        <nav className="flex flex-1 flex-col gap-2">
          {NAV.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`rounded-full border px-4 py-2 text-sm ${
                  active
                    ? "border-leaf-600 bg-white font-semibold text-leaf-800 shadow-sm"
                    : "border-leaf-200 bg-white/70 text-leaf-800"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="mt-6">
          <CharacterAvatar character={user.character} size={64} />
        </div>
        <div className="mt-4">
          <DisclaimerBanner compact />
        </div>
        <button
          type="button"
          onClick={logout}
          className="mt-4 rounded-full border border-leaf-300 bg-white px-4 py-2 text-sm text-leaf-800"
        >
          Log out
        </button>
      </aside>

      <div className="flex min-h-screen flex-col">
        <header className="flex items-center justify-between border-b border-leaf-100 bg-white px-4 py-3 md:hidden">
          <div className="flex items-center gap-2 text-leaf-800">
            <span>🌿</span>
            <span className="font-semibold">PlantMitra</span>
          </div>
          <CharacterAvatar character={user.character} size={40} />
        </header>
        <main className="flex-1 px-4 py-5 md:px-8 md:py-7">{children}</main>
        <nav className="sticky bottom-0 grid grid-cols-6 border-t border-leaf-100 bg-white md:hidden">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`py-3 text-center text-xs ${pathname === item.href ? "font-semibold text-leaf-700" : "text-leaf-600"}`}
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </div>
    </div>
  );
}
