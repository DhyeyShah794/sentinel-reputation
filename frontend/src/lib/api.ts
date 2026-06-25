/**
 * Sentinel API Client — Communicates with the FastAPI backend.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!res.ok) {
    throw new Error(`API Error: ${res.status} ${res.statusText}`);
  }

  return res.json();
}

// ── Types ──

export interface Mention {
  id: string;
  date: string | null;
  url: string;
  source_name: string;
  source_type: string;
  title: string;
  combined_text: string;
  reach: number;
  driver: string | null;
  sub_driver: string | null;
  classification_confidence: number;
  classification_rationale: string | null;
  sentiment: string;
  sentiment_confidence: number;
  sentiment_explanation: string | null;
  impact_score: number;
  risk_level: string;
  risk_type: string | null;
  risk_signal: string | null;
  themes: string[];
  emotional_intensity: string;
  sentiment_agreement: boolean;
}

export interface MentionListResponse {
  data: Mention[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface OverviewData {
  total_mentions: number;
  reputation_score: number;
  sentiment_distribution: Record<string, number>;
  driver_distribution: Record<string, number>;
  sub_driver_distribution: Record<string, number>;
  source_distribution: Record<string, number>;
  source_type_distribution: Record<string, number>;
  risk_summary: Record<string, number>;
  mention_trend: { date: string; count: number }[];
}

export interface DriverScore {
  driver: string;
  score: number;
  sub_scores: Record<string, number>;
  mention_count: number;
  positive_count: number;
  negative_count: number;
  neutral_count: number;
}

export interface ReputationScoreData {
  overall_score: number;
  driver_scores: DriverScore[];
  top_positive_driver: string | null;
  top_negative_driver: string | null;
  methodology_note: string;
}

export interface Theme {
  theme_name: string;
  description: string;
  mention_count: number;
  sentiment_skew: string;
  representative_quotes: string[];
  business_implication: string;
}

export interface ExecutiveSummary {
  brand_name: string;
  period: string;
  reputation_score: number;
  total_mentions: number;
  key_findings: string[];
  top_positives: string[];
  top_negatives: string[];
  emerging_themes: string[];
  recommended_actions: string[];
  risk_alerts: string[];
}

export interface CommandCenterData {
  reputation_score: number;
  driver_scores: DriverScore[];
  biggest_positive_driver: {
    driver: string;
    score: number;
    mention_count: number;
    representative: string;
  } | null;
  biggest_negative_driver: {
    driver: string;
    score: number;
    mention_count: number;
    representative: string;
  } | null;
  emerging_theme: Theme | null;
  primary_risk: {
    title: string;
    risk_level: string;
    risk_type: string;
    risk_signal: string;
  } | null;
  recommended_actions: string[];
  score_waterfall: {
    name: string;
    driver: string;
    value: number;
    type: string;
  }[];
}

export interface RiskData {
  risks: {
    mention_id: string;
    title: string;
    risk_level: string;
    risk_type: string;
    risk_signal: string;
    source_name: string;
    sentiment: string;
    impact_score: number;
  }[];
  total: number;
}

export interface SourceData {
  sources: {
    source_name: string;
    source_type: string;
    count: number;
    sentiment: Record<string, number>;
    total_reach: number;
    avg_reach: number;
  }[];
}

export interface TimelineData {
  timeline: {
    month: string;
    total: number;
    positive: number;
    neutral: number;
    negative: number;
  }[];
}

export interface SentimentAnalytics {
  by_driver: Record<string, Record<string, number>>;
  by_source_type: Record<string, Record<string, number>>;
  agreement_rate: number;
  total_agreements: number;
  total_disagreements: number;
}

export interface DriverAnalytics {
  drivers: Record<
    string,
    {
      count: number;
      sentiment: Record<string, number>;
      sub_drivers: Record<string, { count: number; sentiment: Record<string, number> }>;
      avg_impact: number;
    }
  >;
  driver_scores: DriverScore[];
}

// ── API Calls ──

export const api = {
  // Health
  health: () => fetchAPI<{ status: string; data_loaded: boolean; mentions_count: number }>("/api/health"),

  // Mentions
  getMentions: (params?: {
    driver?: string;
    sub_driver?: string;
    sentiment?: string;
    source_type?: string;
    source_name?: string;
    risk_level?: string;
    theme?: string;
    search?: string;
    sort_by?: string;
    sort_order?: string;
    page?: number;
    page_size?: number;
  }) => {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== "") {
          searchParams.set(key, String(value));
        }
      });
    }
    const query = searchParams.toString();
    return fetchAPI<MentionListResponse>(`/api/mentions${query ? `?${query}` : ""}`);
  },

  getMention: (id: string) => fetchAPI<Mention>(`/api/mentions/${id}`),

  // Analytics
  getOverview: () => fetchAPI<OverviewData>("/api/analytics/overview"),
  getSentimentAnalytics: () => fetchAPI<SentimentAnalytics>("/api/analytics/sentiment"),
  getDriverAnalytics: () => fetchAPI<DriverAnalytics>("/api/analytics/drivers"),
  getSourceAnalytics: () => fetchAPI<SourceData>("/api/analytics/sources"),
  getTimeline: () => fetchAPI<TimelineData>("/api/analytics/timeline"),

  // Intelligence
  getReputationScore: () => fetchAPI<ReputationScoreData>("/api/intelligence/score"),
  getThemes: () => fetchAPI<{ themes: Theme[] }>("/api/intelligence/themes"),
  getRisks: () => fetchAPI<RiskData>("/api/intelligence/risks"),
  getOpportunities: () => fetchAPI<{ opportunities: Record<string, unknown>[] }>("/api/intelligence/opportunities"),
  getExecutiveSummary: () => fetchAPI<ExecutiveSummary>("/api/intelligence/summary"),
  getCommandCenter: () => fetchAPI<CommandCenterData>("/api/intelligence/command-center"),

  // Pipeline
  runPipeline: () => fetchAPI<{ status: string; message: string }>("/api/pipeline/run", { method: "POST" }),
  getPipelineStatus: () => fetchAPI<{ status: string; progress?: number; message?: string }>("/api/pipeline/status"),
};
