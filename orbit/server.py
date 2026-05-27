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
        "Relationship timing intelligence for genuine pipeline building. "
        "Know when to show up and what to bring — you still write and send everything yourself."
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
