import asyncio
from datetime import datetime, timezone, timedelta

from sqlalchemy import select

from orbit.server import mcp
from orbit.database import async_session, init_db
from orbit.models.prospect import Prospect
from orbit.models.signal import Signal
from orbit.services.linkedin import get_recent_posts, get_recent_activity
from orbit.services.exa import find_company_signals
from orbit.services.scoring import score_signal, compute_signal_density, compute_attention_metrics
from orbit.models.engagement import Engagement
from orbit.services.state import get_next_action
from orbit.config import SCAN_RATE_LIMIT


@mcp.tool()
async def orbit_get_signals(linkedin_url: str, days: int = 14) -> dict:
    """Get recent signals for a specific prospect. LinkedIn + Exa combined and ranked."""
    await init_db()
    async with async_session() as session:
        prospect = await session.scalar(select(Prospect).where(Prospect.linkedin_url == linkedin_url))
        if not prospect:
            return {"error": "Prospect not found."}

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        signals = (await session.scalars(
            select(Signal)
            .where(Signal.prospect_id == prospect.id)
            .where(Signal.created_at >= cutoff)
            .order_by(Signal.composite_score.desc())
        )).all()

        return {
            "prospect": prospect.name or linkedin_url,
            "signal_density": prospect.signal_density,
            "signals": [
                {
                    "type": s.type,
                    "source": s.source,
                    "title": s.title,
                    "content": s.content[:300],
                    "composite_score": s.composite_score,
                    "confidence": s.confidence,
                    "suggested_action": s.suggested_action,
                    "why_now": s.why_now,
                    "url": s.url,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                }
                for s in signals
            ],
            "signal_density_assessment": _density_assessment(prospect.signal_density),
        }


@mcp.tool()
async def orbit_get_opportunities() -> dict:
    """What should I do today? Returns prospects with actionable signals right now."""
    await init_db()
    async with async_session() as session:
        prospects = (await session.scalars(
            select(Prospect).where(Prospect.relationship_state != "archived")
        )).all()

        if not prospects:
            return {"message": "No active prospects. Add some with orbit_add_prospect."}

        opportunities = {"engage": [], "share": [], "intro": []}
        checked = 0

        for prospect in prospects:
            signals = (await session.scalars(
                select(Signal)
                .where(Signal.prospect_id == prospect.id)
                .where(Signal.composite_score > 6)
                .order_by(Signal.composite_score.desc())
                .limit(3)
            )).all()

            if not signals:
                continue

            top = signals[0]
            entry = {
                "name": prospect.name or prospect.linkedin_url,
                "company": prospect.company or "Unknown",
                "state": prospect.relationship_state,
                "signal_density": prospect.signal_density,
                "top_signal": {
                    "title": top.title,
                    "type": top.type,
                    "composite_score": top.composite_score,
                    "why_now": top.why_now,
                },
                "next_action": prospect.next_suggested_action,
                "why_now": prospect.why_now,
            }

            if top.suggested_action == "engage":
                opportunities["engage"].append(entry)
            elif top.suggested_action == "share":
                opportunities["share"].append(entry)
            elif prospect.relationship_state == "ready":
                opportunities["intro"].append(entry)

            checked += 1

        total = sum(len(v) for v in opportunities.values())
        if total == 0:
            return {"message": "Nothing actionable right now. Check back later.", "prospects_checked": checked}

        return {
            "opportunities": opportunities,
            "total_actionable": total,
            "prospects_checked": checked,
        }


