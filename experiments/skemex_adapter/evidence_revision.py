"""Opt-in tools-v2 evidence contracts; no API, labels, or filesystem access."""
from copy import deepcopy
import json
import re

from v12_evidence import question_parts

VERSION = 'tools-v2'
RUN_ID = 'skemex_tools_v2_20261104'
TOOL_CONTRACT = '''Tool limits override retrieved experience. Tools are optional, even for CXR.
The chest X-ray classifier accepts confirmed CXR only, never CT/MRI. Its finding scores
are not calibrated probabilities, severity measurements, or longitudinal change scores.
Do not infer severity or progression from differences in classifier scores. No strong
finding does not imply normality. The report generator receives one image only, with
no prior/timepoint; its interval/change claims are unsupported. Changes must be checked
against original images with timepoints explicitly bound by the question. Filenames,
image order, and single-image reports cannot establish chronology. If the question does
not bind timepoints, report that uncertainty; do not invent a before/after assignment.
Tool invocation is not itself evidence. Decline irrelevant tools. Identify contradictions
and prefer supported original-image evidence; do not assume either tool is authoritative.
Learn a concrete discriminating check and its limitations, not a mandatory tool rule.'''

ANSWER_CONTRACT = '''Return one strict JSON object, no markdown:
{"answer":"one legal letter","option_text":"verbatim complete text of that original option","reason":"concise evidence summary"}.
Before submitting, check that answer, option_text and the clinical conclusion in reason
refer to the same option. Copy option_text exactly, preserving internal newlines as JSON
escapes. No second answer, repair call or reinterpretation of the letter is allowed.'''


def parse_bound_answer(raw, options):
    """Enforce letter/text binding, retaining invalid raw output without repairing it."""
    try:
        value = json.loads(raw)
        if not isinstance(value, dict) or set(value) != {'answer', 'option_text', 'reason'}:
            raise ValueError('answer_fields')
        letter = value['answer']
        if not isinstance(letter, str) or letter not in options:
            raise ValueError('illegal_letter')
        if value['option_text'] != options[letter]:
            raise ValueError('letter_option_text_mismatch')
        if not isinstance(value['reason'], str) or not value['reason'].strip():
            raise ValueError('missing_reason')
    except (TypeError, ValueError) as exc:
        return {'answer': None, 'status': 'unparsed', 'parser_rule': 'bound-option-v2',
                'answer_contract_error': str(exc)}
    return {'answer': letter, 'status': 'completed', 'parser_rule': 'bound-option-v2',
            'option_text': value['option_text'], 'answer_contract_error': None}


def reflection_steps(row, prediction, reference, raw_tool_returns=None):
    """Called ONLY after case-level feedback release, never by the actor/target."""
    stem, options = question_parts(row['question'])
    if reference not in options:
        raise ValueError('source_reference_not_in_options')
    letter = prediction.get('answer')
    context = {'full_question_and_options': row['question'], 'stem': stem, 'options': options,
               'old_answer_letter': letter, 'old_answer_text': options.get(letter),
               'old_raw_response': prediction.get('raw_response'),
               'correct_answer_letter': reference, 'correct_answer_text': options[reference],
               'original_image_bindings': row['images'],
               'tool_observations': prediction.get('tool_observations', []),
               'raw_tool_returns_for_source_review': raw_tool_returns or [],
               'limitations': TOOL_CONTRACT,
               'instruction': 'These are source-only supervised facts, not agent reasoning. '
                   'Compare old and correct option meanings; distinguish evidence errors from '
                   'letter mapping errors. Do not invent a medical explanation from a letter. '
                   'Generalize checks, never memorize this question, options or reference.'}
    # Official _format_steps does not truncate action_input (observation IS truncated).
    # Use the actual serialized input channel, not the unused Trajectory.query field.
    steps = [{'step': 0, 'action': 'source_feedback_context', 'action_input': context}]
    steps.extend(deepcopy(prediction.get('trajectory_steps') or []))
    return steps


_TEMPORAL = re.compile(r'\b(?:interval|improv\w*|worsen\w*|increas\w*|decreas\w*|'
    r'progress\w*|resolv\w*|resolution|previous\w*|prior|unchanged|stable|new|'
    r'compar\w*|persist\w*|remain\w*|again|recurrent|reduc\w*)\b', re.I)


def report_projection(report):
    """Conservatively withhold whole temporal clauses; raw report stays in tool cache."""
    chunks = re.split(r'(?<=[.!?;])\s+|\n+', str(report))
    kept, withheld = [], []
    for chunk in chunks:
        if not chunk.strip():
            continue
        (withheld if _TEMPORAL.search(chunk) else kept).append(chunk)
    return {'static_report': '\n'.join(kept)[:10000],
            'truncated': len('\n'.join(kept)) > 10000,
            'withheld_temporal_clause_count': len(withheld),
            'chronology_evidence': False,
            'note': 'Single-image output, no prior supplied. Temporal clauses withheld. '
                    'Remaining text is unverified and can still contradict pixels or itself.'}


def skill_policy_rejection(text):
    """Narrow deterministic backstop, not a medical truth/semantic quality verifier."""
    normalized=text.lower().replace('_', ' ')
    has_classifier=bool(re.search(r'classif|xrv|分类器|分类分', normalized))
    for sentence in re.split(r'[.!?;\n]+', normalized):
        # Safe limitation statements must remain learnable.
        if re.search(r'\b(?:not|never|cannot|avoid|without|unsupported|uncalibrated)\b|不得|不能|不要|并非', sentence):
            continue
        classifier = has_classifier
        if classifier and re.search(r'severity|严重程度|严重度', sentence):
            return 'classifier_score_not_severity'
        if classifier and re.search(r'\bcts?\b|\bmri\b|computed tomography|magnetic resonance', sentence):
            return 'CXR_classifier_not_CT_MRI'
        if re.search(r'mandatory.*tool|(?:must|always|required).*?(?:call|invok|use).*tool|必须.*工具', sentence):
            return 'mandatory_tool_rule'
    return None


def require_safe_library(store):
    """Check newly created/merged content before it can be retrieved; never edit it."""
    for skill in store.list_skills(statuses=['active', 'mature']):
        if skill.branch == 'meta_memory':
            continue
        text = ' '.join(str(getattr(skill, k, '')) for k in
                        ('name', 'description', 'applicable_conditions', 'body'))
        reason = skill_policy_rejection(text)
        if reason:
            raise ValueError('new_library_policy:' + skill.id + ':' + reason)
