import asyncio
import os
import time
from typing import cast

import pytest
from anthropic import Anthropic
from anthropic.types import (
    MessageParam,
    ToolChoiceParam,
    ToolResultBlockParam,
    ToolUseBlock,
)
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

from tests.contract.contract_prompts import SYSTEM_PROMPT, USER_PROMPT
from tests.contract.contract_utils import (
    extract_company_from_document,
    extract_complaint_id_from_search_payload,
    extract_complaint_id_from_text,
    tool_payload,
    tool_result_text,
)


async def _call_llm_with_timeout(func, timeout: float, **kwargs):
    return await asyncio.wait_for(asyncio.to_thread(func, **kwargs), timeout=timeout)


def _extract_text(blocks) -> str:
    if not isinstance(blocks, list):
        return str(blocks or '')
    parts = []
    for b in blocks:
        if getattr(b, 'type', None) == 'text' and hasattr(b, 'text'):
            parts.append(str(b.text))
    return '\n'.join([p for p in parts if p]).strip()


@pytest.mark.contract
@pytest.mark.fast
@pytest.mark.anyio
async def test_anthropic_mcp_tool_loop_smoke(server_url: str) -> None:
    api_key = os.getenv('ANTHROPIC_API_KEY')
    assert api_key, 'Missing ANTHROPIC_API_KEY'

    print('[anthropic-contract] initializing Anthropic client', flush=True)
    client = Anthropic(api_key=api_key, timeout=15.0)
    model = os.getenv('ANTHROPIC_MODEL', 'claude-haiku-4-5')

    # Use the Streamable HTTP endpoint
    mcp_url = f'{server_url}/mcp'
    print(f'[anthropic-contract] using model={model} mcp_url={mcp_url}', flush=True)

    user_prompt = USER_PROMPT

    final_text: str | None = None
    complaint_id_from_tools: int | None = None
    complaint_doc: object | None = None

    # Connect using Streamable HTTP client
    async with streamable_http_client(mcp_url) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as mcp:
            print('[anthropic-contract] initializing MCP session', flush=True)
            await mcp.initialize()
            tool_list = await mcp.list_tools()
            print(f'[anthropic-contract] loaded {len(tool_list.tools)} tools', flush=True)

            tools = []
            for t in tool_list.tools:
                tools.append(
                    {
                        'name': t.name,
                        'description': t.description or '',
                        'input_schema': t.inputSchema,
                    }
                )

            messages: list[MessageParam] = [{'role': 'user', 'content': user_prompt}]

            for step in range(10):
                print(f'[anthropic-contract] LLM step {step + 1}/10', flush=True)
                start = time.monotonic()
                # Encourage at least one tool call so this behaves like a
                # "first attempt" agent that must use MCP to answer.
                tool_choice: ToolChoiceParam = {'type': 'any'} if complaint_id_from_tools is None else {'type': 'auto'}
                resp = await _call_llm_with_timeout(
                    client.messages.create,
                    15,
                    model=model,
                    max_tokens=800,
                    system=SYSTEM_PROMPT,
                    tools=tools,
                    tool_choice=tool_choice,
                    messages=messages,
                )
                print(
                    f'[anthropic-contract] LLM response received in {time.monotonic() - start:.2f}s',
                    flush=True,
                )

                messages.append(cast('MessageParam', {'role': 'assistant', 'content': resp.content}))

                # tool_uses = [c for c in resp.content if getattr(c, "type", None) == "tool_use"]
                tool_uses: list[ToolUseBlock] = [c for c in resp.content if isinstance(c, ToolUseBlock)]

                if not tool_uses:
                    # Some responses may contain only thinking/metadata blocks.
                    # If we didn't get any visible text, ask explicitly for the final answer.
                    if _extract_text(resp.content):
                        break
                    messages.append(
                        cast(
                            'MessageParam',
                            {
                                'role': 'user',
                                'content': 'Please provide the final answer now (complaint id, company, state if present, and a 2-3 sentence grounded summary).',
                            },
                        )
                    )
                    continue

                for tu in tool_uses:
                    print(f'[anthropic-contract] calling tool {tu.name}', flush=True)
                    start = time.monotonic()
                    result = await asyncio.wait_for(mcp.call_tool(tu.name, tu.input), timeout=15)
                    print(
                        f'[anthropic-contract] tool {tu.name} completed in {time.monotonic() - start:.2f}s',
                        flush=True,
                    )

                    # Capture complaint id from tool interactions, so the test doesn't
                    # depend on regex guessing from final prose.
                    if (
                        tu.name == 'get_complaint_document'
                        and isinstance(tu.input, dict)
                        and 'complaint_id' in tu.input
                    ):
                        try:
                            complaint_id_from_tools = int(str(tu.input['complaint_id']))
                        except ValueError:
                            complaint_id_from_tools = None
                    elif tu.name == 'search_complaints':
                        payload = tool_payload(result)
                        cid = extract_complaint_id_from_search_payload(payload)
                        if cid is not None:
                            complaint_id_from_tools = cid

                    tool_payload_result = tool_payload(result)
                    tool_block = cast(
                        'ToolResultBlockParam',
                        {
                            'type': 'tool_result',
                            'tool_use_id': tu.id,
                            'content': tool_result_text(tool_payload_result),
                        },
                    )
                    messages.append(cast('MessageParam', {'role': 'user', 'content': [tool_block]}))

            last_assistant = next((m for m in reversed(messages) if m.get('role') == 'assistant'), None)
            assert last_assistant is not None
            text = _extract_text(last_assistant.get('content'))
            assert text
            assert 'MCP tools unavailable' not in text

            final_text = text

            assert complaint_id_from_tools is not None, 'Expected the agent to obtain a complaint id via tools'
            assert 4 <= len(str(complaint_id_from_tools)) <= 9
            assert str(complaint_id_from_tools) in text

            # Keep the original "must contain a 4-9 digit integer" guard, but validate
            # it matches the tool-derived complaint id for stability.
            complaint_id, _ = extract_complaint_id_from_text(text)
            if complaint_id != complaint_id_from_tools:
                messages.append(
                    cast(
                        'MessageParam',
                        {
                            'role': 'user',
                            'content': (
                                f'Please correct the final answer using complaint id {complaint_id_from_tools} '
                                'from the MCP tools. Provide the final answer now.'
                            ),
                        },
                    )
                )
                resp = await _call_llm_with_timeout(
                    client.messages.create,
                    15,
                    model=model,
                    max_tokens=800,
                    system=SYSTEM_PROMPT,
                    tools=tools,
                    tool_choice={'type': 'auto'},
                    messages=messages,
                )
                messages.append(cast('MessageParam', {'role': 'assistant', 'content': resp.content}))
                text = _extract_text(resp.content)
                assert text
                final_text = text
                complaint_id, _ = extract_complaint_id_from_text(text)

            assert complaint_id == complaint_id_from_tools

            print('[anthropic-contract] fetching complaint document', flush=True)
            doc_result = await asyncio.wait_for(
                mcp.call_tool('get_complaint_document', {'complaint_id': str(complaint_id_from_tools)}),
                timeout=15,
            )
            complaint_doc = tool_payload(doc_result)

    assert final_text is not None
    assert complaint_id_from_tools is not None

    company = extract_company_from_document(complaint_doc)
    assert company, f'Complaint {complaint_id_from_tools} document missing company field'
    first_word = company.split()[0].lower()
    assert first_word in final_text.lower()
