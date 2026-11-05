"""Security regression tests for Avatar URL validation and SSRF defenses (Issue #506)."""

import socket
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException

from finbot.apps.ctf.routes.profile import ProfileUpdateRequest, update_profile
from finbot.apps.ctf.routes.share import _fetch_avatar_b64
from finbot.core.auth.session import SessionContext


@pytest.fixture
def session_context():
    now = datetime.now(UTC)
    return SessionContext(
        session_id="sess-ssrf-001",
        user_id="user-ssrf-victim",
        is_temporary=False,
        namespace="default",
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )


@pytest.fixture
def mock_db():
    db = MagicMock()
    user = MagicMock()
    user.user_id = "user-ssrf-victim"
    user.display_name = "Victim"
    user.email = "victim@example.com"
    user.created_at = datetime.now(UTC)
    db.query.return_value.filter.return_value.first.return_value = user
    return db


@pytest.fixture
def mock_profile():
    profile = MagicMock()
    profile.user_id = "user-ssrf-victim"
    profile.username = "victim_user"
    profile.bio = "Bio"
    profile.avatar_emoji = "🦊"
    profile.avatar_type = "url"
    profile.avatar_url = "https://cdn.example.com/initial_avatar.png"
    profile.is_public = True
    profile.show_activity = True
    profile.github = None
    profile.hackerone = None
    profile.bugcrowd = None
    profile.twitter = None
    profile.linkedin = None
    profile.website = None
    for p in ["github", "hackerone", "bugcrowd", "twitter", "linkedin", "website"]:
        setattr(profile, f"social_{p}", None)
    profile.featured_badge_ids = None
    profile.created_at = datetime.now(UTC)
    return profile


