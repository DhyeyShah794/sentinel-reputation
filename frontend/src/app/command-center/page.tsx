"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  TrendingUp, TrendingDown, AlertTriangle, Lightbulb,
  Zap, ChevronRight, ArrowRight, Activity,
} from "lucide-react";
import { api, CommandCenterData } from "@/lib/api";
import { getScoreColor, getScoreLabel } from "@/lib/utils";

function ScoreGaugeLarge({ score }: { score: number }) {
  const color = getScoreColor(score);
  const cx = 105, cy = 108, r = 76;
  const startAngle = 145, totalSweep = 250;

  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const pt = (deg: number) => ({
    x: +(cx + r * Math.cos(toRad(deg))).toFixed(3),
    y: +(cy + r * Math.sin(toRad(deg))).toFixed(3),
  });

  // Build an SVG arc path from pctStart to pctEnd (0–1) along the gauge sweep
  const arcPath = (pctStart: number, pctEnd: number) => {
    const a1 = startAngle + pctStart * totalSweep;
    const a2 = startAngle + pctEnd * totalSweep;
    const p1 = pt(a1), p2 = pt(a2);
    const large = (pctEnd - pctStart) * totalSweep > 180 ? 1 : 0;
    return `M ${p1.x} ${p1.y} A ${r} ${r} 0 ${large} 1 ${p2.x} ${p2.y}`;
  };

  // Colour-zone track segments
  const zones = [
    { start: 0,   end: 0.4, color: "#F43F5E" },
    { start: 0.4, end: 0.7, color: "#F59E0B" },
    { start: 0.7, end: 1.0, color: "#10B981" },
  ];

  const scorePct = score / 100;
  const progressSweepDeg = scorePct * totalSweep;
  const progressEndAngle = startAngle + progressSweepDeg;
  const tipPt = pt(progressEndAngle);
  const progressPath = arcPath(0, scorePct);

  return (
    <div className="flex flex-col items-center">
      <svg width="210" height="172" viewBox="0 0 210 172">
        <defs />

        {/* Zone-coloured background track segments */}
        {zones.map((z, i) => (
          <path
            key={i}
            d={arcPath(z.start, z.end)}
            fill="none"
            stroke={z.color}
            strokeWidth="11"
            strokeLinecap={i === 0 ? "round" : i === zones.length - 1 ? "round" : "butt"}
            opacity={0.18}
          />
        ))}

        {/* Progress arc */}
        {score > 0 && (
          <path
            d={progressPath}
            fill="none"
            stroke={color}
            strokeWidth="11"
            strokeLinecap="round"
          />
        )}

        {/* Tip dot */}
        {score > 0 && score < 100 && (
          <circle cx={tipPt.x} cy={tipPt.y} r="5.5" fill={color} />
        )}

        {/* Score number */}
        <text x={cx} y={cy - 8} textAnchor="middle" fill="var(--text-primary)" fontSize="36" fontWeight="800" fontFamily="inherit">
          {score}
        </text>
        <text x={cx} y={cy + 16} textAnchor="middle" fill="#64748b" fontSize="11.5" fontWeight="500" fontFamily="inherit">
          out of 100
        </text>
        <text x={cx} y={cy + 34} textAnchor="middle" fill={color} fontSize="13" fontWeight="700" fontFamily="inherit">
          {getScoreLabel(score)}
        </text>
      </svg>
    </div>
  );
}

function TargetIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <circle cx="12" cy="12" r="10" /><circle cx="12" cy="12" r="6" /><circle cx="12" cy="12" r="2" />
    </svg>
  );
}

