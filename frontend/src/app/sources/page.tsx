"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell,
} from "recharts";
import { Radio, AlertTriangle, ArrowRight } from "lucide-react";
import { api, SourceData } from "@/lib/api";
import { formatNumber } from "@/lib/utils";

const SOURCE_TYPE_COLORS: Record<string, string> = {
  news: "#3B82F6",
  forum: "#8B5CF6",
  review: "#F59E0B",
  professional: "#10B981",
  aggregator: "#6B7280",
  unknown: "#475569",
};

export default function SourceAnalysis() {
  const router = useRouter();
  const [data, setData] = useState<SourceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const result = await api.getSourceAnalytics();
        if (!cancelled) setData(result);
      } catch (e: unknown) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load source data");
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
          <p className="text-sm text-[var(--text-muted)] mt-3">Loading source data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card p-8 text-center">
        <AlertTriangle className="w-10 h-10 text-amber-400 mx-auto" />
        <p className="text-lg font-semibold mt-3">Unable to Load Source Data</p>
        <p className="text-sm text-[var(--text-secondary)] mt-1">{error}</p>
        <p className="text-xs text-[var(--text-muted)] mt-4">
          Start the backend: <code className="text-blue-400">uvicorn app.main:app --reload</code>
        </p>
      </div>
    );
  }

  if (!data || !data.sources.length) {
    return (
      <div className="card p-8 text-center">
        <Radio className="w-10 h-10 text-[var(--text-muted)] mx-auto" />
        <p className="text-base font-semibold mt-3">No Source Data Available</p>
        <p className="text-sm text-[var(--text-secondary)] mt-1">
          Run the pipeline to process mentions and generate source analytics.
        </p>
      </div>
    );
  }

  // Source type aggregation
  const typeAgg: Record<string, number> = {};
  data.sources.forEach((s) => {
    typeAgg[s.source_type] = (typeAgg[s.source_type] || 0) + s.count;
  });
  const typeData = Object.entries(typeAgg).map(([name, value]) => ({
    name: name.charAt(0).toUpperCase() + name.slice(1),
    rawName: name,
    value,
    color: SOURCE_TYPE_COLORS[name] || "#475569",
  }));
  const typeTotal = typeData.reduce((sum, item) => sum + item.value, 0);

  // Top sources by mention count
  const topSources = data.sources.slice(0, 15);

  // Top sources by reach
  const topByReach = [...data.sources]
    .filter((s) => s.total_reach > 0)
    .sort((a, b) => b.total_reach - a.total_reach)
    .slice(0, 10);

  return (
    <div>
      <div className="mb-5 animate-fade-in">
        <div className="flex items-center gap-2">
          <Radio className="w-6 h-6 text-blue-400" />
          <h1 className="text-2xl font-bold">Source Analysis</h1>
        </div>
        <p className="text-sm text-[var(--text-secondary)] mt-1">
          Breakdown of mention sources, reach, and influence
        </p>
      </div>

      {/* Source Type Distribution */}
      <div className="grid grid-cols-2 gap-4 mb-4">
        <div className="card p-5 animate-fade-in">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-[var(--text-secondary)]">Source Type Distribution</h3>
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
                    data={typeData}
                    cx="50%" cy="50%"
                    innerRadius={50} outerRadius={76}
                    dataKey="value"
                    strokeWidth={0}
                    paddingAngle={3}
                    className="cursor-pointer"
                    onClick={(entry) => {
                      const rawName = (entry as unknown as { rawName?: string }).rawName ?? "";
                      router.push(`/explorer?source_type=${rawName}`);
                    }}
                  >
                    {typeData.map((entry, i) => (
                      <Cell key={i} fill={entry.color} />
                    ))}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                <span className="text-[1.4rem] font-extrabold leading-none text-[var(--text-primary)]">{typeTotal}</span>
                <span className="text-[8px] uppercase tracking-[0.14em] text-[var(--text-muted)] mt-1">mentions</span>
              </div>
            </div>

            {/* Legend with progress bars */}
            <div className="flex flex-col justify-center gap-3 flex-1">
              {typeData.map((item) => {
                const pct = Math.round((item.value / typeTotal) * 100);
                return (
                  <Link
                    key={item.name}
                    href={`/explorer?source_type=${item.rawName}`}
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

        {/* Top Sources by Reach */}
        <div className="card p-5 animate-fade-in" style={{ animationDelay: "50ms" }}>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-[var(--text-secondary)]">Top Sources by Reach</h3>
            <Link href="/explorer?sort_by=reach" className="text-[10px] text-[var(--text-muted)] hover:text-blue-400 flex items-center gap-1 transition-colors">
              Explore <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
          {topByReach.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={topByReach.slice(0, 6)} layout="vertical" margin={{ left: 0, right: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 10, fill: "var(--text-muted)" }}
                  tickFormatter={(v: number) => formatNumber(v)} />
                <YAxis type="category" dataKey="source_name" tick={{ fontSize: 10, fill: "var(--text-secondary)" }} width={140} />
                <Tooltip
                  cursor={false}
                  contentStyle={{ background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: "8px", fontSize: "12px", color: "#fff" }}
                  formatter={(v) => [formatNumber(Number(v)), "Total Reach"]}
                />
                <Bar
                  dataKey="total_reach"
                  fill="#10B981"
                  radius={[0, 4, 4, 0]}
                  barSize={18}
                  className="cursor-pointer"
                  onClick={(entry) => {
                    const sourceName = (entry as unknown as { source_name?: string }).source_name ?? "";
                    router.push(`/explorer?source_name=${encodeURIComponent(sourceName)}`);
                  }}
                />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-[180px] text-xs text-[var(--text-muted)]">
              No reach data available
            </div>
          )}
        </div>
      </div>

      {/* Source Table */}
      <div className="card p-5 animate-fade-in" style={{ animationDelay: "100ms" }}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-[var(--text-secondary)]">All Sources</h3>
          <p className="text-[10px] text-[var(--text-muted)]">Click a row to explore its mentions</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-[var(--border)]">
                <th className="text-left py-2 px-3 text-[var(--text-primary)] font-medium">Source</th>
                <th className="text-left py-2 px-3 text-[var(--text-primary)] font-medium">Type</th>
                <th className="text-center py-2 px-3 text-[var(--text-primary)] font-medium">Mentions</th>
                <th className="text-center py-2 px-3 text-[var(--text-primary)] font-medium">Positive</th>
                <th className="text-center py-2 px-3 text-[var(--text-primary)] font-medium">Neutral</th>
                <th className="text-center py-2 px-3 text-[var(--text-primary)] font-medium">Negative</th>
                <th className="text-right py-2 px-3 text-[var(--text-primary)] font-medium">Total Reach</th>
              </tr>
            </thead>
            <tbody>
              {topSources.map((source, i) => (
                <tr
                  key={i}
                  className="border-b border-[var(--border)] hover:bg-[var(--bg-card-hover)] transition-colors cursor-pointer"
                  onClick={() => router.push(`/explorer?source_name=${encodeURIComponent(source.source_name)}`)}
                >
                  <td className="py-2.5 px-3 font-medium text-[var(--text-muted)]">{source.source_name}</td>
                  <td className="py-2.5 px-3">
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-medium"
                      style={{
                        background: `${SOURCE_TYPE_COLORS[source.source_type] || "#475569"}15`,
                        color: SOURCE_TYPE_COLORS[source.source_type] || "#475569",
                      }}>
                      {source.source_type}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-center font-semibold">{source.count}</td>
                  <td className="py-2.5 px-3 text-center text-emerald-400">{source.sentiment.positive || 0}</td>
                  <td className="py-2.5 px-3 text-center text-amber-400">{source.sentiment.neutral || 0}</td>
                  <td className="py-2.5 px-3 text-center text-rose-400">{source.sentiment.negative || 0}</td>
                  <td className="py-2.5 px-3 text-right text-[var(--text-secondary)]">
                    {source.total_reach > 0 ? formatNumber(source.total_reach) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
