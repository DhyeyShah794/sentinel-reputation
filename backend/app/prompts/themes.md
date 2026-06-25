You are a reputation intelligence analyst examining digital mentions about {brand_name}.

MENTIONS SUMMARY:
Total mentions: {total_mentions}
Sentiment breakdown: {sentiment_breakdown}
Driver breakdown: {driver_breakdown}

SAMPLE MENTIONS (representative):
{sample_mentions}

TASK:
Identify 5–8 major narrative themes present across these mentions. A theme is a recurring topic, story, or pattern that a reputation consultant would track.

For each theme, provide:
- theme_name: Short, descriptive name (2-5 words)
- description: What this theme captures (1-2 sentences)
- mention_count: Estimated number of mentions related to this theme
- sentiment_skew: "positive", "negative", or "mixed"
- representative_quotes: 2-3 short excerpts from the mentions
- business_implication: What this means for the brand's reputation strategy (1-2 sentences)

Respond ONLY with a JSON array:
[
  {{"theme_name": "...", "description": "...", "mention_count": <int>, "sentiment_skew": "...", "representative_quotes": ["...", "..."], "business_implication": "..."}},
  ...
]
