from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from space_watch_cloud.http_adapter import ExactHttpAdapter, MAX_RESPONSE_BYTES  # noqa: E402


class Response:
    def __init__(self, uri: str, body: bytes): self.uri, self.stream = uri, io.BytesIO(body)
    def __enter__(self): return self
    def __exit__(self, *args): return None
    def geturl(self): return self.uri
    def read(self, size=-1): return self.stream.read(size)


class Opener:
    def __init__(self, result): self.result, self.calls = result, []
    def open(self, request, timeout):
        self.calls.append((request.full_url, timeout, request.get_method()))
        if isinstance(self.result, Exception): raise self.result
        return self.result


class HttpAdapterTests(unittest.TestCase):
    def test_ll2_json_projects_window_and_status_with_one_get(self) -> None:
        uri = "https://example.test/ll2"
        opener = Opener(Response(uri, b'{"window_start":"2026-09-01T00:00:00Z","status":{"id":2,"name":"To Be Determined"},"last_updated":"2026-08-29T00:00:00Z"}'))
        result = ExactHttpAdapter(opener)("f14-ll2-current-observation", uri, 60)
        self.assertEqual(result["status"], "available"); self.assertEqual(result["typed_content"]["status"]["id"], 2)
        self.assertEqual(opener.calls, [(uri, 60, "GET")])

    def test_fcc_projection_does_not_infer_landing_or_catch(self) -> None:
        uri = "https://example.test/fcc"
        opener = Opener(Response(uri, b"<html>returning the first-stage booster to the launch site</html>"))
        result = ExactHttpAdapter(opener)("f14-fcc-1597-ex-st-2026", uri, 60)
        self.assertEqual(result["typed_content"], {"action": "return_to_launch_site", "landing": "unavailable", "tower_catch": "unavailable"})

    def test_x_projection_keeps_identity_and_mission_binding_unavailable(self) -> None:
        uri = "https://example.test/x"
        opener = Opener(Response(uri, b"<meta content='Full-duration 60-second static fire of all six-engine vehicle'>"))
        result = ExactHttpAdapter(opener)("spacex-starship-six-engine-static-fire-2026-08-21", uri, 60)
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["typed_content"]["ship_identity"], "unavailable"); self.assertEqual(result["typed_content"]["flight14_binding"], "unavailable")

    def test_redirect_is_rejected_without_following(self) -> None:
        uri = "https://example.test/source"
        error = HTTPError(uri, 302, "Found", {"Location": "https://other.test/"}, None)
        opener = Opener(error)
        result = ExactHttpAdapter(opener)("f14-ll2-current-observation", uri, 60)
        self.assertEqual(result["status"], "unavailable"); self.assertIn("redirect", result["limitations"][0])
        self.assertEqual(len(opener.calls), 1); self.assertEqual(result["redirect_count"], 0)

    def test_changed_response_uri_and_oversize_fail_closed(self) -> None:
        uri = "https://example.test/source"
        changed = ExactHttpAdapter(Opener(Response("https://other.test/", b"{}")))("f14-ll2-current-observation", uri, 60)
        self.assertEqual(changed["status"], "unavailable")
        oversized = ExactHttpAdapter(Opener(Response(uri, b"x" * (MAX_RESPONSE_BYTES + 1))))("f14-fcc-1597-ex-st-2026", uri, 60)
        self.assertEqual(oversized["status"], "unavailable"); self.assertIn("1 MiB", oversized["limitations"][0])


if __name__ == "__main__": unittest.main()
