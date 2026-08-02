"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type {
  ScanResult,
  TelegramLinkResult,
  TelegramSettings,
  TelegramStatus,
} from "@/lib/types";
import { Button, Card, Input, Label, Spinner } from "@/components/ui";
import { cn } from "@/lib/utils";

const INTERVALS = [
  { value: 15, label: "Every 15 minutes" },
  { value: 30, label: "Every 30 minutes" },
  { value: 60, label: "Every hour" },
  { value: 360, label: "Every 6 hours" },
  { value: 1440, label: "Once a day" },
];

function Toggle({
  label,
  hint,
  checked,
  onChange,
}: {
  label: string;
  hint?: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-start gap-3">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-0.5 h-4 w-4 accent-indigo-500"
      />
      <div>
        <span className="text-sm font-medium text-zinc-200">{label}</span>
        {hint && <p className="text-xs text-zinc-500">{hint}</p>}
      </div>
    </label>
  );
}

export default function TelegramPage() {
  const [status, setStatus] = useState<TelegramStatus | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [linkResult, setLinkResult] = useState<TelegramLinkResult | null>(null);
  const [copied, setCopied] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const [settings, setSettings] = useState<TelegramSettings>({
    notify_enabled: false,
    min_match_score: 60,
    scheduler_interval_minutes: 60,
    search_keywords: [],
    max_per_scan: 5,
    daily_summary_enabled: false,
    weekly_report_enabled: false,
  });
  const [keywordsInput, setKeywordsInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api
      .get<TelegramStatus>("/api/v1/telegram/status")
      .then((data) => {
        setStatus(data);
        setSettings(data.settings);
        setKeywordsInput((data.settings.search_keywords ?? []).join(", "));
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : "Failed to load Telegram status");
      })
      .finally(() => setLoaded(true));
  }, []);

  function generateCode() {
    setGenerating(true);
    setLinkResult(null);
    setError("");
    api
      .post<TelegramLinkResult>("/api/v1/telegram/link")
      .then((res) => setLinkResult(res))
      .catch((e) =>
        setError(e instanceof Error ? e.message : "Failed to generate link code")
      )
      .finally(() => setGenerating(false));
  }

  async function copyCode() {
    if (!linkResult) return;
    try {
      await navigator.clipboard.writeText(`/link ${linkResult.code}`);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard unavailable */
    }
  }

  function saveSettings() {
    setSaving(true);
    setSaved(false);
    setError("");
    const keywords = keywordsInput
      .split(",")
      .map((k) => k.trim())
      .filter(Boolean);
    api
      .put<{ ok: boolean }>("/api/v1/telegram/settings", {
        ...settings,
        search_keywords: keywords,
      })
      .then(() => {
        setSaved(true);
        setSettings((s) => ({ ...s, search_keywords: keywords }));
        setTimeout(() => setSaved(false), 2500);
      })
      .catch((e) =>
        setError(e instanceof Error ? e.message : "Failed to save settings")
      )
      .finally(() => setSaving(false));
  }

  function syncNow() {
    setSyncing(true);
    setScanResult(null);
    setMessage("");
    setError("");
    api
      .post<ScanResult | { error: string }>("/api/v1/telegram/sync-now")
      .then((res) => {
        if ("error" in res) {
          setMessage(res.error);
        } else {
          setScanResult(res as ScanResult);
        }
        return api.get<TelegramStatus>("/api/v1/telegram/status");
      })
      .then(setStatus)
      .catch((e) =>
        setError(e instanceof Error ? e.message : "Sync failed")
      )
      .finally(() => setSyncing(false));
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
        <h1 className="text-2xl font-bold tracking-tight">Telegram Agent</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Get AI-matched jobs pushed to your Telegram with one tap
        </p>
      </header>

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span
              className={cn(
                "h-2.5 w-2.5 rounded-full",
                status?.bot_available ? "bg-emerald-500" : "bg-amber-500"
              )}
            />
            <div>
              <p className="text-sm font-medium text-zinc-100">
                {status?.bot_available ? "Bot is online" : "Bot not configured"}
              </p>
              <p className="text-xs text-zinc-500">
                {status?.bot_username
                  ? `@${status.bot_username}`
                  : "The server owner must add a TELEGRAM_BOT_TOKEN to enable the bot."}
              </p>
            </div>
          </div>
          {status?.linked && (
            <span className="rounded-full border border-emerald-500/30 bg-emerald-500/15 px-3 py-1 text-xs font-medium text-emerald-400">
              Linked as {status.username ?? status.chat_id}
            </span>
          )}
        </div>
      </Card>

      {!status?.linked ? (
        <Card>
          <h2 className="mb-2 font-semibold">Link your Telegram</h2>
          <p className="mb-4 text-sm text-zinc-500">
            Generate a one-time code, then send it to the bot on Telegram.
          </p>
          {!linkResult ? (
            <Button onClick={generateCode} disabled={generating}>
              {generating && <Spinner />}
              {generating ? "Generating…" : "Generate link code"}
            </Button>
          ) : (
            <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
              <p className="text-xs text-zinc-500">Your code (expires in 15 min)</p>
              <p className="my-2 font-mono text-2xl font-bold tracking-widest text-indigo-400">
                {linkResult.code}
              </p>
              <p className="text-sm text-zinc-400">
                Open Telegram, search for{" "}
                <span className="font-medium text-zinc-200">
                  @{linkResult.bot_username}
                </span>{" "}
                and send:
              </p>
              <p className="mt-2 rounded bg-zinc-900 px-3 py-2 font-mono text-sm text-emerald-400">
                /link {linkResult.code}
              </p>
              <Button variant="outline" className="mt-3" onClick={copyCode}>
                {copied ? "Copied ✓" : "Copy command"}
              </Button>
            </div>
          )}
        </Card>
      ) : (
        <Card>
          <div className="flex items-center justify-between">
            <div>
              <h2 className="font-semibold">Telegram connected</h2>
              <p className="text-sm text-zinc-500">
                {status.username
                  ? `@{status.username}`
                  : status.chat_id
                    ? `Chat ${status.chat_id}`
                    : "Unknown chat"}
              </p>
            </div>
            <span className="text-xs text-zinc-600">
              {status.last_message_at
                ? `Last message ${new Date(status.last_message_at).toLocaleString()}`
                : "Waiting for first message"}
            </span>
          </div>
        </Card>
      )}

      <Card>
        <h2 className="mb-4 font-semibold">Scan settings</h2>
        <div className="space-y-5">
          <Toggle
            label="Send job alerts to Telegram"
            hint="New AI-matched jobs are pushed as they're found"
            checked={settings.notify_enabled}
            onChange={(v) => setSettings({ ...settings, notify_enabled: v })}
          />
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label>Minimum match score (%)</Label>
              <Input
                type="number"
                min={0}
                max={100}
                value={settings.min_match_score}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    min_match_score: Number(e.target.value),
                  })
                }
              />
            </div>
            <div>
              <Label>How often to scan</Label>
              <select
                value={settings.scheduler_interval_minutes}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    scheduler_interval_minutes: Number(e.target.value),
                  })
                }
                className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-indigo-500"
              >
                {INTERVALS.map((i) => (
                  <option key={i.value} value={i.value}>
                    {i.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <Label>Search keywords</Label>
            <Input
              value={keywordsInput}
              onChange={(e) => setKeywordsInput(e.target.value)}
              placeholder="e.g. python, data analyst, internship"
            />
            <p className="mt-1.5 text-xs text-zinc-600">
              Comma-separated. Leave empty to use your resume and preferences.
            </p>
          </div>
          <div>
            <Label>Max alerts per scan</Label>
            <Input
              type="number"
              min={1}
              max={20}
              value={settings.max_per_scan}
              onChange={(e) =>
                setSettings({ ...settings, max_per_scan: Number(e.target.value) })
              }
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Toggle
              label="Daily summary"
              hint="Recap of each day's scan at 8 PM"
              checked={settings.daily_summary_enabled}
              onChange={(v) => setSettings({ ...settings, daily_summary_enabled: v })}
            />
            <Toggle
              label="Weekly report"
              hint="Full week's performance every Sunday"
              checked={settings.weekly_report_enabled}
              onChange={(v) => setSettings({ ...settings, weekly_report_enabled: v })}
            />
          </div>
          {settings.last_scan_at && (
            <p className="text-xs text-zinc-600">
              Last scan: {new Date(settings.last_scan_at).toLocaleString()}
            </p>
          )}
          <div className="flex items-center gap-3">
            <Button onClick={saveSettings} disabled={saving}>
              {saving && <Spinner />}
              {saving ? "Saving…" : "Save settings"}
            </Button>
            {saved && <span className="text-sm text-emerald-400">Saved ✓</span>}
          </div>
        </div>
      </Card>

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-semibold">Run a scan now</h2>
            <p className="text-sm text-zinc-500">
              Scrape Internshala, match against your profile, and push alerts to
              Telegram.
            </p>
          </div>
          <Button
            variant="outline"
            onClick={syncNow}
            disabled={syncing || !status?.linked || !status.bot_available}
          >
            {syncing && <Spinner />}
            {syncing ? "Scanning…" : "Sync now"}
          </Button>
        </div>
        {message && (
          <p className="mt-3 text-sm text-amber-400">
            {message.startsWith("Synced") ? "✅" : "⚠️"} {message}
          </p>
        )}
        {scanResult && (
          <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              { label: "Scanned", value: scanResult.scanned },
              { label: "Matched", value: scanResult.matched },
              { label: "Sent", value: scanResult.sent },
              { label: "Ignored", value: scanResult.ignored },
            ].map((s) => (
              <div
                key={s.label}
                className="rounded-lg border border-zinc-800 bg-zinc-950 p-3"
              >
                <div className="text-2xl font-bold text-zinc-100">{s.value}</div>
                <div className="text-xs text-zinc-500">{s.label}</div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
