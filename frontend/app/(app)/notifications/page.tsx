"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { NotificationItem } from "@/lib/types";
import { Button, Card, EmptyState, Spinner } from "@/components/ui";
import { cn, timeAgo } from "@/lib/utils";

const KIND_ICONS: Record<string, string> = {
  job_match: "💼",
  daily_summary: "📅",
  weekly_report: "📊",
  application: "📁",
  system: "⚙️",
};

export default function NotificationsPage() {
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get<{ items: NotificationItem[]; unread: number }>("/api/v1/notifications?limit=50")
      .then((data) => {
        setItems(data.items);
        setUnread(data.unread);
      })
      .catch((e) =>
        setError(e instanceof Error ? e.message : "Failed to load notifications")
      )
      .finally(() => setLoading(false));
  }, []);

  function markRead(id: number) {
    api
      .post<{ ok: boolean }>(`/api/v1/notifications/${id}/read`)
      .then(() => {
        setItems((prev) =>
          prev.map((n) => (n.id === id ? { ...n, read: true } : n))
        );
        setUnread((u) => Math.max(0, u - 1));
      })
      .catch(() => {
        /* ignore */
      });
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Notifications</h1>
          <p className="mt-1 text-sm text-zinc-500">
            AI matches and updates from your job agent
          </p>
        </div>
        {unread > 0 && (
          <span className="rounded-full border border-indigo-500/30 bg-indigo-500/15 px-3 py-1 text-xs font-medium text-indigo-300">
            {unread} unread
          </span>
        )}
      </header>

      {error ? (
        <EmptyState icon="⚠️" title="Couldn't load notifications" description={error} />
      ) : loading ? (
        <div className="flex items-center justify-center py-24 text-zinc-500">
          <Spinner className="h-5 w-5" />
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          icon="🔔"
          title="No notifications yet"
          description="Match alerts, daily summaries and weekly reports will show up here once your Telegram agent starts scanning."
          action={
            <Link href="/telegram">
              <Button>Set up the agent</Button>
            </Link>
          }
        />
      ) : (
        <ul className="space-y-2">
          {items.map((n) => (
            <li key={n.id}>
              <Card
                className={cn(
                  "flex items-start gap-3",
                  !n.read && "border-indigo-500/40"
                )}
              >
                <span className="text-xl">{KIND_ICONS[n.kind] ?? "🔔"}</span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <h2 className="text-sm font-semibold text-zinc-100">
                      {n.title}
                    </h2>
                    <span className="shrink-0 text-xs text-zinc-600">
                      {timeAgo(n.created_at)}
                    </span>
                  </div>
                  <p className="mt-0.5 text-sm text-zinc-400">{n.body}</p>
                  {n.job_id != null && (
                    <Link
                      href={`/jobs/${n.job_id}`}
                      className="mt-2 inline-block text-xs font-medium text-indigo-400 hover:text-indigo-300"
                    >
                      View job →
                    </Link>
                  )}
                </div>
                {!n.read && (
                  <Button variant="ghost" className="shrink-0" onClick={() => markRead(n.id)}>
                    Mark read
                  </Button>
                )}
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
