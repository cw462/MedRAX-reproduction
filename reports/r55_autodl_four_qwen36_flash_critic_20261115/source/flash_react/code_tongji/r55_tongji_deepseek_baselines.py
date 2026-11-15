"""Send Tongji AGI HTTPS requests over the experiment's private SSH listener."""

from http.client import HTTPSConnection
import socket
from urllib.request import HTTPRedirectHandler, HTTPSHandler, ProxyHandler, build_opener


MODEL = "DeepSeek-V4.1-Flash"
BASE_URL = "https://agi.tongji.edu.cn/v1"
ENDPOINT = BASE_URL + "/chat/completions"
PORT = 28444
LOGICAL_MODEL = "deepseek-flash"
ROUTE = {
    "transport": "tongji_agi_via_lab_ssh",
    "endpoint": ENDPOINT,
    "model_requested": MODEL,
    "logical_model": LOGICAL_MODEL,
    "enable_thinking": False,
}


class TongjiConnection(HTTPSConnection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._create_connection = self.connect_loopback

    @staticmethod
    def connect_loopback(address, timeout, source_address):
        if address != ("agi.tongji.edu.cn", 443):
            raise ValueError("Unexpected HTTPS destination for the Tongji connection")
        return socket.create_connection(("127.0.0.1", PORT), timeout, source_address)


class TongjiHTTPSHandler(HTTPSHandler):
    def https_open(self, request):
        return self.do_open(TongjiConnection, request, context=self._context)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = build_opener(ProxyHandler({}), TongjiHTTPSHandler(), NoRedirect())


def urlopen(request, timeout):
    if request.full_url not in (ENDPOINT, BASE_URL + "/models"):
        raise ValueError("Unexpected Tongji AGI API path")
    return _OPENER.open(request, timeout=timeout)


def wire_request(logical):
    if (logical["model"], logical["thinking"], logical["stream"]) != (
        LOGICAL_MODEL, {"type": "disabled"}, False
    ):
        raise ValueError("Unexpected R55 memory request")
    payload = dict(logical, model=MODEL, enable_thinking=False)
    del payload["thinking"]
    return payload


def valid_response(response):
    message = response["choices"][0]["message"]
    return response.get("model") == MODEL and not message.get("reasoning_content")
