"""V12 evidence-conditioned differential retrieval and action experience.

No current answer or reference label is accepted. Knowledge remains a conditional
rule. Training outcomes are not step credit, and reported image observations remain
fallible. Every option and discriminator is retained; dense queries are chunked so
the encoder's sequence ceiling cannot silently discard the end of a long question.
"""
from __future__ import annotations

import json
import math
import re

from v9_retrieval import V9Retriever, GENERIC_TERMS, _token_estimate, stem_of, task_types
from v10_retrieval import ATTRIBUTE_PATTERNS, ANATOMY_PATTERNS, tags, canonical_tasks


MODALITIES = {
    'cxr': 'radiograph', 'chest x-ray': 'radiograph', 'chest radiograph': 'radiograph',
    'x-ray': 'xray', 'xray': 'xray', 'radiography': 'radiograph',
    'chest radiography': 'radiograph', 'radiograph': 'radiograph', 'hrct': 'ct',
    'ctpa': 'ct', 'cta': 'ct', 'contrast_ct': 'ct', 'computed tomography': 'ct',
    'ct': 'ct', 'mri': 'mri', 'mr': 'mri', 'ultrasound': 'ultrasound', 'us': 'ultrasound',
}
TOOL_CAPABILITIES = {
    'chest_xray_expert': {'modalities': {'radiograph'}, 'attributes': {'presence','location','morphology','comparison','relation','number','laterality'}},
    'llava_med_qa': {'modalities': {'radiograph','xray','ct','mri','ultrasound'}, 'attributes': {'presence','location','morphology','comparison','relation','number','laterality','size'}},
    'xray_phrase_grounding': {'modalities': {'radiograph'}, 'attributes': {'location','relation'}, 'caution': 'A query-conditioned box does not confirm that the named finding exists.'},
    'image_visualizer': {'modalities': {'radiograph','xray','ct','mri','ultrasound','unknown'}, 'attributes': {'presence','location','morphology','comparison','relation','number','laterality','size'}},
    'crop_current_image': {'modalities': {'radiograph','xray','ct','mri','ultrasound','unknown'}, 'attributes': {'location','morphology','number','size'}, 'caution': 'Pair the crop with its original; cropping provides no new pixels or scale calibration.'},
    'chest_xray_classifier': {'modalities': {'radiograph'}, 'attributes': {'presence'}, 'caution': 'Image-level class scores cannot establish side, object, location, or mechanism.'},
    'chest_xray_report_generator': {'modalities': {'radiograph'}, 'attributes': {'presence','description'}, 'caution': 'Report omissions are not observed absence.'},
    'chest_xray_segmentation': {'modalities': {'radiograph'}, 'attributes': {'location','size','relation'}, 'caution': 'Masks identify model regions, not calibrated physical dimensions.'},
    'dicom_processor': {'modalities': {'radiograph','xray','ct','mri','ultrasound'}, 'attributes': {'view','orientation'}, 'caution': 'Only supplied DICOM metadata can establish a pixel scale or acquisition information.'},
}
PROHIBITED_INPUT_KEYS = {'answer','first_answer','initial_answer','selected_option','reference_answer','correct'}
ERROR_TEXT = re.compile(r'cuda out of memory|traceback|tool_call_rejected|not matched|exception|api.?error', re.I)
GENERIC = GENERIC_TERMS | {'image','images','figure','figures','option','options','patient','question',
                          'attribute','attributes','current','unknown','unresolved','left','right',
                          'radiograph','radiographs','chest','visible','visual','full','observe','observation'}
K_HEADER='[K: CONDITIONAL DIFFERENTIAL RULES; choose what and where to inspect, never infer a patient fact]\n'
E_HEADER='[E: TRAINING ACTION SUGGESTIONS; choose one specific observation, do not transfer source findings or treat whole-answer success as step credit]\n'


