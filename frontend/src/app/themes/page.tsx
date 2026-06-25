"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Layers, MessageSquare, TrendingUp, TrendingDown, AlertTriangle, X, ArrowRight, Search } from "lucide-react";
import { api, Theme } from "@/lib/api";
import { getSentimentColor } from "@/lib/utils";

// ── Helpers ──────────────────────────────────────────────────────────────────

function sentimentColorFor(skew: string) {
  return getSentimentColor(skew === "mixed" || skew === "neutral" ? "neutral" : skew);
}

function SentimentIcon({ skew }: { skew: string }) {
  if (skew === "positive") return <TrendingUp className="w-5 h-5" />;
  if (skew === "negative") return <TrendingDown className="w-5 h-5" />;
  return <MessageSquare className="w-5 h-5" />;
}

// ── Modal ─────────────────────────────────────────────────────────────────────

function ThemeModal({ theme, onClose }: { theme: Theme; onClose: () => void }) {
  const color = sentimentColorFor(theme.sentiment_skew);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

      {/* Panel */}
      <div
        className="relative card p-6 w-full max-w-2xl max-h-[80vh] overflow-y-auto animate-fade-in shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1.5 rounded-lg hover:bg-[var(--bg-card-hover)] transition-colors"
          aria-label="Close"
        >
          <X className="w-4 h-4 text-[var(--text-muted)]" />
        </button>

        {/* Sentiment badge + title */}
        <div className="mb-5">
          <div className="flex items-center gap-2 mb-3">
            <span
              className="text-[10px] px-2 py-0.5 rounded-full border font-medium"
              style={{
                background: `${color}15`,
                color,
                borderColor: `${color}30`,
              }}
            >
              {theme.sentiment_skew}
            </span>
            <span className="text-[10px] text-[var(--text-muted)]">
              {theme.mention_count} mentions
            </span>
          </div>
          <h2 className="text-xl font-bold">{theme.theme_name}</h2>
          <p className="text-sm text-[var(--text-secondary)] mt-2 leading-relaxed">
            {theme.description}
          </p>
        </div>

        {/* Business Implication */}
        <div className="p-4 rounded-lg bg-[var(--bg-primary)] mb-4">
          <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider mb-2">
            Business Implication
          </p>
          <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
            {theme.business_implication}
          </p>
        </div>

        {/* Representative Quotes */}
        {theme.representative_quotes.length > 0 && (
          <div className="mb-5">
            <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider mb-3">
              Representative Quotes
            </p>
            <div className="space-y-3">
              {theme.representative_quotes.map((quote, i) => (
                <div
                  key={i}
                  className="pl-4 border-l-2"
                  style={{ borderColor: `${color}60` }}
                >
                  <p className="text-sm text-[var(--text-secondary)] italic leading-relaxed">
                    &ldquo;{quote}&rdquo;
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Explore Mentions CTA */}
        <Link
          href={`/explorer?sentiment=${theme.sentiment_skew === "mixed" ? "neutral" : theme.sentiment_skew}`}
          onClick={onClose}
          className="flex items-center justify-center gap-2 w-full py-2.5 rounded-lg text-xs font-medium transition-colors"
          style={{
            background: `${color}15`,
            color,
            border: `1px solid ${color}30`,
          }}
        >
          <Search className="w-3.5 h-3.5" />
          Explore {theme.sentiment_skew} mentions in Content Explorer
          <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>
    </div>
  );
}

// ── Card ──────────────────────────────────────────────────────────────────────

function ThemeCard({
  theme,
  onSelect,
}: {
  theme: Theme;
  onSelect: (theme: Theme) => void;
}) {
  const color = sentimentColorFor(theme.sentiment_skew);

  return (
    <div
      className="card p-5 cursor-pointer flex flex-col"
      onClick={() => onSelect(theme)}
    >
      <div className="flex items-start justify-between flex-1">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <span
              className="text-[10px] px-2 py-0.5 rounded-full border font-medium"
              style={{
                background: `${color}15`,
                color,
                borderColor: `${color}30`,
              }}
            >
              {theme.sentiment_skew}
            </span>
            <span className="text-[10px] text-[var(--text-muted)]">
              {theme.mention_count} mentions
            </span>
          </div>
          <h3 className="text-base font-bold">{theme.theme_name}</h3>
          <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed line-clamp-3">
            {theme.description}
          </p>
        </div>
        <div className="p-2 rounded-lg flex-shrink-0 ml-3" style={{ background: `${color}10`, color }}>
          <SentimentIcon skew={theme.sentiment_skew} />
        </div>
      </div>

      {/* Footer hint */}
      <div className="mt-3 pt-3 border-t border-[var(--border)] flex items-center justify-between">
        <span className="text-[10px] text-[var(--text-muted)]">Click to view details</span>
        <span className="text-[10px]" style={{ color }}>→</span>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ThemeExplorer() {
  const [themes, setThemes] = useState<Theme[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Theme | null>(null);
  const [sentimentFilter, setSentimentFilter] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const result = await api.getThemes();
        if (!cancelled) setThemes(result.themes || []);
      } catch (e: unknown) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load themes");
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
          <p className="text-sm text-[var(--text-muted)] mt-3">Loading themes...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card p-8 text-center">
        <AlertTriangle className="w-10 h-10 text-amber-400 mx-auto" />
        <p className="text-lg font-semibold mt-3">Unable to Load Themes</p>
        <p className="text-sm text-[var(--text-secondary)] mt-1">{error}</p>
        <p className="text-xs text-[var(--text-muted)] mt-4">
          Start the backend: <code className="text-blue-400">uvicorn app.main:app --reload</code>
        </p>
      </div>
    );
  }

  const positive = themes.filter((t) => t.sentiment_skew === "positive");
  const negative = themes.filter((t) => t.sentiment_skew === "negative");
  const neutral  = themes.filter((t) => t.sentiment_skew === "neutral" || t.sentiment_skew === "mixed");

  const filteredThemes = sentimentFilter
    ? themes.filter((t) => {
        if (sentimentFilter === "positive") return t.sentiment_skew === "positive";
        if (sentimentFilter === "negative") return t.sentiment_skew === "negative";
        if (sentimentFilter === "neutral") return t.sentiment_skew === "neutral" || t.sentiment_skew === "mixed";
        return true;
      })
    : themes;

  return (
    <div>
      <div className="mb-5 animate-fade-in">
        <div className="flex items-center gap-2">
          <Layers className="w-6 h-6 text-violet-400" />
          <h1 className="text-2xl font-bold">Theme Explorer</h1>
        </div>
        <p className="text-sm text-[var(--text-secondary)] mt-1">
          AI-discovered narrative themes across all mentions
        </p>
      </div>

      {themes.length === 0 ? (
        <div className="card p-8 text-center">
          <Layers className="w-10 h-10 text-[var(--text-muted)] mx-auto" />
          <p className="text-base font-semibold mt-3">No Themes Found</p>
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            No themes extracted yet. Run the pipeline to generate themes.
          </p>
        </div>
      ) : (
        <>
          {/* Summary counts — click to filter grid */}
          <div className="grid grid-cols-3 gap-4 mb-5">
            <button
              onClick={() => setSentimentFilter(sentimentFilter === "positive" ? null : "positive")}
              className={`card p-4 animate-fade-in text-left transition-all hover:ring-1 hover:ring-emerald-500/30 ${sentimentFilter === "positive" ? "ring-1 ring-emerald-500/50" : ""}`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full bg-emerald-400" />
                  <span className="text-xs text-[var(--text-muted)]">Positive Themes</span>
                </div>
                {sentimentFilter === "positive" && (
                  <X className="w-3 h-3 text-emerald-400" />
                )}
              </div>
              <p className="text-xl font-bold mt-1">{positive.length}</p>
              <p className="text-[10px] text-emerald-400/70 mt-1 flex items-center gap-1">
                {sentimentFilter === "positive" ? "Click to clear filter" : "Click to filter"} <ArrowRight className="w-3 h-3" />
              </p>
            </button>

            <button
              onClick={() => setSentimentFilter(sentimentFilter === "neutral" ? null : "neutral")}
              className={`card p-4 animate-fade-in text-left transition-all hover:ring-1 hover:ring-amber-500/30 ${sentimentFilter === "neutral" ? "ring-1 ring-amber-500/50" : ""}`}
              style={{ animationDelay: "50ms" }}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full bg-amber-400" />
                  <span className="text-xs text-[var(--text-muted)]">Neutral Themes</span>
                </div>
                {sentimentFilter === "neutral" && (
                  <X className="w-3 h-3 text-amber-400" />
                )}
              </div>
              <p className="text-xl font-bold mt-1">{neutral.length}</p>
              <p className="text-[10px] text-amber-400/70 mt-1 flex items-center gap-1">
                {sentimentFilter === "neutral" ? "Click to clear filter" : "Click to filter"} <ArrowRight className="w-3 h-3" />
              </p>
            </button>

            <button
              onClick={() => setSentimentFilter(sentimentFilter === "negative" ? null : "negative")}
              className={`card p-4 animate-fade-in text-left transition-all hover:ring-1 hover:ring-rose-500/30 ${sentimentFilter === "negative" ? "ring-1 ring-rose-500/50" : ""}`}
              style={{ animationDelay: "100ms" }}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full bg-rose-400" />
                  <span className="text-xs text-[var(--text-muted)]">Negative Themes</span>
                </div>
                {sentimentFilter === "negative" && (
                  <X className="w-3 h-3 text-rose-400" />
                )}
              </div>
              <p className="text-xl font-bold mt-1">{negative.length}</p>
              <p className="text-[10px] text-rose-400/70 mt-1 flex items-center gap-1">
                {sentimentFilter === "negative" ? "Click to clear filter" : "Click to filter"} <ArrowRight className="w-3 h-3" />
              </p>
            </button>
          </div>

          {/* Active filter bar */}
          {sentimentFilter && (
            <div className="flex items-center gap-2 mb-4 animate-fade-in">
              <span className="text-xs text-[var(--text-muted)]">Showing:</span>
              <span className={`text-xs px-2 py-1 rounded-full flex items-center gap-1 ${
                sentimentFilter === "positive" ? "bg-emerald-500/10 text-emerald-400"
                : sentimentFilter === "negative" ? "bg-rose-500/10 text-rose-400"
                : "bg-amber-500/10 text-amber-400"
              }`}>
                {sentimentFilter} themes
                <button onClick={() => setSentimentFilter(null)}>
                  <X className="w-3 h-3" />
                </button>
              </span>
              <span className="text-xs text-[var(--text-muted)]">{filteredThemes.length} themes</span>
              <Link
                href={`/explorer?sentiment=${sentimentFilter === "neutral" ? "neutral" : sentimentFilter}`}
                className="ml-auto text-[10px] text-blue-400 hover:text-blue-300 flex items-center gap-1 transition-colors"
              >
                Explore {sentimentFilter} mentions <ArrowRight className="w-3 h-3" />
              </Link>
            </div>
          )}

          {/* Theme grid */}
          <div className="grid grid-cols-2 gap-4 items-start">
            {filteredThemes.map((theme) => (
              <ThemeCard
                key={theme.theme_name}
                theme={theme}
                onSelect={setSelected}
              />
            ))}
          </div>
        </>
      )}

      {/* Detail modal */}
      {selected && (
        <ThemeModal theme={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  );
}
