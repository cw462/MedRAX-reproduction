"""DeepSeek API transport for lab scoring and memory calls."""

from http.client import RemoteDisconnected
from io import BytesIO
import json
from pathlib import Path
from ssl import SSLCertVerificationError
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener

MODEL = "deepseek-flash"
BASE_URL = "https://api.deepseek.com"
ENDPOINT = BASE_URL + "/chat/completions"
ROUTE = {"transport": "deepseek_official", "endpoint": ENDPOINT,
         "model_requested": MODEL, "logical_model": MODEL, "enable_thinking": False}
RETRY_DELAYS = (0.5, 1, 2)
RSI_ARTIFACTS = Path("/root/autodl-tmp/medrax_m5_data_rsi_v2_20261117_plus/artifacts")
REPLAY_ACTIVE_CALL = Path("model_calls/m5rsi_rad_1884_0042/retrieve/4")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


opener = build_opener(ProxyHandler({}), NoRedirect())


def retry_log():
    stream = Path.cwd().resolve()
    memory = stream / "external_memory"
    if RSI_ARTIFACTS in stream.parents and memory.is_dir():
        return memory / "transport_retries.jsonl"
    return None


def record_retry(path, error, attempt, result):
    cause = getattr(error, "reason", None)
    if not isinstance(cause, BaseException):
        cause = error
    number = getattr(cause, "errno", None)
    entry = {"reason_class": type(cause).__name__, "errno": number if isinstance(number, int) else None,
             "attempt": attempt, "result": result}
    try:
        with path.open("a", encoding="utf-8") as log:
            log.write(json.dumps(entry) + "\n")
    except OSError:
        print(json.dumps(entry), file=sys.stderr, flush=True)


def saved_json(path):
    return json.loads(path.read_bytes())


def replay_archived(memory, request):
    plan_file = memory / "transport_replay_plan.json"
    if not plan_file.exists() and not plan_file.is_symlink():
        return None
    if plan_file.is_symlink():
        raise ValueError("Unexpected DeepSeek replay plan link")
    plan = saved_json(plan_file)
    planned_active = Path(plan["active_call"])
    planned_archive = Path(plan["archived_call"])
    if (planned_active != REPLAY_ACTIVE_CALL or len(planned_archive.parts) != 4
            or planned_archive.parts[0] != "recovery" or ".." in planned_archive.parts
            or planned_archive.parts[-2:] != ("deepseek-retrieval-no-response", "call-4")):
        raise ValueError("Unexpected DeepSeek replay plan scope")
    active = memory / planned_active
    archived = memory.parent / planned_archive
    if active.resolve() != active or archived.resolve() != archived:
        raise ValueError("Unexpected DeepSeek replay evidence link")

    started = active / "started.json"
    result = active / "result.json"
    response = active / "response.raw"
    if not started.is_file():
        raise RuntimeError("Planned DeepSeek replay has no active start record")
    previous = saved_json(archived / "result.json")
    logical = saved_json(archived / "request.json")
    raw = (archived / "response.raw").read_bytes()
    if (previous.get("response_received") is not True or previous.get("error")
            or not valid_response(json.loads(raw)) or saved_json(active / "request.json") != logical):
        raise RuntimeError("Archived DeepSeek success does not match the active replay evidence")

    if result.exists() or response.exists():
        if result.is_file() and response.is_file():
            closed = saved_json(result)
            if closed.get("response_received") is True and not closed.get("error") and response.read_bytes() == raw:
                return None
        raise RuntimeError("Planned DeepSeek replay is only partially recorded")
    if request.get_method() != "POST" or json.loads(request.data) != logical:
        raise RuntimeError("Active DeepSeek replay request differs from the archived request")

    receipt = {"type": "archived_response_replay", "network_requests": 0,
               "active_call": planned_active.as_posix(), "archived_call": planned_archive.as_posix()}
    with (memory / "transport_replays.jsonl").open("a", encoding="utf-8") as log:
        log.write(json.dumps(receipt) + "\n")
    return BytesIO(raw)


def urlopen(request, timeout):
    if request.full_url not in (ENDPOINT, BASE_URL + "/models"):
        raise ValueError("Unexpected DeepSeek URL")
    log = retry_log()
    if log is None:
        return opener.open(request, timeout=timeout)
    if request.full_url == ENDPOINT:
        replay = replay_archived(log.parent, request)
        if replay is not None:
            return replay
    for attempt, delay in enumerate((*RETRY_DELAYS, None), start=1):
        try:
            return opener.open(request, timeout=timeout)
        except HTTPError:
            raise
        except (URLError, RemoteDisconnected) as error:
            if isinstance(getattr(error, "reason", None), SSLCertVerificationError):
                raise
            record_retry(log, error, attempt, "exhausted" if delay is None else "retrying")
            if delay is None:
                raise
            time.sleep(delay)


def matches(model):
    return isinstance(model, str) and model.lower() in ("deepseek-flash", "deepseek-v4.1-flash", "deepseek-v4.1-flash-1017")


def wire_request(logical):
    assert logical["model"] == MODEL and logical["thinking"] == {"type": "disabled"}
    return logical


def valid_response(response):
    message = response["choices"][0]["message"]
    return matches(response.get("model")) and not message.get("reasoning_content")
