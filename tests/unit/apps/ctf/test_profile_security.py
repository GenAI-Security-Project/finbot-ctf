"""Unit tests for CTF profile security and validation checks"""

import ipaddress
import socket

import pytest
from fastapi import HTTPException
from unittest.mock import AsyncMock, MagicMock

from finbot.apps.ctf.routes import share
from finbot.apps.ctf.routes.profile import (
    ProfileUpdateRequest,
    get_safe_ssrf_ip,
    update_profile,
)
from finbot.core.auth.session import SessionContext


@pytest.fixture
def mock_session_context():
    """Mock session context for an authenticated user"""
    context = MagicMock(spec=SessionContext)
    context.user_id = "test_user_id"
    return context


@pytest.fixture
def mock_db():
    """Mock database session"""
    return MagicMock()


@pytest.fixture
def mock_profile_repo():
    """Mock profile repository"""
    return MagicMock()


FAKE_DNS = {
    "example.com": ["93.184.215.14"],
    "avatars.example.com": ["93.184.215.14", "2606:2800:21f:cb07:6820:80da:af6b:8b2c"],
    "rebind.example.com": ["93.184.215.14", "10.0.0.5"],
    "cgnat.example.com": ["100.64.1.1"],
}


@pytest.fixture(autouse=True)
def fake_dns(monkeypatch):
    """Keep tests off the network: resolve hostnames from FAKE_DNS"""

    def getaddrinfo(host, port, *args, **kwargs):
        try:
            ips = [str(ipaddress.ip_address(host))]
        except ValueError:
            if host not in FAKE_DNS:
                raise socket.gaierror(f"unknown host {host}")
            ips = FAKE_DNS[host]
        return [(None, None, None, "", (ip, port)) for ip in ips]

    monkeypatch.setattr(
        "finbot.apps.ctf.routes.profile.socket.getaddrinfo", getaddrinfo
    )


@pytest.fixture
def patch_dependencies(monkeypatch, mock_profile_repo):
    """Patch the UserProfileRepository, validate_username, and _update_social_links"""
    monkeypatch.setattr(
        "finbot.apps.ctf.routes.profile.UserProfileRepository",
        lambda db, context: mock_profile_repo,
    )
    monkeypatch.setattr(
        "finbot.apps.ctf.routes.profile.validate_username",
        lambda username: (True, None),
    )
    monkeypatch.setattr(
        "finbot.apps.ctf.routes.profile._update_social_links",
        lambda profile, request, db: None,
    )
    monkeypatch.setattr(
        "finbot.apps.ctf.routes.profile._build_profile_response",
        lambda profile, user: MagicMock(),
    )


@pytest.mark.asyncio
async def test_update_profile_avatar_url_valid_https(
    mock_session_context, mock_db, mock_profile_repo, patch_dependencies
):
    """Test that a valid HTTPS URL is accepted during profile update"""
    # Arrange
    existing_profile = MagicMock()
    existing_profile.avatar_type = "url"
    existing_profile.avatar_url = "https://example.com/old.png"
    existing_profile.user_id = "test_user_id"
    mock_profile_repo.get_by_user_id.return_value = existing_profile

    updated_profile = MagicMock()
    mock_profile_repo.update_profile.return_value = updated_profile

    request = ProfileUpdateRequest(
        avatar_type="url",
        avatar_url="https://example.com/new.png"
    )

    # Act
    response = await update_profile(
        request=request,
        session_context=mock_session_context,
        db=mock_db
    )

    # Assert
    assert response is not None
    mock_profile_repo.update_profile.assert_called_once()


@pytest.mark.asyncio
async def test_update_profile_avatar_url_insecure_blocked(
    mock_session_context, mock_db, mock_profile_repo, patch_dependencies
):
    """Test that an insecure HTTP URL is blocked when avatar_type is explicitly 'url'"""
    # Arrange
    existing_profile = MagicMock()
    existing_profile.avatar_type = "url"
    existing_profile.avatar_url = "https://example.com/old.png"
    existing_profile.user_id = "test_user_id"
    mock_profile_repo.get_by_user_id.return_value = existing_profile

    request = ProfileUpdateRequest(
        avatar_type="url",
        avatar_url="http://127.0.0.1/malicious.png"
    )

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await update_profile(
            request=request,
            session_context=mock_session_context,
            db=mock_db
        )
    
    assert exc_info.value.status_code == 400
    assert "Invalid Avatar URL: Only public HTTPS URLs are allowed" in exc_info.value.detail
    mock_profile_repo.update_profile.assert_not_called()


