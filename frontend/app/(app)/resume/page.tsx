"use client";

import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Resume, ResumeSkill } from "@/lib/types";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Spinner,
} from "@/components/ui";

function ProfileCard({ structured }: { structured: Record<string, unknown> }) {
  const profile = structured as {
    full_name?: string;
    email?: string;
    location?: string;
    summary?: string;
  };
  return (
    <Card>
      <h2 className="mb-3 font-semibold">Profile</h2>
      <div className="grid gap-2 text-sm text-zinc-400 sm:grid-cols-2">
        {profile.full_name && (
          <div>
            <span className="text-zinc-600">Name: </span>
            {profile.full_name}
          </div>
        )}
        {profile.email && (
          <div>
            <span className="text-zinc-600">Email: </span>
            {profile.email}
          </div>
        )}
        {profile.location && (
          <div>
            <span className="text-zinc-600">Location: </span>
            {profile.location}
          </div>
        )}
        {profile.summary && (
          <div className="sm:col-span-2">
            <span className="text-zinc-600">Summary: </span>
            {profile.summary}
          </div>
        )}
      </div>
    </Card>
  );
}

function groupSkills(skills: ResumeSkill[]): Record<string, ResumeSkill[]> {
  const groups: Record<string, ResumeSkill[]> = {};
  for (const s of skills) {
    const key = s.category || "Other";
    (groups[key] ??= []).push(s);
  }
  return groups;
}

export default function ResumePage() {
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api
      .get<Resume[]>("/api/v1/resumes")
      .then((data) => {
        setResumes(data);
        setLoading(false);
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : "Failed to load resumes");
        setLoading(false);
      });
  }, []);

  async function onFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await api.post<{ resume: Resume }>("/api/v1/resumes/upload", form);
      setResumes((prev) => [res.resume, ...prev]);
      if (fileRef.current) fileRef.current.value = "";
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  const latest = resumes[0];

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Resume</h1>
          <p className="mt-1 text-sm text-zinc-500">
            Upload a PDF or TXT — JobPilot parses your skills and experience with AI
          </p>
        </div>
        <Button onClick={() => fileRef.current?.click()} disabled={uploading}>
          {uploading ? <Spinner /> : null}
          {uploading ? "Analyzing…" : "Upload resume"}
        </Button>
        <input
          ref={fileRef}
          type="file"
          accept=".pdf,.txt,application/pdf,text/plain"
          className="hidden"
          onChange={onFileChange}
        />
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
      ) : !latest ? (
        <EmptyState
          icon="📄"
          title="No resume yet"
          description="Upload your resume and the AI will extract skills, projects, experience, and education to power your job matches."
          action={
            <Button onClick={() => fileRef.current?.click()}>
              Upload your resume
            </Button>
          }
        />
      ) : latest.parse_status === "failed" ? (
        <EmptyState
          icon="⚠️"
          title="Couldn't parse this resume"
          description={latest.parse_error ?? "Try a different file."}
        />
      ) : latest.parse_status === "parsing" ? (
        <div className="flex items-center justify-center gap-3 py-24 text-zinc-500">
          <Spinner className="h-5 w-5" /> Analyzing resume…
        </div>
      ) : (
        <div className="space-y-6">
          <Card className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-zinc-200">{latest.filename}</p>
              <p className="mt-0.5 text-xs text-zinc-500">
                Parsed {new Date(latest.created_at).toLocaleDateString()} ·{" "}
                {latest.skills?.length ?? 0} skills extracted
              </p>
            </div>
            <Badge className="border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
              ✓ Parsed
            </Badge>
          </Card>

          {latest.structured && (
            <ProfileCard structured={latest.structured} />
          )}

          {latest.skills && latest.skills.length > 0 && (
            <Card>
              <h2 className="mb-4 font-semibold">Skills</h2>
              <div className="space-y-4">
                {Object.entries(groupSkills(latest.skills)).map(([category, skills]) => (
                  <div key={category}>
                    <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-500">
                      {category}
                    </h3>
                    <div className="flex flex-wrap gap-1.5">
                      {skills.map((s) => (
                        <Badge key={s.name} className="border-indigo-500/25 bg-indigo-500/10 text-indigo-300">
                          {s.name}
                        </Badge>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {latest.projects && latest.projects.length > 0 && (
            <Card>
              <h2 className="mb-3 font-semibold">Projects</h2>
              <ul className="space-y-3">
                {latest.projects.map((p, i) => (
                  <li key={i}>
                    <p className="font-medium text-zinc-100">
                      {String(p.name ?? "Untitled project")}
                    </p>
                    {p.description ? (
                      <p className="mt-0.5 text-sm text-zinc-400">{String(p.description)}</p>
                    ) : null}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {latest.experience && latest.experience.length > 0 && (
            <Card>
              <h2 className="mb-3 font-semibold">Experience</h2>
              <ul className="space-y-3">
                {latest.experience.map((e, i) => (
                  <li key={i}>
                    <p className="font-medium text-zinc-100">
                      {String(e.role ?? "")}
                      {e.company ? ` · ${String(e.company)}` : ""}
                    </p>
                    {e.start ? (
                      <p className="text-xs text-zinc-600">
                        {String(e.start)} – {String(e.end ?? "Present")}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {latest.education && latest.education.length > 0 && (
            <Card>
              <h2 className="mb-3 font-semibold">Education</h2>
              <ul className="space-y-3">
                {latest.education.map((e, i) => {
                  const parts = [
                    String(e.institution ?? ""),
                    String(e.year ?? ""),
                    e.cgpa ? `CGPA ${String(e.cgpa)}` : "",
                  ].filter(Boolean);
                  return (
                    <li key={i}>
                      <p className="font-medium text-zinc-100">{String(e.degree ?? "")}</p>
                      {parts.length > 0 && (
                        <p className="text-sm text-zinc-500">{parts.join(" · ")}</p>
                      )}
                    </li>
                  );
                })}
              </ul>
            </Card>
          )}

          {latest.certifications && latest.certifications.length > 0 && (
            <Card>
              <h2 className="mb-3 font-semibold">Certifications</h2>
              <ul className="list-inside list-disc space-y-1 text-sm text-zinc-400">
                {latest.certifications.map((c) => (
                  <li key={c}>{c}</li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
