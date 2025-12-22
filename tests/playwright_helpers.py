from __future__ import annotations

from contextlib import asynccontextmanager


@asynccontextmanager
async def fast_playwright_context():
    try:
        from playwright.async_api import async_playwright
    except Exception as exc:
        raise RuntimeError(f'Playwright unavailable for UI verification: {exc}') from exc

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        async def _block_heavy_assets(route, request):
            if request.resource_type in {'image', 'media', 'font'}:
                await route.abort()
            else:
                await route.continue_()

        await context.route('**/*', _block_heavy_assets)
        context.set_default_timeout(20000)

        try:
            yield context
        finally:
            await context.close()
            await browser.close()
