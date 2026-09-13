"""Run `python test_ai.py`; optional real, fictional-input check: `python test_ai.py --live`."""

from copy import deepcopy
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from unittest.mock import patch

from ai_service import AIService, MAX_CONTEXT_CHARS, make_context, prompt_for, protect_key, validate_base, validate_result


def workspace():
    return {"topics": [{"id": "harbor", "title": "虚构港城", "deletedAt": None}, {"id": "forest", "title": "虚构森林", "deletedAt": None}],
            "ideas": [{"id": "tide", "topicId": "harbor", "parentId": None, "title": "退潮集市", "body": "虚构城市的集市只在退潮时开放。请发展一个日常事件。", "tags": [], "updatedAt": "2026-01-01", "deletedAt": None},
                      {"id": "bird", "topicId": "forest", "parentId": None, "title": "飞鸟", "body": "虚构林地的飞鸟。", "tags": [], "updatedAt": "2026-01-01", "deletedAt": None}]}


def suggestion(**overrides):
    return {"type": "rewrite", "ideaId": "tide", "topicId": "harbor", "parentId": None, "title": "潮水回来之前", "body": "虚构港城里，一位摊主在退潮集市等最后一位客人。", "kind": "idea", "tags": ["虚构事件"], "reason": "将城市规则变成可展开的场景。", **overrides}


def fails(call, exception=ValueError):
    try:
        call()
    except exception:
        return
    raise AssertionError("Expected validation failure")


def wait_done(service, identifier, seconds=3):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        job = service.get_job(identifier)
        if job["status"] in {"completed", "failed"}:
            return job
        time.sleep(0.01)
    raise AssertionError("Worker did not finish")


class FakeService(AIService):
    def __init__(self, directory):
        self.started, self.release = threading.Event(), threading.Event()
        self.calls, self.failure = [], None
        super().__init__(directory)

    def _run(self, settings, mode, context):
        self.calls.append((mode, context, deepcopy(settings)))
        self.started.set()
        assert self.release.wait(3)
        if self.failure:
            raise self.failure
        target = next(item for item in context["ideas"] if item["role"] == "target")
        return {"summary": "虚构样例整理建议", "suggestions": [suggestion(ideaId=target["id"], topicId=target["topicId"])]}


def api_check(service):
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            seen.append(self.path)
            assert self.headers["Authorization"] == "Bearer fictional-environment-key"
            if self.path.startswith("/denied/"):
                self.send_response(401)
                self.end_headers()
                self.wfile.write(b"fictional-environment-key")
            elif self.path.startswith("/redirect/"):
                self.send_response(302)
                self.send_header("Location", "/v1/models")
                self.end_headers()
            else:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({"data": [{"id": "listed-model", "name": "Listed Model"}, {"id": "listed-model"}, {"id": "bad\nmodel"}]}).encode("utf-8"))

        def do_POST(self):
            seen.append(self.path)
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert body["model"] == "fictional-model" and body["response_format"] == {"type": "json_object"}
            assert self.headers["Authorization"] == "Bearer fictional-environment-key"
            if self.path.startswith("/redirect/"):
                self.send_response(302)
                self.send_header("Location", "/v1/chat/completions")
                self.end_headers()
            elif self.path.startswith("/denied/"):
                self.send_response(401)
                self.end_headers()
                self.wfile.write(b"fictional-environment-key")
            else:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"choices": [{"message": {"content": json.dumps({"summary": "虚构 API 测试", "suggestions": [suggestion()]}, ensure_ascii=False)}}]}, ensure_ascii=False).encode("utf-8"))

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with patch.dict(os.environ, {"SPARKSPACE_AI_API_KEY": "fictional-environment-key"}):
            settings = {"apiBase": f"http://127.0.0.1:{server.server_port}/v1", "model": "fictional-model", "protectedKey": ""}
            assert service._run_api(settings, "虚构测试输入")["suggestions"][0]["ideaId"] == "tide"
            for route, expected in (("redirect", "重定向"), ("denied", "认证")):
                settings["apiBase"] = f"http://127.0.0.1:{server.server_port}/{route}"
                try:
                    service._run_api(settings, "虚构测试输入")
                except ValueError as error:
                    assert expected in str(error) and "fictional-environment-key" not in str(error)
                else:
                    raise AssertionError("Expected sanitized API failure")
            assert seen == ["/v1/chat/completions", "/redirect/chat/completions", "/denied/chat/completions"]
            service.update_settings({"apiBase": f"http://127.0.0.1:{server.server_port}/v1/chat/completions"})
            assert service.list_models("api") == {"models": [{"id": "listed-model", "name": "Listed Model"}], "source": "api"}
            for route in ("denied", "redirect"):
                service.update_settings({"apiBase": f"http://127.0.0.1:{server.server_port}/{route}"})
                listing = service.list_models("api")
                assert listing["models"] == [] and listing["warning"] and "fictional-environment-key" not in json.dumps(listing)
            assert seen[-3:] == ["/v1/models", "/denied/models", "/redirect/models"]
            service.update_settings({"apiBase": ""})
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)


