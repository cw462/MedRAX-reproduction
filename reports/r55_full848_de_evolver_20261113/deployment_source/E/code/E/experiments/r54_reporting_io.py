"""Receipt I/O copied from established local reporting functions.
No R50 module/run import, historical scoring, labels or API execution.
"""
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path
from online_memory_r49 import read

def utc(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('timestamp_requires_timezone')
    return parsed.astimezone(timezone.utc)

def closed_calls(folder):
    calls = sorted((p for p in folder.iterdir() if p.is_dir()), key=lambda p: int(p.name)) if folder.exists() else []
    if [int(p.name) for p in calls] != list(range(1, len(calls)+1)):
        raise ValueError('noncontiguous_calls:' + str(folder))
    values = []
    for call in calls:
        if any(not (call/name).is_file() for name in ('request.json', 'started.json', 'response.json', 'result.json')):
            raise ValueError('unclosed_request:' + str(call))
        started, receipt = read(call/'started.json'), read(call/'result.json')
        if (receipt.get('error') or receipt.get('response_received') is not True
                or started.get('request_id') != receipt.get('request_id')
                or utc(started['utc']) > utc(receipt['utc'])):
            raise ValueError('unhealthy_request_receipt:' + str(call))
        values.append((call, started, receipt))
    return values

def response_text(call):
    message = read(call/'response.json')['choices'][0]['message']
    value = message.get('content')
    if isinstance(value, list):
        value = '\n'.join(item.get('text', '') for item in value
                          if isinstance(item, dict) and item.get('type') == 'text')
    return value if isinstance(value, str) and not (message.get('tool_calls') or message.get('function_call')) else None

def receipt_resources(values):
    records = [value[2] for value in values]
    known = [Decimal(str(value['settlement']['charged_cny'])) for value in records
             if value.get('settlement', {}).get('charged_cny') is not None]
    return {'requests': len(records), 'returned_models': sorted({v['model_returned'] for v in records if v.get('model_returned')}),
            'prompt_tokens': sum((v.get('usage') or {}).get('prompt_tokens', 0) or 0 for v in records),
            'completion_tokens': sum((v.get('usage') or {}).get('completion_tokens', 0) or 0 for v in records),
            'cached_tokens': sum(((v.get('usage') or {}).get('prompt_tokens_details') or {}).get('cached_tokens', 0) or 0 for v in records),
            'usage_cost_cny_proxy_known': str(sum(known, Decimal(0))), 'cost_unknown_count': len(records)-len(known),
            'elapsed_seconds_known': sum(v.get('elapsed_s') or 0 for v in records),
            'elapsed_unknown_count': sum(v.get('elapsed_s') is None for v in records), 'provider_invoice': False}
