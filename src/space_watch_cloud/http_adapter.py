"""Repository-owned, standard-library, exact-URI D1 HTTP acquisition adapter."""

from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_RESPONSE_BYTES = 1_048_576
USER_AGENT = "space-watch-core-d1/0.1 (+exact-public-carrier; no-retry)"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def _observed_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _text(body: bytes) -> str:
    value = body.decode("utf-8", errors="replace")
    metadata = " ".join(match.group(1) or match.group(2) for match in re.finditer(r"<meta\b[^>]*\bcontent=(?:\"([^\"]*)\"|'([^']*)')[^>]*>", value, flags=re.I))
    value = re.sub(r"<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>", " ", value, flags=re.I | re.S)
    return re.sub(r"\s+", " ", html.unescape(metadata + " " + re.sub(r"<[^>]+>", " ", value))).strip()


def _project(source_id: str, body: bytes) -> tuple[str, dict[str, Any] | None, list[str]]:
    if source_id == "f14-ll2-current-observation":
        try:
            value = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return "unavailable", None, ["exact LL2 carrier did not return valid JSON"]
        status = value.get("status") if isinstance(value, dict) else None
        window = value.get("window_start") if isinstance(value, dict) else None
        precision = value.get("net_precision") if isinstance(value, dict) else None
        if not isinstance(status, dict) or not isinstance(window, str) or not isinstance(precision, dict):
            return "unavailable", None, ["LL2 response lacked required window_start, status, or net_precision fields", "aggregate observation only; no claim promotion"]
        precision_name = precision.get("name")
        if not isinstance(precision_name, str):
            return "unavailable", None, ["LL2 net_precision.name was unavailable", "aggregate observation only; no claim promotion"]
        normalized_precision = precision_name.strip().lower()
        if normalized_precision == "month" and re.fullmatch(r"\d{4}-\d{2}-.+", window):
            window_value = window[:7] + "-TBD"
            precision_value = "month"
        else:
            window_value = window
            precision_value = normalized_precision
        return "available", {"window": {"value": window_value, "precision": precision_value}, "status": {"id": status.get("id"), "name": status.get("name")}}, ["aggregate observation only; not an operator or regulator window", "last_updated is observation metadata and excluded from the comparison digest"]
    text = _text(body)
    lowered = text.lower()
    if source_id == "f14-fcc-1597-ex-st-2026":
        if re.search(r"return(?:ing)?\s+(?:the\s+)?(?:first[- ]stage|booster)?.{0,80}launch site", lowered):
            return "available", {"action": "return_to_launch_site", "landing": "unavailable", "tower_catch": "unavailable"}, ["return does not imply landing, tower catch, catch attempt, or launch window"]
        return "unavailable", None, ["exact FCC carrier did not expose the frozen return-to-launch-site statement"]
    if source_id == "spacex-starship-six-engine-static-fire-2026-08-21":
        static_fire = "static fire" in lowered
        six_engines = re.search(r"(?:six|6)[ -](?:engine|raptor)", lowered) is not None
        duration = re.search(r"(?:60[ -]second|60\s*s(?:ec(?:ond)?)?|full[- ]duration)", lowered) is not None
        if static_fire and six_engines and duration:
            return "available", {"action": "full_duration_60_second_six_engine_static_fire", "engine_count": 6, "ship_identity": "unavailable", "flight14_binding": "unavailable"}, ["hardware event only; no Ship 41 identity or Flight 14 mission binding"]
        return "unavailable", None, ["exact X carrier did not expose all frozen static-fire fields without login or alternate access"]
    return "unavailable", None, ["source_id is not supported by the concrete D1 adapter"]


class ExactHttpAdapter:
    """One ``open`` call per invocation; redirects and response overflow fail closed."""

    def __init__(self, opener=None):  # noqa: ANN001
        self._opener = opener or build_opener(NoRedirect())

    def __call__(self, source_id: str, exact_uri: str, timeout: float) -> dict[str, Any]:
        attempted_at = _observed_now()
        request = Request(exact_uri, headers={"User-Agent": USER_AGENT, "Accept": "application/json,text/html;q=0.9,*/*;q=0.1"}, method="GET")
        try:
            with self._opener.open(request, timeout=timeout) as response:
                if response.geturl() != exact_uri:
                    return self._result("unavailable", attempted_at, exact_uri, None, ["response URI differed from exact carrier; redirect/substitution rejected"])
                body = response.read(MAX_RESPONSE_BYTES + 1)
                if len(body) > MAX_RESPONSE_BYTES:
                    return self._result("unavailable", attempted_at, exact_uri, None, ["response exceeded fixed 1 MiB limit"])
        except HTTPError as exc:
            reason = "redirect response rejected" if 300 <= exc.code < 400 else f"HTTP status {exc.code}"
            return self._result("unavailable", attempted_at, exact_uri, None, [reason])
        except (URLError, TimeoutError, OSError) as exc:
            return self._result("unavailable", attempted_at, exact_uri, None, [f"network acquisition unavailable: {type(exc).__name__}"])
        status, typed_content, limitations = _project(source_id, body)
        return self._result(status, attempted_at, exact_uri, typed_content, limitations)

    @staticmethod
    def _result(status: str, attempted_at: str, exact_uri: str, typed_content: dict[str, Any] | None, limitations: list[str]) -> dict[str, Any]:
        return {"status": status, "attempted_at": attempted_at, "final_uri": exact_uri, "redirect_count": 0, "login_used": False, "search_used": False, "alternate_carrier_used": False, "retry_used": False, "typed_content": typed_content, "limitations": limitations}
