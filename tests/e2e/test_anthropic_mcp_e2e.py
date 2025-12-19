import os
import json
import re
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


def _coerce_json(payload: object) -> dict | None:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    if isinstance(payload, list):
        text = _extract_text(payload)
        if not text:
            return None
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def _extract_complaint_id_from_text(text: str) -> tuple[int, str]:
    matches = re.findall(r"\b\d{4,9}\b", text or "")
    assert matches, "Expected a 4-9 digit integer token in the final response text"

    # Prefer the longest match to avoid accidentally grabbing a year like 2024.
    token = max(matches, key=len)
    assert 4 <= len(token) <= 9
    return int(token), token


def _extract_company_from_document(doc: object) -> str:
    if not isinstance(doc, dict):
        return ""

    # CFPB "document by id" endpoint returns an ES-style response.
    hits = doc.get("hits") if isinstance(doc.get("hits"), dict) else None
    if hits and isinstance(hits.get("hits"), list) and hits["hits"]:
        hit0 = hits["hits"][0] if isinstance(hits["hits"][0], dict) else {}
        source = hit0.get("_source") if isinstance(hit0.get("_source"), dict) else {}
    else:
        source = doc.get("_source") if isinstance(doc.get("_source"), dict) else doc

    if not isinstance(source, dict):
        return ""

    company = source.get("company")
    return str(company or "").strip()


def _extract_complaint_id_from_search_payload(payload: object) -> int | None:
    if not isinstance(payload, dict):
        return None
    hits = payload.get("hits", {})
    if not isinstance(hits, dict):
        return None
    inner = hits.get("hits", [])
    if not isinstance(inner, list) or not inner:
        return None
    hit0 = inner[0] if isinstance(inner[0], dict) else None
    if not hit0:
        return None
    cid = hit0.get("_id") or (
        hit0.get("_source", {}) if isinstance(hit0.get("_source"), dict) else {}
    ).get("complaint_id")
    if cid is None:
        return None
    try:
        cid_int = int(str(cid))
    except ValueError:
        return None
    if 4 <= len(str(cid_int)) <= 9:
        return cid_int
    return None


@pytest.mark.e2e
@pytest.mark.anyio
async def test_anthropic_mcp_tool_loop_smoke(server_url: str) -> None:
    _require_e2e_opt_in()

    _load_dotenv_if_present()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("Missing ANTHROPIC_API_KEY")

    client = Anthropic(api_key=api_key)
    model = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")

    mcp_sse_url = f"{server_url}/mcp/sse"

    user_prompt = (
        "I'm researching CFPB consumer complaints about loan forbearance. "
        "Please find a complaint mentioning 'forbearance' where the company name is present, then tell me the complaint id, "
        "the company (if present), the state (if present), and a short 2-3 sentence summary grounded in the complaint. "
        "If you can't use tools, say 'MCP tools unavailable'."
    )

    final_text: str | None = None
    complaint_id_from_tools: int | None = None

    async with sse_client(mcp_sse_url) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as mcp:
            await mcp.initialize()
            tool_list = await mcp.list_tools()

            tools = []
            for t in tool_list.tools:
                tools.append(
                    {
                        "name": t.name,
                        "description": t.description or "",
                        "input_schema": t.inputSchema,
                    }
                )

            messages: list[MessageParam] = [{"role": "user", "content": user_prompt}]

            for _ in range(10):
                # Encourage at least one tool call so this behaves like a
                # "first attempt" agent that must use MCP to answer.
                tool_choice: ToolChoiceParam = (
                    {"type": "any"}
                    if complaint_id_from_tools is None
                    else {"type": "auto"}
                )
                resp = client.messages.create(
                    model=model,
                    max_tokens=800,
                    tools=tools,
                    tool_choice=tool_choice,
                    messages=messages,
                )

                messages.append(
                    cast(MessageParam, {"role": "assistant", "content": resp.content})
                )

                # tool_uses = [c for c in resp.content if getattr(c, "type", None) == "tool_use"]
                tool_uses: list[ToolUseBlock] = [
                    c for c in resp.content if isinstance(c, ToolUseBlock)
                ]

                if not tool_uses:
                    # Some responses may contain only thinking/metadata blocks.
                    # If we didn't get any visible text, ask explicitly for the final answer.
                    if _extract_text(resp.content):
                        break
                    messages.append(
                        cast(
                            MessageParam,
                            {
                                "role": "user",
                                "content": "Please provide the final answer now (complaint id, company, state if present, and a 2-3 sentence grounded summary).",
                            },
                        )
                    )
                    continue

                for tu in tool_uses:
                    result = await mcp.call_tool(tu.name, tu.input)

                    # Capture complaint id from tool interactions, so the test doesn't
                    # depend on regex guessing from final prose.
                    if (
                        tu.name == "get_complaint_document"
                        and isinstance(tu.input, dict)
                        and "complaint_id" in tu.input
                    ):
                        try:
                            complaint_id_from_tools = int(str(tu.input["complaint_id"]))
                        except ValueError:
                            complaint_id_from_tools = None
                    elif tu.name == "search_complaints":
                        payload = result.structuredContent or result.content
                        cid = _extract_complaint_id_from_search_payload(
                            _coerce_json(payload) or payload
                        )
                        if cid is not None:
                            complaint_id_from_tools = cid

                    tool_payload = result.structuredContent or result.content
                    tool_block = cast(
                        ToolResultBlockParam,
                        {
                            "type": "tool_result",
                            "tool_use_id": tu.id,
                            "content": _tool_result_text(tool_payload),
                        },
                    )
                    messages.append(
                        cast(MessageParam, {"role": "user", "content": [tool_block]})
                    )

            last_assistant = next(
                (m for m in reversed(messages) if m.get("role") == "assistant"), None
            )
            assert last_assistant is not None
            text = _extract_text(last_assistant.get("content"))
            assert text
            assert "MCP tools unavailable" not in text

            final_text = text

            assert complaint_id_from_tools is not None, (
                "Expected the agent to obtain a complaint id via tools"
            )
            assert 4 <= len(str(complaint_id_from_tools)) <= 9
            assert str(complaint_id_from_tools) in text

            # Keep the original "must contain a 4-9 digit integer" guard, but validate
            # it matches the tool-derived complaint id for stability.
            complaint_id, _ = _extract_complaint_id_from_text(text)
            assert complaint_id == complaint_id_from_tools

    assert final_text is not None
    assert complaint_id_from_tools is not None

    # Do REST assertions outside MCP SSE context to avoid pytest.skip leaking out of
    # the AnyIO TaskGroup and producing noisy ExceptionGroup logs.
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(f"{server_url}/complaint/{complaint_id_from_tools}")
        r.raise_for_status()
        doc = r.json()

    company = _extract_company_from_document(doc)
    if not company:
        pytest.skip(
            f"Complaint {complaint_id_from_tools} document missing company field"
        )
    first_word = company.split()[0].lower()
    assert first_word in final_text.lower()
