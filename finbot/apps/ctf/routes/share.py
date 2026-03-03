"""Share Routes - OG image generation for social sharing"""

import hashlib
import logging
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from finbot.config import settings
from finbot.core.data.database import get_db
from finbot.core.data.models import UserBadge, UserChallengeProgress
from finbot.core.data.repositories import (
    BadgeRepository,
    ChallengeRepository,
    UserProfileRepository,
)

from .profile import calculate_level

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/share", tags=["share"])

# Cache directory for generated images
CACHE_DIR = (
    Path(settings.DATA_DIR if hasattr(settings, "DATA_DIR") else ".")
    / "cache"
    / "share_cards"
)
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def get_cache_path(cache_key: str) -> Path:
    """Get cache file path for a given key"""
    return CACHE_DIR / f"{cache_key}.png"


def _get_font(size: int, bold: bool = False):
    """Get a font, trying multiple paths for cross-platform support."""
    from PIL import ImageFont

    # Font paths to try (macOS, Linux, Windows)
    font_paths = [
        # macOS
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNSText.ttf",
        "/Library/Fonts/Arial.ttf",
        # Linux
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        # Windows
        "C:/Windows/Fonts/arial.ttf",
    ]

    for path in font_paths:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue

    # Fall back to default
    return ImageFont.load_default(size=size)


