import json
import re

BASE_SYSTEM='''You answer medical image multiple-choice questions. Inspect all supplied original images and the complete question and options. The memory context contains historical experiences and conditional inspection rules; use them to decide which visible distinctions to examine in THIS case. Historical diagnoses and findings are not facts about the current patient. Check whether each retrieved lesson applies before using it. Prefer current pixels and explicit question facts over an analogy. Respect figure identity and only the chronology supplied in the question. Choose the single best complete legal option even when details remain uncertain. Return two short lines:
Answer: <one legal option letter; option text may follow>
Reason: <one or two brief sentences about the decisive current-case evidence>'''

REFLECT_SYSTEM='''Reflect on a COMPLETED historical case using its original images, full question/options, saved response, reference answer and any supplied reference explanation. Identify the specific successful distinction or error, and a reusable conditional inspection action for a different future patient. The reference diagnosis does not prove that every associated visual sign is visible. Separate image observations, explicit clinical facts and reference-only information. If the provided material cannot explain the answer, state the limitation rather than inventing an explanation. Write one concise episode and at most one conditional procedure patch. A procedure must specify when it applies, what to inspect, and an exception/limitation; avoid generic advice and patient-specific answer-letter rules. Return one compact JSON object with episode and procedure_patch. Do not revise the already submitted answer.
Use this schema:
{"episode":{"task":["diagnosis/comparison/localization/etc"],"modality":"CXR|CT|other|unknown",
"case_pattern":"supported distribution/explicit clinical situation",
"error_or_success":"specific choice distinction; if old reasoning missing do not claim to know why it was chosen",
"decisive_difference":"competing explanations and discriminating visible/explicit attribute",
"inspection_action":"concrete structure/figure relation and attribute to inspect next time",
"evidence_basis":{"image":"unverified visual observation","question":"explicit source facts","reference_only":"what is known only from feedback"},
"limitations":"missing scale/history/chronology or insufficiency of pixels/reference explanation"},
"procedure_patch":null OR {"op":"add|revise|retire","id":"existing supplied rule ID only for revise/retire",
"condition":"specific applicable ambiguity","action":"concrete anatomical inspection",
"limitation":"exception/limit","priority":3}}
Priority is an engineering integer 1..5, not a credit score. At most one patch.
No long hidden reasoning. Keep an injectable episode within roughly 180 English
words and a conditional rule within 70 words. No new patient facts from reference
diagnosis alone. If only a saved choice survives, state reasoning unavailable.'''


def clean_letters(value):
    text=str(value or '')
    text=re.sub(r'(?i)\b(?:option|answer|choice)\s*(?:(?:is|was)\s*|[:=]\s*)?[A-F]\b','the historical alternative',text)
    text=re.sub(r'(?i)\b(?:chose|selected|choose)\s+[A-F]\b','selected the historical alternative',text)
    text=re.sub(r'(?i)\b[A-F]\s*(?:vs\.?|versus|/)\s*[A-F]\b','the competing alternatives',text)
    return re.sub(r'^\s*[A-F][).:]\s*','',text).strip()


def words(value,n):
    text=clean_letters(value);parts=text.split()
    return ' '.join(parts[:n])+(' [truncated]' if len(parts)>n else '')


def episode_text(episode,ordinal):
    basis=episode.get('evidence_basis',{})
    if isinstance(basis,dict):basis='; '.join(f'{k}: {v}' for k,v in basis.items())
    # Keep the complete historical corrected option (including disease name).
    # Shorter surrounding fields preserve actions/limits without another LLM call.
    correct=clean_letters(episode.get('correct_choice_text'))
    fields=[('Pattern',episode.get('case_pattern'),12),('Earlier choice',episode.get('previous_choice_text'),10),
            ('Corrected interpretation',correct,max(1,len(correct.split()))),
            ('Earlier distinction',episode.get('error_or_success'),10),('Difference',episode.get('decisive_difference'),18),
            ('Inspect',episode.get('inspection_action'),25),('Basis',basis,6),('Limit',episode.get('limitations'),18)]
    return f'Historical example {ordinal} (modality {episode.get("modality","unknown")}): '+'; '.join(k+': '+words(v,n) for k,v,n in fields)+'.'


def rule_text(rule,ordinal):
    return f'Conditional procedure {ordinal}: when {words(rule["condition"],20)}, inspect {words(rule["action"],26)}; limitation: {words(rule["limitation"],14)}.'


def answer_payload(row,context):
    if set(row)!={'question_id','question','images'}:raise ValueError('answer_input_not_whitelisted')
    return {'MEMORY_CONTEXT':context,'current_question_and_all_options':row['question'],
            'instruction':'Historical examples are other patients; use current pixels and explicit facts. No current reference or prior prediction is supplied.'}


def reflection_payload(row,saved_response,reference,candidates):
    return {'completed_question_and_all_options':row['question'],'saved_response':saved_response,
            'reference_answer_letter':reference['answer'],'reference_choice_full_text':reference['correct_choice_text'],
            'reference_explanation':reference.get('explanation'),
            'reference_explanation_available':reference.get('explanation') is not None,
            'allowed_existing_procedure_candidates':[{k:r[k] for k in ('id','condition','action','limitation')} for r in candidates],
            'instruction':'Feedback is authorized only for this completed case; do not revise its submitted prediction.'}


def parse_reflection(text):
    text=str(text).strip()
    if text.startswith('```'):text=re.sub(r'^```(?:json)?\s*','',text,flags=re.I);text=re.sub(r'\s*```$','',text)
    value=json.loads(text)
    if not isinstance(value,dict) or not isinstance(value.get('episode'),dict):raise ValueError('reflection_episode_missing')
    return value
