from datetime import datetime, timezone

from sqlalchemy import select

from orbit.server import mcp
from orbit.database import async_session, init_db
from orbit.models.prospect import Prospect
from orbit.models.signal import Signal
from orbit.models.engagement import Engagement
from orbit.services.state import transition_state, get_next_action
from orbit.services.intelligence import update_relationship_memory, generate_value_ideas, generate_intro_angle
from orbit.services.exa import find_relevant_content


@mcp.tool()
async def orbit_log_engagement(
    linkedin_url: str,
    type: str,
    description: str,
    prospect_response: str = "",
    response_depth: str = "none",
) -> dict:
    """Log an engagement (commented, shared_content, sent_connection, sent_message, intro_made, received_reply)."""
    await init_db()
    valid_types = {"commented", "shared_content", "sent_connection", "sent_message", "intro_made", "received_reply"}
    if type not in valid_types:
        return {"error": f"Invalid type. Must be one of: {', '.join(sorted(valid_types))}"}

    valid_depths = {"none", "shallow", "moderate", "deep"}
    if response_depth not in valid_depths:
        return {"error": f"Invalid response_depth. Must be one of: {', '.join(sorted(valid_depths))}"}

    async with async_session() as session:
        prospect = await session.scalar(select(Prospect).where(Prospect.linkedin_url == linkedin_url))
        if not prospect:
            return {"error": "Prospect not found."}

        engagement = Engagement(
            prospect_id=prospect.id,
            type=type,
            description=description,
            prospect_response=prospect_response or None,
            response_depth=response_depth,
            impact="positive" if response_depth in ("moderate", "deep") else "neutral",
        )
        session.add(engagement)

        all_engagements = (await session.scalars(
            select(Engagement).where(Engagement.prospect_id == prospect.id).order_by(Engagement.created_at.desc())
        )).all()

        recent_signals = (await session.scalars(
            select(Signal).where(Signal.prospect_id == prospect.id).order_by(Signal.composite_score.desc()).limit(5)
        )).all()

        responses = [
            {
                "response_depth": e.response_depth,
                "created_at": e.created_at.isoformat() if e.created_at else "",
                "date": e.created_at.isoformat() if e.created_at else "",
            }
            for e in all_engagements
            if e.prospect_response
        ]

        signal_dicts = [
            {"composite_score": s.composite_score, "type": s.type, "title": s.title}
            for s in recent_signals
        ]

        engagement_dicts = [{"type": e.type, "description": e.description} for e in all_engagements]

        new_state, reason = transition_state(
            prospect.relationship_state, engagement_dicts, signal_dicts, responses
        )

        prospect.relationship_state = new_state
        prospect.last_touch_at = datetime.now(timezone.utc)
        prospect.updated_at = datetime.now(timezone.utc)

        top_signal = signal_dicts[0] if signal_dicts else None
        days_since_touch = 0
        action, why_now = get_next_action(
            new_state, top_signal, days_since_touch, engagement_dicts, prospect.signal_density
        )
        prospect.next_suggested_action = action
        prospect.why_now = why_now

        try:
            memory_update = await update_relationship_memory(
                {
                    "name": prospect.name,
                    "company": prospect.company,
                    "shared_interests": prospect.shared_interests,
                    "past_topics": prospect.past_topics,
                    "communication_preferences": prospect.communication_preferences,
                },
                {"type": type, "description": description, "prospect_response": prospect_response},
                signal_dicts[:3],
            )
            if not memory_update.get("error"):
                if memory_update.get("shared_interests"):
                    existing = prospect.shared_interests or ""
                    prospect.shared_interests = f"{existing}, {memory_update['shared_interests']}" if existing else memory_update["shared_interests"]
                if memory_update.get("past_topics"):
                    existing = prospect.past_topics or ""
                    prospect.past_topics = f"{existing}, {memory_update['past_topics']}" if existing else memory_update["past_topics"]
                if memory_update.get("communication_preferences"):
                    prospect.communication_preferences = memory_update["communication_preferences"]
        except Exception:
            pass

        await session.commit()

        return {
            "status": "logged",
            "prospect": prospect.name or linkedin_url,
            "state_transition": f"{prospect.relationship_state} (was: {prospect.relationship_state})" if new_state == prospect.relationship_state else f"{new_state} (was: {prospect.relationship_state})",
            "new_state": new_state,
            "transition_reason": reason,
            "next_action": action,
            "why_now": why_now,
        }


