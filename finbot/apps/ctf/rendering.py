"""Playwright-based HTML-to-PNG renderer for OG image generation."""

import logging

logger = logging.getLogger(__name__)

_renderer: "PlaywrightRenderer | None" = None


class PlaywrightRenderer:
    """Singleton headless Chromium renderer that converts HTML to PNG screenshots."""

    def __init__(self) -> None:
        self._playwright = None
        self._browser = None

    async def start(self) -> None:
        """Launch headless Chromium (idempotent)."""
        if self._browser is not None:
            return

        # pylint: disable=import-outside-toplevel
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=True)
        logger.info("PlaywrightRenderer: Chromium launched")

    async def render_to_png(
        self,
        html: str,
        *,
        width: int = 1200,
        height: int = 630,
        scale: int = 2,
    ) -> bytes:
        """Render an HTML string to a PNG byte buffer.

        Creates a new browser page sized to *width* x *height* with the given
        device *scale* factor, sets the HTML content, takes a full-page
        screenshot, and closes the page.
        """
        if self._browser is None:
            await self.start()

        page = await self._browser.new_page(
            viewport={"width": width, "height": height},
            device_scale_factor=scale,
        )
        try:
            await page.set_content(html, wait_until="load")
            return await page.screenshot(type="png", full_page=False)
        finally:
            await page.close()

    async def shutdown(self) -> None:
        """Close the browser and Playwright process."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info("PlaywrightRenderer: shut down")


def get_renderer() -> PlaywrightRenderer:
    """Return the module-level renderer singleton, creating it if needed."""
    global _renderer  # pylint: disable=global-statement
    if _renderer is None:
        _renderer = PlaywrightRenderer()
    return _renderer
