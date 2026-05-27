from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func

from orbit.server import mcp
from orbit.database import async_session, init_db
from orbit.models.prospect import Prospect
from orbit.models.signal import Signal
from orbit.models.engagement import Engagement
from orbit.services.state import get_next_action


@mcp.tool()
async def orbit_get_overview() -> dict:
    """Full active list grouped by relationship state."""
    await init_db()
    async with async_session() as session:
        prospects = (await session.scalars(
            select(Prospect).where(Prospect.relationship_state != "archived").order_by(Prospect.signal_score.desc())
        )).all()

        if not prospects:
            return {"message": "No active prospects. Add some with orbit_add_prospect."}

        grouped = {"ready": [], "warm": [], "warming": [], "cold": []}

        for p in prospects:
            entry = {
                "name": p.name or p.linkedin_url,
                "company": p.company or "Unknown",
                "state": p.relationship_state,
                "signal_score": p.signal_score,
                "signal_density": p.signal_density,
                "next_action": p.next_suggested_action,
                "why_now": p.why_now,
                "last_touch": p.last_touch_at.isoformat() if p.last_touch_at else "Never",
            }
            if p.signal_density < 3:
                entry["flag"] = "Low signal density — consider removing."

            state = p.relationship_state
            if state in grouped:
                grouped[state].append(entry)
            else:
                grouped.setdefault("other", []).append(entry)

        return {
            "total_active": len(prospects),
            "by_state": {k: v for k, v in grouped.items() if v},
            "low_density_count": sum(1 for p in prospects if p.signal_density < 3),
        }


@mcp.tool()
async def orbit_get_stats() -> dict:
    """Dashboard stats: prospects by state, engagement rate, signal processing."""
    await init_db()
    async with async_session() as session:
        total = await session.scalar(
            select(func.count()).select_from(Prospect).where(Prospect.relationship_state != "archived")
        )

        state_counts = {}
        for state in ("cold", "warming", "warm", "ready"):
            count = await session.scalar(
                select(func.count()).select_from(Prospect).where(Prospect.relationship_state == state)
            )
            state_counts[state] = count or 0

        total_engagements = await session.scalar(select(func.count()).select_from(Engagement)) or 0
        engagements_with_response = await session.scalar(
            select(func.count()).select_from(Engagement).where(Engagement.prospect_response.isnot(None))
        ) or 0

        engagement_rate = (
            round(engagements_with_response / total_engagements * 100, 1)
            if total_engagements > 0
            else 0
        )

        low_density = await session.scalar(
            select(func.count()).select_from(Prospect)
            .where(Prospect.relationship_state != "archived")
            .where(Prospect.signal_density < 3)
        ) or 0

        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        signals_this_week = await session.scalar(
            select(func.count()).select_from(Signal).where(Signal.created_at >= week_ago)
        ) or 0

        return {
            "total_active_prospects": total or 0,
            "by_state": state_counts,
            "engagement_rate": f"{engagement_rate}%",
            "total_engagements": total_engagements,
            "engagements_with_response": engagements_with_response,
            "low_density_flagged": low_density,
            "signals_processed_this_week": signals_this_week,
        }


@mcp.tool()
async def orbit_get_relationship(linkedin_url: str) -> dict:
    """Full relationship summary: state, scores, last touch, signal density, memory, next action + why_now."""
    await init_db()
    async with async_session() as session:
        prospect = await session.scalar(select(Prospect).where(Prospect.linkedin_url == linkedin_url))
        if not prospect:
            return {"error": "Prospect not found."}

        signals = (await session.scalars(
            select(Signal)
            .where(Signal.prospect_id == prospect.id)
            .order_by(Signal.composite_score.desc())
            .limit(5)
        )).all()

        engagements = (await session.scalars(
            select(Engagement)
            .where(Engagement.prospect_id == prospect.id)
            .order_by(Engagement.created_at.desc())
        )).all()

        days_since_touch = 999
        if prospect.last_touch_at:
            days_since_touch = (datetime.now(timezone.utc) - prospect.last_touch_at).days

        top_signal = None
        if signals:
            s = signals[0]
            top_signal = {"composite_score": s.composite_score, "type": s.type, "title": s.title, "why_now": s.why_now}

        engagement_dicts = [{"type": e.type, "description": e.description} for e in engagements]
        action, why_now = get_next_action(
            prospect.relationship_state, top_signal, days_since_touch, engagement_dicts, prospect.signal_density,
        )

        return {
            "prospect": prospect.name or linkedin_url,
            "linkedin_url": prospect.linkedin_url,
            "company": prospect.company or "Unknown",
            "context": prospect.context,
            "relationship_state": prospect.relationship_state,
            "signal_score": prospect.signal_score,
            "signal_density": prospect.signal_density,
            "last_touch": prospect.last_touch_at.isoformat() if prospect.last_touch_at else "Never",
            "last_scanned": prospect.last_scanned_at.isoformat() if prospect.last_scanned_at else "Never",
            "total_engagements": len(engagements),
            "relationship_memory": {
                "shared_interests": prospect.shared_interests,
                "past_topics": prospect.past_topics,
                "communication_preferences": prospect.communication_preferences,
                "notes": prospect.relationship_notes,
            },
            "top_signals": [
                {"type": s.type, "title": s.title, "score": s.composite_score, "why_now": s.why_now}
                for s in signals[:3]
            ],
            "next_action": action,
            "why_now": why_now,
        }
