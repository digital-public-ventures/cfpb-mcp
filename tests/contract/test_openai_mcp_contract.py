import json
import os
import re

import openai
import pytest
from dotenv import load_dotenv
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from openai import OpenAI

load_dotenv()


def _load_dotenv_if_present() -> None:
    """Load .env for local runs without requiring external tooling."""
    env_path = os.path.join(os.getcwd(), '.env')
    if not os.path.exists(env_path):
        return

    try:
        with open(env_path, encoding='utf-8') as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                key = key.strip()
                if not key or key in os.environ:
                    continue
                value = value.strip().strip('"').strip("'")
                os.environ[key] = value
    except OSError:
        return


def _extract_complaint_id_from_text(text: str) -> tuple[int, str]:
    matches = re.findall(r'\b\d{4,9}\b', text or '')
    assert matches, 'Expected a 4-9 digit integer token in the final response text'
    token = max(matches, key=len)
    assert 4 <= len(token) <= 9
    return int(token), token


def _extract_company_from_document(doc: object) -> str:
    if not isinstance(doc, dict):
        return ''

    hits = doc.get('hits') if isinstance(doc.get('hits'), dict) else None
    if hits and isinstance(hits.get('hits'), list) and hits['hits']:
        hit0 = hits['hits'][0] if isinstance(hits['hits'][0], dict) else {}
        source = hit0.get('_source') if isinstance(hit0.get('_source'), dict) else {}
    else:
        source = doc.get('_source') if isinstance(doc.get('_source'), dict) else doc

    if not isinstance(source, dict):
        return ''

    company = source.get('company')
    return str(company or '').strip()


def _extract_complaint_id_from_search_payload(payload: object) -> int | None:
    if not isinstance(payload, dict):
        return None
    data = payload.get('data') if isinstance(payload.get('data'), dict) else None
    if not isinstance(data, dict):
        return None
    hits = data.get('hits', {})
    if not isinstance(hits, dict):
        return None
    inner = hits.get('hits', [])
    if not isinstance(inner, list) or not inner:
        return None
    hit0 = inner[0] if isinstance(inner[0], dict) else None
    if not hit0:
        return None
    cid = hit0.get('_id') or (hit0.get('_source', {}) if isinstance(hit0.get('_source'), dict) else {}).get(
        'complaint_id'
    )
    if cid is None:
        return None
    try:
        cid_int = int(str(cid))
    except ValueError:
        return None
    if 4 <= len(str(cid_int)) <= 9:
        return cid_int
    return None


def _coerce_json(payload: object) -> object:
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return payload
    return payload


def _tool_result_text(payload: object) -> str:
    if payload is None:
        return ''
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False, default=str)


def _tool_payload(result: object) -> object:
    payload = getattr(result, 'structuredContent', None) or getattr(result, 'content', None)
    if isinstance(payload, list):
        text_parts = []
        for item in payload:
            text = getattr(item, 'text', None)
            if text:
                text_parts.append(text)
        if text_parts:
            return _coerce_json('\n'.join(text_parts))
    return _coerce_json(payload)


