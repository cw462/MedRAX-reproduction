import json

def parse(raw):
    text=raw.strip()
    if text.startswith('```') and text.endswith('```'):
        text=text.split('\n',1)[1].rsplit('```',1)[0].strip()
    obj=json.loads(text)
    if not isinstance(obj,dict):raise ValueError('object_required')
    return obj

def answer(obj):
    # Ignore auxiliary fields; preserve explicit answer even when evidence labels are malformed.
    if isinstance(obj.get('answer'),str) and obj['answer'].strip() and len(obj['answer'])<=300:
        return {'answer':obj['answer'],'reason':obj.get('reason') if isinstance(obj.get('reason'),str) else '', 'status':'completed'}
    return None
