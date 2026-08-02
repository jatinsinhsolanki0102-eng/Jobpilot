"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Preference } from "@/lib/types";
import { Button, Card, Input, Label, Spinner } from "@/components/ui";
import { cn } from "@/lib/utils";

const WORK_MODES = ["Remote", "Hybrid", "Onsite"];
const COMPANY_TYPES = ["Startup", "MNC", "Product company", "Agency"];
const DOMAINS = [
  "AI",
  "Machine Learning",
  "Backend",
  "Frontend",
  "Full Stack",
  "Data Science",
  "Data Engineering",
  "DevOps",
  "Mobile",
];

const EMPTY: Preference = {
  job_type: "",
  work_modes: [],
  locations: [],
  salary_min: null,
  salary_max: null,
  experience_level: "",
  company_types: [],
  domains: [],
  include_broad_suggestions: false,
};

function Chip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rounded-full border px-3 py-1.5 text-sm font-medium transition-colors",
        active
          ? "border-indigo-500 bg-indigo-500/15 text-indigo-300"
          : "border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-200"
      )}
    >
      {label}
    </button>
  );
}

export default function PreferencesPage() {
  const [pref, setPref] = useState<Preference>(EMPTY);
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const [locationInput, setLocationInput] = useState("");

  useEffect(() => {
    api
      .get<Preference | null>("/api/v1/preferences")
      .then((data) => {
        if (data) {
          setPref({ ...EMPTY, ...data });
          setLocationInput((data.locations ?? []).join(", "));
        }
      })
      .finally(() => setLoaded(true));
  }, []);

  function toggle(listKey: keyof Pick<Preference, "work_modes" | "company_types" | "domains">, value: string) {
    setPref((prev) => {
      const list = (prev[listKey] as string[] | null) ?? [];
      return {
        ...prev,
        [listKey]: list.includes(value)
          ? list.filter((v) => v !== value)
          : [...list, value],
      };
    });
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setSaved(false);
    setError("");
    try {
      const locations = locationInput
        .split(",")
        .map((l) => l.trim())
        .filter(Boolean);
      const payload: Preference = {
        ...pref,
        job_type: pref.job_type || null,
        experience_level: pref.experience_level || null,
        locations: locations.length ? locations : null,
      };
      await api.put("/api/v1/preferences", payload);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save preferences");
    } finally {
      setSaving(false);
    }
  }

  if (!loaded) {
    return (
      <div className="flex items-center justify-center py-24 text-zinc-500">
        <Spinner className="h-5 w-5" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">Preferences</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Tell JobPilot what you want — it never recommends outside these bounds
        </p>
      </header>

      <form onSubmit={save} className="space-y-6">
        <Card>
          <h2 className="mb-4 font-semibold">Role</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label>Job type</Label>
              <select
                value={pref.job_type ?? ""}
                onChange={(e) => setPref({ ...pref, job_type: e.target.value })}
                className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-indigo-500"
              >
                <option value="">Any</option>
                <option value="internship">Internship</option>
                <option value="full-time">Full-time</option>
                <option value="contract">Contract</option>
              </select>
            </div>
            <div>
              <Label>Experience level</Label>
              <select
                value={pref.experience_level ?? ""}
                onChange={(e) => setPref({ ...pref, experience_level: e.target.value })}
                className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-indigo-500"
              >
                <option value="">Any</option>
                <option value="fresher">Fresher</option>
                <option value="1-2 years">1-2 years</option>
                <option value="2-4 years">2-4 years</option>
                <option value="5+ years">5+ years</option>
              </select>
            </div>
          </div>
        </Card>

        <Card>
          <h2 className="mb-3 font-semibold">Work mode</h2>
          <div className="flex flex-wrap gap-2">
            {WORK_MODES.map((m) => (
              <Chip
                key={m}
                label={m}
                active={(pref.work_modes ?? []).includes(m)}
                onClick={() => toggle("work_modes", m)}
              />
            ))}
          </div>
        </Card>

        <Card>
          <h2 className="mb-3 font-semibold">Locations</h2>
          <Input
            value={locationInput}
            onChange={(e) => setLocationInput(e.target.value)}
            placeholder="e.g. Bengaluru, Mumbai, Remote"
          />
          <p className="mt-1.5 text-xs text-zinc-600">
            Comma-separated cities. Add &quot;Remote&quot; to include remote roles.
          </p>
        </Card>

        <Card>
          <h2 className="mb-3 font-semibold">Salary</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label>Minimum (₹/year or ₹/month stipend)</Label>
              <Input
                type="number"
                min={0}
                value={pref.salary_min ?? ""}
                onChange={(e) =>
                  setPref({ ...pref, salary_min: e.target.value ? Number(e.target.value) : null })
                }
                placeholder="e.g. 400000"
              />
            </div>
            <div>
              <Label>Maximum (optional)</Label>
              <Input
                type="number"
                min={0}
                value={pref.salary_max ?? ""}
                onChange={(e) =>
                  setPref({ ...pref, salary_max: e.target.value ? Number(e.target.value) : null })
                }
                placeholder="e.g. 1200000"
              />
            </div>
          </div>
        </Card>

        <Card>
          <h2 className="mb-3 font-semibold">Company type</h2>
          <div className="flex flex-wrap gap-2">
            {COMPANY_TYPES.map((c) => (
              <Chip
                key={c}
                label={c}
                active={(pref.company_types ?? []).includes(c)}
                onClick={() => toggle("company_types", c)}
              />
            ))}
          </div>
        </Card>

        <Card>
          <h2 className="mb-3 font-semibold">Domains</h2>
          <div className="flex flex-wrap gap-2">
            {DOMAINS.map((d) => (
              <Chip
                key={d}
                label={d}
                active={(pref.domains ?? []).includes(d)}
                onClick={() => toggle("domains", d)}
              />
            ))}
          </div>
        </Card>

        <Card>
          <label className="flex cursor-pointer items-start gap-3">
            <input
              type="checkbox"
              checked={pref.include_broad_suggestions}
              onChange={(e) =>
                setPref({ ...pref, include_broad_suggestions: e.target.checked })
              }
              className="mt-0.5 h-4 w-4 accent-indigo-500"
            />
            <div>
              <span className="text-sm font-medium text-zinc-200">
                Include broader suggestions
              </span>
              <p className="text-xs text-zinc-500">
                Occasionally surface opportunities slightly outside your preferences.
              </p>
            </div>
          </label>
        </Card>

        {error && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
            {error}
          </div>
        )}

        <div className="flex items-center gap-3">
          <Button type="submit" disabled={saving}>
            {saving ? <Spinner /> : null}
            {saving ? "Saving…" : "Save preferences"}
          </Button>
          {saved && <span className="text-sm text-emerald-400">Saved ✓</span>}
        </div>
      </form>
    </div>
  );
}
