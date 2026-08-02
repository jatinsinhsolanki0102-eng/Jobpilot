"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type {
  AnalyticsOverview,
  AnalyticsReports,
  Funnel,
  ScanReportData,
  SkillCount,
} from "@/lib/types";
import { Badge, Card, EmptyState, Spinner } from "@/components/ui";
import { cn } from "@/lib/utils";

function StatCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: number;
  accent?: string;
}) {
  return (
    <Card className="flex flex-col gap-1">
      <span className="text-xs font-medium text-zinc-500">{label}</span>
      <span className={cn("text-3xl font-bold", accent ?? "text-zinc-100")}>
        {value}
      </span>
    </Card>
  );
}

function BarChart({ series }: { series: AnalyticsOverview["series"] }) {
  const max = Math.max(1, ...series.map((s) => s.scanned));
  return (
    <div className="flex h-40 items-end gap-1.5">
      {series.map((s) => (
        <div key={s.date} className="flex flex-1 flex-col items-center gap-1">
          <span className="text-[10px] font-medium text-zinc-500">
            {s.scanned > 0 ? s.scanned : ""}
          </span>
          <div className="relative w-full rounded-t bg-indigo-500/20" style={{ flex: 1 }}>
            <div
              className="absolute bottom-0 left-0 right-0 rounded-t bg-indigo-500"
              style={{
                height: `${Math.round((s.scanned / max) * 100)}%`,
                opacity: s.scanned > 0 ? 0.9 : 0.25,
              }}
            />
          </div>
          <span className="text-[10px] text-zinc-600">
            {new Date(s.date + "T00:00:00").toLocaleDateString(undefined, {
              day: "2-digit",
              month: "short",
            })}
          </span>
        </div>
      ))}
    </div>
  );
}

function ReportTable({
  rows,
  kind,
}: {
  rows: AnalyticsReports["daily"];
  kind: "daily" | "weekly";
}) {
  if (rows.length === 0) {
    return (
      <p className="text-sm text-zinc-500">
        No {kind} reports yet. Enable them in the Telegram agent and run a scan.
      </p>
    );
  }
  return (
    <ul className="divide-y divide-zinc-800">
      {rows.map((r) => {
        const d = r.data as ScanReportData;
        return (
          <li key={r.period_date} className="flex flex-wrap items-center justify-between gap-2 py-3">
            <div className="min-w-0">
              <p className="text-sm font-medium text-zinc-200">
                {new Date(r.period_date + "T00:00:00").toLocaleDateString(undefined, {
                  day: "numeric",
                  month: "short",
                  year: "numeric",
                })}
              </p>
              {d.best && (
                <p className="truncate text-xs text-zinc-500">
                  Best: {d.best.title} · {d.best.company} ({d.best.score.toFixed(0)}%)
                </p>
              )}
              {d.top_skills && d.top_skills.length > 0 && (
                <p className="mt-1 text-xs text-zinc-600">
                  Top skills: {d.top_skills.slice(0, 5).map((s) => s.skill).join(", ")}
                </p>
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge>scanned {d.scanned ?? 0}</Badge>
              <Badge>matched {d.matched ?? 0}</Badge>
              <Badge>sent {d.sent ?? 0}</Badge>
              {d.applications != null && <Badge>apps {d.applications}</Badge>}
              <Badge>avg {Math.round(d.avg_score ?? 0)}%</Badge>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

export default function AnalyticsPage() {
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [reports, setReports] = useState<AnalyticsReports | null>(null);
  const [skills, setSkills] = useState<SkillCount[]>([]);
  const [funnel, setFunnel] = useState<Funnel | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      api.get<AnalyticsOverview>("/api/v1/analytics/overview?days=14"),
      api.get<AnalyticsReports>("/api/v1/analytics/reports"),
      api.get<{ skills: SkillCount[] }>("/api/v1/analytics/skills?limit=10"),
      api.get<Funnel>("/api/v1/analytics/funnel"),
    ])
      .then(([ov, rep, sk, fun]) => {
        setOverview(ov);
        setReports(rep);
        setSkills(sk.skills);
        setFunnel(fun);
      })
      .catch((e) =>
        setError(e instanceof Error ? e.message : "Failed to load analytics")
      )
      .finally(() => setLoaded(true));
  }, []);

  if (error) {
    return <EmptyState icon="⚠️" title="Couldn't load analytics" description={error} />;
  }

  if (!loaded || !overview || !reports || !funnel) {
    return (
      <div className="flex items-center justify-center py-24 text-zinc-500">
        <Spinner className="h-5 w-5" />
      </div>
    );
  }

  const maxSkill = Math.max(1, ...skills.map((s) => s.count));

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">Analytics</h1>
        <p className="mt-1 text-sm text-zinc-500">
          How your autonomous job agent is performing
        </p>
      </header>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        <StatCard label="Jobs scanned" value={overview.totals.scanned} accent="text-indigo-400" />
        <StatCard label="Matched" value={overview.totals.matched} accent="text-emerald-400" />
        <StatCard label="Alerts sent" value={overview.totals.sent} accent="text-sky-400" />
        <StatCard label="Ignored" value={overview.totals.ignored} accent="text-zinc-400" />
        <StatCard label="Applications" value={overview.totals.apps} accent="text-violet-400" />
      </div>

      <Card>
        <h2 className="mb-4 font-semibold">Jobs scanned per day</h2>
        <BarChart series={overview.series} />
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-0">
          <div className="border-b border-zinc-800 px-5 py-4">
            <h2 className="font-semibold">Daily scan reports</h2>
          </div>
          <div className="px-5">
            <ReportTable rows={reports.daily} kind="daily" />
          </div>
        </Card>

        <Card className="p-0">
          <div className="border-b border-zinc-800 px-5 py-4">
            <h2 className="font-semibold">Weekly reports</h2>
          </div>
          <div className="px-5">
            <ReportTable rows={reports.weekly} kind="weekly" />
          </div>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <h2 className="mb-4 font-semibold">Most in-demand skills</h2>
          {skills.length === 0 ? (
            <p className="text-sm text-zinc-500">
              No skills data yet — run a scan to populate it.
            </p>
          ) : (
            <ul className="space-y-2.5">
              {skills.map((s) => (
                <li key={s.skill}>
                  <div className="mb-1 flex items-center justify-between text-sm">
                    <span className="text-zinc-200">{s.skill}</span>
                    <span className="text-xs text-zinc-500">{s.count} jobs</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-zinc-800">
                    <div
                      className="h-full rounded-full bg-indigo-500/70"
                      style={{ width: `${Math.round((s.count / maxSkill) * 100)}%` }}
                    />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card>
          <h2 className="mb-4 font-semibold">Application funnel</h2>
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: "Total applications", value: funnel.total },
              { label: "Saved jobs", value: funnel.saved },
            ].map((s) => (
              <div key={s.label} className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
                <div className="text-2xl font-bold text-zinc-100">{s.value}</div>
                <div className="text-xs text-zinc-500">{s.label}</div>
              </div>
            ))}
          </div>
          {funnel.total > 0 ? (
            <ul className="mt-4 space-y-2">
              {Object.entries(funnel.by_status).map(([status, count]) => (
                <li key={status} className="flex items-center justify-between text-sm">
                  <span className="capitalize text-zinc-300">{status}</span>
                  <span className="text-zinc-400">
                    {count} · {funnel.rates[status]}%
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-4 text-sm text-zinc-500">
              Apply to jobs to see your funnel.
            </p>
          )}
        </Card>
      </div>
    </div>
  );
}
