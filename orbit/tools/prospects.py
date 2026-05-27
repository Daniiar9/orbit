import csv
from datetime import datetime, timezone

from sqlalchemy import select, func

from orbit.server import mcp
from orbit.database import async_session, init_db
from orbit.models.prospect import Prospect
from orbit.models.signal import Signal
from orbit.config import MAX_PROSPECTS
from orbit.services.linkedin import get_person_profile, get_recent_posts, get_recent_activity
from orbit.services.exa import find_company_signals
from orbit.services.scoring import score_signal, compute_signal_density


@mcp.tool()
async def orbit_add_prospect(linkedin_url: str, context: str) -> dict:
    """Add a prospect to your active list. Runs initial LinkedIn + Exa signal scan."""
    await init_db()
    async with async_session() as session:
        count = await session.scalar(
            select(func.count()).select_from(Prospect).where(Prospect.relationship_state != "archived")
        )
        if count >= MAX_PROSPECTS:
            return {"error": f"Active prospect limit reached ({MAX_PROSPECTS}). Remove or archive someone first."}

        existing = await session.scalar(select(Prospect).where(Prospect.linkedin_url == linkedin_url))
        if existing:
            return {"error": f"Prospect already exists: {existing.name or linkedin_url} ({existing.relationship_state})"}

        profile = await get_person_profile(linkedin_url)
        posts = await get_recent_posts(linkedin_url, limit=5)
        activity = await get_recent_activity(linkedin_url)

        company = profile.get("company", "") if not profile.get("error") else ""
        exa_signals = await find_company_signals(company, context) if company else []
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

        prospect = Prospect(
            linkedin_url=linkedin_url,
            name=profile.get("name") if not profile.get("error") else None,
            title=profile.get("title") if not profile.get("error") else None,
            company=company or None,
            context=context,
            relationship_state="cold",
            signal_density=density,
            last_scanned_at=datetime.now(timezone.utc),
        )
        session.add(prospect)
        await session.flush()

        for sig in exa_clean:
            scored = score_signal(sig.get("summary", ""), context, datetime.now(timezone.utc))
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

        await session.commit()

        result = {
            "status": "added",
            "name": prospect.name or "Unknown (profile scan may have failed)",
            "company": prospect.company or "Unknown",
            "signal_density": density,
            "signals_found": len(exa_clean),
            "relationship_state": "cold",
        }
        if density < 3:
            result["warning"] = (
                "Low-observable prospect — may not have enough signal to engage meaningfully. "
                f"Signal density: {density}/10."
            )
        return result


@mcp.tool()
async def orbit_remove_prospect(linkedin_url: str, reason: str = "") -> dict:
    """Archive a prospect. Keeps history, removes from active monitoring."""
    await init_db()
    async with async_session() as session:
        prospect = await session.scalar(select(Prospect).where(Prospect.linkedin_url == linkedin_url))
        if not prospect:
            return {"error": "Prospect not found."}
        prospect.relationship_state = "archived"
        prospect.relationship_notes = (prospect.relationship_notes or "") + f"\nArchived: {reason}" if reason else prospect.relationship_notes
        prospect.updated_at = datetime.now(timezone.utc)
        await session.commit()
        return {"status": "archived", "name": prospect.name or linkedin_url, "reason": reason}


@mcp.tool()
async def orbit_update_context(linkedin_url: str, new_context: str) -> dict:
    """Update why someone is on your list. Re-scores signals with new context."""
    await init_db()
    async with async_session() as session:
        prospect = await session.scalar(select(Prospect).where(Prospect.linkedin_url == linkedin_url))
        if not prospect:
            return {"error": "Prospect not found."}

        prospect.context = new_context
        prospect.updated_at = datetime.now(timezone.utc)

        signals = (await session.scalars(
            select(Signal).where(Signal.prospect_id == prospect.id).order_by(Signal.created_at.desc()).limit(20)
        )).all()

        rescored = []
        for sig in signals:
            scored = score_signal(sig.content, new_context, sig.created_at)
            sig.relevance_score = scored["relevance_score"]
            sig.recency_score = scored["recency_score"]
            sig.composite_score = scored["composite_score"]
            sig.confidence = scored["confidence"]
            sig.suggested_action = scored["suggested_action"]
            sig.why_now = scored["why_now"]
            rescored.append({"title": sig.title, "new_composite": scored["composite_score"]})

        await session.commit()
        return {
            "status": "updated",
            "name": prospect.name or linkedin_url,
            "new_context": new_context,
            "signals_rescored": len(rescored),
        }


@mcp.tool()
async def orbit_import_csv(file_path: str, context: str = "") -> dict:
    """Import prospects from a Sales Navigator CSV export. Rate-limited scanning."""
    import asyncio

    await init_db()

    try:
        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except Exception as e:
        return {"error": f"Could not read CSV: {e}"}

    if not rows:
        return {"error": "CSV is empty."}

    headers = {h.lower().strip(): h for h in rows[0].keys()}

    def find_col(candidates):
        for c in candidates:
            for h_lower, h_orig in headers.items():
                if c in h_lower:
                    return h_orig
        return None

    url_col = find_col(["linkedin url", "linkedin", "profile url", "url"])
    first_col = find_col(["first name", "first"])
    last_col = find_col(["last name", "last"])
    company_col = find_col(["company", "organization"])

    if not url_col:
        return {"error": "Could not find LinkedIn URL column in CSV."}

    async with async_session() as session:
        count = await session.scalar(
            select(func.count()).select_from(Prospect).where(Prospect.relationship_state != "archived")
        )
        available = MAX_PROSPECTS - count

    results = []
    added = 0
    skipped = 0

    for row in rows:
        linkedin_url = row.get(url_col, "").strip()
        if not linkedin_url:
            skipped += 1
            continue

        if added >= available:
            results.append({
                "linkedin_url": linkedin_url,
                "status": "skipped",
                "reason": f"Would exceed {MAX_PROSPECTS} prospect limit.",
            })
            skipped += 1
            continue

        name_parts = []
        if first_col and row.get(first_col):
            name_parts.append(row[first_col].strip())
        if last_col and row.get(last_col):
            name_parts.append(row[last_col].strip())
        name = " ".join(name_parts) or None
        company = row.get(company_col, "").strip() if company_col else ""

        row_context = context or f"Imported from CSV. Company: {company}" if company else "Imported from CSV."

        result = await orbit_add_prospect(linkedin_url, row_context)
        if result.get("error"):
            results.append({"linkedin_url": linkedin_url, "name": name, "status": "skipped", "reason": result["error"]})
            skipped += 1
        else:
            results.append({
                "linkedin_url": linkedin_url,
                "name": result.get("name", name),
                "status": "added",
                "signal_density": result.get("signal_density", 0),
            })
            added += 1

        await asyncio.sleep(60 / max(1, __import__("orbit.config", fromlist=["SCAN_RATE_LIMIT"]).SCAN_RATE_LIMIT))

    results.sort(key=lambda r: r.get("signal_density", 0), reverse=True)

    return {
        "total_rows": len(rows),
        "added": added,
        "skipped": skipped,
        "prospects": results,
        "recommendation": "Review prospects sorted by signal density above. Consider removing those with density < 3.",
    }