@mcp.tool()
async def orbit_get_engagement_history(linkedin_url: str) -> dict:
    """Full log of all touches and responses for a prospect."""
    await init_db()
    async with async_session() as session:
        prospect = await session.scalar(select(Prospect).where(Prospect.linkedin_url == linkedin_url))
        if not prospect:
            return {"error": "Prospect not found."}

        engagements = (await session.scalars(
            select(Engagement).where(Engagement.prospect_id == prospect.id).order_by(Engagement.created_at.asc())
        )).all()

        return {
            "prospect": prospect.name or linkedin_url,
            "relationship_state": prospect.relationship_state,
            "total_engagements": len(engagements),
            "relationship_memory": {
                "shared_interests": prospect.shared_interests,
                "past_topics": prospect.past_topics,
                "communication_preferences": prospect.communication_preferences,
                "notes": prospect.relationship_notes,
            },
            "engagements": [
                {
                    "type": e.type,
                    "description": e.description,
                    "prospect_response": e.prospect_response,
                    "response_depth": e.response_depth,
                    "impact": e.impact,
                    "date": e.created_at.isoformat() if e.created_at else None,
                }
                for e in engagements
            ],
        }


@mcp.tool()
async def orbit_get_value_ideas(linkedin_url: str) -> dict:
    """What can you share that's genuinely useful, no ask? Evidence-based content suggestions."""
    await init_db()
    async with async_session() as session:
        prospect = await session.scalar(select(Prospect).where(Prospect.linkedin_url == linkedin_url))
        if not prospect:
            return {"error": "Prospect not found."}

        recent_signals = (await session.scalars(
            select(Signal)
            .where(Signal.prospect_id == prospect.id)
            .order_by(Signal.composite_score.desc())
            .limit(5)
        )).all()

        signal_dicts = [
            {
                "type": s.type,
                "title": s.title,
                "content": s.content[:300],
                "composite_score": s.composite_score,
                "why_now": s.why_now,
            }
            for s in recent_signals
        ]

        exa_content = await find_relevant_content(
            prospect.context,
            prospect.shared_interests or prospect.context,
        )
        exa_clean = [c for c in exa_content if not c.get("error")]

        ideas = await generate_value_ideas(
            {
                "name": prospect.name,
                "company": prospect.company,
                "context": prospect.context,
                "shared_interests": prospect.shared_interests,
            },
            signal_dicts,
            exa_clean,
        )

        return {
            "prospect": prospect.name or linkedin_url,
            "value_ideas": ideas,
            "based_on_signals": len(signal_dicts),
            "exa_content_sourced": len(exa_clean),
        }


@mcp.tool()
async def orbit_get_intro_angle(linkedin_url: str) -> dict:
    """Get a natural intro angle. BLOCKED unless relationship_state is 'ready'."""
    await init_db()
    async with async_session() as session:
        prospect = await session.scalar(select(Prospect).where(Prospect.linkedin_url == linkedin_url))
        if not prospect:
            return {"error": "Prospect not found."}

        if prospect.relationship_state != "ready":
            engagements = (await session.scalars(
                select(Engagement).where(Engagement.prospect_id == prospect.id)
            )).all()
            responses = [e for e in engagements if e.prospect_response]
            deep_responses = [e for e in responses if e.response_depth in ("moderate", "deep")]

            if prospect.relationship_state in ("cold", "warming") and len(deep_responses) == 0:
                return {
                    "blocked": True,
                    "reason": "Not enough relationship evidence. Send a connection request first and wait for acceptance before any follow-up.",
                    "current_state": prospect.relationship_state,
                }

            missing = []
            if len(deep_responses) < 2:
                missing.append(f"Need {2 - len(deep_responses)} more meaningful bidirectional interactions.")
            if not any(True for e in engagements if e.response_depth in ("moderate", "deep")):
                missing.append("No moderate or deep responses from prospect yet.")
            missing.append(f"Current state: {prospect.relationship_state}. Must be 'ready' for intro.")

            return {
                "blocked": True,
                "reason": "Relationship is not ready for an intro.",
                "current_state": prospect.relationship_state,
                "what_is_missing": missing,
            }

        engagements = (await session.scalars(
            select(Engagement)
            .where(Engagement.prospect_id == prospect.id)
            .order_by(Engagement.created_at.asc())
        )).all()

        top_signals = (await session.scalars(
            select(Signal)
            .where(Signal.prospect_id == prospect.id)
            .order_by(Signal.composite_score.desc())
            .limit(5)
        )).all()

        engagement_dicts = [
            {
                "type": e.type,
                "description": e.description,
                "prospect_response": e.prospect_response,
                "response_depth": e.response_depth,
                "date": e.created_at.isoformat() if e.created_at else None,
            }
            for e in engagements
        ]

        signal_dicts = [
            {"type": s.type, "title": s.title, "content": s.content[:300], "why_now": s.why_now}
            for s in top_signals
        ]

        angle = await generate_intro_angle(
            {
                "name": prospect.name,
                "company": prospect.company,
                "context": prospect.context,
                "relationship_state": prospect.relationship_state,
                "past_topics": prospect.past_topics,
                "shared_interests": prospect.shared_interests,
            },
            engagement_dicts,
            signal_dicts,
        )

        return {
            "prospect": prospect.name or linkedin_url,
            "relationship_state": "ready",
            "intro_angle": angle,
            "based_on_engagements": len(engagement_dicts),
            "based_on_signals": len(signal_dicts),
        }
