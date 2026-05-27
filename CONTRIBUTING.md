# Contributing to Orbit

Thanks for considering a contribution. Please read this entire document before submitting a PR.

## Local Development

```bash
git clone https://github.com/your-username/orbit.git
cd orbit
uv pip install -e ".[dev]"
```

## Running Tests

```bash
pytest tests/
```

## Code Style

- Format with [black](https://github.com/psf/black)
- Lint with [ruff](https://github.com/astral-sh/ruff)
- Type hints on all public functions

## PR Guidelines

- One logical change per PR
- Include tests for new logic (especially scoring and state transitions)
- Update README if adding new tools
- Describe *why* the change exists, not just *what* it does

## Principles to Preserve (Mandatory Reading)

These are non-negotiable. PRs that violate them will be closed with an explanation.

### 1. No automation of messages

Orbit surfaces opportunities. Humans act on them. No "auto-send," no "schedule message," no "draft and send." If a feature sends anything to a prospect on the user's behalf, it violates this principle.

### 2. No bulk outreach features

MAX_PROSPECTS exists for a reason. Orbit is designed for building 40 genuine relationships, not spraying 4,000 connection requests. Features that optimize for volume over depth are out of scope.

### 3. No fake personalization

Every recommendation must cite a specific signal. "Hi {name}, I noticed your company is growing" is not personalization — it's a mail merge. If the recommendation can't point to a specific post, comment, or news event, it shouldn't exist.

### 4. No creepy signals

Only publicly visible information. No profile view tracking, no invisible monitoring, no behavioral inference from private data. If the prospect would feel surveilled rather than engaged, the feature is rejected.

### Why these rules exist

Orbit exists because most sales tools optimize for volume and automation, which produces spam. The constraints above are what make Orbit different. Relaxing them would turn Orbit into another outreach tool, and there are already plenty of those.

If you have a feature idea that bumps up against these principles, open an issue first to discuss. There may be a way to achieve the goal without violating the philosophy.