def generate_profile_card(
    username: str,
    avatar_emoji: str,
    bio: str,
    level: int,
    level_title: str,
    total_points: int,
    badges_earned: int,
    challenges_completed: int,
    completion_percentage: int,
) -> bytes:
    """Generate a profile share card using Pillow at 2x resolution for HD"""
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        logger.error("Pillow not installed. Run: pip install Pillow")
        raise HTTPException(
            status_code=500, detail="Image generation not available"
        ) from exc

    # Scale factor for HD rendering (2x = 2400x1260)
    scale = 2
    width, height = 1200 * scale, 630 * scale

    # Helper to scale values
    def s(val: int) -> int:
        return val * scale

    # Create image with dark background
    img = Image.new("RGB", (width, height), (10, 10, 15))
    draw = ImageDraw.Draw(img)

    # Draw gradient background
    for y in range(height):
        # Dark gradient from top to bottom
        r = 8 + int(y * 0.0075)
        g = 8 + int(y * 0.01)
        b = 12 + int(y * 0.0125)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # Add cyan accent glow at top-left
    for i in range(s(200)):
        alpha = int((1 - i / s(200)) * 25)
        draw.ellipse(
            [-s(100) - i, -s(100) - i, s(200) + i, s(200) + i],
            fill=(alpha, int(alpha * 0.8), int(alpha * 0.5)),
        )

    # Add purple accent glow at bottom-right
    for i in range(s(150)):
        alpha = int((1 - i / s(150)) * 15)
        draw.ellipse(
            [width - s(150) - i, height - s(100) - i, width + i, height + i],
            fill=(int(alpha * 0.5), alpha // 4, alpha),
        )

    # Draw decorative grid pattern (subtle)
    for x in range(0, width, s(50)):
        draw.line([(x, 0), (x, height)], fill=(20, 20, 25), width=scale)
    for y in range(0, height, s(50)):
        draw.line([(0, y), (width, y)], fill=(20, 20, 25), width=scale)

    # Load fonts (scaled)
    font_large = _get_font(s(44), bold=True)
    font_medium = _get_font(s(28))
    font_small = _get_font(s(20))
    font_xl = _get_font(s(56), bold=True)
    font_stat = _get_font(s(36), bold=True)

    # Try to load and paste FinBot logo
    logo_path = (
        Path(__file__).parent.parent.parent.parent
        / "static"
        / "images"
        / "common"
        / "finbot.png"
    )
    logo_size = s(70)
    try:
        logo = Image.open(logo_path).convert("RGBA")
        logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
        # Create a circular mask
        mask = Image.new("L", (logo_size, logo_size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse([0, 0, logo_size, logo_size], fill=255)
        # Draw cyan ring behind logo
        draw.ellipse([s(35), s(25), s(115), s(105)], fill=(0, 212, 255))
        draw.ellipse([s(40), s(30), s(110), s(100)], fill=(15, 15, 20))
        img.paste(logo, (s(40), s(30)), mask)
    except (OSError, IOError):
        # Draw fallback circle if logo not found
        draw.ellipse([s(40), s(30), s(110), s(100)], fill=(0, 212, 255))

    # Draw "FINBOT CTF" header
    draw.text((s(130), s(45)), "FINBOT", font=font_medium, fill=(255, 255, 255))
    draw.text((s(245), s(52)), "CTF", font=_get_font(s(16)), fill=(0, 212, 255))

    # Draw OWASP ASI text
    draw.text((s(130), s(80)), "OWASP ASI", font=_get_font(s(14)), fill=(100, 116, 139))

    # Main content area
    content_x = s(80)
    content_y = s(150)

    # Avatar section with gradient ring
    avatar_x, avatar_y = content_x + s(80), content_y + s(120)

    # Draw gradient ring
    for r in range(s(85), s(75), -1):
        progress = (s(85) - r) / s(10)
        ring_color = (
            int(0 + progress * 124),  # cyan to purple
            int(212 - progress * 154),
            int(255 - progress * 18),
        )
        draw.ellipse(
            [avatar_x - r, avatar_y - r, avatar_x + r, avatar_y + r],
            outline=ring_color,
            width=scale,
        )

    # Inner circle
    draw.ellipse(
        [avatar_x - s(70), avatar_y - s(70), avatar_x + s(70), avatar_y + s(70)],
        fill=(21, 21, 32),
    )

    # Avatar letter
    avatar_text = username[0].upper() if username else "?"
    try:
        bbox = draw.textbbox((0, 0), avatar_text, font=font_xl)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        draw.text(
            (avatar_x - text_width // 2, avatar_y - text_height // 2 - s(8)),
            avatar_text,
            font=font_xl,
            fill=(0, 212, 255),
        )
    except (OSError, IOError):
        pass

    # Username and info (right of avatar)
    info_x = avatar_x + s(120)
    info_y = content_y + s(50)

    # Username
    draw.text((info_x, info_y), f"@{username}", font=font_large, fill=(255, 255, 255))

    # Level badge with background
    level_text = f"Lvl {level} · {level_title}"
    try:
        level_bbox = draw.textbbox((0, 0), level_text, font=font_medium)
        level_width = level_bbox[2] - level_bbox[0]
        draw.rounded_rectangle(
            [info_x - s(12), info_y + s(52), info_x + level_width + s(24), info_y + s(98)],
            radius=s(10),
            fill=(124, 58, 237, 40),
            outline=(124, 58, 237),
        )
    except (OSError, IOError, TypeError):
        pass
    draw.text(
        (info_x + s(6), info_y + s(60)), level_text, font=font_medium, fill=(167, 139, 250)
    )

    # Bio
    bio_display = (bio[:100] + "...") if len(bio) > 100 else bio
    draw.text(
        (info_x, info_y + s(110)), bio_display, font=font_small, fill=(148, 163, 184)
    )

    # Stats section at bottom
    stats_y = s(420)
    stats = [
        (f"{total_points:,}", "Points", (0, 212, 255)),
        (str(badges_earned), "Badges", (124, 58, 237)),
        (f"{completion_percentage}%", "Complete", (6, 255, 165)),
        (str(challenges_completed), "Challenges", (255, 184, 0)),
    ]

    # Draw stats background bar
    draw.rounded_rectangle(
        [s(60), stats_y - s(20), width - s(60), stats_y + s(100)],
        radius=s(16),
        fill=(20, 20, 28),
        outline=(40, 40, 50),
    )

    stat_width = (width - s(160)) // 4
    for i, (value, label, stat_color) in enumerate(stats):
        x = s(80) + i * stat_width + stat_width // 2

        # Value
        try:
            bbox = draw.textbbox((0, 0), value, font=font_stat)
            val_width = bbox[2] - bbox[0]
            draw.text((x - val_width // 2, stats_y), value, font=font_stat, fill=stat_color)
        except (OSError, IOError):
            draw.text((x - s(30), stats_y), value, font=font_stat, fill=stat_color)

        # Label
        try:
            bbox = draw.textbbox((0, 0), label, font=font_small)
            label_width = bbox[2] - bbox[0]
            draw.text(
                (x - label_width // 2, stats_y + s(45)),
                label,
                font=font_small,
                fill=(100, 116, 139),
            )
        except (OSError, IOError):
            draw.text(
                (x - s(30), stats_y + s(45)), label, font=font_small, fill=(100, 116, 139)
            )

    # Footer line
    draw.line([(s(60), s(550)), (width - s(60), s(550))], fill=(40, 40, 50), width=scale)

    # Footer text
    draw.text((s(60), s(570)), "owasp-finbot-ctf.org", font=font_small, fill=(80, 80, 100))

    # Hashtags
    hashtags = "#OWASPGenAISecurityProject"
    try:
        bbox = draw.textbbox((0, 0), hashtags, font=font_small)
        tag_width = bbox[2] - bbox[0]
        draw.text(
            (width - s(60) - tag_width, s(570)), hashtags, font=font_small, fill=(0, 212, 255)
        )
    except (OSError, IOError):
        pass

    # Convert to bytes
    buffer = BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    buffer.seek(0)
    return buffer.getvalue()


@router.get("/profile/{username}/card.png")
async def get_profile_card(
    username: str,
    db: Session = Depends(get_db),
):
    """Generate and return a profile share card image"""
    # Fetch profile data
    profile_repo = UserProfileRepository(db)
    profile, user = profile_repo.get_public_profile_with_user(username)

    if not profile or not user:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Get stats
    completed_progress = (
        db.query(UserChallengeProgress)
        .filter(
            UserChallengeProgress.namespace == user.namespace,
            UserChallengeProgress.user_id == profile.user_id,
            UserChallengeProgress.status == "completed",
        )
        .all()
    )

    earned_badges = (
        db.query(UserBadge)
        .filter(
            UserBadge.namespace == user.namespace,
            UserBadge.user_id == profile.user_id,
        )
        .all()
    )

    # Calculate points
    challenge_repo = ChallengeRepository(db)
    badge_repo = BadgeRepository(db)

    challenge_points = challenge_repo.get_effective_points(completed_progress)
    earned_badge_ids = [b.badge_id for b in earned_badges]
    badge_points = badge_repo.get_total_points(earned_badge_ids)
    hints_cost = sum(p.hints_cost for p in completed_progress)
    total_points = challenge_points + badge_points - hints_cost

    # Completion percentage
    total_challenges = len(challenge_repo.list_challenges())
    completion_pct = (
        int((len(completed_progress) / total_challenges) * 100)
        if total_challenges > 0
        else 0
    )

    # Level
    level, level_title = calculate_level(total_points)

    # Generate cache key
    cache_data = (
        f"{username}:{total_points}:{len(earned_badges)}:{len(completed_progress)}"
    )
    cache_key = hashlib.md5(cache_data.encode()).hexdigest()
    cache_path = get_cache_path(cache_key)

    # Check cache
    if cache_path.exists():
        return Response(
            content=cache_path.read_bytes(),
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=300"},
        )

    # Generate image
    image_bytes = generate_profile_card(
        username=profile.username,
        avatar_emoji=profile.avatar_emoji or "🦊",
        bio=profile.bio or "AI Security Enthusiast",
        level=level,
        level_title=level_title,
        total_points=total_points,
        badges_earned=len(earned_badges),
        challenges_completed=len(completed_progress),
        completion_percentage=completion_pct,
    )

    # Save to cache
    cache_path.write_bytes(image_bytes)

    return Response(
        content=image_bytes,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=300"},
    )


@router.get("/badge/{badge_id}/card.png")
async def get_badge_card(
    badge_id: str,
    db: Session = Depends(get_db),
):
    """Generate and return a badge share card image"""
    badge_repo = BadgeRepository(db)
    badge = badge_repo.get_badge(badge_id)

    if not badge:
        raise HTTPException(status_code=404, detail="Badge not found")

    # Generate badge share card with achievement/trophy vibe
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise HTTPException(
            status_code=500, detail="Image generation not available"
        ) from exc

    width, height = 1200, 630
    img = Image.new("RGB", (width, height), (5, 5, 10))
    draw = ImageDraw.Draw(img)

    # Rarity colors (RGB tuples)
    rarity_colors = {
        "common": (100, 116, 139),
        "rare": (59, 130, 246),
        "epic": (168, 85, 247),
        "legendary": (251, 191, 36),
    }
    color = rarity_colors.get(badge.rarity, (100, 116, 139))

    # Draw dramatic radial gradient from center
    center_x, center_y = width // 2, 260
    for r in range(400, 0, -1):
        progress = r / 400
        fill_color = (
            5 + int(color[0] * 0.03 * (1 - progress)),
            5 + int(color[1] * 0.03 * (1 - progress)),
            10 + int(color[2] * 0.04 * (1 - progress)),
        )
        draw.ellipse(
            [center_x - r, center_y - r, center_x + r, center_y + r],
            fill=fill_color,
        )

    # Add light rays emanating from badge (for rare+)
    if badge.rarity in ("rare", "epic", "legendary"):
        import math

        num_rays = 12 if badge.rarity == "legendary" else 8
        for i in range(num_rays):
            angle = (2 * math.pi * i) / num_rays
            ray_length = 350 if badge.rarity == "legendary" else 280
            x1 = center_x + int(100 * math.cos(angle))
            y1 = center_y + int(100 * math.sin(angle))
            x2 = center_x + int(ray_length * math.cos(angle))
            y2 = center_y + int(ray_length * math.sin(angle))
            ray_color = (color[0] // 8, color[1] // 8, color[2] // 8)
            draw.line([(x1, y1), (x2, y2)], fill=ray_color, width=3)

    # Subtle diagonal lines pattern
    for i in range(-height, width + height, 30):
        draw.line([(i, 0), (i + height, height)], fill=(15, 15, 20), width=1)

    # Load fonts
    font_xl = _get_font(72, bold=True)
    font_large = _get_font(48, bold=True)
    font_medium = _get_font(28)
    font_small = _get_font(20)
    font_header = _get_font(18, bold=True)

    # "BADGE UNLOCKED" banner at top
    banner_text = "ACHIEVEMENT UNLOCKED"
    try:
        banner_bbox = draw.textbbox((0, 0), banner_text, font=font_header)
        banner_width = banner_bbox[2] - banner_bbox[0]
        # Draw banner background
        draw.rounded_rectangle(
            [
                (width - banner_width) // 2 - 25,
                30,
                (width + banner_width) // 2 + 25,
                65,
            ],
            radius=6,
            fill=(color[0] // 5, color[1] // 5, color[2] // 5),
            outline=color,
        )
        draw.text(
            ((width - banner_width) // 2, 38),
            banner_text,
            font=font_header,
            fill=color,
        )
    except (OSError, IOError, TypeError):
        pass

    # Large glowing badge circle
    # Outer glow rings
    for r in range(140, 100, -2):
        alpha = int((140 - r) * 2)
        glow_color = (
            min(255, color[0] // 4 + alpha // 2),
            min(255, color[1] // 4 + alpha // 2),
            min(255, color[2] // 4 + alpha // 2),
        )
        draw.ellipse(
            [center_x - r, center_y - r, center_x + r, center_y + r],
            outline=glow_color,
            width=2,
        )

    # Main badge ring with thick border
    draw.ellipse(
        [center_x - 95, center_y - 95, center_x + 95, center_y + 95],
        fill=color,
    )
    draw.ellipse(
        [center_x - 85, center_y - 85, center_x + 85, center_y + 85],
        fill=(15, 15, 22),
    )

    # Inner accent ring
    draw.ellipse(
        [center_x - 75, center_y - 75, center_x + 75, center_y + 75],
        outline=(color[0] // 2, color[1] // 2, color[2] // 2),
        width=2,
    )

    # Badge icon (first letter) - large and prominent
    icon_text = badge.title[0].upper() if badge.title else "?"
    try:
        bbox = draw.textbbox((0, 0), icon_text, font=font_xl)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        draw.text(
            (center_x - text_width // 2, center_y - text_height // 2 - 8),
            icon_text,
            font=font_xl,
            fill=color,
        )
    except (OSError, IOError):
        pass

    # Badge title - large and centered below badge
    try:
        title_bbox = draw.textbbox((0, 0), badge.title, font=font_large)
        title_width = title_bbox[2] - title_bbox[0]
        draw.text(
            ((width - title_width) // 2, 400),
            badge.title,
            font=font_large,
            fill=(255, 255, 255),
        )
    except (OSError, IOError):
        pass

    # Rarity and points in styled pills
    rarity_label = badge.rarity.upper()
    points_label = f"+{badge.points} PTS"

    try:
        # Rarity pill (left)
        rarity_bbox = draw.textbbox((0, 0), rarity_label, font=font_medium)
        rarity_w = rarity_bbox[2] - rarity_bbox[0]
        rarity_x = width // 2 - rarity_w - 50
        draw.rounded_rectangle(
            [rarity_x - 20, 465, rarity_x + rarity_w + 20, 505],
            radius=10,
            fill=(color[0] // 6, color[1] // 6, color[2] // 6),
            outline=color,
        )
        draw.text((rarity_x, 472), rarity_label, font=font_medium, fill=color)

        # Points pill (right)
        points_bbox = draw.textbbox((0, 0), points_label, font=font_medium)
        points_w = points_bbox[2] - points_bbox[0]
        points_x = width // 2 + 30
        draw.rounded_rectangle(
            [points_x - 20, 465, points_x + points_w + 20, 505],
            radius=10,
            fill=(20, 25, 20),
            outline=(6, 255, 165),
        )
        draw.text((points_x, 472), points_label, font=font_medium, fill=(6, 255, 165))
    except (OSError, IOError, TypeError):
        pass

    # Description below pills (strictly one-liner, ~45 chars max)
    if badge.description:
        desc = (
            (badge.description[:45] + "...")
            if len(badge.description) > 45
            else badge.description
        )
        try:
            desc_bbox = draw.textbbox((0, 0), desc, font=font_small)
            desc_width = desc_bbox[2] - desc_bbox[0]
            draw.text(
                ((width - desc_width) // 2, 525),
                desc,
                font=font_small,
                fill=(120, 130, 150),
            )
        except (OSError, IOError):
            pass

    # Bottom bar with branding
    draw.rectangle([0, height - 70, width, height], fill=(10, 10, 15))
    draw.line([(0, height - 70), (width, height - 70)], fill=color, width=2)

    # FinBot logo in footer
    logo_path = (
        Path(__file__).parent.parent.parent.parent
        / "static"
        / "images"
        / "common"
        / "finbot.png"
    )
    try:
        logo = Image.open(logo_path).convert("RGBA")
        logo = logo.resize((40, 40), Image.Resampling.LANCZOS)
        mask = Image.new("L", (40, 40), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse([0, 0, 40, 40], fill=255)
        img.paste(logo, (60, height - 55), mask)
    except (OSError, IOError):
        draw.ellipse([60, height - 55, 100, height - 15], fill=(0, 212, 255))

    # Branding text with better spacing
    draw.text((115, height - 50), "FINBOT", font=font_medium, fill=(255, 255, 255))
    draw.text((220, height - 44), "CTF", font=_get_font(16), fill=(0, 212, 255))

    # URL centered
    url_text = "owasp-finbot-ctf.org"
    try:
        url_bbox = draw.textbbox((0, 0), url_text, font=font_small)
        url_width = url_bbox[2] - url_bbox[0]
        draw.text(
            ((width - url_width) // 2, height - 45),
            url_text,
            font=font_small,
            fill=(100, 110, 130),
        )
    except (OSError, IOError):
        draw.text(
            (width // 2 - 80, height - 45),
            url_text,
            font=font_small,
            fill=(100, 110, 130),
        )

    # Hashtag on right
    hashtags = "#OWASPFinBotCTF"
    try:
        bbox = draw.textbbox((0, 0), hashtags, font=font_small)
        tag_width = bbox[2] - bbox[0]
        draw.text(
            (width - 70 - tag_width, height - 45), hashtags, font=font_small, fill=color
        )
    except (OSError, IOError):
        pass

    buffer = BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    buffer.seek(0)

    return Response(
        content=buffer.getvalue(),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/badge/{username}/{badge_id}/card.png")
async def get_user_badge_card(
    username: str,
    badge_id: str,
    db: Session = Depends(get_db),
):
    """Generate a personalized badge card showing the user earned this badge"""
    # Look up user by username
    profile_repo = UserProfileRepository(db)
    profile, user = profile_repo.get_public_profile_with_user(username)

    if not profile or not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Verify user actually earned this badge (query directly without session context)
    user_badge = (
        db.query(UserBadge)
        .filter(
            UserBadge.namespace == user.namespace,
            UserBadge.user_id == profile.user_id,
            UserBadge.badge_id == badge_id,
        )
        .first()
    )

    if not user_badge:
        raise HTTPException(status_code=404, detail="User has not earned this badge")

    # Get badge details
    badge_repo = BadgeRepository(db)
    badge = badge_repo.get_badge(badge_id)

    if not badge:
        raise HTTPException(status_code=404, detail="Badge not found")

    # Generate personalized badge card at 2x resolution for HD quality
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise HTTPException(
            status_code=500, detail="Image generation not available"
        ) from exc

    # Scale factor for HD rendering (2x = 2400x1260)
    scale = 2
    width, height = 1200 * scale, 630 * scale
    img = Image.new("RGB", (width, height), (5, 5, 10))
    draw = ImageDraw.Draw(img)

    # Helper to scale values
    def s(val: int) -> int:
        return val * scale

    # Rarity colors
    rarity_colors = {
        "common": (100, 116, 139),
        "rare": (59, 130, 246),
        "epic": (168, 85, 247),
        "legendary": (251, 191, 36),
    }
    color = rarity_colors.get(badge.rarity, (100, 116, 139))

    # Draw dramatic radial gradient from center
    center_x, center_y = width // 2, s(240)
    for r in range(s(400), 0, -1):
        progress = r / s(400)
        fill_color = (
            5 + int(color[0] * 0.03 * (1 - progress)),
            5 + int(color[1] * 0.03 * (1 - progress)),
            10 + int(color[2] * 0.04 * (1 - progress)),
        )
        draw.ellipse(
            [center_x - r, center_y - r, center_x + r, center_y + r],
            fill=fill_color,
        )

    # Add light rays for rare+ badges
    if badge.rarity in ("rare", "epic", "legendary"):
        import math

        num_rays = 12 if badge.rarity == "legendary" else 8
        for i in range(num_rays):
            angle = (2 * math.pi * i) / num_rays
            ray_length = s(350) if badge.rarity == "legendary" else s(280)
            x1 = center_x + int(s(100) * math.cos(angle))
            y1 = center_y + int(s(100) * math.sin(angle))
            x2 = center_x + int(ray_length * math.cos(angle))
            y2 = center_y + int(ray_length * math.sin(angle))
            ray_color = (color[0] // 8, color[1] // 8, color[2] // 8)
            draw.line([(x1, y1), (x2, y2)], fill=ray_color, width=s(3))

    # Diagonal lines pattern
    for i in range(-height, width + height, s(30)):
        draw.line([(i, 0), (i + height, height)], fill=(15, 15, 20), width=scale)

    # Load fonts (scaled)
    font_xl = _get_font(s(72), bold=True)
    font_large = _get_font(s(48), bold=True)
    font_medium = _get_font(s(28))
    font_header = _get_font(s(18), bold=True)

    # "ACHIEVEMENT UNLOCKED" banner
    banner_text = "ACHIEVEMENT UNLOCKED"
    try:
        banner_bbox = draw.textbbox((0, 0), banner_text, font=font_header)
        banner_width = banner_bbox[2] - banner_bbox[0]
        draw.rounded_rectangle(
            [
                (width - banner_width) // 2 - s(25),
                s(30),
                (width + banner_width) // 2 + s(25),
                s(65),
            ],
            radius=s(6),
            fill=(color[0] // 5, color[1] // 5, color[2] // 5),
            outline=color,
        )
        draw.text(
            ((width - banner_width) // 2, s(38)),
            banner_text,
            font=font_header,
            fill=color,
        )
    except (OSError, IOError, TypeError):
        pass

    # Badge circle with glow
    for r in range(s(140), s(100), -2):
        alpha = int((s(140) - r) * 2)
        glow_color = (
            min(255, color[0] // 4 + alpha // 2),
            min(255, color[1] // 4 + alpha // 2),
            min(255, color[2] // 4 + alpha // 2),
        )
        draw.ellipse(
            [center_x - r, center_y - r, center_x + r, center_y + r],
            outline=glow_color,
            width=s(2),
        )

    # Main badge ring
    draw.ellipse(
        [center_x - s(95), center_y - s(95), center_x + s(95), center_y + s(95)],
        fill=color,
    )
    draw.ellipse(
        [center_x - s(85), center_y - s(85), center_x + s(85), center_y + s(85)],
        fill=(15, 15, 22),
    )
    draw.ellipse(
        [center_x - s(75), center_y - s(75), center_x + s(75), center_y + s(75)],
        outline=(color[0] // 2, color[1] // 2, color[2] // 2),
        width=s(2),
    )

    # Badge icon (first letter)
    icon_text = badge.title[0].upper() if badge.title else "?"
    try:
        bbox = draw.textbbox((0, 0), icon_text, font=font_xl)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        draw.text(
            (center_x - text_width // 2, center_y - text_height // 2 - s(8)),
            icon_text,
            font=font_xl,
            fill=color,
        )
    except (OSError, IOError):
        pass

    # Badge title
    try:
        title_bbox = draw.textbbox((0, 0), badge.title, font=font_large)
        title_width = title_bbox[2] - title_bbox[0]
        draw.text(
            ((width - title_width) // 2, s(385)),
            badge.title,
            font=font_large,
            fill=(255, 255, 255),
        )
    except (OSError, IOError):
        pass

    # Rarity and points pills
    rarity_label = badge.rarity.upper()
    points_label = f"+{badge.points} PTS"

    try:
        rarity_bbox = draw.textbbox((0, 0), rarity_label, font=font_medium)
        rarity_w = rarity_bbox[2] - rarity_bbox[0]
        rarity_x = width // 2 - rarity_w - s(50)
        draw.rounded_rectangle(
            [rarity_x - s(20), s(450), rarity_x + rarity_w + s(20), s(490)],
            radius=s(10),
            fill=(color[0] // 6, color[1] // 6, color[2] // 6),
            outline=color,
        )
        draw.text((rarity_x, s(457)), rarity_label, font=font_medium, fill=color)

        points_bbox = draw.textbbox((0, 0), points_label, font=font_medium)
        points_w = points_bbox[2] - points_bbox[0]
        points_x = width // 2 + s(30)
        draw.rounded_rectangle(
            [points_x - s(20), s(450), points_x + points_w + s(20), s(490)],
            radius=s(10),
            fill=(20, 25, 20),
            outline=(6, 255, 165),
        )
        draw.text((points_x, s(457)), points_label, font=font_medium, fill=(6, 255, 165))
    except (OSError, IOError, TypeError):
        pass

    # Bottom bar with branding and "Earned by" text
    draw.rectangle([0, height - s(80), width, height], fill=(10, 10, 15))
    draw.line([(0, height - s(80)), (width, height - s(80))], fill=color, width=s(2))

    # "Earned by @username" - prominent on left
    earned_text = f"Earned by @{username}"
    try:
        draw.text((s(60), height - s(55)), earned_text, font=font_medium, fill=(0, 212, 255))
    except (OSError, IOError):
        pass

    # FinBot logo + CTF branding on right
    logo_path = (
        Path(__file__).parent.parent.parent.parent
        / "static"
        / "images"
        / "common"
        / "finbot.png"
    )
    logo_size = s(45)
    try:
        logo = Image.open(logo_path).convert("RGBA")
        logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
        mask = Image.new("L", (logo_size, logo_size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse([0, 0, logo_size, logo_size], fill=255)
        img.paste(logo, (width - s(295), height - s(62)), mask)
    except (OSError, IOError):
        draw.ellipse(
            [width - s(295), height - s(62), width - s(250), height - s(17)], fill=(0, 212, 255)
        )

    try:
        draw.text(
            (width - s(240), height - s(55)), "FINBOT", font=font_medium, fill=(255, 255, 255)
        )
        draw.text(
            (width - s(125), height - s(50)), "CTF", font=_get_font(s(16)), fill=(0, 212, 255)
        )
    except (OSError, IOError):
        pass

    buffer = BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    buffer.seek(0)

    return Response(
        content=buffer.getvalue(),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=300"},
    )
