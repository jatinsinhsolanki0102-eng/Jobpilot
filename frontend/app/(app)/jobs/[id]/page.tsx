"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, ApiError, formatSalary } from "@/lib/api";
import type { JobDetail } from "@/lib/types";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  MatchBadge,
  Spinner,
} from "@/components/ui";
import { formatDate, timeAgo } from "@/lib/utils";

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [job, setJob] = useState<JobDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [coverLetter, setCoverLetter] = useState("");
  const [generating, setGenerating] = useState(false);
  const [letterError, setLetterError] = useState("");
  const [applying, setApplying] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);

  const fetchJob = useCallback(
    (withAi = false) =>
      api
        .get<JobDetail>(
          `/api/v1/jobs/${id}${withAi ? "?with_ai=true" : ""}`
        )
        .then((data) => setJob(data)),
    [id]
  );

  useEffect(() => {
    fetchJob()
      .catch((e) =>
        setError(e instanceof Error ? e.message : "Failed to load job")
      )
      .finally(() => setLoading(false));
  }, [fetchJob]);

  async function generateLetter() {
    setGenerating(true);
    setLetterError("");
    try {
      const res = await api.post<{ cover_letter: string }>(
        `/api/v1/jobs/${id}/cover-letter`
      );
      setCoverLetter(res.cover_letter);
    } catch (e) {
      setLetterError(
        e instanceof ApiError ? e.message : "Failed to generate cover letter"
      );
    } finally {
      setGenerating(false);
    }
  }

  async function apply() {
    setApplying(true);
    try {
      await api.post("/api/v1/applications", {
        job_id: Number(id),
        cover_letter: coverLetter || null,
      });
      router.push("/applications");
    } catch (e) {
      setLetterError(e instanceof ApiError ? e.message : "Failed to apply");
    } finally {
      setApplying(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-zinc-500">
        <Spinner className="h-5 w-5" />
      </div>
    );
  }

  if (error || !job) {
    return (
      <EmptyState icon="⚠️" title="Job not found" description={error} />
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <button
        onClick={() => router.back()}
        className="text-sm text-zinc-500 transition-colors hover:text-zinc-300"
      >
        ← Back
      </button>

      <Card>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight text-zinc-100">
                {job.title}
              </h1>
              {job.match && <MatchBadge score={job.match.score} />}
            </div>
            <p className="mt-1 text-zinc-400">
              {job.company_name}
              {job.location ? ` · ${job.location}` : ""}
            </p>
            <div className="mt-3 flex flex-wrap gap-2 text-sm text-zinc-500">
              {job.work_mode && <Badge>{job.work_mode}</Badge>}
              {job.employment_type && <Badge>{job.employment_type}</Badge>}
              {job.experience_required && (
                <Badge>Exp: {job.experience_required}</Badge>
              )}
              <Badge>
                {formatSalary(job.salary_min, job.salary_max, job.salary_currency)}
              </Badge>
            </div>
          </div>
          {!job.has_applied ? (
            <Button onClick={apply} disabled={applying}>
              {applying ? <Spinner /> : null}
              {applying ? "Applying…" : "Apply now"}
            </Button>
          ) : (
            <Badge className="border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
              ✓ Applied
            </Badge>
          )}
        </div>

        {job.posted_at && (
          <p className="mt-4 text-xs text-zinc-600">
            Posted {timeAgo(job.posted_at)} · Deadline{" "}
            {formatDate(job.application_deadline)}
          </p>
        )}
      </Card>

      {job.match && (
        <Card>
          <h2 className="mb-4 font-semibold">Match analysis</h2>
          <div className="mb-4 grid grid-cols-3 gap-3">
            <div className="rounded-xl bg-zinc-800/60 p-3 text-center">
              <div className="text-2xl font-bold text-indigo-400">
                {job.match.score.toFixed(0)}%
              </div>
              <div className="mt-1 text-xs text-zinc-500">Overall match</div>
            </div>
            <div className="rounded-xl bg-zinc-800/60 p-3 text-center">
              <div className="text-2xl font-bold text-zinc-100">
                {job.match.skill_match.toFixed(0)}%
              </div>
              <div className="mt-1 text-xs text-zinc-500">Skill overlap</div>
            </div>
            <div className="rounded-xl bg-zinc-800/60 p-3 text-center">
              <div className="text-2xl font-bold text-zinc-100">
                {job.match.semantic_match.toFixed(0)}%
              </div>
              <div className="mt-1 text-xs text-zinc-500">Semantic match</div>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            {job.match.matched_skills.length > 0 && (
              <div>
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-emerald-400">
                  You have
                </h3>
                <div className="flex flex-wrap gap-1.5">
                  {job.match.matched_skills.map((s) => (
                    <Badge key={s} className="border-emerald-500/25 bg-emerald-500/10 text-emerald-400">
                      {s}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
            {job.match.missing_skills.length > 0 && (
              <div>
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-amber-400">
                  To improve
                </h3>
                <div className="flex flex-wrap gap-1.5">
                  {job.match.missing_skills.map((s) => (
                    <Badge key={s} className="border-amber-500/25 bg-amber-500/10 text-amber-400">
                      {s}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </div>

          <button
            onClick={async () => {
              setAiLoading(true);
              try {
                await fetchJob(true);
              } finally {
                setAiLoading(false);
              }
            }}
            className="mt-4 text-xs font-medium text-indigo-400 hover:text-indigo-300"
          >
            {aiLoading
              ? "Asking AI…"
              : job.ai_assessment
                ? "Refresh AI assessment"
                : "Ask AI for a deeper assessment →"}
          </button>
          {job.ai_assessment && (
            <div className="mt-3 rounded-xl border border-zinc-800 bg-zinc-900 p-4">
              <div className="flex items-center gap-2">
                <span className="text-lg font-bold text-indigo-400">
                  {job.ai_assessment.score}%
                </span>
                <span className="text-sm text-zinc-500">AI assessment</span>
              </div>
              {job.ai_assessment.summary && (
                <p className="mt-2 text-sm text-zinc-300">
                  {job.ai_assessment.summary}
                </p>
              )}
              <div className="mt-3 grid gap-4 sm:grid-cols-2">
                <div>
                  <h4 className="mb-1 text-xs font-semibold text-emerald-400">
                    Strengths
                  </h4>
                  <ul className="list-inside list-disc space-y-0.5 text-sm text-zinc-400">
                    {job.ai_assessment.strengths.map((s) => (
                      <li key={s}>{s}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h4 className="mb-1 text-xs font-semibold text-amber-400">Gaps</h4>
                  <ul className="list-inside list-disc space-y-0.5 text-sm text-zinc-400">
                    {job.ai_assessment.gaps.map((g) => (
                      <li key={g}>{g}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          )}
        </Card>
      )}

      {job.skills_required && job.skills_required.length > 0 && (
        <Card>
          <h2 className="mb-3 font-semibold">Required skills</h2>
          <div className="flex flex-wrap gap-1.5">
            {job.skills_required.map((s) => (
              <Badge key={s}>{s}</Badge>
            ))}
          </div>
        </Card>
      )}

      {job.description && (
        <Card>
          <h2 className="mb-3 font-semibold">About the role</h2>
          <p className="whitespace-pre-line text-sm leading-relaxed text-zinc-300">
            {job.description}
          </p>
        </Card>
      )}

      {job.benefits && job.benefits.length > 0 && (
        <Card>
          <h2 className="mb-3 font-semibold">Benefits</h2>
          <ul className="list-inside list-disc space-y-1 text-sm text-zinc-400">
            {job.benefits.map((b) => (
              <li key={b}>{b}</li>
            ))}
          </ul>
        </Card>
      )}

      {!job.has_applied && (
        <Card>
          <div className="flex items-center justify-between gap-3">
            <h2 className="font-semibold">Cover letter</h2>
            <Button variant="outline" onClick={generateLetter} disabled={generating}>
              {generating ? <Spinner /> : null}
              {generating ? "Writing…" : "Generate with AI"}
            </Button>
          </div>
          {letterError && (
            <div className="mt-3 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400">
              {letterError}
            </div>
          )}
          <textarea
            value={coverLetter}
            onChange={(e) => setCoverLetter(e.target.value)}
            rows={10}
            placeholder="Write your own cover letter, or generate one with AI (requires GROQ_API_KEY)."
            className="mt-4 w-full resize-y rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-600 outline-none transition-colors focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20"
          />
          <div className="mt-3 flex justify-end">
            <Button onClick={apply} disabled={applying}>
              {applying ? <Spinner /> : null}
              {applying ? "Submitting…" : "Submit application"}
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
