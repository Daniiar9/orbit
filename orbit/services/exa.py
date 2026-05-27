import asyncio
from datetime import datetime, timedelta, timezone

from exa_py import Exa

from orbit.config import get_exa_api_key

_client = None


def _get_client() -> Exa:
    global _client
    if _client is None:
        _client = Exa(api_key=get_exa_api_key())
    return _client


async def find_company_signals(company: str, context: str, days: int = 30) -> list[dict]:
    query = f"{company} {context}"
    start_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        results = await asyncio.to_thread(
            _get_client().search_and_contents,
            query,
            num_results=10,
            start_published_date=start_date,
            use_autoprompt=True,
            text=True,
        )
        signals = []
        for r in results.results:
            signal_type = "company_news"
            text_snippet = (r.text or "")[:500]
            lower_text = text_snippet.lower()
            if any(w in lower_text for w in ("hiring", "job", "role", "position", "recruit")):
                signal_type = "hiring"
            elif any(w in lower_text for w in ("pain", "challenge", "struggle", "problem")):
                signal_type = "pain_point"

            signals.append({
                "title": r.title or "Untitled",
                "url": r.url,
                "published_date": r.published_date or "",
                "summary": text_snippet,
                "signal_type": signal_type,
                "confidence": "medium",
                "source": "exa",
            })
        return signals
    except Exception as e:
        return [{"error": True, "message": f"Exa search failed: {e}"}]


async def find_relevant_content(context: str, prospect_interests: str) -> list[dict]:
    query = f"{context} {prospect_interests} insights analysis"
    try:
        results = await asyncio.to_thread(
            _get_client().search_and_contents,
            query,
            num_results=5,
            use_autoprompt=True,
            text=True,
        )
        content = []
        for r in results.results:
            content.append({
                "title": r.title or "Untitled",
                "url": r.url,
                "summary": (r.text or "")[:500],
                "why_relevant": f"Matches prospect context: {context[:100]}",
                "source": "exa",
            })
        return content
    except Exception as e:
        return [{"error": True, "message": f"Exa content search failed: {e}"}]


async def find_hiring_signals(company: str) -> list[dict]:
    query = f"{company} hiring OR job posting OR open role"
    try:
        results = await asyncio.to_thread(
            _get_client().search_and_contents,
            query,
            num_results=5,
            use_autoprompt=True,
            text=True,
        )
        signals = []
        for r in results.results:
            text_snippet = (r.text or "")[:500].lower()
            if "ops" in text_snippet or "operations" in text_snippet or "logistics" in text_snippet:
                signal_type = "ops_pain"
            elif "engineer" in text_snippet or "developer" in text_snippet or "migration" in text_snippet:
                signal_type = "tech_migration"
            else:
                signal_type = "expansion"

            signals.append({
                "role_title": r.title or "Unknown Role",
                "url": r.url,
                "location": "",
                "signal_type": signal_type,
                "source": "exa",
            })
        return signals
    except Exception as e:
        return [{"error": True, "message": f"Exa hiring search failed: {e}"}]
