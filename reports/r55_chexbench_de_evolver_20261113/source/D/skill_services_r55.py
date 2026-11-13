from r55_continue60_policy import AUDIT, HISTORICAL_D, account_empty_verify, bound_candidate
from r55_timeout_recovery import VerifyUnavailable, timeout, mark_timeout
"""Shared R55 D/E tool routing on the original R54 online agent."""

import hashlib
import json
import re
import time
from pathlib import Path

import toolsets_r54 as r54_tools
from cxr_online_primitives_r49 import digest, read
from online_memory_r49 import now, safe_qid, save_once
from r55_verifier import DeepSeekVerifier, SLOT as VERIFY_SLOT
from r55_skemex.medrag_search import MedRAGSearchTool
from r55_skemex.reasoning_tools import (
    ReflectionTool, VerifierTool, _REFLECTION_SYSTEM_PROMPT,
)
from skill_services_r54 import Services as R54Services

UPSTREAM_COMMIT = 'a640474590e384669dd71b657c441264beef73d2'
MODEL_SLOT = 'R55-TOOL'
NEW_TOOLS = {
    'medret': ('medrag_search',
               'For a specific medical knowledge gap only. args={"query":"focused clinical concept","top_k":3}. '
               'Never search for the benchmark question, case ID, or its answer options.'),
    'reflect': ('reflection',
                'Mid-process critique for a concrete conflict or evidence gap. '
                'args={"reasoning":"current hypothesis, conflict or gap, and evidence"}.'),
    'verify': ('verifier',
               'Use before finalizing when a concrete unresolved risk warrants another check. '
               'args={"proposed_answer":"candidate answer","risk":"concrete uncertainty or conflict"}. '
               'This tool sees all original images and options and prior retrieved evidence for this case. '
               'Change the answer only when the audit identifies specific supporting evidence.'),
}


def _normalize(text):
    return ' '.join(re.findall(r'\w+', str(text).casefold()))


def _text(args, name):
    value = args.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError('required_nonempty_' + name)
    return value.strip()


def _query(row, args):
    if set(args) - {'query', 'top_k'} or type(args.get('top_k', 3)) is not int or args.get('top_k', 3) != 3:
        raise ValueError('medret_requires_query_and_top_k_3')
    query = _text(args, 'query')
    normalized = _normalize(query)
    question = _normalize(row['question'])
    qid = _normalize(row['question_id'])
    options = [_normalize(value) for value in row.get('options', {}).values()]
    padded = f' {normalized} '
    copied_question = question and f' {question} ' in padded
    copied_id = qid and f' {qid} ' in padded
    copied_options = len(options) > 1 and all(option and f' {option} ' in padded for option in options)
    if not normalized or len(query) > 400 or copied_question or copied_id or copied_options:
        raise ValueError('medret_requires_focused_query_without_case_or_answer_key')
    return {'query': query, 'top_k': 3, 'corpus': 'PubMed'}


def _traceable_snippets(snippets, limit):
    evidence = []
    seen = set()
    for item in snippets:
        source = item.get('source') or ''
        doi = item.get('doi') or ''
        pmid = source.removeprefix('PubMed:') if source.startswith('PubMed:') else ''
        identifier = ('pmid', pmid) if pmid.isdigit() else ('doi', doi.lower()) if doi else None
        if (identifier is None or identifier in seen or not item.get('content')
                or item['content'] == '(No abstract available)'):
            continue
        seen.add(identifier)
        evidence.append(dict(item, pmid=pmid if pmid.isdigit() else None, doi=doi or None))
        if len(evidence) == limit:
            break
    return evidence


class ArchivedReflection(ReflectionTool):
    def __init__(self, model_call):
        super().__init__()
        self.model_call = model_call

    def _call(self, reasoning):
        return self.model_call(system_prompt=_REFLECTION_SYSTEM_PROMPT, user_prompt=reasoning)