def selection_checks():
    state = workspace()
    root = state["ideas"][0]
    state["ideas"] += [{**root, "id": "market", "parentId": "tide", "body": "本次应处理的子问题"},
                       {**root, "id": "closing", "parentId": "market"},
                       {**root, "id": "unrelated", "body": "同主题但不相关的问题"}]
    focused = make_context(state, "harbor", ["market"])
    assert {item["id"]: item["role"] for item in focused["ideas"]} == {"market": "target", "tide": "background"}
    assert focused["contextStats"]["targetIdeas"] == focused["contextStats"]["backgroundIdeas"] == 1
    assert focused["contextStats"]["omittedIdeas"] == 0
    for identifier in ("tide", "unrelated", "closing"):
        for kind in ("rewrite", "move"):
            fails(lambda identifier=identifier, kind=kind: validate_result({"summary": "", "suggestions": [suggestion(type=kind, ideaId=identifier)]}, focused))
    new = validate_result({"summary": "", "suggestions": [suggestion(type="new", ideaId=None, topicId=None)]}, focused)["suggestions"][0]
    assert new["parentId"] == "market" and new["topicId"] == "harbor"
    fails(lambda: validate_result({"summary": "", "suggestions": [suggestion(type="new", ideaId=None, parentId="tide")]}, focused))
    expanded = make_context(state, "harbor", ["tide"], True)
    assert {item["id"] for item in expanded["ideas"]} == {"tide", "market", "closing"}
    assert expanded["contextStats"]["targetIdeas"] == 3 and expanded["contextStats"]["backgroundIdeas"] == 0
    multi = make_context(state, "harbor", ["market", "unrelated"])
    fails(lambda: validate_result({"summary": "", "suggestions": [suggestion(type="new", ideaId=None)]}, multi))
    assert validate_result({"summary": "", "suggestions": [suggestion(type="new", ideaId=None, parentId="market")]}, multi)["suggestions"][0]["parentId"] == "market"
    for choices in ([], ["bird"], ["missing"], ["market", "market"], [None], ["market"] * 81):
        fails(lambda choices=choices: make_context(state, "harbor", choices))
    fails(lambda: make_context(state, None, ["tide"]))
    fails(lambda: make_context(state, "harbor", ["market"], "true"))
    many = deepcopy(state)
    many["ideas"] += [{**root, "id": "desc-" + str(index), "parentId": "tide", "body": "长" * 50000} for index in range(100)]
    bounded = make_context(many, "harbor", ["tide"], True)
    assert bounded["ideas"][0]["id"] == "tide" and bounded["contextStats"]["omittedTargetIdeas"] > 0
    assert len(json.dumps(bounded, ensure_ascii=False, separators=(",", ":"))) <= MAX_CONTEXT_CHARS
    with patch("ai_service.MAX_CONTEXT_CHARS", 200):
        fails(lambda: make_context(state, "harbor", ["market"]))
    return state


def override_checks(service, state):
    service.update_settings({"model": "fictional-default", "customPrompt": "默认写作要求"})
    for number, (left, right) in enumerate((
        ({"model": "fictional-one"}, {"model": "fictional-two"}),
        ({"prompt": ""}, {"prompt": "本次补充要求"}),
        ({"ideaIds": ["tide"]}, {"ideaIds": ["market"]}),
        ({"includeDescendants": False}, {"includeDescendants": True}),
    )):
        service.release.clear()
        service.started.clear()
        before = len(service.calls)
        first_options = {"ideaIds": ["tide"], **left}
        first = service.submit(state, 20 + number, "organize", "harbor", **first_options)
        assert service.started.wait(2)
        assert service.submit(state, 20 + number, "organize", "harbor", **first_options)["id"] == first["id"]
        second = service.submit(state, 20 + number, "organize", "harbor", **{"ideaIds": ["tide"], **right})
        assert first["id"] != second["id"]
        service.release.set()
        assert wait_done(service, first["id"])["status"] == wait_done(service, second["id"])["status"] == "completed"
        settings = service.calls[before][2]
        assert settings["model"] == first["model"] and settings["customPrompt"] == first["prompt"]
        assert first["prompt"] == left.get("prompt", "默认写作要求")
        assert first["targetIdeaIds"] and first["ideaIds"] == first_options["ideaIds"]
    assert service.get_settings()["model"] == "fictional-default" and service.get_settings()["customPrompt"] == "默认写作要求"
    rendered = prompt_for("organize", make_context(state, "harbor", ["market"]), "本次补充要求")
    assert "本次补充要求" in rendered and "默认写作要求" not in rendered
    fails(lambda: service.update_settings({"customPrompt": "文" * 12001}))
    fails(lambda: service.submit(state, 90, "organize", "harbor", prompt="文" * 12001))
    fails(lambda: service.submit(state, 90, "organize", "harbor", model="bad\nmodel"))


