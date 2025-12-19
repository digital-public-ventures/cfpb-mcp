import os
import json
import base64
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from anthropic import Anthropic
from anthropic.types import (
    MessageParam,
    ToolChoiceParam,
    ToolResultBlockParam,
    ToolUseBlock,
)
from dotenv import load_dotenv

from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

load_dotenv()


def _load_dotenv_if_present() -> None:
    """Load .env for local runs without requiring external tooling.

    Only sets variables that are not already present in the environment.
    """

    env_path = os.path.join(os.getcwd(), ".env")
    if not os.path.exists(env_path):
        return

    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                if not key or key in os.environ:
                    continue
                value = value.strip().strip('"').strip("'")
                os.environ[key] = value
    except OSError:
        return


def _require_e2e_opt_in() -> None:
    if os.getenv("RUN_E2E") not in {"1", "true", "TRUE", "yes", "YES"}:
        pytest.skip("E2E tests are disabled. Re-run with RUN_E2E=1")


def _extract_text(blocks) -> str:
    if not isinstance(blocks, list):
        return str(blocks or "")
    parts = []
    for b in blocks:
        if getattr(b, "type", None) == "text" and hasattr(b, "text"):
            parts.append(str(getattr(b, "text")))
    return "\n".join([p for p in parts if p]).strip()


def _tool_result_text(payload: Any) -> str:
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False, default=str)


def _extract_image_from_content(content: list) -> tuple[bytes, str] | None:
    """Extract image data and media type from Anthropic content blocks.

    Returns (image_bytes, media_type) or None if no image found.
    """
    for block in content:
        if getattr(block, "type", None) == "image":
            # Extract the source data
            source = getattr(block, "source", None)
            if not source:
                continue

            media_type = getattr(source, "media_type", "image/png")
            data = getattr(source, "data", None)

            if data:
                # Data should be base64 encoded
                try:
                    image_bytes = base64.b64decode(data)
                    return image_bytes, media_type
                except Exception:
                    continue

    return None


def _save_image(image_bytes: bytes, media_type: str) -> Path:
    """Save image to tests/e2e/outputs with timestamp.

    Returns the path to the saved file.
    """
    # Create outputs directory if needed
    outputs_dir = Path(__file__).parent / "outputs"
    outputs_dir.mkdir(exist_ok=True)

    # Determine file extension from media type
    extension = "png"  # default
    if "jpeg" in media_type or "jpg" in media_type:
        extension = "jpg"
    elif "webp" in media_type:
        extension = "webp"

    # Create filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"cfpb_chart_{timestamp}.{extension}"
    filepath = outputs_dir / filename

    # Write the image
    with open(filepath, "wb") as f:
        f.write(image_bytes)

    return filepath


@pytest.mark.e2e
@pytest.mark.anyio
async def test_anthropic_mcp_screenshot_generation(server_url: str) -> None:
    """Test screenshot generation via REST endpoint with AI-suggested parameters.

    This test:
    1. Uses the AI to determine appropriate filter parameters for mortgage complaints
    2. Calls the REST screenshot endpoint with those parameters
    3. Verifies that a valid image is returned
    4. Saves the image to tests/e2e/outputs for manual inspection
    """
    _require_e2e_opt_in()

    _load_dotenv_if_present()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("Missing ANTHROPIC_API_KEY")

    client = Anthropic(api_key=api_key)
    model = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")

    # Ask AI for date range suggestion in a simple, token-efficient way
    user_prompt = (
        "What date range would you suggest for analyzing mortgage complaints "
        "from the past 2 years? Reply in JSON format: "
        '{"date_received_min": "YYYY-MM-DD", "date_received_max": "YYYY-MM-DD", "product": "Mortgage"}'
    )

    resp = client.messages.create(
        model=model,
        max_tokens=200,
        messages=[{"role": "user", "content": user_prompt}],
    )

    text_response = _extract_text(resp.content)

    # Parse the AI's suggested parameters
    try:
        # Extract JSON from response
        json_start = text_response.find("{")
        json_end = text_response.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            params = json.loads(text_response[json_start:json_end])
        else:
            # Fallback to hardcoded params
            from datetime import datetime, timedelta

            end_date = datetime.now()
            start_date = end_date - timedelta(days=730)  # 2 years
            params = {
                "date_received_min": start_date.strftime("%Y-%m-%d"),
                "date_received_max": end_date.strftime("%Y-%m-%d"),
                "product": "Mortgage",
            }
    except (json.JSONDecodeError, ValueError):
        # Fallback to hardcoded params
        from datetime import datetime, timedelta

        end_date = datetime.now()
        start_date = end_date - timedelta(days=730)  # 2 years
        params = {
            "date_received_min": start_date.strftime("%Y-%m-%d"),
            "date_received_max": end_date.strftime("%Y-%m-%d"),
            "product": "Mortgage",
        }

    print(f"\n✓ Using parameters: {params}")

    # Call the REST screenshot endpoint
    async with httpx.AsyncClient(timeout=60.0) as http_client:
        resp = await http_client.get(
            f"{server_url}/cfpb-ui/screenshot",
            params=params,
        )

        if resp.status_code == 503:
            pytest.skip(
                "Playwright not available in server (expected in CI/non-Docker)"
            )

        resp.raise_for_status()

        image_bytes = resp.content
        media_type = resp.headers.get("content-type", "image/png")

    # Verify it's a valid image (non-empty, reasonable size)
    assert len(image_bytes) > 1000, (
        f"Image seems too small ({len(image_bytes)} bytes), "
        "might be corrupted or invalid"
    )

    # Verify it starts with PNG magic bytes or JPEG magic bytes
    is_png = image_bytes[:8] == b"\x89PNG\r\n\x1a\n"
    is_jpeg = image_bytes[:2] == b"\xff\xd8"
    is_webp = image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP"

    assert is_png or is_jpeg or is_webp, (
        f"Image data doesn't match expected format. "
        f"First 12 bytes: {image_bytes[:12].hex()}"
    )

    # Save the image for manual inspection
    saved_path = _save_image(image_bytes, media_type)

    print(f"\n✓ Screenshot saved to: {saved_path}")
    print(f"  Size: {len(image_bytes):,} bytes")
    print(f"  Media type: {media_type}")
    print(f"  Format: {'PNG' if is_png else 'JPEG' if is_jpeg else 'WebP'}")