@pytest.mark.asyncio
async def test_update_profile_avatar_url_bypass_attempt_blocked(
    mock_session_context, mock_db, mock_profile_repo, patch_dependencies
):
    """Test that omitting avatar_type still blocks insecure URLs if the database type is 'url'"""
    # Arrange
    existing_profile = MagicMock()
    existing_profile.avatar_type = "url"
    existing_profile.avatar_url = "https://example.com/old.png"
    existing_profile.user_id = "test_user_id"
    mock_profile_repo.get_by_user_id.return_value = existing_profile

    # request omits 'avatar_type', but tries to inject insecure 'avatar_url'
    request = ProfileUpdateRequest(
        avatar_url="http://169.254.169.254/latest/meta-data"
    )

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await update_profile(
            request=request,
            session_context=mock_session_context,
            db=mock_db
        )
    
    assert exc_info.value.status_code == 400
    assert "Invalid Avatar URL: Only public HTTPS URLs are allowed" in exc_info.value.detail
    mock_profile_repo.update_profile.assert_not_called()


@pytest.mark.asyncio
async def test_update_profile_avatar_url_emoji_retains_insecure_url_ignored(
    mock_session_context, mock_db, mock_profile_repo, patch_dependencies
):
    """Test that changing avatar_type to emoji clears/ignores insecure URL checks"""
    # Arrange
    existing_profile = MagicMock()
    existing_profile.avatar_type = "url"
    existing_profile.avatar_url = "https://example.com/old.png"
    existing_profile.user_id = "test_user_id"
    mock_profile_repo.get_by_user_id.return_value = existing_profile

    updated_profile = MagicMock()
    mock_profile_repo.update_profile.return_value = updated_profile

    # User changes type to emoji, URL should no longer trigger validation error even if old url was insecure
    request = ProfileUpdateRequest(
        avatar_type="emoji",
        avatar_emoji="🦊"
    )

    # Act
    response = await update_profile(
        request=request,
        session_context=mock_session_context,
        db=mock_db
    )

    # Assert
    assert response is not None
    mock_profile_repo.update_profile.assert_called_once_with(
        user_id="test_user_id",
        bio=None,
        avatar_emoji="🦊",
        avatar_type="emoji",
        avatar_url=None,
        is_public=None,
        show_activity=None
    )


@pytest.mark.asyncio
async def test_update_profile_avatar_url_ssrf_blocked(
    mock_session_context, mock_db, mock_profile_repo, patch_dependencies
):
    """Test that a private IP is blocked even if it uses HTTPS"""
    # Arrange
    existing_profile = MagicMock()
    existing_profile.avatar_type = "url"
    existing_profile.avatar_url = "https://example.com/old.png"
    existing_profile.user_id = "test_user_id"
    mock_profile_repo.get_by_user_id.return_value = existing_profile

    request = ProfileUpdateRequest(
        avatar_type="url",
        avatar_url="https://127.0.0.1/malicious.png"
    )

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await update_profile(
            request=request,
            session_context=mock_session_context,
            db=mock_db
        )
    
    assert exc_info.value.status_code == 400
    assert "Invalid Avatar URL: Only public HTTPS URLs are allowed" in exc_info.value.detail
    mock_profile_repo.update_profile.assert_not_called()


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/a.png",                  # not https
        "https://127.0.0.1/a.png",                   # loopback
        "https://169.254.169.254/latest/meta-data",  # cloud metadata
        "https://100.64.0.1/a.png",                  # CGNAT
        "https://cgnat.example.com/a.png",           # resolves to CGNAT
        "https://0.0.0.0/a.png",                     # "this" network
        "https://[::1]/a.png",                       # IPv6 loopback
        "https://[::ffff:127.0.0.1]/a.png",          # IPv4-mapped loopback
        "https://[fd00::1]/a.png",                   # IPv6 ULA
        "https://rebind.example.com/a.png",          # one public, one private answer
        "https://user:pass@example.com/a.png",       # embedded credentials
        "https://example.com:99999/a.png",           # out-of-range port
        "https://example.com:abc/a.png",             # non-numeric port
        "https://unknown.invalid/a.png",             # does not resolve
        "https:///a.png",                            # no host
    ],
)
def test_get_safe_ssrf_ip_blocks_unsafe_urls(url):
    """Every non-public or malformed avatar URL fails closed"""
    assert get_safe_ssrf_ip(url) is None


