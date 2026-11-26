"""Unit tests for profile share-card cache key generation and cache hits."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from finbot.apps.ctf.routes import share


def _base_template_context() -> dict:
    return {
        "username": "alice",
        "avatar_emoji": "🦊",
        "avatar_image_b64": "",
        "bio": "AI Security Enthusiast",
        "level": 3,
        "level_title": "Bug Hunter",
        "total_points": 500,
        "badges_earned": 2,
        "challenges_completed": 3,
        "xp_current": 500,
        "xp_next_threshold": 1000,
        "xp_next_title": "Red Teamer",
        "xp_pct": 0,
        "featured_badges": [
            {"title": "First Blood", "rarity": "rare", "is_secret": False},
        ],
        "latest_badge_title": "Prompt Ninja",
        "member_since": "May 2026",
        "rarity_colors": share.RARITY_COLORS_HEX,
        "logo_b64": "logo",
        "owasp_logo_b64": "owasp",
        "qr_data_uri": "",
    }


def test_cache_key_is_sha256_and_deterministic():
    """Cache key is a deterministic 64-char SHA-256 hex digest."""
    ctx = _base_template_context()
    key1 = share._build_profile_card_cache_key(
        ctx,
        avatar_type="url",
        avatar_url="https://example.com/a.png",
        profile_link="https://finbot.test/ctf/h/alice",
    )
    key2 = share._build_profile_card_cache_key(
        ctx,
        avatar_type="url",
        avatar_url="https://example.com/a.png",
        profile_link="https://finbot.test/ctf/h/alice",
    )
    assert key1 == key2
    assert len(key1) == 64
    assert all(c in "0123456789abcdef" for c in key1)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("username", "bob"),
        ("avatar_emoji", "🐱"),
        ("bio", "Updated bio"),
        ("total_points", 750),
        ("badges_earned", 3),
        ("challenges_completed", 4),
        (
            "featured_badges",
            [{"title": "Another Badge", "rarity": "epic", "is_secret": True}],
        ),
        ("latest_badge_title", "Different Latest"),
        ("member_since", "Jun 2026"),
    ],
)
def test_cache_key_changes_when_template_field_changes(field, value):
    """Any change in rendered template fields produces a different cache key."""
    base = _base_template_context()
    updated = {**base, field: value}

    key_before = share._build_profile_card_cache_key(
        base, avatar_type="emoji", avatar_url=None, profile_link="https://finbot.test/ctf/h/alice"
    )
    key_after = share._build_profile_card_cache_key(
        updated, avatar_type="emoji", avatar_url=None, profile_link="https://finbot.test/ctf/h/alice"
    )
    assert key_before != key_after


def test_cache_key_changes_when_featured_badges_reordered():
    """Reordering featured badges changes the rendered card and invalidates the cache key."""
    badge_a = {"title": "Alpha", "rarity": "common", "is_secret": False}
    badge_b = {"title": "Beta", "rarity": "epic", "is_secret": False}
    ctx1 = {**_base_template_context(), "featured_badges": [badge_a, badge_b]}
    ctx2 = {**_base_template_context(), "featured_badges": [badge_b, badge_a]}

    assert share._build_profile_card_cache_key(ctx1) != share._build_profile_card_cache_key(ctx2)


def test_cache_key_changes_on_avatar_type_or_url_change():
    """Switching avatar_type or avatar_url (including gravatar URL) invalidates the cache key."""
    ctx = _base_template_context()
    k_url1 = share._build_profile_card_cache_key(
        ctx, avatar_type="url", avatar_url="https://example.com/1.png"
    )
    k_url2 = share._build_profile_card_cache_key(
        ctx, avatar_type="url", avatar_url="https://example.com/2.png"
    )
    k_gravatar = share._build_profile_card_cache_key(
        ctx, avatar_type="gravatar", avatar_url="https://www.gravatar.com/avatar/abc?s=256&d=retro"
    )
    k_emoji = share._build_profile_card_cache_key(
        ctx, avatar_type="emoji", avatar_url=None
    )

    assert len({k_url1, k_url2, k_gravatar, k_emoji}) == 4


@pytest.mark.asyncio
async def test_get_profile_card_cache_hit_and_featured_badge_invalidation(
    monkeypatch, tmp_path
):
    """Cache hits skip avatar fetch and render; changing featured badges produces a new cache file."""
    monkeypatch.setattr(share, "CACHE_DIR", tmp_path)

    featured = ["b1"]
    profile = SimpleNamespace(
        user_id="u1",
        username="alice",
        avatar_emoji="🦊",
        avatar_type="url",
        avatar_url="https://example.com/a.png",
        bio="Hello",
        created_at=datetime(2026, 5, 1, tzinfo=UTC),
        get_featured_badge_ids=lambda: list(featured),
    )
    user = SimpleNamespace(namespace="default", email="alice@example.com")

    profile_repo = MagicMock()
    profile_repo.get_public_profile_with_user.return_value = (profile, user)
    monkeypatch.setattr(share, "UserProfileRepository", lambda db: profile_repo)

    badges = {
        "b1": SimpleNamespace(title="First", rarity="common", is_secret=False),
        "b2": SimpleNamespace(title="Second", rarity="rare", is_secret=False),
    }
    badge_repo = MagicMock()
    badge_repo.get_total_points.return_value = 100
    badge_repo.get_badge.side_effect = lambda bid: badges.get(bid)
    monkeypatch.setattr(share, "BadgeRepository", lambda db: badge_repo)

    challenge_repo = MagicMock()
    challenge_repo.get_effective_points.return_value = 0
    monkeypatch.setattr(share, "ChallengeRepository", lambda db: challenge_repo)

    earned = [
        SimpleNamespace(badge_id="b1", earned_at=datetime(2026, 5, 2, tzinfo=UTC)),
        SimpleNamespace(badge_id="b2", earned_at=datetime(2026, 5, 3, tzinfo=UTC)),
    ]
    db = MagicMock()
    db.query.return_value.filter.return_value.all.side_effect = [[], earned, [], earned, [], earned]

    fetch_mock = AsyncMock(return_value="data:image/png;base64,abc")
    render_mock = AsyncMock(side_effect=[b"png-v1", b"png-v2"])
    monkeypatch.setattr(share, "_fetch_avatar_b64", fetch_mock)
    monkeypatch.setattr(share, "_render_card", render_mock)

    request = SimpleNamespace(base_url="https://finbot.test/")

    # 1. Cold cache renders and writes PNG
    resp1 = await share.get_profile_card(request=request, username="alice", db=db, html=False)
    assert resp1.body == b"png-v1"
    assert fetch_mock.call_count == 1
    assert render_mock.call_count == 1

    # 2. Warm cache serves cached PNG without fetching avatar or rendering again
    resp2 = await share.get_profile_card(request=request, username="alice", db=db, html=False)
    assert resp2.body == b"png-v1"
    assert fetch_mock.call_count == 1
    assert render_mock.call_count == 1

    # 3. Changing featured badges invalidates cache and renders new PNG
    featured[:] = ["b2"]
    resp3 = await share.get_profile_card(request=request, username="alice", db=db, html=False)
    assert resp3.body == b"png-v2"
    assert fetch_mock.call_count == 2
    assert render_mock.call_count == 2
