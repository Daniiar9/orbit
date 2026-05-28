import asyncio
import re
import sys
from pathlib import Path

from orbit.config import LINKEDIN_SESSION_PATH


def _normalize_linkedin_url(url: str) -> str:
    return re.sub(r"https://([\w-]+)\.linkedin\.com", "https://www.linkedin.com", url)


def _session_path() -> Path:
    return Path(LINKEDIN_SESSION_PATH)


async def login_and_save_session():
    from patchright.async_api import async_playwright

    session_path = _session_path()
    session_path.parent.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("https://www.linkedin.com/login")

        print("A browser window has opened. Please log in to LinkedIn manually.")
        print("After you are fully logged in and see your feed, come back here.")
        await asyncio.to_thread(input, "Press Enter after logging in...")

        await context.storage_state(path=str(session_path))
        print(f"Session saved to {session_path}")
        await browser.close()


def login():
    asyncio.run(login_and_save_session())


async def _get_context():
    from patchright.async_api import async_playwright

    session_path = _session_path()
    if not session_path.exists():
        return None, None, "Session not found. Run 'orbit-login' to authenticate."

    p = await async_playwright().__aenter__()
    browser = await p.chromium.launch(headless=True)
    context = await browser.new_context(storage_state=str(session_path))
    return p, context, None


async def _safe_close(p, context):
    if context:
        try:
            await context.browser.close()
        except Exception:
            pass
    if p:
        try:
            await p.__aexit__(None, None, None)
        except Exception:
            pass


async def get_person_profile(linkedin_url: str) -> dict:
    linkedin_url = _normalize_linkedin_url(linkedin_url)
    p, context, error = await _get_context()
    if error:
        return {"error": True, "message": error}

    try:
        page = await context.new_page()
        await page.goto(linkedin_url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)

        login_wall = await page.query_selector('input[id="session_key"]')
        if login_wall:
            return {"error": True, "message": "LinkedIn login wall detected. Run 'orbit-login' to re-authenticate."}

        name = await _safe_text(page, "h1")
        title = await _safe_text(page, "div.text-body-medium")
        company = ""
        about = ""

        experience_section = await page.query_selector("section#experience")
        if experience_section:
            company_el = await experience_section.query_selector("span.t-bold span")
            if company_el:
                company = (await company_el.inner_text()).strip()

        about_section = await page.query_selector("section#about")
        if about_section:
            about_el = await about_section.query_selector("div.display-flex span")
            if about_el:
                about = (await about_el.inner_text()).strip()

        return {
            "name": name,
            "title": title,
            "company": company,
            "about": about[:500] if about else "",
            "linkedin_url": linkedin_url,
            "error": False,
        }
    except Exception as e:
        return {"error": True, "message": f"Profile scrape failed: {e}"}
    finally:
        await _safe_close(p, context)


async def get_recent_posts(linkedin_url: str, limit: int = 5) -> list[dict]:
    linkedin_url = _normalize_linkedin_url(linkedin_url)
    p, context, error = await _get_context()
    if error:
        return []

    try:
        activity_url = linkedin_url.rstrip("/") + "/recent-activity/all/"
        page = await context.new_page()
        await page.goto(activity_url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        login_wall = await page.query_selector('input[id="session_key"]')
        if login_wall:
            return []

        posts = []
        post_elements = await page.query_selector_all("div.feed-shared-update-v2")
        for el in post_elements[:limit]:
            content_el = await el.query_selector("div.feed-shared-text span")
            content = (await content_el.inner_text()).strip() if content_el else ""
            posts.append({
                "content": content[:1000],
                "url": activity_url,
                "source": "linkedin",
            })
        return posts
    except Exception:
        return []
    finally:
        await _safe_close(p, context)


async def get_recent_activity(linkedin_url: str) -> list[dict]:
    linkedin_url = _normalize_linkedin_url(linkedin_url)
    p, context, error = await _get_context()
    if error:
        return []

    try:
        activity_url = linkedin_url.rstrip("/") + "/recent-activity/all/"
        page = await context.new_page()
        await page.goto(activity_url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        login_wall = await page.query_selector('input[id="session_key"]')
        if login_wall:
            return []

        activities = []
        items = await page.query_selector_all("div.feed-shared-update-v2")
        for el in items[:10]:
            text_el = await el.query_selector("div.feed-shared-text span")
            text = (await text_el.inner_text()).strip() if text_el else "Activity"
            activities.append({
                "type": "activity",
                "content": text[:500],
                "source": "linkedin",
            })
        return activities
    except Exception:
        return []
    finally:
        await _safe_close(p, context)


async def check_connection_status(linkedin_url: str) -> str:
    linkedin_url = _normalize_linkedin_url(linkedin_url)
    p, context, error = await _get_context()
    if error:
        return "unknown"

    try:
        page = await context.new_page()
        await page.goto(linkedin_url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)

        connect_btn = await page.query_selector('button:has-text("Connect")')
        if connect_btn:
            return "not_connected"

        pending_btn = await page.query_selector('button:has-text("Pending")')
        if pending_btn:
            return "pending"

        message_btn = await page.query_selector('button:has-text("Message")')
        if message_btn:
            return "connected"

        return "unknown"
    except Exception:
        return "unknown"
    finally:
        await _safe_close(p, context)


async def get_inbox_messages(linkedin_url: str, limit: int = 5) -> list[dict]:
    return [{"note": "Inbox message retrieval requires active session. Use orbit-login to authenticate."}]


async def _safe_text(page, selector: str) -> str:
    el = await page.query_selector(selector)
    if el:
        return (await el.inner_text()).strip()
    return ""
