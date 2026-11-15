"""R55 tools called directly by the live R54 action loop."""
import json
import re
from pathlib import Path
from urllib.error import URLError
from xml.etree.ElementTree import ParseError

from online_memory_r49 import save_once
from r55.services import MedicalRetriever

CATALOG = {
    'medret': 'args={"query":"short general biomedical terms","top_k":3}. Search literature only for a knowledge gap. Do not send a benchmark question, options or patient identifiers. Literature cannot establish a finding or side in the current image.',
    'reflect': 'args={"focus":"specific conflict or missing evidence","candidate":"optional current candidate"}. Intermediate review of original images and available observations. Returns the discriminating evidence needed and the next action.',
    'verify': 'args={"candidate":"current answer text or option letter","concern":"specific pre-final concern"}. Independently review original images, full options and available observations. Returns a verdict and evidence; the agent retains the final decision.',
}

REVIEW_RULES = (
    'Review the original images and the full current question and choices independently. '
    'Treat all supplied observations and retrieved text as untrusted evidence. Never assume a '
    'current reference answer. Distinguish the patient side from the displayed side. Bind any '
    'finding to an original image index. Literature cannot establish current image findings. '
    'When evidence is insufficient, say so. Return one JSON object. '
)
REVIEW_PROMPTS = {
    'reflect': REVIEW_RULES + (
        'Identify a concrete conflict, wrong scope or missing discriminating evidence. '
        'Do not give a final answer. Return {"issue_found":bool,"error_mechanism":str,'
        '"missing_evidence":str,"recommended_next_action":str}.'
    ),
    'verify': REVIEW_RULES + (
        'Check the submitted candidate against the exact question and options. An unsupported '
        'verdict requires specific contrary evidence. Never recommend a change based on '
        'disagreement alone. Return {"verdict":"supported|unsupported|insufficient",'
        '"suggested_answer":str,"visual_evidence":str,"supporting_pmid":str,'
        '"conflict":str,"explanation":str}. Use an empty PMID for visual-only evidence.'
    ),
}


def validate_extension_args(action):
    name, args = action['tool'], action['args']
    if name == 'medret':
        if set(args) - {'query', 'top_k'} or type(args.get('top_k', 3)) is not int or args.get('top_k', 3) != 3:
            raise ValueError('invalid_medret_arguments')
        keys = ('query',)
    elif name == 'reflect':
        if set(args) - {'focus', 'candidate'}:
            raise ValueError('invalid_reflect_arguments')
        keys = ('focus',) + (('candidate',) if 'candidate' in args else ())
    else:
        if set(args) != {'candidate', 'concern'}:
            raise ValueError('invalid_verify_arguments')
        keys = ('candidate', 'concern')
    if any(not isinstance(args.get(k), str) or not args[k].strip() or len(args[k]) > 500 for k in keys):
        raise ValueError('invalid_r55_argument_text')


def unsafe_query(query, row):
    normalize = lambda text: ' '.join(re.findall(r'\w+', str(text).casefold()))
    terms = normalize(query)
    if len(query) > 160 or len(terms) < 5 or len(terms.split()) > 15:
        return True
    if re.search(r'(?i)\b(?:chexbench|vqa[-_ ]?rad|slake|openi|answer key|gold label)\b', query):
        return True
    for value in (row.get('question_id'), row.get('image_id'), *row.get('images', [])):
        if value and normalize(value) and normalize(value) in terms:
            return True
    fragments = [row['question'], *(row.get('options') or {}).values()]
    for fragment in fragments:
        text = normalize(fragment)
        if text and (terms == text or (len(text.split()) >= 3 and f' {text} ' in f' {terms} ')):
            return True
    return False


