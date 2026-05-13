"""Prompt text used when serializing analyzer output for AI review."""

AI_ANALYSIS_PROMPT = (
    "Analyze this X++ class JSON. Focus on DB reads/writes, ttsBegin transaction boundaries, "
    "nested while select patterns, update/insert/delete risks, and risky method-call chains."
)
