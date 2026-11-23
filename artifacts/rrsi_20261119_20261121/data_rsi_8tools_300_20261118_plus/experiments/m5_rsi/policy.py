"""Editable M5 instructions and a capability-free numeric harness policy."""

import ast
import math


# These substrings occur in the original R55 solver or CerebraFusionMemory calls.
# The surrounding output schema, call topology, and data in those messages are fixed.
P0 = {
    "solver_instruction": "Select useful registered tools as needed",
    "memory_write": "Extract ABSTRACT, GENERALIZABLE patterns from this successful task.",
    "advice_synthesis": "Provide OPTIONAL REFERENCE for an autonomous AI agent.",
}
H0 = """top_k = 5
semantic_weight = 0.8
max_neighbors = 3

def rank(score, position, is_neighbor):
    return score

def keep(score, position, is_neighbor):
    return True
"""

EXPRESSION_NODES = (
    ast.Expression, ast.BoolOp, ast.IfExp, ast.Compare, ast.BinOp, ast.UnaryOp,
    ast.Constant, ast.Name, ast.Load, ast.Add, ast.Sub, ast.Mult, ast.UAdd, ast.USub,
    ast.And, ast.Or, ast.Not, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
)
ARGUMENTS = ["score", "position", "is_neighbor"]


def prompt_set(value):
    if set(value) != set(P0):
        raise ValueError("Editable prompt components differ from the frozen set")
    if any(not isinstance(text, str) or not text.strip() or len(text) > 2400 or "\x00" in text
           for text in value.values()):
        raise ValueError("Invalid instruction proposal")
    return dict(value)


def edit_instruction(messages, key, value, *, role, required=False):
    anchor = P0[key]
    if value == anchor:
        return messages
    matches = [i for i, m in enumerate(messages)
               if m.get("role") == role and isinstance(m.get("content"), str) and anchor in m["content"]]
    if len(matches) > 1 or (required and not matches):
        raise ValueError(f"Unexpected native prompt binding for {key}")
    if not matches:
        return messages
    i = matches[0]
    if messages[i]["content"].count(anchor) != 1:
        raise ValueError(f"Multiple native prompt anchors for {key}")
    result = list(messages)
    result[i] = {**messages[i], "content": messages[i]["content"].replace(anchor, value, 1)}
    return result


def compile_expression(value, name):
    expression = ast.Expression(value)
    nodes = list(ast.walk(expression))
    if len(nodes) > 90 or any(type(node) not in EXPRESSION_NODES for node in nodes):
        raise ValueError(f"Only bounded numeric expressions are editable in {name}")
    for node in nodes:
        if isinstance(node, ast.Name) and node.id not in ARGUMENTS:
            raise ValueError(f"Unrecognized policy variable {node.id}")
        if isinstance(node, ast.Constant):
            val = node.value
            if type(val) not in (int, float, bool) or abs(val) > 100:
                raise ValueError("Only bounded numeric and boolean literals are allowed")
    return compile(ast.fix_missing_locations(expression), f"<m5-policy:{name}>", "eval")


class HarnessPolicy:
    """A proposed file has three bounded literals and two pure numeric expressions.

    The file is parsed, never imported. Only expressions over the three scalar
    features are compiled, with no calls, attributes, strings, or ambient access.
    """

    def __init__(self, source):
        if not isinstance(source, str) or len(source) > 4_000:
            raise ValueError("Policy source is missing or oversized")
        values, functions = {}, {}
        for node in ast.parse(source, mode="exec").body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
                if name not in {"top_k", "semantic_weight", "max_neighbors"} or name in values:
                    raise ValueError(f"Cannot assign {name}")
                values[name] = ast.literal_eval(node.value)
                continue
            if not isinstance(node, ast.FunctionDef) or node.name not in {"rank", "keep"} or node.name in functions:
                raise ValueError("Only rank/keep functions and retrieval settings are permitted")
            args = node.args
            annotated = any(x.annotation is not None for x in args.args)
            if (node.decorator_list or node.returns is not None or getattr(node, "type_params", ())
                    or args.posonlyargs or args.vararg or args.kwonlyargs or args.kwarg or args.defaults
                    or annotated or [x.arg for x in args.args] != ARGUMENTS or len(node.body) != 1
                    or not isinstance(node.body[0], ast.Return)):
                raise ValueError(f"Invalid policy interface for {node.name}")
            functions[node.name] = compile_expression(node.body[0].value, node.name)
        if set(values) != {"top_k", "semantic_weight", "max_neighbors"} or set(functions) != {"rank", "keep"}:
            raise ValueError("The whole harness policy interface is required")
        if (type(values["top_k"]) is not int or not 1 <= values["top_k"] <= 10
                or type(values["max_neighbors"]) is not int or not 0 <= values["max_neighbors"] <= 6
                or type(values["semantic_weight"]) not in (int, float) or not 0 <= values["semantic_weight"] <= 1):
            raise ValueError("Retrieval settings outside the allowed range")
        self.source = source
        self.values = values
        self.functions = functions
        for score in (0., .22, .75, 1.):
            self.rank(score, 1, False)
            self.keep(score, 1, True)

    def rank(self, score, position, is_neighbor):
        value = self._evaluate("rank", score, position, is_neighbor)
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("Harness rank must be finite")
        return value

    def keep(self, score, position, is_neighbor):
        value = self._evaluate("keep", score, position, is_neighbor)
        if type(value) is not bool:
            raise ValueError("Harness keep must be boolean")
        return value

    def _evaluate(self, name, score, position, is_neighbor):
        return eval(self.functions[name], {"__builtins__": {}}, {
            "score": float(score), "position": int(position), "is_neighbor": bool(is_neighbor),
        })

    def apply(self, provider):
        if self.source == H0:
            # DATA and GEPA use the loaded native baseline without any override.
            return
        provider.top_k = self.values["top_k"]
        weight = self.values["semantic_weight"]
        provider.search_weights = {"text": 1 - weight, "semantic": weight}
        provider.max_neighbors_expand = self.values["max_neighbors"]
        native = provider._graph_expand

        def expand(initial, query):
            pairs, edges = native(initial, query)
            seed_nodes = {key for key, _ in initial}
            choices = []
            for ix, (key, score) in enumerate(pairs, 1):
                features = (score, ix, key not in seed_nodes)
                if self.keep(*features):
                    choices.append((self.rank(*features), key, score))
            choices.sort(key=lambda item: item[0], reverse=True)
            return [(key, score) for _, key, score in choices], edges

        provider._graph_expand = expand