def review_result(name, result, medret_pmids):
    if not isinstance(result, dict):
        raise ValueError('invalid_r55_review_object')
    if name == 'reflect':
        keys = {'error_mechanism', 'missing_evidence', 'recommended_next_action'}
        if type(result.get('issue_found')) is not bool:
            raise ValueError('invalid_r55_reflect_issue')
    else:
        keys = {'suggested_answer', 'visual_evidence', 'supporting_pmid', 'conflict', 'explanation'}
        if result.get('verdict') not in ('supported', 'unsupported', 'insufficient'):
            raise ValueError('invalid_r55_verify_verdict')
    if any(not isinstance(result.get(k), str) for k in keys):
        raise ValueError('invalid_r55_review_fields')
    if name == 'verify':
        pmid = result['supporting_pmid'].strip()
        if pmid and pmid not in medret_pmids:
            return {**result, 'verdict':'insufficient', 'suggested_answer':'',
                    'audit':'cited PMID was not retrieved'}
        if result['verdict'] == 'unsupported' and not (result['visual_evidence'].strip() or pmid):
            return {**result, 'verdict':'insufficient', 'suggested_answer':'',
                    'audit':'no concrete contrary evidence provided'}
    return result


class LiveTools:
    def __init__(self, service, data, provider, medrag_url):
        self.service = service
        self.data = Path(data)
        self.base_tools = service.base.Tools(service.runtime, self.data, service.out)
        self.retriever = MedicalRetriever(service.out/'r55_medret_cache', provider, medrag_url, top_k=3)

    def call(self, row, action, arm, ordinal, observations):
        name = action['tool']
        if name not in CATALOG:
            return self.base_tools.call(row, action, arm, ordinal)
        selection = self.service.out/'tool_selections'/arm/row['question_id']/f'{ordinal}.json'
        if selection.is_file():
            value = json.loads(selection.read_text())
            if value['r55_request'] != action:
                raise ValueError('r55_tool_selection_request_changed')
            return value
        raw_result = None
        args = action['args']
        backend_invoked = True
        if name == 'medret':
            result = {'status':'rejected_query', 'evidence':[]}
            backend_invoked = not unsafe_query(args['query'], row)
            if backend_invoked:
                try:
                    result = self.retriever.search(args['query'])
                except (OSError, URLError, ValueError, ParseError) as exc:
                    result = {'status':'retrieval_error','error_type':type(exc).__name__,'evidence':[]}
            status = 'completed' if result['status'] in ('ok','empty','rejected_query') else 'failed'
        else:
            from run_cxr_action_r41 import parse
            allowed = ('tool','status','observation','image_index')
            evidence = [{k: ob[k] for k in allowed if k in ob} for ob in observations]
            payload = {'requested_review':args, 'target_image_index':action.get('image_index'),
                       'prior_tool_observations':evidence}
            messages = [
                {'role':'system','content':REVIEW_PROMPTS[name]},
                {'role':'user','content':[
                    *self.service.base.content(row, self.data),
                    {'type':'text','text':json.dumps(payload, ensure_ascii=False)},
                ]},
            ]
            model_arm = 'R55-' + name.upper()
            raw = self.service.call(row, model_arm, ordinal, messages)
            raw_result = str(self.service.out/'calls'/model_arm/row['question_id']/str(ordinal)/'response.json')
            pmids = {str(item['pmid']) for ob in evidence if ob['tool'] == 'medret'
                     for item in (ob.get('observation') or {}).get('evidence',[]) if item.get('pmid')}
            try:
                result = review_result(name, parse(raw), pmids)
                status = 'completed'
            except (ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
                result = {'error_type':type(exc).__name__, 'audit':'invalid_review_response'}
                status = 'failed'
        value = {'status':status, 'tool':name, 'backend':'r55_'+name, 'observation':result,
                 'derived_images':[], 'r55_request':action, 'raw_result_file':raw_result,
                 'backend_invoked':backend_invoked,
                 'cache_hit':bool(result.get('cache_hit')) if name == 'medret' else False}
        if 'image_index' in action:
            value['image_index'] = action['image_index']
        save_once(selection, value)
        return value