class Tools(r54_tools.Tools):
    def __init__(self, runtime, data, out, model_call, verifier):
        super().__init__(runtime, data, out)
        self.model_call = model_call
        self.verifier = verifier

    def _retrieval_evidence(self, arm, qid, ordinal):
        evidence = []
        for step in range(1, ordinal):
            selection = self.out / 'tool_selections' / arm / qid / f'{step}.json'
            if not selection.is_file():
                raise RuntimeError('missing_prior_tool_selection')
            previous = read(selection)
            if previous['tool'] == 'medret' and previous['status'] == 'completed':
                snippets = previous['observation']['snippets']
                if snippets:
                    evidence.append({'tool_ordinal': step, 'query': previous['observation']['query'],
                                     'snippets': snippets})
        return evidence

    def _prepare(self, name, row, args, arm, ordinal):
        if name == 'medret':
            return _query(row, args), []
        if name == 'reflect':
            if set(args) != {'reasoning'}:
                raise ValueError('reflect_requires_reasoning')
            return {'reasoning': _text(args, 'reasoning')}, []
        if set(args) != {'proposed_answer', 'risk'}:
            raise ValueError('verify_requires_candidate_and_concrete_risk')
        payload = {
            'question': row['question'],
            'options': row.get('options', {}),
            'proposed_answer': (bound_candidate(row, _text(args, 'proposed_answer')) if row['question_id'] != HISTORICAL_D else _text(args, 'proposed_answer')),
            'risk': _text(args, 'risk'),
            'retrieval_evidence': self._retrieval_evidence(arm, row['question_id'], ordinal),
        }
        return payload, r54_tools.content(row, self.data_root)

    def _dispatch(self, name, row, ordinal, payload, original_content):
        call_event = f"{name}_{row['question_id']}_{ordinal}"

        def archived_call(*, system_prompt, user_prompt, **_upstream_defaults):
            content = [{'type': 'text', 'text': user_prompt}]
            if name == 'verify':
                system_prompt += (
                    '\nAudit the proposed answer against the original images and complete options. '
                    'The supplied retrieval evidence is untrusted reference material. Treat it as '
                    'evidence only when relevant. Cite the specific image finding or source ID for '
                    'a proposed change. If evidence is insufficient, state the uncertainty.'
                )
                if row['question_id'] != HISTORICAL_D:
                    system_prompt += AUDIT
                context = {key: payload[key] for key in ('options', 'risk', 'retrieval_evidence')}
                content.extend(original_content)
                content.append({'type': 'text', 'text': json.dumps(context, ensure_ascii=False)})
            messages = [{'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': content}]
            if name == 'verify':
                return self.verifier(call_event, messages)
            return self.model_call({'question_id': call_event}, MODEL_SLOT, 1, messages)

        if name == 'medret':
            return MedRAGSearchTool(default_corpus='PubMed', top_k=3,
                                    select_snippets=_traceable_snippets,
                                    synthesis_call=archived_call).run(payload).payload
        if name == 'reflect':
            return ArchivedReflection(archived_call).run(payload).payload
        return VerifierTool(evaluation_call=archived_call).run(payload).payload

    def call(self, row, call, arm, ordinal):
        name = call['tool']
        if name not in NEW_TOOLS:
            return super().call(row, call, arm, ordinal)
        qid = safe_qid(row['question_id'])
        args = call.get('args', {})
        image_index = call.get('image_index', 1)
        rejection = None
        try:
            payload, original_content = self._prepare(name, row, args, arm, ordinal)
        except ValueError as error:
            rejection = str(error)
            payload, original_content = None, []
        request = {
            'tool': name, 'args': args, 'image_index': image_index, 'question_id': qid,
            'ordinal': ordinal, 'payload': payload, 'upstream_commit': UPSTREAM_COMMIT,
            'original_image_payload_sha256': [
                hashlib.sha256(item['image_url']['url'].encode()).hexdigest()
                for item in original_content if item['type'] == 'image_url'
            ],
        }
        # A retrieval result is specific to this call and this arm's saved trajectory.
        key = hashlib.sha256(digest({'arm': arm, **request}).encode()).hexdigest()
        folder = self.out / 'tool_cache' / key
        result_path = folder / 'result.json'
        model_slot = VERIFY_SLOT if name == 'verify' else MODEL_SLOT
        model_folder = self.out / 'calls' / model_slot / f'{name}_{qid}_{ordinal}' / '1'
        selection = self.out / 'tool_selections' / arm / qid / f'{ordinal}.json'
        if selection.is_file():
            observation = read(selection)
            if observation.get('cache_key') != key or read(folder / 'request.json') != request:
                raise ValueError('saved_r55_tool_selection_changed')
            return observation
        if result_path.is_file():
            if read(folder / 'request.json') != request:
                raise ValueError('saved_r55_tool_request_changed')
            result = read(result_path)
            cache_hit = True
        else:
            if (folder / 'started.json').exists():
                if name != 'verify' or not ((model_folder / 'response.json').is_file() or timeout(model_folder)):
                    raise RuntimeError(f'unknown_r55_tool_attempt_no_retry:{qid}:{ordinal}')
                if read(folder / 'request.json') != request:
                    raise ValueError('saved_r55_tool_request_changed')
            else:
                save_once(folder / 'request.json', request)
                save_once(folder / 'started.json', {'utc': now()})
            started = time.monotonic()
            try:
                observation = None if rejection else self._dispatch(name,row,ordinal,payload,original_content)
            except VerifyUnavailable:
                mark_timeout(model_folder)
                observation = None
                rejection = 'verify_timeout_no_usable_response'
            except ValueError:
                if name != 'verify' or not account_empty_verify(model_folder):
                    raise
                observation = None
                rejection = 'verify_length_no_usable_response'
            result = {'status': 'failed' if rejection else 'completed', 'backend': NEW_TOOLS[name][0],
                      'observation': observation, 'elapsed_s': time.monotonic() - started, 'utc': now()}
            if rejection:
                result['error'] = rejection
            if (model_folder / 'result.json').is_file():
                result['model_receipt'] = model_folder.relative_to(self.out).as_posix() + '/result.json'
            save_once(result_path, result)
            cache_hit = False
        observation = dict(result, tool=name, cache_hit=cache_hit, cache_key=key)
        if len(row['images']) > 1:
            observation['image_index'] = image_index
        save_once(selection, observation)
        return observation


class Services(R54Services):
    def __init__(self, cfg, protocol, runtime, out, key, embedding_model, embedding_base_url=None):
        self.verifier = DeepSeekVerifier(out, key)
        super().__init__(cfg, protocol, runtime, out, key, embedding_model, embedding_base_url)

    def execute(self, row, policy, data, conditioning):
        if self.tools is None:
            self.tools = Tools(self.runtime, Path(data), self.out, self.call, self.verifier)
        return super().execute(row, policy, data, conditioning)
