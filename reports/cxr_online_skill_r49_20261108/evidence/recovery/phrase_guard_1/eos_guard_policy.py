"""Unexecuted R49 candidate: suppress EOS only while generated MAIRA tags remain open.

This is a declared generation-policy change, not parsing repair or a clinical result.
It loads no models, performs no inference, and changes no production records on import.
"""
from contextlib import contextmanager

POLICY_ID='maira_unclosed_tag_eos_guard_v1'
TOKENS={'obj_start':32000,'obj_end':32001,'box_start':32202,'box_end':32203,'eos':2}
TOKEN_TEXT={'obj_start':'<obj>','obj_end':'</obj>','box_start':'<box>','box_end':'</box>'}


def open_depths(token_ids):
    """Independent unmatched tag depths; this does not validate the full grammar."""
    obj=box=0
    for token in token_ids:
        if token==TOKENS['obj_start']:obj+=1
        elif token==TOKENS['obj_end']:obj=max(0,obj-1)
        elif token==TOKENS['box_start']:box+=1
        elif token==TOKENS['box_end']:box=max(0,box-1)
    return obj,box


class UnclosedTagEOSGuard:
    """A Transformers-compatible callable; all non-EOS scores stay identical."""
    def __init__(self,prompt_length,evidence):
        if type(prompt_length) is not int or prompt_length<0:raise ValueError('invalid_prompt_length')
        self.prompt_length=prompt_length;self.evidence=evidence;self.steps=0

    def __call__(self,input_ids,scores):
        if len(input_ids.shape)!=2 or len(scores.shape)!=2 or input_ids.shape[0]!=scores.shape[0] or scores.shape[1]<=TOKENS['eos']:
            raise ValueError('invalid_eos_guard_tensor_shape')
        if input_ids.shape[1]<self.prompt_length:raise ValueError('generated_suffix_precedes_prompt')
        self.steps+=1;changed=None
        for row in range(input_ids.shape[0]):
            suffix=input_ids[row,self.prompt_length:].tolist()
            obj,box=open_depths(suffix)
            if obj or box:
                if changed is None:changed=scores.clone()
                changed[row,TOKENS['eos']]=float('-inf')
                if not changed[row].isfinite().any().item():
                    raise RuntimeError('eos_guard_no_finite_non_eos_token_stop')
                self.evidence.append({'step':self.steps,'batch_row':row,'generated_length':len(suffix),
                  'unclosed_obj_depth':obj,'unclosed_box_depth':box,'masked_token_id':TOKENS['eos']})
        return scores if changed is None else changed


def validate_original_profile(tool):
    tokenizer=tool.processor.tokenizer;config=tool.model.generation_config
    actual={key:tokenizer.convert_tokens_to_ids(text) for key,text in TOKEN_TEXT.items()}
    if actual!={key:TOKENS[key] for key in TOKEN_TEXT}:raise ValueError('pinned_maira_tag_token_mapping_changed')
    if tokenizer.eos_token_id!=TOKENS['eos'] or config.eos_token_id!=TOKENS['eos']:
        raise ValueError('pinned_maira_eos_identity_changed')
    if any(token in tokenizer.all_special_ids for token in actual.values()):raise ValueError('grounding_tags_unexpectedly_special')
    if (config.do_sample is not False or config.num_beams!=1 or getattr(config,'forced_eos_token_id',None) is not None or
        not getattr(tool.model,'is_loaded_in_8bit',False) or getattr(tool.model,'is_loaded_in_4bit',False) or
        str(tool.model.dtype)!='torch.float16' or str(tool.model.device)!='cuda:0'):
        raise ValueError('original_maira_generation_profile_changed')
    return {'tag_token_ids':actual,'eos_token_id':TOKENS['eos'],'do_sample':False,'num_beams':1,'forced_eos_token_id':None,
      'is_loaded_in_8bit':True,'model_dtype':'torch.float16','visible_model_device':'cuda:0'}


@contextmanager
def install_eos_guard(tool,record):
    """Candidate integration after the original factory; no tool/parser replacement."""
    from unittest.mock import patch
    from transformers import LogitsProcessorList
    profile=validate_original_profile(tool);original=tool.model.generate
    record.update(policy_id=POLICY_ID,profile=profile,inserted_tokens=0,parse_fallback=False,forced_box=False,calls=[])
    def guarded_generate(*args,**kwargs):
        if args or kwargs.get('input_ids') is None:raise ValueError('original_keyword_generation_call_required')
        if kwargs.get('max_new_tokens')!=300 or kwargs.get('use_cache') is not True:
            raise ValueError('original_300_token_generation_arguments_required')
        prompt_length=int(kwargs['input_ids'].shape[-1])
        masking=[];guard=UnclosedTagEOSGuard(prompt_length,masking)
        supplied=kwargs.get('logits_processor')
        if supplied is not None and any(isinstance(item,UnclosedTagEOSGuard) for item in supplied):
            raise ValueError('duplicate_eos_guard_forbidden')
        changed=dict(kwargs);changed['logits_processor']=LogitsProcessorList([*(supplied or []),guard])
        call={'prompt_length':prompt_length,'max_new_tokens':300,'use_cache':True,'masking_steps':masking,
          'existing_logits_processors':len(supplied or []),'generation_policy_changed':True}
        record['calls'].append(call)
        try:return original(*args,**changed)
        finally:call['processor_invocations']=guard.steps;call['masking_step_count']=len(masking)
    with patch.object(tool.model,'generate',guarded_generate):yield record
