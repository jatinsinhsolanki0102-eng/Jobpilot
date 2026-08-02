"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, formatSalary } from "@/lib/api";
import type { RankedJob } from "@/lib/types";
import { Badge, Button, Card, EmptyState, MatchBadge, Spinner } from "@/components/ui";
import { timeAgo } from "@/lib/utils";

export default function SavedJobsPage() {
  const [jobs, setJobs] = useState<RankedJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get<RankedJob[]>("/api/v1/saved")
      .then(setJobs)
      .catch((e) =>
        setError(e instanceof Error ? e.message : "Failed to load saved jobs")
      )
      .finally(() => setLoading(false));
  }, []);

  function unsave(id: number) {
    api
      .del<{ saved: boolean }>(`/api/v1/saved/${id}`)
      .then(() => setJobs((prev) => prev.filter((j) => j.id !== id)))
      .catch((e) =>
        setError(e instanceof Error ? e.message : "Failed to unsave job")
      );
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">Saved jobs</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Opportunities you&apos;ve bookmarked for later
        </p>
      </header>

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-24 text-zinc-500">
          <Spinner className="h-5 w-5" />
        </div>
      ) : jobs.length === 0 ? (
        <EmptyState
          icon="🔖"
          title="Nothing saved yet"
          description="Save interesting jobs and they'll appear here for quick access."
          action={
            <Link href="/jobs">
              <Button>Browse jobs</Button>
            </Link>
          }
        />
      ) : (
        <ul className="space-y-3">
          {jobs.map((job) => (
            <li key={job.id}>
              <Card>
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <Link href={`/jobs/${job.id}`}>
                      <div className="flex flex-wrap items-center gap-2">
                        <h2 className="text-base font-semibold text-zinc-100 hover:text-indigo-300">
                          {job.title}
                        </h2>
                        {job.rank_score != null && <MatchBadge score={job.rank_score} />}
                      </div>
                    </Link>
                    <p className="mt-1 text-sm text-zinc-500">
                      {job.company_name}
                      {job.location ? ` · ${job.location}` : ""}
                      {job.work_mode ? ` · ${job.work_mode}` : ""}
                    </p>
                    <p className="mt-1 text-xs text-zinc-600">
                      {formatSalary(job.salary_min, job.salary_max, job.salary_currency)}
                      {job.posted_at || job.created_at
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
                  <div className="flex shrink-0 flex-col items-end gap-2">
                    <Link href={`/jobs/${job.id}`}>
                      <Button variant="outline">View</Button>
                    </Link>
                    <Button variant="ghost" onClick={() => unsave(job.id)}>
                      Unsave
                    </Button>
                  </div>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