def similar_terms(a,b):
    """Conservative text redundancy, not a medical equivalence judgement."""
    if not a or not b:return False
    if a==b:return True
    intersection=len(a&b)
    return (intersection/len(a|b)>=0.75 or
            (min(len(a),len(b))>=3 and intersection/min(len(a),len(b))>=0.9))


def redundant_knowledge(a,b,tokenize):
    # Source IDs and wording alone do not make a second independent observation.
    # Keep distinct discriminating signs even when published by the same source.
    if not set(a['target_image_ids'])&set(b['target_image_ids']):return False
    terms=lambda v:set(tokenize(' '.join(strings(v))))-GENERIC
    return (similar_terms(terms(a['observe']),terms(b['observe'])) or
            similar_terms(terms(a['differential_rule']),terms(b['differential_rule'])))


def redundant_action(a,b,tokenize):
    # Switching tools or repeating a historical tool sequence is not a new goal.
    # A genuinely different region, image, object, or question is complementary.
    if set(a['target_image_ids'])!=set(b['target_image_ids']):return False
    if a.get('comparison_object')!=b.get('comparison_object'):return False
    if a.get('object_id')!=b.get('object_id'):return False
    if a.get('target_region')!=b.get('target_region'):return False
    terms=lambda s:set(tokenize(s))-GENERIC
    return similar_terms(terms(a['specific_question']),terms(b['specific_question']))


