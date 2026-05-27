from datetime import datetime, timezone


def score_signal(signal_content: str, prospect_context: str, signal_date: datetime) -> dict:
    now = datetime.now(timezone.utc)
    if signal_date.tzinfo is None:
        signal_date = signal_date.replace(tzinfo=timezone.utc)
    days_old = (now - signal_date).days

    if days_old <= 1:
        recency_score = 10.0
    elif days_old <= 3:
        recency_score = 8.0
    elif days_old <= 7:
        recency_score = 6.0
    elif days_old <= 14:
        recency_score = 4.0
    elif days_old <= 30:
        recency_score = 2.0
    else:
        recency_score = 1.0

    context_lower = prospect_context.lower()
    content_lower = signal_content.lower()
    context_words = set(context_lower.split())
    content_words = set(content_lower.split())
    overlap = context_words & content_words
    stopwords = {"the", "a", "an", "is", "are", "was", "were", "and", "or", "but", "in", "on", "at", "to", "for",
                 "of", "with", "by", "from", "as", "into", "about", "that", "this", "it", "they", "their", "has",
                 "have", "had", "be", "been", "being", "do", "does", "did", "will", "would", "could", "should"}
    meaningful_overlap = overlap - stopwords
    overlap_ratio = len(meaningful_overlap) / max(len(context_words - stopwords), 1)

    if overlap_ratio > 0.3:
        relevance_score = 9.0
    elif overlap_ratio > 0.2:
        relevance_score = 7.0
    elif overlap_ratio > 0.1:
        relevance_score = 5.0
    elif overlap_ratio > 0.05:
        relevance_score = 3.0
    else:
        relevance_score = 1.0

    composite_score = relevance_score * 0.6 + recency_score * 0.4

    if composite_score > 8:
        confidence = "high"
    elif composite_score > 5:
        confidence = "medium"
    else:
        confidence = "low"

    if composite_score > 7:
        suggested_action = "engage"
    elif composite_score > 6:
        suggested_action = "share"
    else:
        suggested_action = "wait"

    if suggested_action == "engage":
        why_now = f"Strong relevance match ({relevance_score:.0f}/10) and fresh signal ({days_old}d old)."
    elif suggested_action == "share":
        why_now = f"Moderate signal strength ({composite_score:.1f}/10) — worth sharing relevant content."
    else:
        why_now = "No strong signal to act on right now."

    return {
        "relevance_score": round(relevance_score, 1),
        "recency_score": round(recency_score, 1),
        "composite_score": round(composite_score, 1),
        "confidence": confidence,
        "suggested_action": suggested_action,
        "why_now": why_now,
    }


def compute_signal_density(
    recent_posts_count: int,
    recent_activity_count: int,
    exa_signals_count: int,
    last_public_activity_days: int,
) -> float:
    post_score = min(recent_posts_count * 1.5, 4.0)
    activity_score = min(recent_activity_count * 0.5, 2.0)
    exa_score = min(exa_signals_count * 0.8, 2.0)

    if last_public_activity_days <= 7:
        recency_bonus = 2.0
    elif last_public_activity_days <= 14:
        recency_bonus = 1.5
    elif last_public_activity_days <= 30:
        recency_bonus = 1.0
    elif last_public_activity_days <= 45:
        recency_bonus = 0.5
    else:
        recency_bonus = 0.0

    density = post_score + activity_score + exa_score + recency_bonus
    return round(min(density, 10.0), 1)


def compute_relationship_state(
    engagements: list,
    signals: list,
    days_since_last_touch: int,
    prospect_responses: list,
) -> str:
    if not engagements:
        return "cold"

    bidirectional = [
        r for r in prospect_responses
        if r.get("response_depth") in ("moderate", "deep")
    ]
    has_deep_response = any(r.get("response_depth") in ("moderate", "deep") for r in prospect_responses)

    if len(bidirectional) >= 2:
        dates = sorted(set(r.get("date", r.get("created_at", ""))[:10] for r in bidirectional))
        weeks = set()
        for d in dates:
            try:
                dt = datetime.fromisoformat(d)
                weeks.add(dt.isocalendar()[1])
            except (ValueError, TypeError):
                pass
        spread_across_weeks = len(weeks) >= 2

        has_current_signal = any(True for s in signals if s.get("composite_score", 0) > 5)

        if spread_across_weeks and has_current_signal and has_deep_response:
            return "ready"

    if has_deep_response or len(bidirectional) >= 1:
        return "warm"

    if len(engagements) >= 1:
        return "warming"

    return "cold"
