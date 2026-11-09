"""Post-run extraction of explicit answers only; no labels or model calls.

Frozen terminal answers are never overwritten. The runtime parser remains
available as a separate operational outcome in the published report.
"""
import re


def explicit_answer(text, legal):
    if not isinstance(text, str):
        return None, 'non_text'
    text = text.replace('**', '').replace('`', '').strip()
    if text.upper() in legal and len(text) == 1:
        return text.upper(), 'bare_letter'
    lines = text.splitlines()
    labelled = [line.strip() for line in lines
                if re.match(r'^\s*(?:Return\s+)?(?:Final\s+)?Answer\s*:', line, re.I)]
    if labelled:
        values = []
        for line in labelled:
            match = re.match(r'^(?:Return\s+)?(?:Final\s+)?Answer\s*:\s*\(?([A-Z])\)?(?=$|[\s).,:;—–-])', line, re.I)
            if match is None or match[1].upper() not in legal:
                return None, 'explicit_refusal_or_non_option'
            values.append(match[1].upper())
        return (values[0], 'explicit_answer_label') if len(set(values)) == 1 else (None, 'conflicting_answer_labels')
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
    def option_start(paragraph):
        match = re.match(r'^\(?([A-Z])\)?[).]\s+\S', paragraph)
        return match[1] if match and match[1] in legal else None
    if paragraphs:
        last = option_start(paragraphs[-1])
        # Do not mistake the end of a multi-option list for an answer.
        if last and (len(paragraphs) == 1 or option_start(paragraphs[-2]) is None):
            if len(re.findall(r'^\s*\(?[A-Z]\)?[).]\s+', paragraphs[-1], re.M)) == 1:
                return last, 'final_option_paragraph'
        first = option_start(paragraphs[0])
        if first and sum(option_start(p) is not None for p in paragraphs) == 1:
            return first, 'opening_single_option_then_explanation'
    return None, 'no_explicit_final_option'