def strings(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [json.dumps(value, ensure_ascii=False)]
    return [v if isinstance(v,str) else json.dumps(v,ensure_ascii=False) for v in value]


def modality(value):
    return MODALITIES.get(str(value or '').strip().lower().replace('_',' '),
                          MODALITIES.get(str(value or '').strip().lower(), 'unknown'))


def options(question):
    marks=list(re.finditer(r'(?m)^\s*(?:([A-Z])[.)：:]|\(([A-Z])\))\s*',str(question)))
    return {m.group(1) or m.group(2):str(question)[m.end():marks[i+1].start() if i+1<len(marks) else None].strip()
            for i,m in enumerate(marks)}


def dense_chunks(text, encoder):
    """Use untruncated tokenizer offsets, retaining every section in the query."""
    text=str(text)
    tokenizer=getattr(encoder,'tokenizer',None)
    if tokenizer is not None and hasattr(tokenizer,'to_str'):
        # The production ONNX tokenizer has a 256-token truncation policy. Clone
        # its configuration so examining full offsets cannot mutate the encoder.
        tokenizer=type(tokenizer).from_str(tokenizer.to_str())
        tokenizer.no_truncation();tokenizer.no_padding()
        offsets=tokenizer.encode(text).offsets
        mode='untruncated_tokenizer_offsets_200_token_chunks'
    else:
        tokenizer=getattr(getattr(encoder,'encoder',None),'tokenizer',None)
        if tokenizer is not None and getattr(tokenizer,'is_fast',False):
            offsets=tokenizer(text,truncation=False,padding=False,add_special_tokens=False,
                              return_offsets_mapping=True)['offset_mapping']
            mode='untruncated_fast_tokenizer_offsets_200_token_chunks'
        else:
            # Defensive fallback for injected test encoders/slow tokenizers. It
            # still visits the complete string instead of a fixed prefix.
            return [text[i:i+180] for i in range(0,len(text),180)] or [''], 'bounded_character_chunks_no_offset_tokenizer'
    offsets=[(a,b) for a,b in offsets if b>a]
    output=[]
    for i in range(0,len(offsets),200):
        part=offsets[i:i+200]
        output.append(text[part[0][0]:part[-1][1]])
    return output or [''],mode


def population_from_conditions(conditions):
    for item in conditions:
        name=str(item.get('name','')).lower();value=str(item.get('value','')).lower()
        if name in {'population','age_group'}:
            if re.search(r'\b(adult|adults|elderly)\b',value):return 'adult'
            if re.search(r'\b(child|children|pediatric|paediatric|infant|neonate)\b',value):return 'pediatric'
        if name in {'age','patient_age'}:
            match=re.search(r'\b(\d{1,3})\s*(?:years?|yrs?|y[ /-]?o)\b',value)
            if match:return 'adult' if int(match.group(1))>=18 else 'pediatric'
    return 'unknown'


def projected_query(row, first_read, images):
    if any(k in first_read for k in PROHIBITED_INPUT_KEYS):
        raise ValueError('V12_retrieval_must_not_receive_first_or_reference_answer')
    full=str(row['question']);stem=stem_of(full);choices=options(full)
    known={im['image_id'] for im in images}
    meta={m['image_id']:m for m in first_read.get('image_metadata',[]) if isinstance(m,dict) and m.get('image_id') in known}
    registry=[]
    for im in images:
        m=meta.get(im['image_id'],{})
        registry.append({k:v for k,v in {**im,**m,'modality':modality(m.get('modality',im.get('modality')))}.items()
                         if k in {'image_id','path','source_filename','figure_label','modality','anatomy','timepoint','timepoint_source_quote','object_id','comparison_object'}})
    observed=[];hypotheses=[];issues=[]
    for item in first_read.get('observations',[]):
        if not isinstance(item,dict):continue
        obs={k:item[k] for k in ('attribute','value','status','evidence_refs','image_ids','object_id') if k in item}
        value=str(obs.get('value','')).strip()
        refs=[v for v in obs.get('evidence_refs',[]) if v in known]
        obs['evidence_refs']=refs
        if not value or ERROR_TEXT.search(value) or value.lower() in {'no','yes','none','normal'}:
            issues.append('nonspecific_or_failed_output_not_a_patient_fact');continue
        is_observed=obs.get('status') in {'observed_present','observed_absent'} and bool(refs)
        if str(obs.get('attribute','')).lower() in {'diagnosis','disease','etiology','mechanism'}:
            is_observed=False
        obs['source']='shared_first_image_read_unverified'
        if is_observed:
            observed.append(obs)
        else:
            obs['status']='hypothesis' if obs.get('status')!='unresolved' else 'unresolved'
            hypotheses.append(obs)
    for value in first_read.get('hypotheses',[]):
        item=dict(value) if isinstance(value,dict) else {'hypothesis':str(value)}
        if any(k in item for k in PROHIBITED_INPUT_KEYS):
            item={k:v for k,v in item.items() if k not in PROHIBITED_INPUT_KEYS}
        item['status']='hypothesis';hypotheses.append(item)
    conditions=[]
    for item in first_read.get('patient_conditions',[]):
        if not isinstance(item,dict):continue
        quote=str(item.get('source_quote','')).strip()
        if quote and quote.casefold() in stem.casefold():
            conditions.append({k:item[k] for k in ('name','value','source_quote') if k in item})
        else:issues.append('patient_condition_without_stem_quote_excluded')
    discriminators=[]
    for item in first_read.get('discriminators',[]):
        if not isinstance(item,dict) or not str(item.get('question','')).strip():continue
        d={k:item[k] for k in ('attribute','question','target_region','object_id','comparison_object') if k in item}
        d['option_labels']=[x for x in item.get('option_labels',[]) if x in choices]
        d['image_ids']=[x for x in item.get('image_ids',[]) if x in known]
        discriminators.append(d)
    tasks=canonical_tasks(row.get('official_group')) or task_types(stem)
    mods=list(dict.fromkeys(x['modality'] for x in registry))
    hypothesis_text=[json.dumps(x,ensure_ascii=False) for x in hypotheses]
    hypothesis_text += [f'Unselected alternative {key}: {value}' for key,value in choices.items()]
    roles={'full_question':full,'options':choices,'patient_conditions':conditions,
           'visible_evidence':observed,'candidate_hypotheses':hypotheses,
           'option_hypotheses':choices,'discriminators':discriminators,
           'image_registry':[{k:v for k,v in im.items() if k!='path'} for im in registry],
           'uncertainties':strings(first_read.get('uncertainties'))}
    # Role labels stay explicit, including when candidate text supplies a search term.
    text=json.dumps(roles,ensure_ascii=False)
    return {'question_stem':full,'full_question':full,'options':choices,
            'visible_evidence':observed,'candidate_hypotheses':hypothesis_text,
            'patient_conditions':conditions,'discriminators':discriminators,
            'image_registry':registry,'modalities':mods,'modality':mods[0] if len(mods)==1 else 'mixed',
            'anatomy':list(dict.fromkeys(str(x.get('anatomy','')) for x in registry if x.get('anatomy'))),
            'task':tasks,'population':population_from_conditions(conditions),
            'missing_attributes':[d.get('attribute','')+' '+d['question'] for d in discriminators]+strings(first_read.get('uncertainties')),
            'full_role_query_text':text,'query_issues':sorted(set(issues)),
            'facts_added_by_retrieval':[], 'observation_provenance':'model_report_not_expert_annotation'}


def compatible_images(tool, images):
    spec=TOOL_CAPABILITIES.get(tool)
    if not spec:return []
    return [im['image_id'] for im in images if modality(im.get('modality')) in spec['modalities']
            and (tool!='dicom_processor' or str(im.get('path','')).lower().endswith('.dcm'))]


def verified_step_benefit(step):
    value=step.get('step_credit')
    if (step.get('step_credit_verified') is True and step.get('step_credit_evidence')
            and type(value) in (int,float) and math.isfinite(value)):
        return {'value':value,'evidence':step['step_credit_evidence'],'source':'verified_training_step_record'}
    return None


class V12Retriever(V9Retriever):
    def __init__(self, knowledge_pack, pool_path, skills_path, dense_model_path=None,
                 questions_path=None, max_chars=5000, top_k=2):
        super().__init__(knowledge_pack,pool_path,skills_path,dense_model_path,questions_path,max_chars,min(2,top_k))
        self.top_k=min(2,self.top_k)

    def describe(self):
        result=super().describe()
        result.update(implementation_version='v12-evidence-differential-retrieval-1',
            query='full_question_all_options_quoted_patient_conditions_first_image_observations_all_discriminators',
            dense_query='all_role_text_chunks_max_similarity_no_prefix_only_truncation',
            experience='training_steps_modality_capability_matching_verified_credit_only_if_recorded',
            current_answer_in_retrieval=False,max_knowledge_cards=2,max_experience_actions=2,
            max_combined_contents=2,combined_selection='one_relevant_K_plus_one_concrete_E_when_both_exist; otherwise_up_to_two_complementary_same_role',
            deduplication='same_rule_or_required_observation; same_image_region_object_question_action_goal_independent_of_tool_order',
            step_credit='unknown_unless_verified_training_record')
        return result

    def _knowledge_v12(self,query):
        # Dense and BM25 both see all input sections. Each chunk is independently
        # encoded; max similarity provides any-section recall, with a separate
        # discriminator relevance gate before a card can be rendered.
        query_chunks,chunk_mode=dense_chunks(query['full_role_query_text'],self.encoder)
        vectors=self.encoder.encode(query_chunks)
        if len(vectors[0])!=self.vectors.shape[1]:raise ValueError('dense_query_dimension_mismatch')
        dense_scores=(self.vectors @ vectors.T).max(axis=1)
        active=set(query['modalities'])-{'unknown'}
        relevant_cards=[];excluded=[]
        for i,card in enumerate(self.cards):
            card_mods={modality(x) for x in card['modality']}-{'unknown'}
            if card_mods and (not active or not card_mods.intersection(active)):
                excluded.append({'knowledge_id':card['knowledge_id'],'reasons':['current_image_modality_not_supported']});continue
            if set(card['task_scope']) <= {'planning'}:
                excluded.append({'knowledge_id':card['knowledge_id'],'reasons':['not_an_observation_discriminator']});continue
            relevant_cards.append(i)
        audit={'mode':'hybrid_bm25_dense_rrf_role_aware','query_roles':query,'dense_chunk_count':len(query_chunks),'dense_chunking':chunk_mode,
               'rejected':excluded,'hits':[],'rendered_ids':[],'facts_added_by_retrieval':[]}
        if not relevant_cards:
            audit.update(abstained=True,abstention_reasons=['no_modality_compatible_differential_card'])
            return '',[],audit
        # Scope modalities were checked per actual image above; mixed cases retain
        # each hit's matching image IDs rather than flattening them to one modality.
        core_query={**query,'modality':'unknown' if len(active)>1 else next(iter(active),'unknown')}
        result=self.core.retrieve([self.cards[i] for i in relevant_cards],core_query,
            {'top_k':len(relevant_cards),'max_per_source':len(relevant_cards),'min_relative_score':0.0},
            self.index_dir,dense_scores[relevant_cards],'hybrid_bm25_dense_rrf',
            ['V12 full-role query; candidate terms locate conditional rules and never create patient observations.'])
        audit['rejected']+=result['rejected'];audit['rankings']=result.get('candidate_rankings',{})
        targets=query['discriminators'] or [{'attribute':'option_distinction','question':query['full_question'],
                                            'image_ids':[im['image_id'] for im in query['image_registry']]}]
        blocks=[];ids=[];selected_advice=[]
        for hit in result['hits']:
            card=hit['knowledge_card'];card_text=self.core.card_text(card)
            card_terms=set(self.core.tokens(card_text))-GENERIC
            scored=[]
            for d in targets:
                target_text=' '.join([d.get('attribute',''),d['question'],d.get('target_region','')])
                common=(set(self.core.tokens(target_text))-GENERIC)&card_terms
                if common:scored.append((len(common),d,sorted(common)))
            if not scored:
                audit['rejected'].append({'knowledge_id':card['knowledge_id'],'reasons':['no_specific_option_discriminator_match']});continue
            best=max(scored,key=lambda v:v[0])[1]
            matched=[d for _,d,_ in scored]
            cm={modality(x) for x in card['modality']}-{'unknown'}
            image_ids=[im['image_id'] for im in query['image_registry'] if not cm or im['modality'] in cm]
            if best.get('image_ids'):
                intersection=[i for i in image_ids if i in best['image_ids']]
                if intersection:image_ids=intersection
            advice={'knowledge_id':card['knowledge_id'],'source_id':card['source_id'],
                    'source_url':card.get('source_url'),'source_pages':card['source_pages'],
                    'differential_rule':card['summary_en'] or card['summary_zh'],
                    'observe':card['required_patient_evidence'], 'target_image_ids':image_ids,
                    'where_to_observe':best.get('target_region') or '; '.join(query['anatomy']) or 'the structure named in the discriminator, using full-image context',
                    'distinguishes_current_questions':[d['question'] for d in matched],
                    'limitations':card['limitations'], 'patient_applicability':'conditional_unless_explicit_conditions_verified',
                    'is_current_patient_fact':False}
            if any(redundant_knowledge(advice,prior,self.core.tokens) for prior in selected_advice):
                audit['rejected'].append({'knowledge_id':card['knowledge_id'],'reasons':['duplicate_rule_or_required_observation']});continue
            rendered=json.dumps(advice,ensure_ascii=False)
            if sum(len(s) for s in blocks)+len(rendered)>self.max_chars:
                audit['rejected'].append({'knowledge_id':card['knowledge_id'],'reasons':['render_budget_whole_card_not_partial']});continue
            blocks.append(rendered);ids.append(card['knowledge_id']);selected_advice.append(advice)
            audit['hits'].append({**hit,'actionable_differential':advice})
            if len(ids)>=self.top_k:break
        audit.update(rendered_ids=ids,abstained=not ids,
                     abstention_reasons=[] if ids else ['no_source_rule_supports_a_current_discriminator'])
        return K_HEADER+'\n'.join(blocks) if blocks else '',ids,audit

    def _experience_v12(self,row,query,tools):
        entry=self._boundary_check(row)
        available=set(tools);registry=query['image_registry']
        scores=self.b_index.scores(query['full_role_query_text'])
        audit={'representation':'training_action_to_current_discriminator','ranked':[],'rejected':[],
               'step_credit_policy':'Only verified source step credit with evidence is used. Whole-question correctness is not credit.'}
        targets=query['discriminators']
        if not targets:
            audit.update(abstained=True,abstention_reasons=['no_specific_discriminator_to_assign_action'])
            return '',[],audit,[]
        candidates=[]
        for i,record in enumerate(self.records):
            source=self.boundary.get(str(record['source_question_id']))
            reasons=[]
            if not source or source.get('split')!='memory_train' or source.get('excluded'):reasons.append('source_not_admitted_training')
            elif source['case_hash']==entry['case_hash']:reasons.append('same_case')
            text=self.b_documents[i]
            overlap=(set(self.core.tokens(text))&set(self.core.tokens(query['full_role_query_text'])))-GENERIC
            if not overlap or scores[i]<=0:reasons.append('no_specific_training_task_match')
            if reasons:
                audit['rejected'].append({'id':record['memory_id'],'reasons':reasons});continue
            for step_index,step in enumerate(record.get('steps',[])):
                tool=step.get('tool_name');spec=TOOL_CAPABILITIES.get(tool)
                if tool not in available or not spec:continue
                ids=compatible_images(tool,registry)
                if not ids:continue
                failed=step.get('execution') in {'exception','returned_invalid','failed','timed_out'}
                for d_index,d in enumerate(targets):
                    requested=d.get('image_ids') or ids
                    targets_ids=[x for x in ids if x in requested]
                    if not targets_ids:continue
                    attrs=set(tags(d.get('attribute','')+' '+d['question'],ATTRIBUTE_PATTERNS))
                    supported=attrs&spec['attributes']
                    if not supported:continue
                    # Whole-image reports/class scores are poor choices for a
                    # requested spatial/multi-attribute distinction; never use
                    # their name ordering as a selection rule.
                    capability=len(supported)/max(1,len(attrs))
                    if tool in {'chest_xray_classifier','chest_xray_report_generator'}:
                        capability*=0.25
                    credit=verified_step_benefit(step)
                    suggestion={'experience_id':record['memory_id'],'source_question_id':str(record['source_question_id']),
                        'source_step_id':step.get('step_id',step_index),'source_event_line':step.get('source_event_line'),
                        'applicable_ambiguity':d['question'],'target_image_ids':targets_ids,
                        'target_region':d.get('target_region') or 'region containing the named distinguishing attribute; planner must bind exact image/ROI',
                        'tool':tool,'specific_question':d['question'],
                        'expected_discriminating_attributes':sorted(supported),
                        'object_id':d.get('object_id'),'comparison_object':d.get('comparison_object'),
                        'historical_execution':step.get('execution','unknown'),
                        'historical_whole_question_outcome':record.get('task_outcome','unknown'),
                        'step_credit':credit['value'] if credit else None,
                        'step_credit_evidence':credit['evidence'] if credit else None,
                        'selection_basis':'verified_training_step_benefit_then_capability' if credit else 'modality_and_capability_match_no_step_gain_data',
                        'heuristic_capability_coverage_not_credit':capability,
                        'caution':spec.get('caution','Tool output is a fallible report; independently check current pixels.'),
                        'historical_failure_advice':'Do not repeat this action after the same execution failure; choose another compatible observation.' if failed else None,
                        'is_patient_fact':False}
                    # Executed failure can supply a warning but is not positive
                    # evidence that the action was useful.
                    rank=(credit is not None,credit['value'] if credit else 0.0,not failed,capability,float(scores[i]))
                    candidates.append((rank,i,step_index,d_index,suggestion))
        candidates.sort(key=lambda x:(tuple(-float(v) for v in x[0]),x[1],x[2],x[3]))
        selected=[];rendered=[];ids=[]
        for rank,i,si,di,s in candidates:
            audit['ranked'].append({'experience_id':s['experience_id'],'source_step_id':s['source_step_id'],
                'tool':s['tool'],'capability_match':s['heuristic_capability_coverage_not_credit'],'step_credit':s['step_credit']})
            if any(redundant_action(s,prior,self.core.tokens) for prior in selected):
                audit['rejected'].append({'id':s['experience_id'],'source_step_id':s['source_step_id'],
                                          'reasons':['duplicate_observation_goal_not_complementary']});continue
            text=json.dumps(s,ensure_ascii=False)
            if sum(len(x) for x in rendered)+len(text)>self.max_chars:continue
            selected.append(s);rendered.append(text)
            if s['experience_id'] not in ids:ids.append(s['experience_id'])
            if len(selected)>=2:break
        audit.update(rendered_ids=ids,selected_actions=selected,abstained=not selected,
                     abstention_reasons=[] if selected else ['no_training_action_matches_current_modality_and_discriminator'])
        return E_HEADER+'\n'.join(rendered) if rendered else '',ids,audit,selected

    def retrieve(self,row,initial_observation,images,available_tools,group):
        if group not in {'A','B'}:raise ValueError('unknown_V12_group')
        self._boundary_check(row)
        query=projected_query(row,initial_observation,images)
        result={'group':group,'query':query,'k_block':'','e_block':'','k_ids':[],'e_ids':[],
                'k_audit':{'disabled':group=='A'},'e_audit':{'disabled':group=='A'},
                'action_suggestions':[],'retrieval_timing':'after_shared_first_image_read_before_action_selection',
                'combined_content_count':0,
                'token_count_method':'utf8_bytes_div4_estimate_not_provider_usage'}
        if group=='B':
            names=[t if isinstance(t,str) else getattr(t,'name',str(t)) for t in available_tools]
            result['k_block'],result['k_ids'],result['k_audit']=self._knowledge_v12(query)
            result['e_block'],result['e_ids'],result['e_audit'],result['action_suggestions']=self._experience_v12(row,query,names)
            # K tells the planner which sign separates options; E specifies a
            # useful action. This pair is complementary even for the same goal.
            # Their TOTAL context is capped at two items, not two of each.
            k_hits=result['k_audit'].get('hits',[])
            e_actions=result['action_suggestions']
            k_count,e_count=len(k_hits),len(e_actions)
            if k_hits and e_actions:
                k_hits=k_hits[:1];e_actions=e_actions[:1]
            else:
                k_hits=k_hits[:2];e_actions=e_actions[:2]
            result['k_ids']=[h['actionable_differential']['knowledge_id'] for h in k_hits]
            result['e_ids']=list(dict.fromkeys(s['experience_id'] for s in e_actions))
            result['action_suggestions']=e_actions
            result['k_block']=K_HEADER+'\n'.join(json.dumps(h['actionable_differential'],ensure_ascii=False) for h in k_hits) if k_hits else ''
            result['e_block']=E_HEADER+'\n'.join(json.dumps(s,ensure_ascii=False) for s in e_actions) if e_actions else ''
            result['k_audit'].update(hits=k_hits,rendered_ids=result['k_ids'],
                trimmed_by_combined_budget=k_count-len(k_hits))
            result['e_audit'].update(selected_actions=e_actions,rendered_ids=result['e_ids'],
                trimmed_by_combined_budget=e_count-len(e_actions))
            result['combined_content_count']=len(k_hits)+len(e_actions)
            result['combined_budget_policy']='at_most_two; prefer_one_conditional_rule_and_one_concrete_action'
        result['k_token_estimate']=_token_estimate(result['k_block'])
        result['e_token_estimate']=_token_estimate(result['e_block'])
        return result
