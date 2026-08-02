"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import type { User } from "@/lib/types";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: "📊" },
  { href: "/jobs", label: "Jobs", icon: "💼" },
  { href: "/applications", label: "Applications", icon: "📁" },
  { href: "/saved", label: "Saved", icon: "🔖" },
  { href: "/telegram", label: "Telegram Agent", icon: "✈️" },
  { href: "/analytics", label: "Analytics", icon: "📈" },
  { href: "/notifications", label: "Notifications", icon: "🔔" },
  { href: "/resume", label: "Resume", icon: "📄" },
  { href: "/preferences", label: "Preferences", icon: "⚙️" },
];

export function Sidebar({ user }: { user: User }) {
  const pathname = usePathname();
  const router = useRouter();
  const { logout } = useAuth();

  return (
    <aside className="sticky top-0 flex h-screen w-60 shrink-0 flex-col border-r border-zinc-800 bg-zinc-950">
      <Link href="/dashboard" className="flex items-center gap-2 px-5 py-5">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500 text-sm font-bold text-white">
          JP
        </span>
        <span className="text-base font-bold tracking-tight text-zinc-100">
          JobPilot <span className="text-indigo-400">AI</span>
        </span>
      </Link>

      <nav className="mt-2 flex-1 space-y-1 px-3">
        {NAV.map((item) => {
          const active =
            pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-indigo-500/15 text-indigo-300"
                  : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200"
              )}
            >
              <span className="text-base">{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-zinc-800 p-4">
        <div className="mb-2 flex items-center gap-3">
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-zinc-800 text-sm font-semibold text-zinc-200">
            {user.full_name.charAt(0).toUpperCase()}
          </span>
          <div className="min-w-0">
            <div className="truncate text-sm font-medium text-zinc-100">
              {user.full_name}
            </div>
            <div className="truncate text-xs text-zinc-500">{user.email}</div>
          </div>
        </div>
        <button
          onClick={() => {
            logout();
            router.replace("/login");
          }}
          className="w-full rounded-lg px-3 py-2 text-left text-sm text-zinc-500 transition-colors hover:bg-zinc-900 hover:text-zinc-200"
        >
          Log out
        </button>
      </div>
    </aside>
  );
}
