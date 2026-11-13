"""Bind new Verify candidates and distinguish prior experience from current evidence."""

import json
import re

from online_memory_r49 import read, save_once


HISTORICAL_D = 'chexbench_openi_0041'
AUDIT = (' A prior case answer, even when included in an experience card or the risk text, '
         'belongs to that source question. It is not evidence about the current image. '
         'Distinguish the observed projection marker, device course and insertion site.')


def bound_candidate(row, text):
    options = row.get('options', {})
    if not options:
        return text
    letter = re.fullmatch(r'([A-Z])(?:[.)：:]\s*.*|\s+.+)?', text, flags=re.IGNORECASE)
    if letter and letter[1].upper() in options:
        key = letter[1].upper()
        return f'{key}. {options[key]}'
    matching = [key for key, value in options.items() if text.casefold() == value.strip().casefold()]
    if len(matching) == 1:
        key = matching[0]
        return f'{key}. {options[key]}'
    raise ValueError('verify_candidate_does_not_identify_one_option')


def empty_length_reply(folder):
    if folder.parent.parent.name != 'R55-VERIFY' or folder.name != '1':
        return False
    if not all((folder/(name+'.json')).is_file() for name in ('request','started','response','result')):
        return False
    receipt = read(folder/'result.json')
    response = read(folder/'response.json')
    choices = response.get('choices') or [{}]
    message = choices[0].get('message') or {}
    return (receipt.get('response_received') is True
            and receipt.get('error') == 'r55_verifier_incomplete_response'
            and receipt.get('request_id') == read(folder/'started.json').get('request_id')
            and choices[0].get('finish_reason') == 'length'
            and not (message.get('content') or '').strip())


def account_empty_verify(folder):
    if not empty_length_reply(folder):
        return False
    save_once(folder/'unavailable.continue60.json', {
        'request_id': read(folder/'started.json')['request_id'], 'finish_reason': 'length',
        'response_received': True, 'content_usable': False, 'resent': False,
    })
    return True


def accounted_empty_verify(folder, require_receipts):
    note = folder/'unavailable.continue60.json'
    if note.is_file():
        return empty_length_reply(folder) and read(note) == {
            'request_id': read(folder/'started.json')['request_id'], 'finish_reason': 'length',
            'response_received': True, 'content_usable': False, 'resent': False,
        }
    return (not require_receipts and folder.parent.name == 'verify_'+HISTORICAL_D+'_3'
            and empty_length_reply(folder))
