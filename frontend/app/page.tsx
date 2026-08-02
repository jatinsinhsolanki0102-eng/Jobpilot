"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { Spinner } from "@/components/ui";

export default function Home() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading) router.replace(user ? "/dashboard" : "/login");
  }, [loading, user, router]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-950">
      <div className="flex flex-col items-center gap-3 text-zinc-400">
        <div className="text-3xl font-bold text-zinc-100">
          JobPilot <span className="text-indigo-400">AI</span>
        </div>
        <Spinner className="h-5 w-5" />
      </div>
    </div>
  );
}
