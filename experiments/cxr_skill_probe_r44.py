"""One fixed task-checking Skill, isolated from references and API transport."""
import base64
import json
from pathlib import Path

EXPERIMENT = 'skill_probe_r44_20261108'
BASE = ('Answer the current visual question using the supplied original image. '
        'Give only the shortest direct answer: yes or no for a binary question, '
        'or the named category requested by the question. Do not give an explanation. '
        'If the image does not support a determination, answer Unknown. '
        'No patient history or previous examination is supplied.')
ARMS = ('P0', 'P1')


def rows(path):
    return [json.loads(x) for x in Path(path).read_text(encoding='utf-8').splitlines() if x.strip()]


def protocol(skill, inputs):
    assert len(inputs) == len({x['question_id'] for x in inputs}) == 27
    return {
        'experiment_id':EXPERIMENT, 'model':'qwen3.7-plus', 'temperature':0.2,
        'top_p':1.0, 'enable_thinking':False, 'max_output_tokens':256,
        'arms':{'P0':'one-shot direct control', 'P1':'same one-shot input plus fixed task-checking Skill'},
        'main_call_limits':{arm:1 for arm in ARMS}, 'tool_call_limits':{arm:0 for arm in ARMS},
        'questions_per_arm':27, 'images_per_arm':8, 'new_main_request_ceiling':54,
        'new_tool_calls':0, 'request_archive':'image_base64_content_addressed_v1',
        'budget':{'existing_shared_ledger':False, 'enforce_money_cap':False},
        'control_system':BASE, 'skill_text':skill,
        'question_ids':[x['question_id'] for x in inputs],
        'pair_order':'ascending official qid; even pair index P0/P1, odd P1/P0',
        'primary_metric':'M4CXR normalized answer exact match via existing common explicit-answer adapter',
        'secondary':['word-set recall','corrections/harms','per-category accuracy','paired image-cluster interval'],
        'json_schema_is_primary_gate':False, 'development_references_read_by_runner':False,
        'technical_failure':'stop the whole run; preserve send intent and response; never retry unknown sent',
        'invalid_output':'retain as missing; one attempt only, no repair or replacement',
        'terminal_response':'finish_reason must be stop and no native tool/function plan',
        'scope':'source/development component pilot, not strongest full Agent or official test experiment',
        'advancement':'net at least +2/27 and harms at most 1 is only a follow-up priority signal; no automatic target expansion',
        'stochasticity':'one sample per arm at temperature 0.2; no multiple-seed confirmation',
    }


def order(inputs):
    for index, row in enumerate(inputs):
        for arm in ARMS if index % 2 == 0 else ARMS[::-1]:
            yield row, arm


def messages(row, arm, data, skill):
    assert arm in ARMS and len(row['images']) == 1
    assert 'answer' not in row and 'reference' not in row and 'content_type' not in row
    image = (data/row['images'][0]).resolve()
    assert image.is_relative_to(data.resolve()) and image.is_file()
    encoded = base64.b64encode(image.read_bytes()).decode('ascii')
    return [
        {'role':'system', 'content':BASE + ('\n\n'+skill if arm == 'P1' else '')},
        {'role':'user', 'content':[
            {'type':'text','text':row['question']},
            {'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+encoded}},
        ]},
    ]
