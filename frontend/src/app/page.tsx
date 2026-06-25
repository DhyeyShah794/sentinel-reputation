"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell, AreaChart, Area,
} from "recharts";
import { TrendingUp, TrendingDown, AlertTriangle, MessageSquare, Shield, ArrowRight } from "lucide-react";
import { api, OverviewData, Theme } from "@/lib/api";
import { getScoreColor, getScoreLabel, getSentimentColor } from "@/lib/utils";

// Map shortened display names back to the filter values the Explorer accepts
const DRIVER_DISPLAY_TO_FILTER: Record<string, string> = {
  "Responsible Business": "Responsible Business Practices",
};
function driverFilterValue(displayName: string) {
  return DRIVER_DISPLAY_TO_FILTER[displayName] ?? displayName;
}

function KPICard({ title, value, subtitle, icon: Icon, color, delay, href }: {
  title: string; value: string | number; subtitle?: string;
  icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>; color: string; delay: number;
  href?: string;
}) {
  const cardStyle = {
    animationDelay: `${delay}ms`,
    background: `linear-gradient(145deg, var(--bg-card) 40%, ${color}0d 100%)`,
    ["--kpi-color" as string]: color,
  } as React.CSSProperties;

  const inner = (
    <div className="flex flex-col h-full">
      {/* Icon + label row */}
      <div className="flex items-start justify-between mb-4">
        <div
          className="p-2.5 rounded-xl"
          style={{
            background: `${color}18`,
            boxShadow: `0 0 0 1px ${color}30`,
          }}
        >
          <Icon className="w-5 h-5" style={{ color }} />
        </div>
        <span className="text-[9px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.12em] pt-0.5">
          {title}
        </span>
      </div>

      {/* Value — flex-1 pushes footer to bottom regardless of subtitle presence */}
      <div className="flex-1">
        <p className="text-[1.6rem] font-extrabold leading-none tracking-tight" style={{ color }}>
          {value}
        </p>
        {subtitle && (
          <p className="text-xs text-[var(--text-secondary)] mt-1.5 font-medium">{subtitle}</p>
        )}
      </div>

      {/* Footer divider */}
      {href && (
        <div className="pt-3 border-t border-[var(--border)] flex items-center justify-between">
          <span className="text-[10px] text-[var(--text-muted)] group-hover:text-[var(--text-secondary)] transition-colors">
            View details
          </span>
          <ArrowRight
            className="w-3 h-3 transition-all group-hover:translate-x-0.5"
            style={{ color: `${color}99` }}
          />
        </div>
      )}
    </div>
  );

  if (href) {
    return (
      <Link
        href={href}
        className="card kpi-card p-5 animate-fade-in flex flex-col group"
        style={cardStyle}
      >
        {inner}
      </Link>
    );
  }

  return (
    <div className="card kpi-card p-5 animate-fade-in flex flex-col" style={cardStyle}>
      {inner}
    </div>
  );
}

