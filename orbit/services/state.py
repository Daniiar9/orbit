from datetime import datetime


def transition_state(
    current_state: str,
    recent_engagements: list,
    recent_signals: list,
    prospect_responses: list,
) -> tuple[str, str]:
    if current_state == "archived":
        return "archived", "Prospect is archived."

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
        has_current_signal = any(True for s in recent_signals if s.get("composite_score", 0) > 5)

        if spread_across_weeks and has_current_signal and has_deep_response:
            return "ready", (
                f"{len(bidirectional)} bidirectional interactions across {len(weeks)} weeks, "
                "active signal present, and meaningful response depth."
            )

    if has_deep_response or len(bidirectional) >= 1:
        reason = "Prospect has responded meaningfully."
        if current_state in ("cold", "warming"):
            return "warm", reason
        return current_state if current_state == "ready" else "warm", reason

    if len(recent_engagements) >= 1:
        if current_state == "cold":
            return "warming", f"First engagement logged ({len(recent_engagements)} total)."
        return current_state, "Engagement exists but no meaningful response yet."

    return current_state, "No new engagement activity."


def get_next_action(
    state: str,
    top_signal: dict | None,
    days_since_last_touch: int,
    engagements: list,
    signal_density: float,
) -> tuple[str, str]:
    if signal_density < 3:
        return (
            "Insufficient signal density. Consider removing from active list.",
            f"Signal density is {signal_density}/10. No LinkedIn activity or Exa signals to act on.",
        )

    if not top_signal or top_signal.get("composite_score", 0) < 4:
        return (
            "No action right now. Check again in a few days.",
            "No fresh signal worth acting on.",
        )

    signal_title = top_signal.get("title", "recent signal")
    signal_type = top_signal.get("type", "unknown")
    composite = top_signal.get("composite_score", 0)

    if state == "ready" and composite > 8:
        return (
            f"Consider an intro based on '{signal_title}'.",
            top_signal.get("why_now", "Strong signal alignment with warm relationship."),
        )

    if composite > 7 and signal_type in ("post", "comment", "pain_point"):
        return (
            f"Engage with their {signal_type}: '{signal_title}'.",
            top_signal.get("why_now", f"High-relevance {signal_type} detected."),
        )

    if composite > 6 and signal_type in ("company_news", "hiring"):
        return (
            f"Share relevant content related to '{signal_title}'.",
            top_signal.get("why_now", f"Company signal ({signal_type}) worth responding to."),
        )

    if composite > 5:
        return (
            f"Monitor '{signal_title}' — not yet strong enough to act.",
            top_signal.get("why_now", "Moderate signal. Wait for a stronger trigger."),
        )

    return (
        "No action right now. Check again in a few days.",
        "No fresh signal worth acting on.",
    )
