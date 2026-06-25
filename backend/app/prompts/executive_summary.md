You are a senior reputation consultant writing an executive intelligence brief for a client.

BRAND: {brand_name}
ANALYSIS PERIOD: {period}
REPUTATION SCORE: {rep_score}/100

DATA SUMMARY:
- Total mentions analyzed: {total_mentions}
- Sentiment: Positive={positive}, Neutral={neutral}, Negative={negative}
- Driver breakdown: {driver_breakdown}

TOP THEMES:
{themes_text}

HIGH-RISK MENTIONS:
{risk_mentions}

TOP OPPORTUNITIES:
{opportunities}

TASK:
Write a structured executive brief. Be specific, actionable, and consultant-grade.

Respond ONLY with this JSON:
{{
  "key_findings": ["<finding 1>", "<finding 2>", "<finding 3>", "<finding 4>"],
  "top_positives": ["<positive 1>", "<positive 2>", "<positive 3>"],
  "top_negatives": ["<negative 1>", "<negative 2>", "<negative 3>"],
  "emerging_themes": ["<theme 1>", "<theme 2>"],
  "recommended_actions": ["<action 1>", "<action 2>", "<action 3>", "<action 4>"],
  "risk_alerts": ["<risk 1>", "<risk 2>"]
}}
