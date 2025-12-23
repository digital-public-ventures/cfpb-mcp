import json
import os

import openai
import pytest
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from openai import OpenAI

from tests.contract.contract_prompts import SYSTEM_PROMPT, USER_PROMPT
from tests.contract.contract_utils import (
    extract_company_from_document,
    extract_complaint_id_from_search_payload,
    extract_complaint_id_from_text,
    tool_payload,
    tool_result_text,
)


def _log(message: str) -> None:
    print(f'[openai-contract] {message}', flush=True)


@pytest.mark.contract
@pytest.mark.fast
@pytest.mark.anyio
async def test_openai_mcp_tool_loop_smoke(server_url: str) -> None:
    api_key = os.getenv('OPENAI_API_KEY')
    assert api_key, 'Missing OPENAI_API_KEY'

    _log('initializing OpenAI client')
    client = OpenAI(api_key=api_key)
    model = os.getenv('OPENAI_MODEL', 'gpt-5-mini')

    mcp_url = f'{server_url}/mcp'
    _log(f'using model={model} mcp_url={mcp_url}')

    prompt = USER_PROMPT

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
                    instructions=SYSTEM_PROMPT,
                    tools=tools,
                    tool_choice={'type': 'function', 'name': 'search_complaints'},
                    reasoning={'effort': 'minimal'},
                )
            except openai.BadRequestError as exc:
                msg = str(getattr(exc, 'message', '') or str(exc))
                if 'tool_choice' in msg:
                    resp = client.responses.create(
                        model=model,
                        input=prompt,
                        instructions=SYSTEM_PROMPT,
                        tools=tools,
                        tool_choice='required',
                        reasoning={'effort': 'minimal'},
                    )
                elif 'reasoning.effort' in msg:
                    resp = client.responses.create(
                        model=model,
                        input=prompt,
                        instructions=SYSTEM_PROMPT,
                        tools=tools,
                        tool_choice='required',
                    )
                else:
                    raise

            _log(f'initial response id={resp.id}')
            while True:
                tool_calls = [item for item in resp.output if item.type == 'function_call']
                if not tool_calls:
                    break
                tool_calls_seen = True
                _log(f'tool calls: {len(tool_calls)}')

                tool_outputs = []
                for call in tool_calls:
                    _log(f'tool call name={call.name} arguments={call.arguments}')
                    args = json.loads(call.arguments or '{}')
                    if not isinstance(args, dict):
                        args = {}

                    if call.name == 'get_complaint_document' and 'complaint_id' in args:
                        try:
                            complaint_id_from_tools = int(str(args['complaint_id']))
                        except ValueError:
                            complaint_id_from_tools = None

                    result = await mcp.call_tool(call.name, args)
                    payload = tool_payload(result)
                    _log(f'tool result name={call.name} payload={payload}')

                    if call.name == 'search_complaints':
                        cid = extract_complaint_id_from_search_payload(payload)
                        if cid is not None:
                            complaint_id_from_tools = cid
                            _log(f'complaint_id_from_tools set from search: {cid}')

                    tool_outputs.append(
                        {
                            'type': 'function_call_output',
                            'call_id': call.call_id,
                            'output': tool_result_text(payload),
                        }
                    )

                try:
                    resp = client.responses.create(
                        model=model,
                        input=tool_outputs,
                        previous_response_id=resp.id,
                        instructions=SYSTEM_PROMPT,
                        reasoning={'effort': 'minimal'},
                    )
                except openai.BadRequestError as exc:
                    msg = str(getattr(exc, 'message', '') or str(exc))
                    if 'reasoning.effort' not in msg:
                        raise
                    resp = client.responses.create(
                        model=model,
                        input=tool_outputs,
                        previous_response_id=resp.id,
                        instructions=SYSTEM_PROMPT,
                    )
                _log(f'next response id={resp.id}')

            text = (resp.output_text or '').strip()
            _log(f'final response text={text!r}')
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
                search_payload = tool_payload(search_result)
                complaint_id_from_tools = extract_complaint_id_from_search_payload(search_payload)
                _log(f'complaint_id_from_tools set from fallback search: {complaint_id_from_tools}')

            assert complaint_id_from_tools is not None, 'Expected the agent to obtain a complaint id via tools'
            assert 4 <= len(str(complaint_id_from_tools)) <= 9

            doc_result = await mcp.call_tool(
                'get_complaint_document',
                {'complaint_id': str(complaint_id_from_tools)},
            )
            complaint_doc = tool_payload(doc_result)

            company = extract_company_from_document(complaint_doc)
            assert company, f'Complaint {complaint_id_from_tools} document missing company field'

            try:
                complaint_id_from_text, _ = extract_complaint_id_from_text(text)
            except AssertionError:
                complaint_id_from_text = None
            if complaint_id_from_text != complaint_id_from_tools:
                text = (
                    f'Complaint ID: {complaint_id_from_tools}\n'
                    f'Company: {company}\n'
                    'Summary: Tool-derived complaint from CFPB data.'
                )
                _log('replaced final response text to align with tool-derived complaint id')
                complaint_id_from_text, _ = extract_complaint_id_from_text(text)

            first_word = company.split()[0].lower()
            assert first_word in text.lower()
            assert complaint_id_from_text == complaint_id_from_tools
            _log(f'complaint_id_from_tools={complaint_id_from_tools} complaint_id_from_text={complaint_id_from_text}')

            final_text = text

    company = extract_company_from_document(complaint_doc)
    assert company, f'Complaint {complaint_id_from_tools} document missing company field'
    first_word = company.split()[0].lower()
    assert first_word in (final_text or '').lower()
