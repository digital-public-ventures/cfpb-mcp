import json
import os
import re

from dotenv import load_dotenv
import httpx
import pytest
import openai
from openai import OpenAI

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
        # If .env can't be read, just fall back to normal env var behavior.
        return


def _require_e2e_opt_in() -> None:
    if os.getenv("RUN_E2E") not in {"1", "true", "TRUE", "yes", "YES"}:
        pytest.skip("E2E tests are disabled. Re-run with RUN_E2E=1")


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


def _path_tool_name(method: str, path: str) -> str:
    # Stable tool names that don't depend on OpenAPI operationId.
    safe = re.sub(r"[^a-zA-Z0-9_]+", "_", path.strip("/") or "root").strip("_")
    return f"{method.lower()}__{safe}"


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
def test_openai_openapi_tool_loop_smoke(server_url: str) -> None:
    _require_e2e_opt_in()

    _load_dotenv_if_present()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("Missing OPENAI_API_KEY")

    # Load OpenAPI spec from the running test server.
    spec = httpx.get(f"{server_url}/openapi.json", timeout=30).json()

    # Convert operations into Responses API tools.
    # (We intentionally do NOT use operationId for tool naming so that refactors
    # that change operationIds don't break this third-party-style test runner.)
    tools = []
    tool_routes: dict[str, tuple[str, str, dict]] = {}
    for path, methods in spec.get("paths", {}).items():
        if not isinstance(methods, dict):
            continue

        for method, op in methods.items():
            if method not in {"get", "post"}:
                continue
            if not isinstance(op, dict):
                continue

            tool_name = _path_tool_name(method, path)

            properties = {}
            required = []

            for p in op.get("parameters", []):
                name = p.get("name")
                if not name:
                    continue
                schema = p.get("schema", {})
                prop = {
                    "type": schema.get("type", "string"),
                    "description": p.get("description", ""),
                }
                if "enum" in schema:
                    prop["enum"] = schema["enum"]
                if "default" in schema:
                    prop["default"] = schema["default"]
                if "minimum" in schema:
                    prop["minimum"] = schema["minimum"]
                if "maximum" in schema:
                    prop["maximum"] = schema["maximum"]

                where = p.get("in")
                if where in {"path", "query"}:
                    properties[name] = prop
                    if p.get("required"):
                        required.append(name)

            # Basic JSON requestBody support for POST.
            if method == "post":
                rb = (
                    op.get("requestBody", {})
                    if isinstance(op.get("requestBody"), dict)
                    else {}
                )
                content = (
                    rb.get("content", {}) if isinstance(rb.get("content"), dict) else {}
                )
                app_json = (
                    content.get("application/json", {})
                    if isinstance(content.get("application/json"), dict)
                    else {}
                )
                schema = (
                    app_json.get("schema", {})
                    if isinstance(app_json.get("schema"), dict)
                    else {}
                )
                if schema:
                    properties["body"] = {
                        "type": "object",
                        "description": "JSON request body",
                    }

            tools.append(
                {
                    "type": "function",
                    "name": tool_name,
                    "description": op.get("summary")
                    or op.get("description")
                    or f"{method.upper()} {path}",
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                }
            )
            tool_routes[tool_name] = (method, path, op)

    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_MODEL", "gpt-5-mini")

    prompt = (
        "I'm researching CFPB consumer complaints about loan forbearance. "
        "Please find a complaint mentioning 'forbearance' where the company name is present, then tell me the complaint id, "
        "the company (if present), the state (if present), and a short 2-3 sentence summary grounded in the complaint. "
        "If you can't use tools, say 'MCP tools unavailable'."
    )

    # Some models reject the `reasoning` parameter; retry without it.
    # This keeps the test closer to a third-party "first attempt" client.
    try:
        resp = client.responses.create(
            model=model,
            input=prompt,
            tools=tools,
            reasoning={"effort": "low"},
        )
    except openai.BadRequestError as exc:
        msg = str(getattr(exc, "message", "") or str(exc))
        if "reasoning.effort" not in msg:
            raise
        resp = client.responses.create(
            model=model,
            input=prompt,
            tools=tools,
        )

    # Minimal tool loop.
    complaint_id_from_tools: int | None = None
    while True:
        tool_calls = [item for item in resp.output if item.type == "function_call"]
        if not tool_calls:
            break

        tool_outputs = []
        for call in tool_calls:
            args = json.loads(call.arguments or "{}")

            route = tool_routes.get(call.name)
            assert route is not None, f"Unknown tool requested by model: {call.name}"

            method, path, op = route
            url_path = path
            query = {}
            for p in op.get("parameters", []):
                name = p.get("name")
                where = p.get("in")
                if not name or name not in args:
                    continue
                if where == "path":
                    url_path = url_path.replace("{" + name + "}", str(args[name]))
                elif where == "query":
                    query[name] = args[name]

            # If the tool call is targeting the stable complaint endpoint, capture the id.
            if path == "/complaint/{complaint_id}" and "complaint_id" in args:
                try:
                    complaint_id_from_tools = int(str(args["complaint_id"]))
                except ValueError:
                    complaint_id_from_tools = None

            if method == "get":
                r = httpx.get(f"{server_url}{url_path}", params=query, timeout=30)
            else:
                body = args.get("body") if isinstance(args.get("body"), dict) else None
                r = httpx.post(
                    f"{server_url}{url_path}", params=query, json=body, timeout=30
                )
            r.raise_for_status()
            payload = r.json()

            # Fallback: if the model only did a search, grab the first hit id.
            if complaint_id_from_tools is None and path == "/search":
                complaint_id_from_tools = _extract_complaint_id_from_search_payload(
                    payload
                )

            tool_outputs.append(
                {
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": json.dumps(payload),
                }
            )

        try:
            resp = client.responses.create(
                model=model,
                input=tool_outputs,
                previous_response_id=resp.id,
                reasoning={"effort": "low"},
            )
        except openai.BadRequestError as exc:
            msg = str(getattr(exc, "message", "") or str(exc))
            if "reasoning.effort" not in msg:
                raise
            resp = client.responses.create(
                model=model,
                input=tool_outputs,
                previous_response_id=resp.id,
            )

    # We don't assert exact wording, just that we got a plausible id-like token.
    text = (resp.output_text or "").strip()
    assert text, "Expected a final answer"

    assert complaint_id_from_tools is not None, (
        "Expected the agent to obtain a complaint id via tools"
    )
    assert 4 <= len(str(complaint_id_from_tools)) <= 9
    assert str(complaint_id_from_tools) in text

    # Keep the original "must contain a 4-9 digit integer" guard, but prefer validating
    # against the tool-derived complaint id for stability.
    complaint_id, _ = _extract_complaint_id_from_text(text)
    assert complaint_id == complaint_id_from_tools

    r = httpx.get(f"{server_url}/complaint/{complaint_id}", timeout=30)
    r.raise_for_status()
    doc = r.json()

    company = _extract_company_from_document(doc)
    if not company:
        pytest.skip(f"Complaint {complaint_id} document missing company field")
    first_word = company.split()[0].lower()
    assert first_word in text.lower()
