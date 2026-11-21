"""Shared single-object action contract and bounded same-decision repair."""
import json
import math

FORMAT_GUARD = '''以下是动作通信协议，不改变原有医学任务、工具权限或取证策略。

在允许选择工具或完成答案的决策阶段，每次回复必须是单个合法 JSON 对象。
不要在 JSON 前后输出解释、计划、Markdown、代码围栏或其他文字。
不要在同一次回复里输出多个 JSON 对象。

需要工具时，使用当前运行器要求的 calls 结构。例如：
{"calls":[{"tool":"chest_xray_expert","args":{"question":"Describe the location of the target finding, including any supported patient laterality."}}],"reason":"Check the distinguishing location"}
这里的工具仅是结构示例，不是强制工具选择。工具名必须来自当前注册清单，参数必须符合该工具的 schema。
reason 位于顶层；不要自行往单个 call 中添加 reason 等未许可字段。
仅当当前协议允许多图 image_index 时，按原协议指定它；不要猜测图像或参数。

决定完成本题时，使用原有最终答案结构：
{"answer":"原题选项标签或协议允许的原选项文本","reason":"一条简短证据说明"}

calls 和 answer 互斥。计划使用工具不等于已经获得工具观察。
若收到格式修复指令，只纠正动作的结构；不要因为格式错误而自动转成最终答案。
当前若是其他明确限定的阶段，继续使用该阶段原有 schema，不将该阶段改成答题阶段。
'''
MAX_REPAIRS = 2


class ProtocolError(ValueError):
    def __init__(self, stage, code, error_type="ValueError"):
        super().__init__(code)
        self.stage, self.code, self.error_type = stage, code, error_type


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key:" + key)
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError("non_json_constant:" + value)


def parse(raw):
    try:
        obj = json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)
    except (ValueError, TypeError) as error:
        raise ProtocolError("parse", str(error), type(error).__name__) from error
    if not isinstance(obj, dict):
        raise ProtocolError("parse", "single_json_object_required")
    return obj


def validate_tool_arguments(row, call):
    """Check registered argument shapes before dispatch, retaining backend validation."""
    name, args = call["tool"], call["args"]
    visual_qa = {"chest_xray_expert", "llava_med_qa", "medgemma", "llava_rad", "medvlm_r1"}
    if name in visual_qa:
        if set(args) - {"question"} or ("question" in args and not isinstance(args["question"], str)):
            raise ValueError("visual_qa_accepts_question_string_only")
    elif name == "maira2_grounded_report":
        if args:
            raise ValueError("maira_report_accepts_empty_args_only")
    elif name == "xray_phrase_grounding":
        if set(args) - {"phrase"} or ("phrase" in args and not isinstance(args["phrase"], str)):
            raise ValueError("phrase_grounding_accepts_phrase_string_only")
    elif name == "roi_crop":
        # Same normalized-box and zoom requirements as roi_r54.crop.
        if set(args) - {"box", "zoom"}:
            raise ValueError("unknown_roi_arguments")
        box, zoom = args.get("box"), args.get("zoom", 2)
        if not isinstance(box, list) or len(box) != 4 or any(type(v) not in (int, float) or not math.isfinite(v) for v in box):
            raise ValueError("finite_normalized_box_required")
        if not (0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1):
            raise ValueError("invalid_box")
        if type(zoom) not in (int, float) or not math.isfinite(zoom) or not 1 <= zoom <= 4:
            raise ValueError("zoom_must_be_1_to_4")
    elif name in {"medret", "reflect", "verify"}:
        from skill_services_r55 import _query, _text, bound_candidate
        if name == "medret":
            _query(row, args)
        elif name == "reflect":
            if set(args) != {"reasoning"}:
                raise ValueError("reflect_requires_reasoning")
            _text(args, "reasoning")
        else:
            if set(args) != {"proposed_answer", "risk"}:
                raise ValueError("verify_requires_candidate_and_concrete_risk")
            bound_candidate(row, _text(args, "proposed_answer"))
            _text(args, "risk")


def decision(raw, row, base, runtime):
    from run_cxr_action_r41 import answer
    from cxr_task_completion_r43 import unscorable
    obj = parse(raw)
    if "calls" in obj and "answer" in obj:
        raise ProtocolError("contract", "calls_and_answer_are_mutually_exclusive")
    if "answer" in obj:
        if set(obj) != {"answer", "reason"} or not all(isinstance(value, str) for value in obj.values()):
            raise ProtocolError("contract", "answer_and_reason_strings_required")
        result = answer(obj)
        if result is None or unscorable(row, result):
            raise ProtocolError("contract", "answer_outside_original_task_output_domain")
        return "answer", result
    if set(obj) != {"calls", "reason"} or not isinstance(obj.get("reason"), str):
        raise ProtocolError("contract", "calls_and_top_level_reason_required")
    calls = obj["calls"]
    if not isinstance(calls, list) or not calls or any(not isinstance(call, dict) for call in calls):
        raise ProtocolError("validate_actions", "nonempty_list_of_call_objects_required")
    try:
        actions = base.validate_actions(obj, runtime, "M", len(calls), len(row["images"]))
        for call in actions:
            validate_tool_arguments(row, call)
    except (ValueError, TypeError, KeyError) as error:
        raise ProtocolError("validate_actions", str(error), type(error).__name__) from error
    return "calls", actions


def repair_prompt(error, attempt, action_prompt):
    return (f"Action protocol error ({error.stage}): {error.code}. "
            f"Format repair {attempt}/{MAX_REPAIRS} for the SAME decision stage. "
            "No tool was dispatched for this rejected reply; it supplied no observation. "
            "Return one JSON object. You may request valid registered tools with calls, "
            "or voluntarily submit the final answer/reason object. "
            "Correct the structure using the current evidence; do not invent tool observations.\n" + action_prompt)