@mcp.tool()
async def orbit_scan_prospect(linkedin_url: str) -> dict:
    """Force a fresh signal scan for one prospect."""
    await init_db()
    async with async_session() as session:
        prospect = await session.scalar(select(Prospect).where(Prospect.linkedin_url == linkedin_url))
        if not prospect:
            return {"error": "Prospect not found."}

        posts = await get_recent_posts(linkedin_url, limit=5)
        activity = await get_recent_activity(linkedin_url)
        company = prospect.company or ""
        exa_signals = await find_company_signals(company, prospect.context) if company else []
        exa_clean = [s for s in exa_signals if not s.get("error")]

        last_activity_days = 90
        if posts:
            last_activity_days = 0

        density = compute_signal_density(
            recent_posts_count=len(posts),
            recent_activity_count=len(activity),
            exa_signals_count=len(exa_clean),
            last_public_activity_days=last_activity_days,
        )

        new_signals = []
        for post in posts:
            scored = score_signal(post.get("content", ""), prospect.context, datetime.now(timezone.utc))
            db_signal = Signal(
                prospect_id=prospect.id,
                type="post",
                source="linkedin",
                title=post.get("content", "")[:100],
                content=post.get("content", ""),
                url=post.get("url"),
                relevance_score=scored["relevance_score"],
                recency_score=scored["recency_score"],
                composite_score=scored["composite_score"],
                confidence=scored["confidence"],
                suggested_action=scored["suggested_action"],
                why_now=scored["why_now"],
            )
            session.add(db_signal)
            new_signals.append(scored)

        for sig in exa_clean:
            scored = score_signal(sig.get("summary", ""), prospect.context, datetime.now(timezone.utc))
            db_signal = Signal(
                prospect_id=prospect.id,
                type=sig.get("signal_type", "company_news"),
                source="exa",
                title=sig.get("title", ""),
                content=sig.get("summary", ""),
                url=sig.get("url"),
                relevance_score=scored["relevance_score"],
                recency_score=scored["recency_score"],
                composite_score=scored["composite_score"],
                confidence=scored["confidence"],
                suggested_action=scored["suggested_action"],
                why_now=scored["why_now"],
            )
            session.add(db_signal)
            new_signals.append(scored)

        top_signal_dict = max(new_signals, key=lambda s: s["composite_score"]) if new_signals else None
        engagements = []
        days_since_touch = 999
        if prospect.last_touch_at:
            days_since_touch = (datetime.now(timezone.utc) - prospect.last_touch_at).days

        action, why_now = get_next_action(
            prospect.relationship_state, top_signal_dict, days_since_touch, engagements, density
        )

        prospect.signal_density = density
        prospect.signal_score = top_signal_dict["composite_score"] if top_signal_dict else 0.0
        prospect.next_suggested_action = action
        prospect.why_now = why_now
        prospect.last_scanned_at = datetime.now(timezone.utc)
        prospect.updated_at = datetime.now(timezone.utc)

        all_engagements = (await session.scalars(
            select(Engagement).where(Engagement.prospect_id == prospect.id)
        )).all()
        engagement_dicts_for_metrics = [
            {"type": e.type, "prospect_response": e.prospect_response}
            for e in all_engagements
        ]
        signal_dicts_for_metrics = [
            {"created_at": s.created_at} for s in (await session.scalars(
                select(Signal).where(Signal.prospect_id == prospect.id)
                .order_by(Signal.created_at.desc()).limit(20)
            )).all()
        ]
        metrics = compute_attention_metrics(
            engagement_dicts_for_metrics,
            signal_dicts_for_metrics,
            prospect.signal_score,
            prospect.last_touch_at,
            prospect.last_scanned_at,
        )
        prospect.staleness_days = metrics["staleness_days"]
        prospect.reciprocity_score = metrics["reciprocity_score"]
        prospect.overinvestment_risk = metrics["overinvestment_risk"]
        prospect.attention_score = metrics["attention_score"]

        await session.commit()

        return {
            "prospect": prospect.name or linkedin_url,
            "signal_density": density,
            "new_signals": len(new_signals),
            "top_score": top_signal_dict["composite_score"] if top_signal_dict else 0,
            "next_action": action,
            "why_now": why_now,
            "density_assessment": _density_assessment(density),
        }


@mcp.tool()
async def orbit_scan_all() -> dict:
    """Scan all active prospects for fresh signals. Rate-limited."""
    await init_db()
    async with async_session() as session:
        prospects = (await session.scalars(
            select(Prospect).where(Prospect.relationship_state != "archived")
        )).all()

    if not prospects:
        return {"message": "No active prospects."}

    results = []
    errors = []
    delay = 60 / max(1, SCAN_RATE_LIMIT)

    for i, prospect in enumerate(prospects):
        if i > 0:
            await asyncio.sleep(delay)

        try:
            result = await orbit_scan_prospect(prospect.linkedin_url)
            results.append({
                "name": prospect.name or prospect.linkedin_url,
                "signal_density": result.get("signal_density", 0),
                "new_signals": result.get("new_signals", 0),
                "next_action": result.get("next_action"),
            })
        except Exception as e:
            errors.append({
                "name": prospect.name or prospect.linkedin_url,
                "error": str(e),
            })

    with_signals = [r for r in results if r["new_signals"] > 0]
    low_density = [r for r in results if r["signal_density"] < 3]

    return {
        "scanned": len(results),
        "errors": len(errors),
        "with_fresh_signals": len(with_signals),
        "low_density_flagged": len(low_density),
        "results": results,
        "error_details": errors if errors else None,
        "removal_suggestions": [
            {"name": r["name"], "signal_density": r["signal_density"]}
            for r in low_density
        ] if low_density else None,
    }


def _density_assessment(density: float) -> str:
    if density >= 7:
        return "High — active poster, company in the news, lots to work with."
    elif density >= 4:
        return "Medium — occasional activity, some company signals."
    else:
        return "Low — insufficient signal density. Hold or consider removing."