export default function ExecutiveOverview() {
  const router = useRouter();
  const [data, setData] = useState<OverviewData | null>(null);
  const [themes, setThemes] = useState<Theme[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [overview, themesRes] = await Promise.all([
          api.getOverview(),
          api.getThemes().catch(() => ({ themes: [] })),
        ]);
        if (!cancelled) {
          setData(overview);
          setThemes(themesRes.themes.slice(0, 4));
        }
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
          <p className="text-sm text-[var(--text-muted)] mt-3">Loading intelligence data...</p>
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

  const total = data.total_mentions || 1;

  const sentimentData = Object.entries(data.sentiment_distribution).map(([name, value]) => ({
    name: name.charAt(0).toUpperCase() + name.slice(1),
    rawName: name,
    value,
    color: getSentimentColor(name),
  }));

  const driverData = Object.entries(data.driver_distribution)
    .filter(([k]) => k !== "Unclassified")
    .map(([name, value]) => ({ name: name.replace("Responsible Business Practices", "Responsible Business"), value }));

  const subDriverData = Object.entries(data.sub_driver_distribution)
    .filter(([k]) => k !== "Unclassified")
    .sort((a, b) => b[1] - a[1])
    .map(([name, value]) => ({
      name: name.length > 25 ? name.slice(0, 22) + "..." : name,
      fullName: name,
      value,
    }));

  const highRisk = data.risk_summary.high || 0;
  const medRisk = data.risk_summary.medium || 0;
  const riskLabel = highRisk > 0 ? "High" : medRisk > 3 ? "Moderate" : "Low";
  const riskColor = highRisk > 0 ? "#F43F5E" : medRisk > 3 ? "#F59E0B" : "#10B981";
  const riskFilterLevel = highRisk > 0 ? "high" : medRisk > 0 ? "medium" : "low";

  return (
    <div>
      {/* Header */}
      <div className="mb-6 animate-fade-in">
        <h1 className="text-2xl font-bold">Executive Overview</h1>
        <p className="text-sm text-[var(--text-secondary)] mt-1">
          ICICI Prudential AMC — Reputation Intelligence Dashboard
        </p>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-5 gap-4 mb-6 stagger-children">
        <KPICard
          title="Total Mentions"
          value={data.total_mentions}
          icon={MessageSquare}
          color="#3B82F6"
          delay={0}
          href="/explorer"
        />
        <KPICard
          title="Rep Score"
          value={`${data.reputation_score}/100`}
          subtitle={getScoreLabel(data.reputation_score)}
          icon={Shield}
          color={getScoreColor(data.reputation_score)}
          delay={50}
          href="/command-center"
        />
        <KPICard
          title="Positive"
          value={`${Math.round((data.sentiment_distribution.positive / total) * 100)}%`}
          subtitle={`${data.sentiment_distribution.positive} mentions`}
          icon={TrendingUp}
          color="#10B981"
          delay={100}
          href="/explorer?sentiment=positive"
        />
        <KPICard
          title="Negative"
          value={`${Math.round((data.sentiment_distribution.negative / total) * 100)}%`}
          subtitle={`${data.sentiment_distribution.negative} mentions`}
          icon={TrendingDown}
          color="#F43F5E"
          delay={150}
          href="/explorer?sentiment=negative"
        />
        <KPICard
          title="Risk Level"
          value={riskLabel}
          subtitle={`${highRisk} high, ${medRisk} medium`}
          icon={AlertTriangle}
          color={riskColor}
          delay={200}
          href={`/explorer?risk_level=${riskFilterLevel}`}
        />
      </div>

      {/* Charts Row 1 */}
      <div className="grid grid-cols-2 gap-4 mb-4">
        {/* Sentiment Distribution */}
        <div className="card p-5 animate-fade-in" style={{ animationDelay: "250ms" }}>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-[var(--text-secondary)]">Sentiment Distribution</h3>
            <Link href="/explorer" className="text-[10px] text-[var(--text-muted)] hover:text-blue-400 flex items-center gap-1 transition-colors">
              Explore <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
          <div className="flex items-center gap-5">
            {/* Donut with center label */}
            <div className="relative flex-shrink-0" style={{ width: "42%", height: 190 }}>
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={sentimentData}
                    cx="50%" cy="50%"
                    innerRadius={52} outerRadius={78}
                    dataKey="value"
                    strokeWidth={0}
                    paddingAngle={3}
                    className="cursor-pointer"
                    onClick={(entry) => {
                      const rawName = (entry as unknown as { rawName: string }).rawName;
                      router.push(`/explorer?sentiment=${rawName}`);
                    }}
                  >
                    {sentimentData.map((entry, i) => (
                      <Cell key={i} fill={entry.color} />
                    ))}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                <span className="text-[1.4rem] font-extrabold leading-none text-[var(--text-primary)]">{total}</span>
                <span className="text-[8px] uppercase tracking-[0.14em] text-[var(--text-muted)] mt-1">total</span>
              </div>
            </div>

            {/* Legend with progress bars */}
            <div className="flex flex-col justify-center gap-3 flex-1">
              {sentimentData.map((item) => {
                const pct = Math.round((item.value / total) * 100);
                return (
                  <Link
                    key={item.name}
                    href={`/explorer?sentiment=${item.rawName}`}
                    className="group block rounded-lg px-2.5 py-2 -mx-2.5 hover:bg-[var(--bg-card-hover)] transition-colors"
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-2">
                        <span
                          className="w-2 h-2 rounded-full flex-shrink-0"
                          style={{ background: item.color, boxShadow: `0 0 6px ${item.color}80` }}
                        />
                        <span className="text-xs font-medium text-[var(--text-secondary)] group-hover:text-[var(--text-primary)] transition-colors">
                          {item.name}
                        </span>
                      </div>
                      <div className="flex items-baseline gap-1.5">
                        <span className="text-sm font-bold text-[var(--text-primary)]">{item.value}</span>
                        <span className="text-[10px] text-[var(--text-muted)] w-7 text-right">{pct}%</span>
                      </div>
                    </div>
                    <div className="h-[3px] rounded-full overflow-hidden" style={{ background: `${item.color}20` }}>
                      <div
                        className="h-full rounded-full"
                        style={{ width: `${pct}%`, background: item.color }}
                      />
                    </div>
                  </Link>
                );
              })}
            </div>
          </div>
        </div>

        {/* Driver Distribution */}
        <div className="card p-5 animate-fade-in" style={{ animationDelay: "300ms" }}>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-[var(--text-secondary)]">Reputation Driver Distribution</h3>
            <Link href="/explorer" className="text-[10px] text-[var(--text-muted)] hover:text-blue-400 flex items-center gap-1 transition-colors">
              Explore <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={driverData} layout="vertical" margin={{ left: 20, right: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 11, fill: "var(--text-muted)" }} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: "var(--text-secondary)" }} width={140} />
              <Tooltip
                cursor={false}
                contentStyle={{ background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: "8px", fontSize: "12px", color: "#fff" }}
              />
              <Bar
                dataKey="value"
                fill="#3B82F6"
                radius={[0, 4, 4, 0]}
                barSize={24}
                className="cursor-pointer"
                onClick={(entry) => {
                  const name = (entry as unknown as { name?: string }).name ?? "";
                  router.push(`/explorer?driver=${encodeURIComponent(driverFilterValue(name))}`);
                }}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Charts Row 2 */}
      <div className="grid grid-cols-2 gap-4">
        {/* Mention Trend */}
        <div className="card p-5 animate-fade-in" style={{ animationDelay: "350ms" }}>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-[var(--text-secondary)]">Mention Volume Over Time</h3>
            <Link href="/explorer?sort_by=date" className="text-[10px] text-[var(--text-muted)] hover:text-blue-400 flex items-center gap-1 transition-colors">
              Explore <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={data.mention_trend} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
              <defs>
                <linearGradient id="colorCount" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#3B82F6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: "var(--text-muted)" }} />
              <YAxis tick={{ fontSize: 11, fill: "var(--text-muted)" }} />
              <Tooltip
                cursor={false}
                contentStyle={{ background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: "8px", fontSize: "12px", color: "#fff" }}
              />
              <Area
                type="monotone"
                dataKey="count"
                stroke="#3B82F6"
                fill="url(#colorCount)"
                strokeWidth={2}
                className="cursor-pointer"
                onClick={() => router.push("/explorer?sort_by=date")}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Sub-driver Distribution */}
        <div className="card p-5 animate-fade-in" style={{ animationDelay: "400ms" }}>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-[var(--text-secondary)]">Top Sub-Drivers</h3>
            <Link href="/explorer" className="text-[10px] text-[var(--text-muted)] hover:text-blue-400 flex items-center gap-1 transition-colors">
              Explore <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={subDriverData} layout="vertical" margin={{ left: 0, right: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 11, fill: "var(--text-muted)" }} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 10, fill: "var(--text-secondary)" }} width={160} />
              <Tooltip
                cursor={false}
                contentStyle={{ background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: "8px", fontSize: "12px", color: "#fff" }}
                formatter={(value, _name, props) => [Number(value), (props as { payload?: { fullName?: string } }).payload?.fullName ?? ""]}
              />
              <Bar
                dataKey="value"
                fill="#8B5CF6"
                radius={[0, 4, 4, 0]}
                barSize={20}
                className="cursor-pointer"
                onClick={(entry) => {
                  const fullName = (entry as unknown as { fullName?: string }).fullName ?? "";
                  router.push(`/explorer?sub_driver=${encodeURIComponent(fullName)}`);
                }}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Top Discussion Themes */}
      {themes.length > 0 && (
        <div className="card p-5 mt-4 animate-fade-in" style={{ animationDelay: "450ms" }}>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-[var(--text-secondary)]">Top Discussion Themes</h3>
            <Link href="/themes" className="text-[10px] text-[var(--text-muted)] hover:text-blue-400 flex items-center gap-1 transition-colors">
              All themes <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
          <div className="grid grid-cols-4 gap-3">
            {themes.map((theme, i) => {
              const skewColor =
                theme.sentiment_skew === "positive" ? "#10B981" :
                theme.sentiment_skew === "negative" ? "#F43F5E" : "#6B7280";
              return (
                <Link
                  key={i}
                  href="/themes"
                  className="group rounded-xl p-3.5 border border-[var(--border)] hover:border-[var(--border-hover)] bg-[var(--bg-card)] hover:bg-[var(--bg-card-hover)] transition-all flex flex-col gap-2"
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-xs font-semibold text-[var(--text-primary)] leading-tight group-hover:text-blue-400 transition-colors">
                      {theme.theme_name}
                    </span>
                    <span
                      className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-full flex-shrink-0"
                      style={{ color: skewColor, background: `${skewColor}18` }}
                    >
                      {theme.sentiment_skew}
                    </span>
                  </div>
                  <p className="text-[10px] text-[var(--text-muted)] leading-relaxed line-clamp-2">
                    {theme.description}
                  </p>
                  <div className="flex items-center gap-1 mt-auto pt-1 border-t border-[var(--border)]">
                    <span className="text-[10px] font-semibold" style={{ color: skewColor }}>
                      {theme.mention_count}
                    </span>
                    <span className="text-[10px] text-[var(--text-muted)]">mentions</span>
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
