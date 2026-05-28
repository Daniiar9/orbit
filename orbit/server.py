import asyncio
import logging
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from orbit.config import LOG_LEVEL

logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))


@asynccontextmanager
async def lifespan(server):
    from orbit.database import init_db

    await init_db()
    yield


mcp = FastMCP(
    "Orbit",
    instructions=(
        "Relationship timing intelligence for founders, consultants, and senior operators. "
        "CRITICAL BEHAVIORAL RULES: When a prospect's relationship_state is cold or warming "
        "AND signal_density is below 5, you must NEVER draft outbound messages, suggest "
        "sending anything, or recommend outreach of any kind. Return the tool result and stop. "
        "Do not suggest follow-ups, do not draft messages, do not recommend timing for sends. "
        "The restraint is the product. Only surface action recommendations when the tools "
        "explicitly return a suggested_action of engage, share, or intro. If the tool returns "
        "wait or insufficient_signal, your response ends there."
    ),
    lifespan=lifespan,
)

import orbit.tools.prospects  # noqa: E402, F401
import orbit.tools.signals  # noqa: E402, F401
import orbit.tools.engagement  # noqa: E402, F401
import orbit.tools.overview  # noqa: E402, F401


def main():
    mcp.run()


if __name__ == "__main__":
    main()