export default function CommandCenter() {
  const router = useRouter();
  const [data, setData] = useState<CommandCenterData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const cc = await api.getCommandCenter();
        if (!cancelled) setData(cc);
      } catch (e: unknown) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load data");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-sm text-[var(--text-muted)] mt-3">Loading command center...</p>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="card p-8 text-center">
        <AlertTriangle className="w-10 h-10 text-amber-400 mx-auto" />
        <p className="text-lg font-semibold mt-3">Unable to Load Data</p>
        <p className="text-sm text-[var(--text-secondary)] mt-1">
          {error || "Run the pipeline first to generate data."}
        </p>
        <p className="text-xs text-[var(--text-muted)] mt-4">
          Start the backend: <code className="text-blue-400">uvicorn app.main:app --reload</code>
        </p>
      </div>
    );
  }

  const activeDrivers = data.driver_scores.filter((d) => d.mention_count > 0);

  return (
    <div>
      {/* Header */}
      <div className="mb-6 animate-fade-in">
        <div className="flex items-center gap-2">
          <TargetIcon className="w-6 h-6 text-blue-400" />
          <h1 className="text-2xl font-bold">Reputation Command Center</h1>
        </div>
        <p className="text-sm text-[var(--text-secondary)] mt-1">
          Single-screen intelligence for executive decision making
        </p>
      </div>

      {/* Row 1: Score gauge | Biggest Positive | Biggest Negative */}
      <div className="grid grid-cols-3 gap-4 mb-4">

        {/* Score card */}
        <div className="card p-5 flex flex-col animate-fade-in" style={{
          background: `linear-gradient(145deg, var(--bg-card) 50%, ${getScoreColor(data.reputation_score)}0a 100%)`,
        }}>
          <div className="flex items-center gap-2 mb-4">
            <Activity className="w-4 h-4" style={{ color: getScoreColor(data.reputation_score) }} />
            <p className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-widest">
              Reputation Score
            </p>
          </div>
          <div className="flex justify-center">
            <ScoreGaugeLarge score={data.reputation_score} />
          </div>

          {/* Driver score bars */}
          {activeDrivers.length > 0 && (
            <div className="mt-4 space-y-2.5">
              <p className="text-[9px] font-semibold text-[var(--text-muted)] uppercase tracking-widest">
                By Driver
              </p>
              {activeDrivers.slice(0, 4).map((d) => (
                <button
                  key={d.driver}
                  className="w-full text-left group"
                  onClick={() => router.push(`/explorer?driver=${encodeURIComponent(d.driver)}`)}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] text-[var(--text-secondary)] group-hover:text-[var(--text-primary)] transition-colors truncate max-w-[78%]">
                      {d.driver.replace("Responsible Business Practices", "Resp. Business")}
                    </span>
                    <span className="text-[10px] font-bold tabular-nums" style={{ color: getScoreColor(d.score) }}>
                      {d.score.toFixed(0)}
                    </span>
                  </div>
                  <div className="h-[3px] rounded-full overflow-hidden" style={{ background: `${getScoreColor(d.score)}20` }}>
                    <div
                      className="h-full rounded-full transition-all"
                      style={{ width: `${d.score}%`, background: getScoreColor(d.score) }}
                    />
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Biggest Positive */}
        {(() => {
          const d = data.biggest_positive_driver;
          const score = d?.score ?? 0;
          return (
            <div
              className="card p-5 flex flex-col justify-between animate-fade-in cursor-pointer group transition-all"
              style={{
                animationDelay: "100ms",
                background: "linear-gradient(135deg, var(--bg-card) 55%, #10B98108 100%)",
                ["--kpi-color" as string]: "#10B981",
              }}
              onClick={() => {
                if (d?.driver) router.push(`/explorer?driver=${encodeURIComponent(d.driver)}&sentiment=positive`);
              }}
            >
              <div>
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <div className="p-1.5 rounded-lg bg-emerald-500/10">
                      <TrendingUp className="w-4 h-4 text-emerald-400" />
                    </div>
                    <span className="text-[10px] font-semibold text-emerald-400 uppercase tracking-[0.1em]">
                      Biggest Positive
                    </span>
                  </div>
                  <span className="text-xl font-extrabold text-emerald-400 leading-none tabular-nums">
                    {score.toFixed(1)}<span className="text-xs font-medium text-emerald-400/60">/100</span>
                  </span>
                </div>
                <p className="text-base font-bold text-[var(--text-primary)] mb-2">{d?.driver || "N/A"}</p>
                <div className="h-[3px] rounded-full mb-3 overflow-hidden" style={{ background: "#10B98120" }}>
                  <div className="h-full rounded-full bg-emerald-400" style={{ width: `${score}%` }} />
                </div>
                <p className="text-xs text-[var(--text-secondary)] leading-relaxed line-clamp-3 border-l-2 border-emerald-500/40 pl-2.5 italic">
                  {d?.representative || "No representative mention available"}
                </p>
              </div>
              <div className="flex items-center justify-between mt-4 pt-3 border-t border-[var(--border)]">
                <span className="text-[10px] text-[var(--text-muted)]">{d?.mention_count ?? 0} mentions</span>
                <span className="text-[10px] text-emerald-400/60 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  Explore <ArrowRight className="w-2.5 h-2.5" />
                </span>
              </div>
            </div>
          );
        })()}

        {/* Biggest Negative */}
        {(() => {
          const d = data.biggest_negative_driver;
          const score = d?.score ?? 0;
          return (
            <div
              className="card p-5 flex flex-col justify-between animate-fade-in cursor-pointer group transition-all"
              style={{
                animationDelay: "150ms",
                background: "linear-gradient(135deg, var(--bg-card) 55%, #F43F5E08 100%)",
                ["--kpi-color" as string]: "#F43F5E",
              }}
              onClick={() => {
                if (d?.driver) router.push(`/explorer?driver=${encodeURIComponent(d.driver)}&sentiment=negative`);
              }}
            >
              <div>
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <div className="p-1.5 rounded-lg bg-rose-500/10">
                      <TrendingDown className="w-4 h-4 text-rose-400" />
                    </div>
                    <span className="text-[10px] font-semibold text-rose-400 uppercase tracking-[0.1em]">
                      Biggest Negative
                    </span>
                  </div>
                  <span className="text-xl font-extrabold text-rose-400 leading-none tabular-nums">
                    {score.toFixed(1)}<span className="text-xs font-medium text-rose-400/60">/100</span>
                  </span>
                </div>
                <p className="text-base font-bold text-[var(--text-primary)] mb-2">{d?.driver || "N/A"}</p>
                <div className="h-[3px] rounded-full mb-3 overflow-hidden" style={{ background: "#F43F5E20" }}>
                  <div className="h-full rounded-full bg-rose-400" style={{ width: `${score}%` }} />
                </div>
                <p className="text-xs text-[var(--text-secondary)] leading-relaxed line-clamp-3 border-l-2 border-rose-500/40 pl-2.5 italic">
                  {d?.representative || "No representative mention available"}
                </p>
              </div>
              <div className="flex items-center justify-between mt-4 pt-3 border-t border-[var(--border)]">
                <span className="text-[10px] text-[var(--text-muted)]">{d?.mention_count ?? 0} mentions</span>
                <span className="text-[10px] text-rose-400/60 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  Explore <ArrowRight className="w-2.5 h-2.5" />
                </span>
              </div>
            </div>
          );
        })()}
      </div>

      {/* Row 2: Score Waterfall — full width */}
      <div className="card p-5 mb-4 animate-fade-in" style={{ animationDelay: "200ms" }}>
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-sm font-semibold text-[var(--text-secondary)]">
            Score Contributors (Deviation from Neutral)
          </h3>
          <Link href="/explorer" className="text-[10px] text-[var(--text-muted)] hover:text-blue-400 flex items-center gap-1 transition-colors">
            Explore <ArrowRight className="w-3 h-3" />
          </Link>
        </div>
        {(() => {
          const sorted = [...data.score_waterfall].sort((a, b) => b.value - a.value);
          const maxAbs = Math.max(...sorted.map((d) => Math.abs(d.value)), 1);
          return (
            <div className="space-y-3">
              {sorted.map((entry, i) => {
                const isPositive = entry.type === "positive";
                const pct = (Math.abs(entry.value) / maxAbs) * 100;
                return (
                  <button
                    key={i}
                    className="w-full group text-left"
                    onClick={() => {
                      const sentiment = isPositive ? "positive" : "negative";
                      router.push(`/explorer?sentiment=${sentiment}`);
                    }}
                  >
                    <div className="flex items-center gap-4">
                      <span className="text-[11px] text-[var(--text-secondary)] w-[200px] flex-shrink-0 truncate group-hover:text-[var(--text-primary)] transition-colors">
                        {entry.name}
                      </span>
                      <div className="flex-1 flex items-center h-7">
                        {!isPositive && (
                          <>
                            <div className="flex-1" />
                            <div className="flex items-center" style={{ width: `${pct / 2}%` }}>
                              <span className="text-[10px] font-semibold text-rose-400 tabular-nums mr-2 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                                {entry.value.toFixed(1)}
                              </span>
                              <div
                                className="h-[18px] rounded-l-md w-full transition-all group-hover:h-[22px]"
                                style={{
                                  background: "linear-gradient(90deg, #F43F5E, #FB7185)",
                                  boxShadow: "0 0 12px #F43F5E30",
                                }}
                              />
                            </div>
                            <div className="w-px h-7 bg-[var(--border)]" />
                            <div style={{ width: `${50}%` }} />
                          </>
                        )}
                        {isPositive && (
                          <>
                            <div style={{ width: `${50}%` }} />
                            <div className="w-px h-7 bg-[var(--border)]" />
                            <div className="flex items-center" style={{ width: `${pct / 2}%` }}>
                              <div
                                className="h-[18px] rounded-r-md w-full transition-all group-hover:h-[22px]"
                                style={{
                                  background: "linear-gradient(90deg, #34D399, #10B981)",
                                  boxShadow: "0 0 12px #10B98130",
                                }}
                              />
                              <span className="text-[10px] font-semibold text-emerald-400 tabular-nums ml-2 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                                +{entry.value.toFixed(1)}
                              </span>
                            </div>
                          </>
                        )}
                      </div>
                    </div>
                  </button>
                );
              })}
              {/* Axis labels */}
              {(() => {
                const ceil = Math.ceil(maxAbs / 10) * 10;
                const ticks: number[] = [];
                for (let v = -ceil; v <= ceil; v += 10) ticks.push(v);
                return (
                  <div className="flex items-center gap-4 mt-1">
                    <div className="w-[200px] flex-shrink-0" />
                    <div className="flex-1 flex items-center text-[9px] text-[var(--text-muted)]">
                      {ticks.map((v, i) => (
                        <span key={v} className={`text-center ${i > 0 ? "flex-1" : ""}`}>
                          {v === 0 ? "0" : v > 0 ? `+${v}` : `${v}`}
                        </span>
                      ))}
                    </div>
                  </div>
                );
              })()}
            </div>
          );
        })()}
      </div>

      {/* Row 3: Insights — 3 equal columns */}
      <div className="grid grid-cols-3 gap-4">
        {/* Emerging Theme */}
        {data.emerging_theme && (
          <Link
            href="/themes"
            className="card p-5 animate-fade-in border-t-2 border-t-violet-500 flex flex-col hover:ring-1 hover:ring-violet-500/30 transition-all group"
            style={{ animationDelay: "250ms" }}
          >
            <div className="flex items-center gap-2 mb-3">
              <div className="p-1.5 rounded-lg bg-violet-500/10 flex-shrink-0">
                <Zap className="w-4 h-4 text-violet-400" />
              </div>
              <p className="text-[10px] font-semibold text-violet-400 uppercase tracking-wider">Emerging Theme</p>
            </div>
            <p className="text-sm font-bold leading-snug mb-2">{data.emerging_theme.theme_name}</p>
            <p className="text-xs text-[var(--text-secondary)] leading-relaxed line-clamp-3 flex-1">
              {data.emerging_theme.description}
            </p>
            <div className="pt-3 mt-3 border-t border-[var(--border)] flex items-center gap-1 text-[10px] text-violet-400/70 opacity-0 group-hover:opacity-100 transition-opacity">
              Explore <ArrowRight className="w-3 h-3" />
            </div>
          </Link>
        )}

        {/* Primary Risk */}
        {data.primary_risk && (
          <Link
            href={`/explorer?risk_level=${data.primary_risk.risk_level}`}
            className="card p-5 animate-fade-in border-t-2 border-t-amber-500 flex flex-col hover:ring-1 hover:ring-amber-500/30 transition-all group"
            style={{ animationDelay: "300ms" }}
          >
            <div className="flex items-center gap-2 mb-3">
              <div className="p-1.5 rounded-lg bg-amber-500/10 flex-shrink-0">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
              </div>
              <p className="text-[10px] font-semibold text-amber-400 uppercase tracking-wider">Primary Risk</p>
            </div>
            <p className="text-sm font-bold leading-snug mb-2">{data.primary_risk.risk_signal || data.primary_risk.title}</p>
            <div className="flex items-center gap-2 mb-2">
              <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                data.primary_risk.risk_level === "high"
                  ? "bg-rose-500/10 text-rose-400"
                  : "bg-amber-500/10 text-amber-400"
              }`}>
                {data.primary_risk.risk_level.toUpperCase()}
              </span>
              {data.primary_risk.risk_type && (
                <span className="text-[10px] text-[var(--text-muted)]">
                  {data.primary_risk.risk_type.replace("_", " ")}
                </span>
              )}
            </div>
            <div className="flex-1" />
            <div className="pt-3 mt-3 border-t border-[var(--border)] flex items-center gap-1 text-[10px] text-amber-400/70 opacity-0 group-hover:opacity-100 transition-opacity">
              Explore <ArrowRight className="w-3 h-3" />
            </div>
          </Link>
        )}

        {/* Recommended Actions */}
        {data.recommended_actions.length > 0 && (
          <Link
            href="/intelligence"
            className="card p-5 animate-fade-in border-t-2 border-t-blue-500 flex flex-col hover:ring-1 hover:ring-blue-500/30 transition-all group"
            style={{ animationDelay: "350ms" }}
          >
            <div className="flex items-center gap-2 mb-3">
              <div className="p-1.5 rounded-lg bg-blue-500/10 flex-shrink-0">
                <Lightbulb className="w-4 h-4 text-blue-400" />
              </div>
              <p className="text-[10px] font-semibold text-blue-400 uppercase tracking-wider">
                Recommended Actions
              </p>
            </div>
            <div className="space-y-2 flex-1">
              {data.recommended_actions.slice(0, 3).map((action, i) => (
                <div key={i} className="flex items-start gap-2">
                  <ChevronRight className="w-3 h-3 text-blue-400 mt-0.5 flex-shrink-0" />
                  <p className="text-xs text-[var(--text-secondary)] leading-relaxed line-clamp-2">{action}</p>
                </div>
              ))}
            </div>
            <div className="pt-3 mt-3 border-t border-[var(--border)] flex items-center gap-1 text-[10px] text-blue-400/70 opacity-0 group-hover:opacity-100 transition-opacity">
              View all <ArrowRight className="w-3 h-3" />
            </div>
          </Link>
        )}
      </div>
    </div>
  );
}
