import { clsx, type ClassValue } from "clsx";

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

export function formatNumber(num: number): string {
  if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(1)}M`;
  if (num >= 1_000) return `${(num / 1_000).toFixed(1)}K`;
  return num.toString();
}

export function formatDate(dateStr: string | null): string {
  if (!dateStr) return "N/A";
  try {
    return new Date(dateStr).toLocaleDateString("en-IN", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return dateStr;
  }
}

export function getSentimentColor(sentiment: string): string {
  switch (sentiment) {
    case "positive":
      return "#10B981";
    case "negative":
      return "#F43F5E";
    case "neutral":
      return "#F59E0B";
    default:
      return "#94A3B8";
  }
}

export function getSentimentBg(sentiment: string): string {
  switch (sentiment) {
    case "positive":
      return "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
    case "negative":
      return "bg-rose-500/10 text-rose-400 border-rose-500/20";
    case "neutral":
      return "bg-amber-500/10 text-amber-400 border-amber-500/20";
    default:
      return "bg-slate-500/10 text-slate-400 border-slate-500/20";
  }
}

export function getRiskColor(level: string): string {
  switch (level) {
    case "high":
      return "bg-rose-500/10 text-rose-400 border-rose-500/20";
    case "medium":
      return "bg-amber-500/10 text-amber-400 border-amber-500/20";
    case "low":
      return "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
    default:
      return "bg-slate-500/10 text-slate-400 border-slate-500/20";
  }
}

export function getScoreColor(score: number): string {
  if (score >= 75) return "#10B981";
  if (score >= 50) return "#F59E0B";
  return "#F43F5E";
}

export function getScoreLabel(score: number): string {
  if (score >= 80) return "Excellent";
  if (score >= 65) return "Strong";
  if (score >= 50) return "Moderate";
  if (score >= 35) return "Weak";
  return "Critical";
}
