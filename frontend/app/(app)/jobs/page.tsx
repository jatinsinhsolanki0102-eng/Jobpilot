"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, formatSalary } from "@/lib/api";
import type { RankedJob } from "@/lib/types";
import { Badge, Button, Card, EmptyState, Input, MatchBadge, Spinner } from "@/components/ui";
import { cn, timeAgo } from "@/lib/utils";

const SOURCES = [
  { key: "", label: "All" },
  { key: "internshala", label: "Internshala" },
  { key: "JobPilot", label: "Sample" },
];

export default function JobsPage() {
  const [jobs, setJobs] = useState<RankedJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [source, setSource] = useState("");
  const [query, setQuery] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState("");

  useEffect(() => {
    api
      .get<RankedJob[]>(`/api/v1/jobs?limit=50${source ? `&source=${source}` : ""}`)
      .then((data) => {
        setJobs(data);
        setError("");
        setLoading(false);
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : "Failed to load jobs");
        setLoading(false);
      });
  }, [source]);

  const reload = (filter: string) =>
    api.get<RankedJob[]>(`/api/v1/jobs?limit=50${filter ? `&source=${filter}` : ""}`);

  const handleSync = () => {
    setSyncing(true);
    setSyncMsg("");
    api
      .post<{ added: number; updated: number; total_found: number; failed: number }>(
        "/api/v1/jobs/sync",
        {
          query: query.trim() || null,
          location: null,
          internship: true,
          limit: 20,
          with_details: true,
        }
      )
      .then((res) => {
        setSyncMsg(
          `Synced ${res.total_found} Internshala listings (${res.added} new, ${res.updated} updated)`
        );
        return reload(source);
      })
      .then(setJobs)
      .catch((e) => {
        setSyncMsg(e instanceof Error ? `Sync failed: ${e.message}` : "Sync failed");
      })
      .finally(() => setSyncing(false));
  };

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">Jobs</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Ranked by how well they match your resume and preferences
        </p>
      </header>

      <Card className="flex flex-col gap-3 lg:flex-row lg:items-center">
        <div className="flex flex-1 flex-col gap-3 sm:flex-row sm:items-center">
          <Input
            placeholder="Keyword (e.g. python, data analyst)"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSync()}
            className="sm:max-w-xs"
          />
          <Button onClick={handleSync} disabled={syncing}>
            {syncing && <Spinner className="h-4 w-4 border-zinc-300 border-t-transparent" />}
            {syncing ? "Syncing…" : "Sync Internshala"}
          </Button>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {SOURCES.map((s) => (
            <button
              key={s.label}
              onClick={() => setSource(s.key)}
              className={cn(
                "rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
                source === s.key
                  ? "border-indigo-500 bg-indigo-500/15 text-indigo-300"
                  : "border-zinc-700 text-zinc-400 hover:bg-zinc-800"
              )}
            >
              {s.label}
            </button>
          ))}
        </div>
      </Card>

      {syncMsg && (
        <p className="text-sm text-zinc-400">
          <span className="mr-1">{syncMsg.startsWith("Synced") ? "✅" : "⚠️"}</span>
          {syncMsg}
        </p>
      )}

      {error ? (
        <EmptyState icon="⚠️" title="Couldn't load jobs" description={error} />
      ) : loading ? (
        <div className="flex items-center justify-center py-24 text-zinc-500">
          <Spinner className="h-5 w-5" />
        </div>
      ) : jobs.length === 0 ? (
        <EmptyState
          icon="💼"
          title="No jobs yet"
          description="Upload a resume and set preferences to unlock ranked matches, or sync live listings from Internshala."
          action={
            <div className="flex gap-2">
              <Link href="/resume">
                <Button>Upload resume</Button>
              </Link>
              <Button variant="outline" onClick={handleSync} disabled={syncing}>
                {syncing ? "Syncing…" : "Sync from Internshala"}
              </Button>
            </div>
          }
        />
      ) : (
        <ul className="space-y-3">
          {jobs.map((job) => (
            <li key={job.id}>
              <Link href={`/jobs/${job.id}`} className="block">
                <Card className="transition-colors hover:border-zinc-700 hover:bg-zinc-900">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <h2 className="text-base font-semibold text-zinc-100">
                          {job.title}
                        </h2>
                        {job.rank_score != null && <MatchBadge score={job.rank_score} />}
                      </div>
                      <p className="mt-1 text-sm text-zinc-500">
                        {job.company_name}
                        {job.location ? ` · ${job.location}` : ""}
                        {job.work_mode ? ` · ${job.work_mode}` : ""}
                        {job.employment_type ? ` · ${job.employment_type}` : ""}
                      </p>
                      <p className="mt-1 text-xs text-zinc-600">
                        {formatSalary(job.salary_min, job.salary_max, job.salary_currency)}
                        {job.experience_required
                          ? ` · Exp: ${job.experience_required}`
                          : ""}
                        {timeAgo(job.posted_at ?? job.created_at)
                          ? ` · ${timeAgo(job.posted_at ?? job.created_at)}`
                          : ""}
                      </p>
                      {job.match && job.match.matched_skills.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {job.match.matched_skills.slice(0, 6).map((s) => (
                            <Badge
                              key={s}
                              className="border-emerald-500/25 bg-emerald-500/10 text-emerald-400"
                            >
                              {s}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </div>
                    {job.match && (
                      <div className="hidden shrink-0 flex-col items-end gap-1 sm:flex">
                        <span className="text-xs text-zinc-600">match score</span>
                        <span className="text-lg font-bold text-indigo-400">
                          {job.match.score.toFixed(0)}%
                        </span>
                      </div>
                    )}
                  </div>
                </Card>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
