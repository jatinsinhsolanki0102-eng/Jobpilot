export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export interface User {
  id: number;
  email: string;
  full_name: string;
  is_active: boolean;
  created_at: string;
}

export interface ResumeSkill {
  name: string;
  category: string;
}

export interface Resume {
  id: number;
  filename: string;
  file_type: string;
  parse_status: string;
  parse_error?: string | null;
  raw_text?: string | null;
  skills?: ResumeSkill[] | null;
  projects?: Record<string, unknown>[] | null;
  experience?: Record<string, unknown>[] | null;
  education?: Record<string, unknown>[] | null;
  certifications?: string[] | null;
  structured?: Record<string, unknown> | null;
  created_at: string;
}

export interface Preference {
  id?: number;
  job_type?: string | null;
  work_modes?: string[] | null;
  locations?: string[] | null;
  salary_min?: number | null;
  salary_max?: number | null;
  experience_level?: string | null;
  company_types?: string[] | null;
  domains?: string[] | null;
  include_broad_suggestions?: boolean;
  updated_at?: string;
}

export interface Job {
  id: number;
  source_id: string;
  source: string;
  title: string;
  company_name: string;
  location?: string | null;
  work_mode?: string | null;
  employment_type?: string | null;
  salary_min?: number | null;
  salary_max?: number | null;
  salary_currency: string;
  experience_required?: string | null;
  description?: string | null;
  skills_required?: string[] | null;
  benefits?: string[] | null;
  application_deadline?: string | null;
  posted_at?: string | null;
  url?: string | null;
  created_at: string;
}

export interface MatchBreakdown {
  score: number;
  skill_match: number;
  semantic_match: number;
  matched_skills: string[];
  missing_skills: string[];
}

export interface RankedJob extends Job {
  match?: MatchBreakdown | null;
  preference_fit?: number | null;
  rank_score?: number | null;
}

export interface AiAssessment {
  score: number;
  strengths: string[];
  gaps: string[];
  summary?: string | null;
}

export interface JobDetail extends RankedJob {
  ai_assessment?: AiAssessment | null;
  has_applied: boolean;
}

export type ApplicationStatus =
  | "applied"
  | "pending"
  | "interview"
  | "rejected"
  | "offer"
  | "withdrawn";

export interface Application {
  id: number;
  job_id: number;
  status: ApplicationStatus;
  cover_letter?: string | null;
  notes?: string | null;
  match_score?: number | null;
  interview_date?: string | null;
  offer_details?: Record<string, unknown> | null;
  created_at: string;
  job_title?: string | null;
  company_name?: string | null;
}

export interface TopMatch {
  id: number;
  title: string;
  company_name: string;
  location?: string | null;
  work_mode?: string | null;
  salary_min?: number | null;
  salary_max?: number | null;
  rank_score: number;
  match_score: number;
  matched_skills: string[];
}

export interface RecentApplication {
  id: number;
  job_id: number;
  status: ApplicationStatus;
  job_title?: string | null;
  company_name?: string | null;
  created_at: string;
}

export interface DashboardStats {
  total_jobs: number;
  applied: number;
  pending: number;
  interviews: number;
  offers: number;
  rejected: number;
  saved: number;
  top_matches: TopMatch[];
  recent_applications: RecentApplication[];
  top_skills: { category: string; count: number }[];
}

export interface TelegramSettings {
  notify_enabled: boolean;
  min_match_score: number;
  scheduler_interval_minutes: number;
  search_keywords: string[];
  max_per_scan: number;
  daily_summary_enabled: boolean;
  weekly_report_enabled: boolean;
  last_scan_at?: string | null;
}

export interface TelegramStatus {
  linked: boolean;
  chat_id: string | null;
  username: string | null;
  last_message_at: string | null;
  bot_available: boolean;
  bot_username: string;
  settings: TelegramSettings;
}

export interface TelegramLinkResult {
  code: string;
  bot_username: string;
  bot_available: boolean;
  expires_in_minutes: number;
}

export interface ScanReportData {
  scanned?: number;
  matched?: number;
  sent?: number;
  ignored?: number;
  avg_score?: number;
  best?: { title: string; company: string; score: number } | null;
  applications?: number;
  interviews?: number;
  top_skills?: { skill: string; count: number }[];
}

export interface ScanReport {
  period_date: string;
  data: ScanReportData;
  created_at: string;
}

export interface AnalyticsOverview {
  series: {
    date: string;
    scanned: number;
    matched: number;
    sent: number;
    ignored: number;
    apps: number;
  }[];
  totals: {
    scanned: number;
    matched: number;
    sent: number;
    ignored: number;
    apps: number;
  };
}

export interface AnalyticsReports {
  daily: ScanReport[];
  weekly: ScanReport[];
}

export interface SkillCount {
  skill: string;
  count: number;
}

export interface Funnel {
  total: number;
  saved: number;
  by_status: Record<string, number>;
  rates: Record<string, number>;
}

export interface NotificationItem {
  id: number;
  kind: string;
  title: string;
  body: string;
  job_id: number | null;
  read: boolean;
  created_at: string;
}

export interface ScanResult {
  scanned: number;
  matched: number;
  sent: number;
  ignored: number;
  avg_score: number;
}
