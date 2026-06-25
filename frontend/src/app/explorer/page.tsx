"use client";

import { useEffect, useRef, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Search, Filter, ExternalLink, ChevronLeft, ChevronRight, X, AlertTriangle, SearchX, ChevronDown } from "lucide-react";
import { api, Mention, MentionListResponse, OverviewData } from "@/lib/api";
import { formatDate, formatNumber, getSentimentBg, getRiskColor } from "@/lib/utils";

const DRIVERS = ["Brand Perception", "User Experience", "Responsible Business Practices"];
const SENTIMENTS = ["positive", "neutral", "negative"];
const SOURCE_TYPES = ["news", "forum", "review", "professional", "aggregator"];
const RISK_LEVELS = ["low", "medium", "high"];

// ── Styled select wrapper — matches the combobox button appearance ────────────
function FilterSelect({
  value,
  onChange,
  dimmed,
  children,
}: {
  value: string;
  onChange: (v: string) => void;
  dimmed?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="appearance-none pl-3 pr-7 py-1.5 bg-[var(--bg-primary)] border border-[var(--border)] rounded-lg text-xs focus:outline-none focus:border-blue-500/50 transition-colors cursor-pointer min-w-[100px] max-w-[180px] truncate"
        style={{ color: (!dimmed && value) ? "var(--text-primary)" : "var(--text-secondary)" }}
      >
        {children}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 w-3 h-3 text-[var(--text-muted)]" />
    </div>
  );
}

// ── Searchable combobox for source names ──────────────────────────────────────
function SourceCombobox({
  options,
  value,
  onChange,
}: {
  options: string[];
  value: string;
  onChange: (v: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const filtered = query
    ? options.filter((o) => o.toLowerCase().includes(query.toLowerCase()))
    : options;

  // Close on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
        setQuery("");
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  function select(name: string) {
    onChange(name);
    setOpen(false);
    setQuery("");
  }

  function clear(e: React.MouseEvent) {
    e.stopPropagation();
    onChange("");
    setQuery("");
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => { setOpen((o) => !o); setTimeout(() => inputRef.current?.focus(), 0); }}
        className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--bg-primary)] border border-[var(--border)] rounded-lg text-xs focus:outline-none focus:border-blue-500/50 transition-colors min-w-[120px] max-w-[180px]"
      >
        <span className={`flex-1 truncate text-left ${value ? "text-[var(--text-primary)]" : "text-[var(--text-secondary)]"}`}>
          {value || "All Sources"}
        </span>
        {value ? (
          <X className="w-3 h-3 text-[var(--text-muted)] hover:text-rose-400 flex-shrink-0" onClick={clear} />
        ) : (
          <ChevronDown className="w-3 h-3 text-[var(--text-muted)] flex-shrink-0" />
        )}
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-1 w-56 bg-[var(--bg-card)] border border-[var(--border)] rounded-lg shadow-lg z-50 overflow-hidden">
          {/* Search input */}
          <div className="p-2 border-b border-[var(--border)]">
            <div className="relative">
              <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-[var(--text-muted)]" />
              <input
                ref={inputRef}
                type="text"
                placeholder="Search sources..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="w-full pl-6 pr-2 py-1 bg-[var(--bg-primary)] border border-[var(--border)] rounded text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-blue-500/50"
              />
            </div>
          </div>

          {/* Options list */}
          <ul className="max-h-52 overflow-y-auto py-1">
            <li>
              <button
                type="button"
                onClick={() => select("")}
                className={`w-full text-left px-3 py-1.5 text-xs transition-colors hover:bg-[var(--bg-card-hover)] ${!value ? "text-blue-400 font-medium" : "text-[var(--text-secondary)]"}`}
              >
                All Sources
              </button>
            </li>
            {filtered.length === 0 ? (
              <li className="px-3 py-2 text-xs text-[var(--text-muted)] italic">No matches</li>
            ) : (
              filtered.map((name) => (
                <li key={name}>
                  <button
                    type="button"
                    onClick={() => select(name)}
                    className={`w-full text-left px-3 py-1.5 text-xs transition-colors hover:bg-[var(--bg-card-hover)] ${value === name ? "text-blue-400 font-medium bg-blue-500/5" : "text-[var(--text-secondary)]"}`}
                  >
                    {name}
                  </button>
                </li>
              ))
            )}
          </ul>
        </div>
      )}
    </div>
  );
}

