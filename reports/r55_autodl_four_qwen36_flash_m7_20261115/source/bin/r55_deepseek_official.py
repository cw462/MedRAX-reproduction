
"""DeepSeek API transport for lab scoring and memory calls."""
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener

MODEL = "deepseek-flash"
BASE_URL = "https://api.deepseek.com"
ENDPOINT = BASE_URL + "/chat/completions"
ROUTE = {"transport": "deepseek_official", "endpoint": ENDPOINT,
         "model_requested": MODEL, "logical_model": MODEL, "enable_thinking": False}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


opener = build_opener(ProxyHandler({}), NoRedirect())


def urlopen(request, timeout):
    if request.full_url not in (ENDPOINT, BASE_URL + "/models"):
        raise ValueError("Unexpected DeepSeek URL")
    return opener.open(request, timeout=timeout)


def matches(model):
    return isinstance(model, str) and model.lower() in ("deepseek-flash", "deepseek-v4.1-flash", "deepseek-v4.1-flash-1017")


def wire_request(logical):
    assert logical["model"] == MODEL and logical["thinking"] == {"type": "disabled"}
    return logical


def valid_response(response):
    message = response["choices"][0]["message"]
    return matches(response.get("model")) and not message.get("reasoning_content")
