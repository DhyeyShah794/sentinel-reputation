"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Brain, FileText, AlertTriangle, TrendingUp, Lightbulb, CheckCircle, Zap, Bell, ArrowRight } from "lucide-react";
import { api, ExecutiveSummary, RiskData } from "@/lib/api";
import { getRiskColor, getScoreColor, getScoreLabel } from "@/lib/utils";

interface Opportunity {
  title?: string;
  driver?: string;
  impact_score?: number;
  description?: string;
  amplification_potential?: string;
  [key: string]: unknown;
}

export default function IntelligenceHub() {
  const [summary, setSummary] = useState<ExecutiveSummary | null>(null);
  const [risks, setRisks] = useState<RiskData | null>(null);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [loading, setLoading] = useState(true);
  const [partialError, setPartialError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const [summaryResult, risksResult, oppsResult] = await Promise.allSettled([
        api.getExecutiveSummary(),
        api.getRisks(),
        api.getOpportunities(),
      ]);

      if (cancelled) return;

      if (summaryResult.status === "fulfilled") {
        setSummary(summaryResult.value);
      } else {
        setPartialError("Executive summary not yet generated. Run the pipeline to produce it.");
      }

      if (risksResult.status === "fulfilled") {
        setRisks(risksResult.value);
      }

      if (oppsResult.status === "fulfilled") {
        setOpportunities((oppsResult.value.opportunities || []) as Opportunity[]);
      }

      setLoading(false);
    }
    load();
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-sm text-[var(--text-muted)] mt-3">Loading intelligence data...</p>
        </div>
      </div>
    );
  }

  if (!summary && !risks && opportunities.length === 0) {
    return (
      <div className="card p-8 text-center">
        <AlertTriangle className="w-10 h-10 text-amber-400 mx-auto" />
        <p className="text-lg font-semibold mt-3">No Intelligence Data Available</p>
        <p className="text-sm text-[var(--text-secondary)] mt-1">
          Run the pipeline first to generate insights, risks, and opportunities.
        </p>
        <p className="text-xs text-[var(--text-muted)] mt-4">
          Start the backend: <code className="text-blue-400">uvicorn app.main:app --reload</code>
        </p>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-5 animate-fade-in">
        <div className="flex items-center gap-2">
          <Brain className="w-6 h-6 text-violet-400" />
          <h1 className="text-2xl font-bold">Intelligence Hub</h1>
        </div>
        <p className="text-sm text-[var(--text-secondary)] mt-1">
          AI-generated insights, trends, risks, and opportunities
        </p>
      </div>

      {partialError && (
        <div className="card p-4 mb-4 border-l-2 border-l-amber-500 animate-fade-in">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />
            <p className="text-xs text-[var(--text-secondary)]">{partialError}</p>
          </div>
        </div>
      )}

      {summary && (
        <>
          {/* Executive Brief Header */}
          <div
            className="card p-6 mb-4 animate-fade-in border-l-2 border-l-blue-500"
            style={{
              background: `linear-gradient(135deg, var(--bg-card) 55%, ${getScoreColor(summary.reputation_score)}0a 100%)`,
            }}
          >
            {/* Eyebrow */}
            <div className="flex items-center gap-2 mb-4">
              <div className="p-1.5 rounded-lg bg-blue-500/10">
                <FileText className="w-4 h-4 text-blue-400" />
              </div>
              <h2 className="text-[10px] font-semibold text-blue-400 uppercase tracking-[0.1em]">
                Executive Intelligence Brief
              </h2>
            </div>

            {/* Brand + Score + Mentions */}
            <div className="flex items-end justify-between gap-6 pb-4 mb-4 border-b border-[var(--border)]">
              <div>
                <p className="text-2xl font-extrabold leading-none">{summary.brand_name}</p>
                <p className="text-xs text-[var(--text-muted)] mt-1.5">{summary.period}</p>
              </div>

              <div className="flex items-center gap-6">
                <Link
                  href="/command-center"
                  className="flex flex-col items-end group"
                  title="View Command Center"
                >
                  <div className="flex items-baseline gap-1">
                    <span
                      className="text-3xl font-extrabold tabular-nums leading-none transition-transform group-hover:scale-105"
                      style={{ color: getScoreColor(summary.reputation_score) }}
                    >
                      {summary.reputation_score}
                    </span>
                    <span className="text-xs font-medium text-[var(--text-muted)]">/100</span>
                  </div>
                  <span
                    className="text-[10px] font-semibold uppercase tracking-wider mt-1"
                    style={{ color: getScoreColor(summary.reputation_score) }}
                  >
                    {getScoreLabel(summary.reputation_score)}
                  </span>
                </Link>

                <div className="h-10 w-px bg-[var(--border)]" />

                <Link
                  href="/explorer"
                  className="flex flex-col items-start group"
                  title="Explore mentions"
                >
                  <span className="text-3xl font-extrabold tabular-nums leading-none text-[var(--text-primary)]">
                    {summary.total_mentions}
                  </span>
                  <span className="text-[10px] font-medium text-[var(--text-muted)] uppercase tracking-wider mt-1 flex items-center gap-1 group-hover:text-blue-400 transition-colors">
                    mentions <ArrowRight className="w-2.5 h-2.5 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </span>
                </Link>
              </div>
            </div>

            {/* Key Findings */}
            <div>
              <h3 className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.1em] mb-3">Key Findings</h3>
              <div className="grid grid-cols-2 gap-x-6 gap-y-2.5">
                {summary.key_findings.map((finding, i) => (
                  <div key={i} className="flex items-start gap-2.5">
                    <span className="flex items-center justify-center w-4 h-4 rounded-full bg-blue-500/10 text-[9px] font-bold text-blue-400 mt-0.5 flex-shrink-0 tabular-nums">
                      {i + 1}
                    </span>
                    <p className="text-sm text-[var(--text-secondary)] leading-relaxed">{finding}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Positives & Negatives */}
          <div className="grid grid-cols-2 gap-4 mb-4">
            <Link
              href="/explorer?sentiment=positive"
              className="card p-5 animate-fade-in block hover:ring-1 hover:ring-emerald-500/20 transition-all group"
              style={{ animationDelay: "100ms" }}
            >
              <div className="flex items-center gap-2 mb-3">
                <TrendingUp className="w-4 h-4 text-emerald-400" />
                <h3 className="text-xs font-semibold text-emerald-400 uppercase tracking-wider">Top Positives</h3>
                <ArrowRight className="w-3 h-3 text-emerald-400/50 ml-auto opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
              <div className="space-y-2">
                {summary.top_positives.map((item, i) => (
                  <div key={i} className="flex items-start gap-2">
                    <CheckCircle className="w-3.5 h-3.5 text-emerald-400 mt-0.5 flex-shrink-0" />
                    <p className="text-sm text-[var(--text-secondary)]">{item}</p>
                  </div>
                ))}
              </div>
            </Link>

            <Link
              href="/explorer?sentiment=negative"
              className="card p-5 animate-fade-in block hover:ring-1 hover:ring-rose-500/20 transition-all group"
              style={{ animationDelay: "150ms" }}
            >
              <div className="flex items-center gap-2 mb-3">
                <AlertTriangle className="w-4 h-4 text-rose-400" />
                <h3 className="text-xs font-semibold text-rose-400 uppercase tracking-wider">Top Negatives</h3>
                <ArrowRight className="w-3 h-3 text-rose-400/50 ml-auto opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
              <div className="space-y-2">
                {summary.top_negatives.map((item, i) => (
                  <div key={i} className="flex items-start gap-2">
                    <div className="w-1.5 h-1.5 rounded-full bg-rose-400 mt-1.5 flex-shrink-0" />
                    <p className="text-sm text-[var(--text-secondary)]">{item}</p>
                  </div>
                ))}
              </div>
            </Link>
          </div>

          {/* Emerging Themes + Risk Alerts */}
          {(summary.emerging_themes?.length > 0 || summary.risk_alerts?.length > 0) && (
            <div className="grid grid-cols-2 gap-4 mb-4">
              {summary.emerging_themes?.length > 0 && (
                <Link
                  href="/themes"
                  className="card p-5 animate-fade-in border-l-2 border-l-violet-500 block hover:ring-1 hover:ring-violet-500/20 transition-all group"
                  style={{ animationDelay: "175ms" }}
                >
                  <div className="flex items-center gap-2 mb-3">
                    <Zap className="w-4 h-4 text-violet-400" />
                    <h3 className="text-xs font-semibold text-violet-400 uppercase tracking-wider">Emerging Themes</h3>
                    <ArrowRight className="w-3 h-3 text-violet-400/50 ml-auto opacity-0 group-hover:opacity-100 transition-opacity" />
                  </div>
                  <div className="space-y-2">
                    {summary.emerging_themes.map((theme, i) => (
                      <div key={i} className="flex items-start gap-2">
                        <div className="w-1.5 h-1.5 rounded-full bg-violet-400 mt-1.5 flex-shrink-0" />
                        <p className="text-sm text-[var(--text-secondary)]">{theme}</p>
                      </div>
                    ))}
                  </div>
                </Link>
              )}

              {summary.risk_alerts?.length > 0 && (
                <Link
                  href="/explorer?risk_level=high"
                  className="card p-5 animate-fade-in border-l-2 border-l-amber-500 block hover:ring-1 hover:ring-amber-500/20 transition-all group"
                  style={{ animationDelay: "175ms" }}
                >
                  <div className="flex items-center gap-2 mb-3">
                    <Bell className="w-4 h-4 text-amber-400" />
                    <h3 className="text-xs font-semibold text-amber-400 uppercase tracking-wider">Risk Alerts</h3>
                    <ArrowRight className="w-3 h-3 text-amber-400/50 ml-auto opacity-0 group-hover:opacity-100 transition-opacity" />
                  </div>
                  <div className="space-y-2">
                    {summary.risk_alerts.map((alert, i) => (
                      <div key={i} className="flex items-start gap-2">
                        <div className="w-1.5 h-1.5 rounded-full bg-amber-400 mt-1.5 flex-shrink-0" />
                        <p className="text-sm text-[var(--text-secondary)]">{alert}</p>
                      </div>
                    ))}
                  </div>
                </Link>
              )}
            </div>
          )}

          {/* Recommended Actions */}
          <div className="card p-5 mb-4 animate-fade-in" style={{ animationDelay: "200ms" }}>
            <div className="flex items-center gap-2 mb-3">
              <Lightbulb className="w-4 h-4 text-amber-400" />
              <h3 className="text-xs font-semibold text-amber-400 uppercase tracking-wider">
                Recommended Actions
              </h3>
            </div>
            <div className="grid grid-cols-2 gap-3">
              {summary.recommended_actions.map((action, i) => (
                <div key={i} className="flex items-start gap-2 p-3 rounded-lg bg-[var(--bg-primary)]">
                  <span className="text-xs font-bold text-amber-400">{i + 1}.</span>
                  <p className="text-xs text-[var(--text-secondary)] leading-relaxed">{action}</p>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {/* Risk Table */}
      {risks && risks.risks.length > 0 && (
        <div className="card p-5 mb-4 animate-fade-in" style={{ animationDelay: "250ms" }}>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-400" />
              <h3 className="text-xs font-semibold text-rose-400 uppercase tracking-wider">
                Risk Alerts ({risks.total})
              </h3>
            </div>
            <Link href="/explorer?risk_level=high" className="text-[10px] text-[var(--text-muted)] hover:text-rose-400 flex items-center gap-1 transition-colors">
              View all high-risk mentions <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
          <div className="space-y-2">
            {risks.risks.slice(0, 8).map((risk, i) => (
              <Link
                key={i}
                href={`/explorer?risk_level=${risk.risk_level}`}
                className="flex items-center gap-3 p-3 rounded-lg bg-[var(--bg-primary)] hover:bg-[var(--bg-card-hover)] transition-colors group"
              >
                <span className={`text-[10px] px-2 py-0.5 rounded-full border font-semibold flex-shrink-0 ${getRiskColor(risk.risk_level)}`}>
                  {risk.risk_level.toUpperCase()}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-[var(--text-primary)] truncate">{risk.title}</p>
                  {risk.risk_signal && (
                    <p className="text-[10px] text-[var(--text-muted)] truncate mt-0.5">{risk.risk_signal}</p>
                  )}
                </div>
                <span className="text-[10px] text-[var(--text-muted)] flex-shrink-0">{risk.source_name}</span>
                <ArrowRight className="w-3 h-3 text-[var(--text-muted)] flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Opportunities */}
      {opportunities.length > 0 && (
        <div className="card p-5 animate-fade-in" style={{ animationDelay: "300ms" }}>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-emerald-400" />
              <h3 className="text-xs font-semibold text-emerald-400 uppercase tracking-wider">
                Amplification Opportunities
              </h3>
            </div>
            <Link href="/explorer?sentiment=positive" className="text-[10px] text-[var(--text-muted)] hover:text-emerald-400 flex items-center gap-1 transition-colors">
              Explore positive mentions <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {opportunities.slice(0, 6).map((opp, i) => (
              <Link
                key={i}
                href={opp.driver ? `/explorer?driver=${encodeURIComponent(opp.driver as string)}&sentiment=positive` : "/explorer?sentiment=positive"}
                className="p-3 rounded-lg bg-[var(--bg-primary)] border border-emerald-500/10 hover:border-emerald-500/30 hover:bg-[var(--bg-card-hover)] transition-all group"
              >
                <p className="text-xs font-semibold text-[var(--text-primary)] line-clamp-2">{opp.title ?? "—"}</p>
                <div className="flex items-center gap-2 mt-1.5 mb-2">
                  <span className="text-[10px] text-emerald-400">{opp.driver ?? ""}</span>
                  {opp.impact_score !== undefined && (
                    <span className="text-[10px] text-[var(--text-muted)]">
                      Impact: {((opp.impact_score as number) * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
                {opp.description && (
                  <p className="text-[10px] text-[var(--text-secondary)] leading-relaxed line-clamp-3">
                    {opp.description as string}
                  </p>
                )}
                {opp.amplification_potential && (
                  <p className="text-[10px] text-emerald-400/80 mt-1.5 leading-relaxed line-clamp-2">
                    ↑ {opp.amplification_potential as string}
                  </p>
                )}
                <p className="text-[10px] text-emerald-400/60 mt-2 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  Explore mentions <ArrowRight className="w-3 h-3" />
                </p>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
