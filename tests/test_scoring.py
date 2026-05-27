from datetime import datetime, timezone, timedelta

from orbit.services.scoring import score_signal, compute_signal_density, compute_relationship_state


class TestScoreSignal:
    def test_high_relevance_recent_signal(self):
        result = score_signal(
            "supply chain operations automation platform scaling",
            "supply chain ops pain, looking to automate operations",
            datetime.now(timezone.utc),
        )
        assert result["relevance_score"] >= 5.0
        assert result["recency_score"] == 10.0
        assert result["composite_score"] > 5.0
        assert result["confidence"] in ("high", "medium", "low")
        assert result["suggested_action"] in ("engage", "share", "wait")
        assert result["why_now"]

    def test_old_signal_gets_low_recency(self):
        old_date = datetime.now(timezone.utc) - timedelta(days=60)
        result = score_signal("anything", "anything", old_date)
        assert result["recency_score"] == 1.0

    def test_unrelated_content_low_relevance(self):
        result = score_signal(
            "cat videos funny animals",
            "enterprise B2B SaaS procurement optimization",
            datetime.now(timezone.utc),
        )
        assert result["relevance_score"] <= 3.0

    def test_composite_formula(self):
        result = score_signal("test content", "test context", datetime.now(timezone.utc))
        expected = result["relevance_score"] * 0.6 + result["recency_score"] * 0.4
        assert abs(result["composite_score"] - expected) < 0.1

    def test_suggested_action_thresholds(self):
        result_high = score_signal(
            "supply chain automation operations platform",
            "supply chain automation operations platform",
            datetime.now(timezone.utc),
        )
        assert result_high["suggested_action"] in ("engage", "share")

        result_low = score_signal(
            "completely unrelated random words xyz",
            "enterprise B2B SaaS procurement",
            datetime.now(timezone.utc) - timedelta(days=45),
        )
        assert result_low["suggested_action"] == "wait"


class TestComputeSignalDensity:
    def test_active_prospect_high_density(self):
        density = compute_signal_density(
            recent_posts_count=5,
            recent_activity_count=10,
            exa_signals_count=3,
            last_public_activity_days=2,
        )
        assert density >= 7.0
        assert density <= 10.0

    def test_ghost_prospect_low_density(self):
        density = compute_signal_density(
            recent_posts_count=0,
            recent_activity_count=0,
            exa_signals_count=0,
            last_public_activity_days=90,
        )
        assert density < 3.0

    def test_moderate_activity(self):
        density = compute_signal_density(
            recent_posts_count=2,
            recent_activity_count=3,
            exa_signals_count=1,
            last_public_activity_days=10,
        )
        assert 3.0 <= density <= 8.0

    def test_density_capped_at_ten(self):
        density = compute_signal_density(
            recent_posts_count=100,
            recent_activity_count=100,
            exa_signals_count=100,
            last_public_activity_days=1,
        )
        assert density == 10.0


class TestComputeRelationshipState:
    def test_no_engagements_returns_cold(self):
        state = compute_relationship_state([], [], 999, [])
        assert state == "cold"

    def test_one_engagement_no_response_returns_warming(self):
        state = compute_relationship_state(
            engagements=[{"type": "commented"}],
            signals=[],
            days_since_last_touch=3,
            prospect_responses=[],
        )
        assert state == "warming"

    def test_deep_response_returns_warm(self):
        state = compute_relationship_state(
            engagements=[{"type": "commented"}, {"type": "shared_content"}],
            signals=[],
            days_since_last_touch=5,
            prospect_responses=[
                {"response_depth": "deep", "created_at": "2026-05-01T00:00:00"},
            ],
        )
        assert state == "warm"

    def test_ready_requires_all_conditions(self):
        state = compute_relationship_state(
            engagements=[{"type": "commented"}, {"type": "shared_content"}, {"type": "sent_message"}],
            signals=[{"composite_score": 8.0}],
            days_since_last_touch=2,
            prospect_responses=[
                {"response_depth": "moderate", "created_at": "2026-04-01T00:00:00"},
                {"response_depth": "deep", "created_at": "2026-05-15T00:00:00"},
            ],
        )
        assert state == "ready"

    def test_ready_blocked_without_spread_across_weeks(self):
        state = compute_relationship_state(
            engagements=[{"type": "commented"}, {"type": "shared_content"}],
            signals=[{"composite_score": 8.0}],
            days_since_last_touch=1,
            prospect_responses=[
                {"response_depth": "deep", "created_at": "2026-05-15T00:00:00"},
                {"response_depth": "moderate", "created_at": "2026-05-15T00:00:00"},
            ],
        )
        assert state != "ready"

    def test_shallow_response_not_bidirectional(self):
        state = compute_relationship_state(
            engagements=[{"type": "commented"}],
            signals=[],
            days_since_last_touch=5,
            prospect_responses=[
                {"response_depth": "shallow", "created_at": "2026-05-01T00:00:00"},
            ],
        )
        assert state == "warming"