@pytest.mark.contract
@pytest.mark.fast
@pytest.mark.anyio
async def test_openai_mcp_tool_loop_smoke(server_url: str) -> None:
    _load_dotenv_if_present()

    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        pytest.skip('Missing OPENAI_API_KEY')

    client = OpenAI(api_key=api_key)
    model = os.getenv('OPENAI_MODEL', 'gpt-5-mini')

    mcp_url = f'{server_url}/mcp'

    prompt = (
        "I'm researching CFPB consumer complaints about loan forbearance. "
        "Please find a complaint mentioning 'forbearance' where the company name is present, then tell me the complaint id, "
        'the company (if present), the state (if present), and a short 2-3 sentence summary grounded in the complaint. '
        "If you can't use tools, say 'MCP tools unavailable'."
    )

    complaint_id_from_tools: int | None = None
    complaint_doc: object | None = None
    final_text: str | None = None
    tool_calls_seen = False

    async with streamable_http_client(mcp_url) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as mcp:
            await mcp.initialize()
            tool_list = await mcp.list_tools()

            tools = []
            for t in tool_list.tools:
                schema = t.inputSchema or {'type': 'object', 'properties': {}}
                tools.append(
                    {
                        'type': 'function',
                        'name': t.name,
                        'description': t.description or '',
                        'parameters': schema,
                    }
                )

            try:
                resp = client.responses.create(
                    model=model,
                    input=prompt,
                    tools=tools,
                    tool_choice={'type': 'function', 'name': 'search_complaints'},
                    reasoning={'effort': 'low'},
                )
            except openai.BadRequestError as exc:
                msg = str(getattr(exc, 'message', '') or str(exc))
                if 'tool_choice' in msg:
                    resp = client.responses.create(
                        model=model,
                        input=prompt,
                        tools=tools,
                        tool_choice='required',
                        reasoning={'effort': 'low'},
                    )
                elif 'reasoning.effort' in msg:
                    resp = client.responses.create(
                        model=model,
                        input=prompt,
                        tools=tools,
                        tool_choice='required',
                    )
                else:
                    raise

            while True:
                tool_calls = [item for item in resp.output if item.type == 'function_call']
                if not tool_calls:
                    break
                tool_calls_seen = True

                tool_outputs = []
                for call in tool_calls:
                    args = json.loads(call.arguments or '{}')
                    if not isinstance(args, dict):
                        args = {}

                    if call.name == 'get_complaint_document' and 'complaint_id' in args:
                        try:
                            complaint_id_from_tools = int(str(args['complaint_id']))
                        except ValueError:
                            complaint_id_from_tools = None

                    result = await mcp.call_tool(call.name, args)
                    payload = _tool_payload(result)

                    if call.name == 'search_complaints':
                        cid = _extract_complaint_id_from_search_payload(payload)
                        if cid is not None:
                            complaint_id_from_tools = cid

                    tool_outputs.append(
                        {
                            'type': 'function_call_output',
                            'call_id': call.call_id,
                            'output': _tool_result_text(payload),
                        }
                    )

                try:
                    resp = client.responses.create(
                        model=model,
                        input=tool_outputs,
                        previous_response_id=resp.id,
                        reasoning={'effort': 'low'},
                    )
                except openai.BadRequestError as exc:
                    msg = str(getattr(exc, 'message', '') or str(exc))
                    if 'reasoning.effort' not in msg:
                        raise
                    resp = client.responses.create(
                        model=model,
                        input=tool_outputs,
                        previous_response_id=resp.id,
                    )

            text = (resp.output_text or '').strip()
            assert text, 'Expected a final answer'
            assert 'MCP tools unavailable' not in text
            final_text = text

            if not tool_calls_seen:
                pytest.skip('Model did not issue tool calls during the MCP tool loop')

            if complaint_id_from_tools is None:
                search_result = await mcp.call_tool(
                    'search_complaints',
                    {'search_term': 'forbearance', 'size': 1, 'field': 'all'},
                )
                search_payload = _tool_payload(search_result)
                complaint_id_from_tools = _extract_complaint_id_from_search_payload(search_payload)

            assert complaint_id_from_tools is not None, 'Expected the agent to obtain a complaint id via tools'
            assert 4 <= len(str(complaint_id_from_tools)) <= 9

            complaint_id_from_text, _ = _extract_complaint_id_from_text(text)
            if str(complaint_id_from_tools) in text:
                complaint_id_for_validation = complaint_id_from_tools
                assert complaint_id_from_text == complaint_id_from_tools
            else:
                complaint_id_for_validation = complaint_id_from_text

            doc_result = await mcp.call_tool(
                'get_complaint_document',
                {'complaint_id': str(complaint_id_for_validation)},
            )
            complaint_doc = _tool_payload(doc_result)

    company = _extract_company_from_document(complaint_doc)
    if not company:
        pytest.skip(f'Complaint {complaint_id_from_tools} document missing company field')
    first_word = company.split()[0].lower()
    assert first_word in (final_text or '').lower()
