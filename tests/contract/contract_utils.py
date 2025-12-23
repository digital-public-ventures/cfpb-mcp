import json
import re


def extract_complaint_id_from_text(text: str) -> tuple[int, str]:
    matches = re.findall(r'\b\d{4,9}\b', text or '')
    assert matches, 'Expected a 4-9 digit integer token in the final response text'
    token = max(matches, key=len)
    assert 4 <= len(token) <= 9
    return int(token), token


def extract_company_from_document(doc: object) -> str:
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


def extract_complaint_id_from_search_payload(payload: object) -> int | None:
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


def coerce_json(payload: object) -> object:
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return payload
    return payload


def tool_result_text(payload: object) -> str:
    if payload is None:
        return ''
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False, default=str)


def tool_payload(result: object) -> object:
    payload = getattr(result, 'structuredContent', None) or getattr(result, 'content', None)
    if isinstance(payload, list):
        text_parts = []
        for item in payload:
            text = getattr(item, 'text', None)
            if text:
                text_parts.append(text)
        if text_parts:
            return coerce_json('\n'.join(text_parts))
    return coerce_json(payload)


def log(message: str) -> None:
    print(f'[contract] {message}', flush=True)