def checks():
    selected_state = selection_checks()
    state = workspace()
    before = deepcopy(state)
    detailed = deepcopy(state)
    for topic in detailed["topics"]:
        topic.update(context="虚构背景", constraints="保留各主题自己的约束", output="候选事件草稿")
    all_context = make_context(detailed)
    assert all(item["context"] == "虚构背景" and item["constraints"] == "保留各主题自己的约束" and item["output"] == "候选事件草稿" for item in all_context["topics"])
    assert all_context["contextStats"]["truncatedFields"] == all_context["contextStats"]["overviewOmissions"] == 0
    detailed["topics"][1].update(description="文" * 301, goal="文" * 501)
    selected = make_context(detailed, "harbor")
    assert selected["topics"][0]["constraints"] == "保留各主题自己的约束" and "constraints" not in selected["topics"][1]
    assert selected["contextStats"]["truncatedFields"] == 0 and selected["contextStats"]["overviewOmissions"] == 5
    wide = {"topics": [{"id": str(index), "title": str(index), **{key: "文" * 50000 for key in ("description", "goal", "context", "constraints", "output")}} for index in range(20)], "ideas": []}
    wide_context = make_context(wide)
    assert len(wide_context["topics"]) == 20 and all(item["context"] and item["constraints"] for item in wide_context["topics"])
    assert len(json.dumps(wide_context, ensure_ascii=False, separators=(",", ":"))) <= MAX_CONTEXT_CHARS
    context = make_context(state, "harbor")
    assert validate_result({"summary": "好", "suggestions": [suggestion()]}, context)["suggestions"][0]["ideaId"] == "tide"
    fails(lambda: validate_result({"summary": "好", "suggestions": [suggestion(ideaId="missing")]}, context))
    fails(lambda: validate_result({"summary": "好", "suggestions": [suggestion(type=[])]}, context))
    fails(lambda: validate_result({"summary": "好", "suggestions": [suggestion()] * 13}, context))
    cross = validate_result({"summary": "好", "suggestions": [suggestion(parentId="bird")]}, make_context(state))
    assert cross["suggestions"][0]["parentId"] is None
    many = deepcopy(state)
    many["ideas"] = [{**state["ideas"][0], "id": "idea-" + str(number), "body": "文" * 50000} for number in range(100)]
    bounded = make_context(many, "harbor")
    assert len(bounded["ideas"]) + len(bounded["topics"]) <= 80
    assert len(json.dumps(bounded, ensure_ascii=False, separators=(",", ":"))) <= MAX_CONTEXT_CHARS
    assert bounded["contextStats"]["omittedIdeas"] and bounded["contextStats"]["truncatedFields"]
    deleted = deepcopy(state)
    deleted["topics"][0]["deletedAt"] = "deleted"
    fails(lambda: make_context(deleted, "harbor"))
    for address in ("http://example.com/v1", "https://user:password@example.com", "https://example.com/#token", "https://example.com/?api_key=secret", "https://example.com:99999"):
        fails(lambda address=address: validate_base(address))
    assert validate_base("http://127.0.0.1:1234/v1/") == "http://127.0.0.1:1234/v1"

    with tempfile.TemporaryDirectory() as directory:
        service = FakeService(directory)
        try:
            assert service.get_settings()["autoMode"] == "off"
            fails(lambda: service.update_settings({"provider": []}))
            fails(lambda: service.update_settings({"command": "arbitrary"}))
            fails(lambda: service.update_settings({"model": "bad\nmodel"}))
            api_check(service)
            cache = Path(directory, "models_cache.json")
            cache.write_text(json.dumps({"models": [{"slug": "fictional-cache-model", "display_name": "Cache Model", "visibility": "list"}, {"slug": "hidden-model", "visibility": "hide"}]}), encoding="utf-8")
            with patch.dict(os.environ, {"CODEX_HOME": directory}):
                assert service.list_models("codex") == {"models": [{"id": "fictional-cache-model", "name": "Cache Model"}], "source": "codex-cache"}
                cache.write_text("broken-json", encoding="utf-8")
                assert service.list_models("codex")["warning"]
            if os.name == "nt":
                secret = "fictional-self-check-not-a-credential"
                ciphertext = protect_key(secret)
                assert protect_key(ciphertext, decrypt=True) == secret
                service.update_settings({"apiKey": secret})
                assert secret not in Path(directory, "ai-state.json").read_text(encoding="utf-8")
                assert secret not in json.dumps(service.get_settings())
                assert service.get_settings()["hasApiKey"]
                service.update_settings({"apiKey": ""})
            first = service.submit(state, 1, "organize", "harbor")
            assert service.started.wait(2)
            assert service.get_job(first["id"])["status"] == "running"
            assert service.submit(state, 1, "organize", "harbor")["id"] == first["id"]
            second = service.submit(state, 2, "organize", "harbor")
            fails(lambda: service.submit(state, 3, "organize", "harbor"), RuntimeError)
            service.release.set()
            assert wait_done(service, first["id"])["status"] == "completed"
            assert wait_done(service, second["id"])["status"] == "completed"
            assert len(service.calls) == 2 and state == before
            override_checks(service, selected_state)
            service.failure = subprocess.TimeoutExpired("redacted", 300)
            timed = service.submit(state, 3, "organize", "harbor")
            failed = wait_done(service, timed["id"])
            assert failed["status"] == "failed" and failed["result"] is None and "超时" in failed["error"]
            service.failure = None
            with patch("ai_service.AUTO_DELAY_SECONDS", 0.03):
                service.update_settings({"autoMode": "organize"})
                service.note_change(state, 9)
                service.note_change(state, 8)
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline and not any(job["trigger"] == "auto" for job in service.list_jobs()["jobs"]):
                    time.sleep(0.01)
                automatic = next(job for job in service.list_jobs()["jobs"] if job["trigger"] == "auto")
                assert automatic["baseRevision"] == 9
                assert wait_done(service, automatic["id"])["status"] == "completed"
                service.note_change(state, 10)
                service.update_settings({"autoMode": "off"})
                assert service._auto is None
        finally:
            service.release.set()
            service.close()
        persisted = Path(directory, "ai-state.json")
        saved = json.loads(persisted.read_text(encoding="utf-8"))
        saved["jobs"][0]["status"] = "running"
        saved["jobs"][1]["status"] = "queued"
        saved["settings"].pop("customPrompt")
        for key in ("ideaIds", "includeDescendants", "targetIdeaIds", "model", "prompt"):
            saved["jobs"][0].pop(key)
        persisted.write_text(json.dumps(saved, ensure_ascii=False), encoding="utf-8")
        restarted = FakeService(directory)
        try:
            assert all(job["status"] in {"completed", "failed"} for job in restarted.list_jobs()["jobs"])
            assert not restarted.calls
            assert restarted.get_settings()["customPrompt"] == "" and restarted.get_settings()["model"] == "fictional-default"
            migrated = restarted.get_job(saved["jobs"][0]["id"])
            assert migrated["ideaIds"] is None and migrated["targetIdeaIds"] is None and migrated["model"] is None
        finally:
            restarted.close()
    print("PASS: AI target/background/descendant scope, branching, context bounds, model catalogs/overrides, custom prompts, DPAPI, API auth/redirects, queue deduplication, timeout, debounce, migration/restart, and workspace preservation")


def live():
    with tempfile.TemporaryDirectory(prefix="sparkspace-fictional-ai-") as directory:
        service = AIService(directory)
        started = time.monotonic()
        try:
            job = service.submit(workspace(), 0, "develop", "harbor")
            result = wait_done(service, job["id"], seconds=310)
            print(json.dumps({"status": result["status"], "provider": result["provider"], "modelConfigured": service.get_settings()["model"],
                              "seconds": round(time.monotonic() - started, 1), "suggestions": len(result["result"]["suggestions"]) if result["result"] else 0,
                              "error": result["error"]}, ensure_ascii=False))
            return result["status"] == "completed"
        finally:
            service.close()


if __name__ == "__main__":
    if "--live" in sys.argv:
        raise SystemExit(0 if live() else 1)
    checks()
