"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Application, ApplicationStatus } from "@/lib/types";
import {
  Card,
  EmptyState,
  Spinner,
  StatusBadge,
} from "@/components/ui";
import { timeAgo } from "@/lib/utils";

const STATUSES: ApplicationStatus[] = [
  "applied",
  "pending",
  "interview",
  "rejected",
  "offer",
  "withdrawn",
];

export default function ApplicationsPage() {
  const [apps, setApps] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState<number | null>(null);

  useEffect(() => {
    api
      .get<Application[]>("/api/v1/applications")
      .then((data) => {
        setApps(data);
        setLoading(false);
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : "Failed to load applications");
        setLoading(false);
      });
  }, []);

  async function updateStatus(app: Application, status: ApplicationStatus) {
    const updated = await api.patch<Application>(`/api/v1/applications/${app.id}`, {
      status,
    });
    setApps((prev) => prev.map((a) => (a.id === updated.id ? updated : a)));
  }

  if (error) {
    return (
      <EmptyState icon="⚠️" title="Couldn't load applications" description={error} />
    );
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">Applications</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Track every application through the hiring pipeline
        </p>
      </header>

      {loading ? (
        <div className="flex items-center justify-center py-24 text-zinc-500">
          <Spinner className="h-5 w-5" />
        </div>
      ) : apps.length === 0 ? (
        <EmptyState
          icon="📁"
          title="No applications yet"
          description="Browse ranked jobs and submit your first application."
        />
      ) : (
        <ul className="space-y-3">
          {apps.map((app) => (
            <Card key={app.id} className="p-0">
              <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="font-semibold text-zinc-100">{app.job_title}</h2>
                    <StatusBadge status={app.status} />
                  </div>
                  <p className="mt-0.5 text-sm text-zinc-500">
                    {app.company_name} · Applied {timeAgo(app.created_at)}
                  </p>
                </div>
                <div className="flex items-center gap-1">
                  {STATUSES.filter((s) => s !== app.status).map((s) => (
                    <button
                      key={s}
                      onClick={() => updateStatus(app, s)}
                      className="rounded-md border border-zinc-700 px-2 py-1 text-xs capitalize text-zinc-400 transition-colors hover:border-zinc-500 hover:text-zinc-200"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
              {app.cover_letter && (
                <button
                  onClick={() => setExpanded(expanded === app.id ? null : app.id)}
                  className="w-full border-t border-zinc-800 px-5 py-2.5 text-left text-xs font-medium text-indigo-400 hover:text-indigo-300"
                >
                  {expanded === app.id ? "Hide" : "Show"} cover letter
                </button>
              )}
              {expanded === app.id && app.cover_letter && (
                <div className="border-t border-zinc-800 px-5 py-4">
                  <p className="whitespace-pre-line text-sm leading-relaxed text-zinc-300">
                    {app.cover_letter}
                  </p>
                </div>
              )}
              {app.interview_date && (
                <div className="border-t border-zinc-800 px-5 py-2.5 text-xs text-zinc-500">
                  📅 Interview scheduled:{" "}
                  {new Date(app.interview_date).toLocaleString()}
                </div>
              )}
            </Card>
          ))}
        </ul>
      )}
    </div>
  );
}