def test_get_safe_ssrf_ip_allows_public_https():
    """A hostname with only public IPv4/IPv6 answers is allowed"""
    assert get_safe_ssrf_ip("https://avatars.example.com/me.png") == "93.184.215.14"


@pytest.mark.asyncio
async def test_update_profile_avatar_url_bad_port_is_400(
    mock_session_context, mock_db, mock_profile_repo, patch_dependencies
):
    """A malformed port is a client error, not a 500"""
    existing_profile = MagicMock()
    existing_profile.avatar_type = "url"
    mock_profile_repo.get_by_user_id.return_value = existing_profile

    request = ProfileUpdateRequest(avatar_url="https://example.com:99999/a.png")

    with pytest.raises(HTTPException) as exc_info:
        await update_profile(
            request=request, session_context=mock_session_context, db=mock_db
        )

    assert exc_info.value.status_code == 400
    mock_profile_repo.update_profile.assert_not_called()


def _avatar_response(chunks, status_code=200, headers=None):
    """Fake streamed response that yields the given body chunks"""
    response = MagicMock(status_code=status_code)
    response.headers = {"content-type": "image/png", **(headers or {})}
    response.chunks_read = 0

    async def aiter_bytes():
        for chunk in chunks:
            response.chunks_read += 1
            yield chunk

    response.aiter_bytes = aiter_bytes
    return response


def _mock_async_client(monkeypatch, response):
    """Replace httpx.AsyncClient in share.py and return the mocks for inspection"""
    client = MagicMock()
    stream_ctx = MagicMock()
    stream_ctx.__aenter__ = AsyncMock(return_value=response)
    stream_ctx.__aexit__ = AsyncMock(return_value=False)
    client.stream = MagicMock(return_value=stream_ctx)
    client_cls = MagicMock()
    client_cls.return_value.__aenter__ = AsyncMock(return_value=client)
    client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(share.httpx, "AsyncClient", client_cls)
    return client_cls, client


@pytest.mark.asyncio
async def test_fetch_avatar_pins_ip_and_keeps_tls_verification(monkeypatch):
    """The fetch connects to the validated IP, with redirects off and TLS still verified"""
    client_cls, client = _mock_async_client(monkeypatch, _avatar_response([b"p", b"ng"]))

    result = await share._fetch_avatar_b64("https://example.com/me.png?s=64")

    assert result == "data:image/png;base64,cG5n"
    client_kwargs = client_cls.call_args.kwargs
    assert client_kwargs["follow_redirects"] is False
    assert client_kwargs.get("verify", True) is True

    (method, url), get_kwargs = client.stream.call_args
    assert method == "GET"
    assert str(url) == "https://93.184.215.14/me.png?s=64"
    assert get_kwargs["headers"] == {"Host": "example.com"}
    assert get_kwargs["extensions"] == {"sni_hostname": "example.com"}


@pytest.mark.asyncio
async def test_fetch_avatar_skips_unsafe_url(monkeypatch):
    """No request is made at all when the avatar URL resolves to a private address"""
    client_cls, _ = _mock_async_client(monkeypatch, MagicMock())

    assert await share._fetch_avatar_b64("https://rebind.example.com/me.png") == ""
    client_cls.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_avatar_stops_reading_oversized_body(monkeypatch):
    """A body over the size limit is dropped while streaming, not after a full download"""
    chunk = b"x" * (1024 * 1024)
    response = _avatar_response([chunk] * 10)
    _mock_async_client(monkeypatch, response)

    assert await share._fetch_avatar_b64("https://example.com/me.png") == ""
    assert response.chunks_read == 3


@pytest.mark.asyncio
async def test_fetch_avatar_rejects_large_content_length(monkeypatch):
    """A declared Content-Length over the limit is rejected before reading the body"""
    response = _avatar_response(
        [b"png"], headers={"content-length": str(share.MAX_AVATAR_BYTES + 1)}
    )
    _mock_async_client(monkeypatch, response)

    assert await share._fetch_avatar_b64("https://example.com/me.png") == ""
    assert response.chunks_read == 0