function ContentExplorerInner() {
  const searchParams = useSearchParams();

  const [data, setData] = useState<MentionListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sourceNames, setSourceNames] = useState<string[]>([]);
  const [searchInput, setSearchInput] = useState(() => searchParams.get("search") || "");
  const [filters, setFilters] = useState(() => ({
    driver: searchParams.get("driver") || "",
    sub_driver: searchParams.get("sub_driver") || "",
    sentiment: searchParams.get("sentiment") || "",
    source_type: searchParams.get("source_type") || "",
    source_name: searchParams.get("source_name") || "",
    risk_level: searchParams.get("risk_level") || "",
    search: searchParams.get("search") || "",
    sort_by: searchParams.get("sort_by") || "impact_score",
    sort_order: "desc",
    page: 1,
    page_size: 15,
  }));
  const [expanded, setExpanded] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);
  const isMounted = useRef(false);

  useEffect(() => {
    api.getOverview().then((overview: OverviewData) => {
      const names = Object.keys(overview.source_distribution).sort();
      setSourceNames(names);
    }).catch(() => {});
  }, []);

  // Debounce search input — only commit to filters after 350ms of inactivity.
  // Skip the initial mount so we don't fire a redundant second fetch right after
  // the first one completes (which is what causes the flicker on page load).
  useEffect(() => {
    if (!isMounted.current) {
      isMounted.current = true;
      return;
    }
    const timer = setTimeout(() => {
      setFilters((prev) => ({ ...prev, search: searchInput, page: 1 }));
    }, 350);
    return () => clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    let cancelled = false;
    async function doLoad() {
      setLoading(true);
      setError(null);
      try {
        const params: Record<string, string | number> = {};
        Object.entries(filters).forEach(([k, v]) => { if (v !== "") params[k] = v; });
        const result = await api.getMentions(params);
        if (!cancelled) setData(result);
      } catch (e: unknown) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load mentions");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    doLoad();
    return () => { cancelled = true; };
  }, [filters, retryKey]);

  const updateFilter = (key: string, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value, page: 1 }));
  };

  const clearFilters = () => {
    setSearchInput("");
    setFilters({
      driver: "", sub_driver: "", sentiment: "", source_type: "", source_name: "", risk_level: "",
      search: "", sort_by: "impact_score", sort_order: "desc", page: 1, page_size: 15,
    });
  };

  const hasFilters = !!(filters.driver || filters.sub_driver || filters.sentiment || filters.source_type || filters.source_name || filters.risk_level || filters.search);

  return (
    <div>
      {/* Header */}
      <div className="mb-5 animate-fade-in">
        <h1 className="text-2xl font-bold">Content Explorer</h1>
        <p className="text-sm text-[var(--text-secondary)] mt-1">
          Search and filter all analyzed mentions
        </p>
      </div>

      {/* Search & Filters */}
      <div className="card p-4 mb-4 animate-fade-in" style={{ animationDelay: "50ms" }}>
        {/* Search Bar */}
        <div className="relative mb-3">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
          <input
            type="text"
            placeholder="Search mentions by title, content, or source..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 bg-[var(--bg-primary)] border border-[var(--border)] rounded-lg text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-blue-500/50 transition-colors"
          />
        </div>

        {/* Filter Row */}
        <div className="flex items-center gap-2 flex-wrap">
          <Filter className="w-4 h-4 text-[var(--text-muted)]" />

          <FilterSelect value={filters.driver} onChange={(v) => updateFilter("driver", v)}>
            <option value="">All Drivers</option>
            {DRIVERS.map((d) => <option key={d} value={d}>{d}</option>)}
          </FilterSelect>

          <FilterSelect value={filters.sentiment} onChange={(v) => updateFilter("sentiment", v)}>
            <option value="">All Sentiments</option>
            {SENTIMENTS.map((s) => <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
          </FilterSelect>

          <FilterSelect value={filters.source_type} onChange={(v) => updateFilter("source_type", v)}>
            <option value="">All Source Types</option>
            {SOURCE_TYPES.map((s) => <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
          </FilterSelect>

          <SourceCombobox
            options={sourceNames}
            value={filters.source_name}
            onChange={(v) => updateFilter("source_name", v)}
          />

          <FilterSelect value={filters.risk_level} onChange={(v) => updateFilter("risk_level", v)}>
            <option value="">All Risk Levels</option>
            {RISK_LEVELS.map((r) => <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>)}
          </FilterSelect>

          <FilterSelect value={filters.sort_by} onChange={(v) => updateFilter("sort_by", v)} dimmed>
            <option value="impact_score">Sort: Impact Score</option>
            <option value="reach">Sort: Reach</option>
            <option value="date">Sort: Date</option>
            <option value="classification_confidence">Sort: Confidence</option>
          </FilterSelect>

          {/* Active sub_driver badge (set via URL, no dropdown) */}
          {filters.sub_driver && (
            <span className="flex items-center gap-1 px-2 py-1 text-[10px] rounded-full bg-violet-500/10 text-violet-400 border border-violet-500/20">
              {filters.sub_driver}
              <button onClick={() => updateFilter("sub_driver", "")} className="hover:text-violet-200">
                <X className="w-3 h-3" />
              </button>
            </span>
          )}

          {hasFilters && (
            <button onClick={clearFilters} className="flex items-center gap-1 px-2 py-1.5 text-xs text-rose-400 hover:bg-rose-500/10 rounded-lg transition-colors">
              <X className="w-3 h-3" /> Clear
            </button>
          )}

          <span className="ml-auto text-xs text-[var(--text-muted)]">
            {data?.total ?? 0} results
          </span>
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex justify-center py-12">
          <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : error ? (
        <div className="card p-8 text-center">
          <AlertTriangle className="w-10 h-10 text-amber-400 mx-auto" />
          <p className="text-base font-semibold mt-3">Failed to Load Mentions</p>
          <p className="text-sm text-[var(--text-secondary)] mt-1">{error}</p>
          <button
            onClick={() => setRetryKey((k) => k + 1)}
            className="mt-4 px-4 py-2 text-xs bg-blue-500/10 text-blue-400 rounded-lg hover:bg-blue-500/20 transition-colors"
          >
            Retry
          </button>
        </div>
      ) : data?.data.length === 0 ? (
        <div className="card p-10 text-center">
          <SearchX className="w-10 h-10 text-[var(--text-muted)] mx-auto" />
          <p className="text-base font-semibold mt-3">No Results Found</p>
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            {hasFilters
              ? "Try adjusting your filters or search query."
              : "No mentions have been processed yet. Run the pipeline to get started."}
          </p>
          {hasFilters && (
            <button
              onClick={clearFilters}
              className="mt-4 px-4 py-2 text-xs bg-[var(--bg-card-hover)] text-[var(--text-secondary)] rounded-lg hover:bg-[var(--bg-card)] transition-colors"
            >
              Clear Filters
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-2">
          {data?.data.map((mention: Mention) => (
            <div
              key={mention.id}
              className="card mention-card p-4 cursor-pointer"
              onClick={() => setExpanded(expanded === mention.id ? null : mention.id)}
            >
              {/* Header */}
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    {mention.driver && (
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20 font-medium">
                        {mention.sub_driver || mention.driver}
                      </span>
                    )}
                    <span className={`text-[10px] px-2 py-0.5 rounded-full border font-medium ${getSentimentBg(mention.sentiment)}`}>
                      {mention.sentiment}
                    </span>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full border font-medium ${getRiskColor(mention.risk_level)}`}>
                      {mention.risk_level} risk
                    </span>
                    <span className="text-[10px] text-[var(--text-muted)]">
                      Confidence: {(mention.classification_confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                  <h3 className="text-sm font-semibold line-clamp-1">{mention.title}</h3>
                  <div className="flex items-center gap-3 mt-1 text-xs text-[var(--text-muted)]">
                    <span>{mention.source_name}</span>
                    <span>·</span>
                    <span>{formatDate(mention.date)}</span>
                    {mention.reach > 0 && (
                      <>
                        <span>·</span>
                        <span>Reach: {formatNumber(mention.reach)}</span>
                      </>
                    )}
                    <span>·</span>
                    <span>Impact: {(mention.impact_score * 100).toFixed(0)}/100</span>
                  </div>
                </div>
                <a
                  href={mention.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="p-1.5 rounded-lg hover:bg-[var(--bg-card-hover)] transition-colors flex-shrink-0"
                >
                  <ExternalLink className="w-3.5 h-3.5 text-[var(--text-muted)]" />
                </a>
              </div>

              {/* Expanded Content */}
              {expanded === mention.id && (
                <div className="mt-3 pt-3 border-t border-[var(--border)] space-y-3 animate-fade-in">
                  <div>
                    <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider mb-1">Content</p>
                    <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                      {mention.combined_text}
                    </p>
                  </div>
                  {mention.classification_rationale && (
                    <div>
                      <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider mb-1">Classification Rationale</p>
                      <p className="text-xs text-[var(--text-secondary)]">{mention.classification_rationale}</p>
                    </div>
                  )}
                  {mention.sentiment_explanation && (
                    <div>
                      <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider mb-1">Sentiment Explanation</p>
                      <p className="text-xs text-[var(--text-secondary)]">{mention.sentiment_explanation}</p>
                    </div>
                  )}
                  {mention.risk_signal && (
                    <div>
                      <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider mb-1">Risk Signal</p>
                      <p className="text-xs text-[var(--text-secondary)]">{mention.risk_signal}</p>
                    </div>
                  )}
                  {mention.themes.length > 0 && (
                    <div className="flex items-center gap-1 flex-wrap">
                      <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider mr-1">Themes:</p>
                      {mention.themes.map((t) => (
                        <span key={t} className="text-[10px] px-2 py-0.5 rounded-full bg-violet-500/10 text-violet-400 border border-violet-500/20">
                          {t}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {data && data.total_pages > 1 && (
        <div className="flex items-center justify-center gap-4 mt-6">
          <button
            onClick={() => setFilters((p) => ({ ...p, page: Math.max(1, p.page - 1) }))}
            disabled={filters.page === 1}
            className="p-2 rounded-lg hover:bg-[var(--bg-card)] disabled:opacity-30 transition-colors"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className="text-sm text-[var(--text-secondary)]">
            Page {data.page} of {data.total_pages}
          </span>
          <button
            onClick={() => setFilters((p) => ({ ...p, page: Math.min(data.total_pages, p.page + 1) }))}
            disabled={filters.page === data.total_pages}
            className="p-2 rounded-lg hover:bg-[var(--bg-card)] disabled:opacity-30 transition-colors"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );
}

export default function ContentExplorer() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center h-96">
          <div className="text-center">
            <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="text-sm text-[var(--text-muted)] mt-3">Loading explorer...</p>
          </div>
        </div>
      }
    >
      <ContentExplorerInner />
    </Suspense>
  );
}