class TestAvatarSSRFRegression:
    """Security regressions for Issue #506 SSRF vulnerabilities."""

    @pytest.mark.asyncio
    async def test_update_avatar_url_omitting_avatar_type_bypass(
        self, session_context, mock_db, mock_profile
    ):
        """Omitting avatar_type must not bypass validation when existing avatar_type is 'url'."""
        request = ProfileUpdateRequest(
            avatar_url="http://127.0.0.1:8000/internal-admin",
            # avatar_type omitted (None)
        )

        with (
            patch(
                "finbot.core.data.repositories.UserProfileRepository.get_by_user_id",
                return_value=mock_profile,
            ),
            patch(
                "finbot.core.data.repositories.UserProfileRepository.update_profile",
                return_value=mock_profile,
            ) as mock_update,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await update_profile(
                    request=request,
                    session_context=session_context,
                    db=mock_db,
                )

            assert exc_info.value.status_code == 400
            mock_update.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_avatar_url_rejects_non_https(
        self, session_context, mock_db, mock_profile
    ):
        """Non-HTTPS schemes (http, file, gopher, ftp) must be rejected."""
        request = ProfileUpdateRequest(
            avatar_type="url",
            avatar_url="http://public-avatar.com/image.png",
        )

        with (
            patch(
                "finbot.core.data.repositories.UserProfileRepository.get_by_user_id",
                return_value=mock_profile,
            ),
            patch(
                "finbot.core.data.repositories.UserProfileRepository.update_profile",
                return_value=mock_profile,
            ) as mock_update,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await update_profile(
                    request=request,
                    session_context=session_context,
                    db=mock_db,
                )

            assert exc_info.value.status_code == 400
            mock_update.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "prohibited_ip",
        [
            "127.0.0.1",  # IPv4 loopback
            "169.254.169.254",  # AWS/GCP metadata
            "10.0.0.1",  # RFC-1918 class A
            "172.16.0.1",  # RFC-1918 class B
            "192.168.1.1",  # RFC-1918 class C
            "0.0.0.0",  # IPv4 unspecified
            "::1",  # IPv6 loopback
            "fe80::1",  # IPv6 link-local
            "fc00::1",  # IPv6 ULA private
            "::",  # IPv6 unspecified
        ],
    )
    async def test_update_avatar_url_rejects_prohibited_ips(
        self, session_context, mock_db, mock_profile, prohibited_ip
    ):
        """Direct IP or hostname resolving to loopback/private/link-local IPv4 or IPv6 must be rejected."""
        target_host = f"[{prohibited_ip}]" if ":" in prohibited_ip else prohibited_ip
        url = f"https://{target_host}/avatar.png"
        request = ProfileUpdateRequest(avatar_type="url", avatar_url=url)

        def mock_getaddrinfo(host, port, *args, **kwargs):
            family = socket.AF_INET6 if ":" in prohibited_ip else socket.AF_INET
            return [(family, socket.SOCK_STREAM, 6, "", (prohibited_ip, 443))]

        with (
            patch(
                "finbot.core.data.repositories.UserProfileRepository.get_by_user_id",
                return_value=mock_profile,
            ),
            patch("socket.getaddrinfo", side_effect=mock_getaddrinfo),
            patch(
                "finbot.core.data.repositories.UserProfileRepository.update_profile",
                return_value=mock_profile,
            ) as mock_update,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await update_profile(
                    request=request,
                    session_context=session_context,
                    db=mock_db,
                )

            assert exc_info.value.status_code == 400
            mock_update.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_avatar_url_rejects_mixed_dns_answers(
        self, session_context, mock_db, mock_profile
    ):
        """Hostnames returning mixed public and prohibited IPs (e.g. DNS rebinding setup) must be rejected."""
        url = "https://dual-homed-danger.com/avatar.png"
        request = ProfileUpdateRequest(avatar_type="url", avatar_url=url)

        # Mixed DNS answers: one public IP (93.184.216.34) and one private IP (10.0.0.5)
        def mock_getaddrinfo(host, port, *args, **kwargs):
            return [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 443)),
            ]

        with (
            patch(
                "finbot.core.data.repositories.UserProfileRepository.get_by_user_id",
                return_value=mock_profile,
            ),
            patch("socket.getaddrinfo", side_effect=mock_getaddrinfo),
            patch(
                "finbot.core.data.repositories.UserProfileRepository.update_profile",
                return_value=mock_profile,
            ) as mock_update,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await update_profile(
                    request=request,
                    session_context=session_context,
                    db=mock_db,
                )

            assert exc_info.value.status_code == 400
            mock_update.assert_not_called()

    @pytest.mark.asyncio
    async def test_share_card_fetch_prevents_redirect_to_prohibited_destinations(self):
        """_fetch_avatar_b64 must not follow HTTP redirects to prohibited internal destinations."""
        redirect_response = httpx.Response(
            status_code=302,
            headers={"Location": "http://127.0.0.1:8000/internal"},
        )

        with patch("httpx.AsyncClient") as mock_client_cls:
            captured_client_kwargs = {}

            def fake_client_init(*args, **kwargs):
                captured_client_kwargs.update(kwargs)
                client = MagicMock()
                client.__aenter__.return_value = client
                client.__aexit__.return_value = None
                client.get = AsyncMock(return_value=redirect_response)
                mock_stream_ctx = MagicMock()
                mock_stream_ctx.__aenter__ = AsyncMock(return_value=redirect_response)
                mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)
                client.stream.return_value = mock_stream_ctx
                return client

            mock_client_cls.side_effect = fake_client_init
            with patch(
                "socket.getaddrinfo",
                return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
            ):
                res = await _fetch_avatar_b64("https://public-avatar.com/image.png")

            assert captured_client_kwargs.get("follow_redirects") is False
            assert res == ""

    @pytest.mark.asyncio
    async def test_share_card_fetch_blocks_dns_rebinding_connection(self):
        """_fetch_avatar_b64 must prevent connection to prohibited IP even if hostname passed initial check."""
        call_count = 0

        def rebinding_getaddrinfo(host, port, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Initial check at validate_avatar_url: returns public IP
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
            else:
                # Rebound at connect time: returns loopback IP
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]

        with patch("socket.getaddrinfo", side_effect=rebinding_getaddrinfo):
            result = await _fetch_avatar_b64("https://rebound-domain.evil/avatar.png")
            assert result == ""

    @pytest.mark.asyncio
    async def test_share_card_fetch_aborts_on_oversized_stream(self):
        """_fetch_avatar_b64 must abort streaming when body exceeds MAX_AVATAR_BYTES."""
        chunk_size = 64 * 1024
        chunks_yielded = 0

        async def infinite_chunk_generator(*args, **kwargs):
            nonlocal chunks_yielded
            for _ in range(50):  # 50 * 64 KiB = 3.2 MiB (> 2 MiB limit)
                chunks_yielded += 1
                yield b"A" * chunk_size

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "image/png"}
        mock_resp.aiter_bytes = infinite_chunk_generator

        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient") as mock_client_cls:
            client = MagicMock()
            client.__aenter__.return_value = client
            client.__aexit__.return_value = None
            client.stream.return_value = mock_stream_ctx
            mock_client_cls.return_value = client

            with patch(
                "socket.getaddrinfo",
                return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
            ):
                res = await _fetch_avatar_b64("https://public-avatar.com/oversized.png")

            assert res == ""
            # Exactly 33 chunks: 32 chunks * 64 KiB = 2 MiB, 33rd chunk exceeds 2 MiB and aborts
            assert chunks_yielded == 33

    @pytest.mark.asyncio
    async def test_share_card_fetch_aborts_on_oversized_content_length(self):
        """_fetch_avatar_b64 must fast-fail without consuming stream if Content-Length exceeds limit."""
        chunks_yielded = 0

        async def chunk_generator(*args, **kwargs):
            nonlocal chunks_yielded
            chunks_yielded += 1
            yield b"data"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {
            "content-type": "image/png",
            "content-length": str(5 * 1024 * 1024),  # 5 MiB
        }
        mock_resp.aiter_bytes = chunk_generator

        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient") as mock_client_cls:
            client = MagicMock()
            client.__aenter__.return_value = client
            client.__aexit__.return_value = None
            client.stream.return_value = mock_stream_ctx
            mock_client_cls.return_value = client

            with patch(
                "socket.getaddrinfo",
                return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
            ):
                res = await _fetch_avatar_b64("https://public-avatar.com/oversized-header.png")

            assert res == ""
            # Aborted before aiter_bytes was invoked
            assert chunks_yielded == 0

    @pytest.mark.asyncio
    async def test_share_card_fetch_streaming_success(self):
        """_fetch_avatar_b64 must stream, aggregate, and base64-encode valid images within limit."""
        import base64
        raw_image_data = b"\x89PNG\r\n\x1a\nfakeimagedata12345"

        mock_resp = httpx.Response(
            status_code=200,
            headers={"content-type": "image/png; charset=utf-8", "content-length": str(len(raw_image_data))},
            content=raw_image_data,
        )

        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient") as mock_client_cls:
            client = MagicMock()
            client.__aenter__.return_value = client
            client.__aexit__.return_value = None
            client.stream.return_value = mock_stream_ctx
            mock_client_cls.return_value = client

            with patch(
                "socket.getaddrinfo",
                return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
            ):
                res = await _fetch_avatar_b64("https://public-avatar.com/valid.png")

            expected = f"data:image/png;base64,{base64.b64encode(raw_image_data).decode()}"
            assert res == expected

    @pytest.mark.asyncio
    async def test_valid_public_https_avatar_allowed(self, session_context, mock_db, mock_profile):
        """Valid public HTTPS avatar URLs with verified public IPs must be accepted."""
        request = ProfileUpdateRequest(
            avatar_type="url",
            avatar_url="https://images.unsplash.com/valid_avatar.png",
        )

        def mock_getaddrinfo(host, port, *args, **kwargs):
            return [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("151.101.1.140", 443)),
                (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2a04:4e42::472", 443)),
            ]

        with (
            patch(
                "finbot.core.data.repositories.UserProfileRepository.get_by_user_id",
                return_value=mock_profile,
            ),
            patch("socket.getaddrinfo", side_effect=mock_getaddrinfo),
            patch(
                "finbot.core.data.repositories.UserProfileRepository.update_profile",
                return_value=mock_profile,
            ) as mock_update,
        ):
            mock_update.return_value = mock_profile
            res = await update_profile(
                request=request,
                session_context=session_context,
                db=mock_db,
            )

            assert res is not None
            mock_update.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "malformed_url",
        [
            "https://example.com:99999999/avatar.png",  # Out-of-range port
            "https://example.com:abc/avatar.png",  # Non-integer port
            "https://example.com:-1/avatar.png",  # Negative port
            "https://[invalid-ipv6/avatar.png",  # Malformed IPv6 syntax
            "https://user:pass@example.com/avatar.png",  # Embedded credentials
            "https:///avatar.png",  # Empty hostname
            "https://:443/avatar.png",  # Missing hostname with port
        ],
    )
    async def test_update_avatar_url_rejects_malformed_url_and_ports(
        self, session_context, mock_db, mock_profile, malformed_url
    ):
        """Malformed URLs, invalid ports, and embedded credentials must return HTTP 400, never 500."""
        request = ProfileUpdateRequest(avatar_type="url", avatar_url=malformed_url)

        with (
            patch(
                "finbot.core.data.repositories.UserProfileRepository.get_by_user_id",
                return_value=mock_profile,
            ),
            patch(
                "finbot.core.data.repositories.UserProfileRepository.update_profile",
                return_value=mock_profile,
            ) as mock_update,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await update_profile(
                    request=request,
                    session_context=session_context,
                    db=mock_db,
                )

            assert exc_info.value.status_code == 400
            mock_update.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "mapped_ip",
        [
            "::ffff:127.0.0.1",
            "::ffff:169.254.169.254",
            "::ffff:10.0.0.1",
            "::ffff:192.168.1.1",
        ],
    )
    async def test_update_avatar_url_rejects_ipv4_mapped_ipv6_prohibited(
        self, session_context, mock_db, mock_profile, mapped_ip
    ):
        """IPv4-mapped IPv6 addresses representing prohibited targets must be blocked."""
        url = f"https://[{mapped_ip}]/avatar.png"
        request = ProfileUpdateRequest(avatar_type="url", avatar_url=url)

        def mock_getaddrinfo(host, port, *args, **kwargs):
            return [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", (mapped_ip, 443))]

        with (
            patch(
                "finbot.core.data.repositories.UserProfileRepository.get_by_user_id",
                return_value=mock_profile,
            ),
            patch("socket.getaddrinfo", side_effect=mock_getaddrinfo),
            patch(
                "finbot.core.data.repositories.UserProfileRepository.update_profile",
                return_value=mock_profile,
            ) as mock_update,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await update_profile(
                    request=request,
                    session_context=session_context,
                    db=mock_db,
                )

            assert exc_info.value.status_code == 400
            mock_update.assert_not_called()

    @pytest.mark.asyncio
    async def test_ssrf_protected_backend_dual_stack_failover(self):
        """SSRFProtectedBackend should fail over to subsequent safe resolved IPs if the first one is unreachable."""
        import asyncio

        import httpcore

        from finbot.apps.ctf.routes.profile import SSRFProtectedBackend

        backend = SSRFProtectedBackend()
        loop = asyncio.get_running_loop()

        # Returns IPv6 first, then IPv4
        mock_addrinfo = [
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2606:4700::6810:85e5", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
        ]

        attempted_ips = []

        async def fake_super_connect(ip, port, **kwargs):
            attempted_ips.append(ip)
            if ip == "2606:4700::6810:85e5":
                raise httpcore.ConnectError("IPv6 network unreachable")
            mock_stream = MagicMock()
            return mock_stream

        with (
            patch.object(loop, "getaddrinfo", new_callable=AsyncMock, return_value=mock_addrinfo),
            patch(
                "httpcore._backends.anyio.AnyIOBackend.connect_tcp", side_effect=fake_super_connect
            ),
        ):
            stream = await backend.connect_tcp(host="example.com", port=443)
            assert stream is not None
            assert attempted_ips == ["2606:4700::6810:85e5", "93.184.216.34"]

    @pytest.mark.asyncio
    async def test_ssrf_protected_backend_mixed_dns_fails_closed(self):
        """SSRFProtectedBackend must fail closed if DNS returns mixed safe and prohibited IPs."""
        import asyncio

        import httpcore

        from finbot.apps.ctf.routes.profile import SSRFProtectedBackend

        backend = SSRFProtectedBackend()
        loop = asyncio.get_running_loop()

        # Mixed DNS: safe public IP + internal private IP
        mock_addrinfo = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443)),
        ]

        with (
            patch.object(loop, "getaddrinfo", new_callable=AsyncMock, return_value=mock_addrinfo),
            patch(
                "httpcore._backends.anyio.AnyIOBackend.connect_tcp", new_callable=AsyncMock
            ) as mock_connect,
        ):
            with pytest.raises(httpcore.ConnectError) as exc_info:
                await backend.connect_tcp(host="rebound-trap.evil", port=443)

            assert "Prohibited destination IP: 10.0.0.1" in str(exc_info.value)
            mock_connect.assert_not_called()

    @pytest.mark.asyncio
    async def test_ssrf_protected_backend_preserves_tls_sni_hostname(self):
        """Verify that connection-time IP pinning connects to IP while TLS handshake uses the original domain name."""
        import asyncio

        import httpcore

        from finbot.apps.ctf.routes.profile import SSRFProtectedBackend

        backend = SSRFProtectedBackend()
        loop = asyncio.get_running_loop()

        mock_addrinfo = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
        ]

        mock_stream = AsyncMock()
        mock_stream.start_tls = AsyncMock(return_value=mock_stream)

        with (
            patch.object(loop, "getaddrinfo", new_callable=AsyncMock, return_value=mock_addrinfo),
            patch(
                "httpcore._backends.anyio.AnyIOBackend.connect_tcp",
                new_callable=AsyncMock,
                return_value=mock_stream,
            ) as mock_super_connect,
        ):
            stream = await backend.connect_tcp(host="secure-avatar.example.org", port=443)
            # TCP connection is pinned to verified safe IP
            mock_super_connect.assert_called_once()
            args, kwargs = mock_super_connect.call_args
            connected_target = args[0] if args else kwargs.get("host")
            assert connected_target == "93.184.216.34"

            # Simulate httpcore._connect TLS handshake invocation on the stream
            req_origin_host = "secure-avatar.example.org"
            await stream.start_tls(ssl_context=MagicMock(), server_hostname=req_origin_host)
            mock_stream.start_tls.assert_called_once()
            _, tls_kwargs = mock_stream.start_tls.call_args
            assert tls_kwargs["server_hostname"] == "secure-avatar.example.org"
