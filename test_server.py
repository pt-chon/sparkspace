"""Run: python test_server.py. Uses temporary files and loopback only."""

from copy import deepcopy
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
import http.client
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import time

from server import APIError, EMPTY_WORKSPACE, MAX_BYTES, SparkServer, Store, validate_workspace


def example():
    topic = {
        "id": "topic-1", "title": "测试主题", "description": "", "goal": "整理灵感",
        "context": "", "constraints": "", "output": "Markdown", "template": "general",
        "color": "sage", "createdAt": "2026-09-11T00:00:00Z", "updatedAt": "2026-09-11T00:00:00Z",
        "archived": False, "deletedAt": None,
    }
    idea = {
        "id": "idea-1", "topicId": "topic-1", "parentId": None, "title": "保留原文",
        "body": '<script>alert("仅作为文本")</script>', "kind": "idea", "status": "spark",
        "tags": ["测试"], "pinned": False, "source": "", "createdAt": topic["createdAt"],
        "updatedAt": topic["updatedAt"], "deletedAt": None,
    }
    return {"schemaVersion": 1, "topics": [topic], "ideas": [idea]}


def request(server, method, path, body=None, cookie=None, headers=None, host=None):
    host = host or f"127.0.0.1:{server.server_port}"
    request_headers = {"Host": host}
    if cookie:
        request_headers["Cookie"] = cookie
    payload = None
    if method in {"POST", "PUT"}:
        payload = json.dumps({} if body is None else body, ensure_ascii=False).encode("utf-8")
        request_headers.update({"Origin": f"http://{host}", "Content-Type": "application/json"})
    request_headers.update(headers or {})
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    try:
        connection.request(method, path, body=payload, headers=request_headers)
        response = connection.getresponse()
        raw = response.read()
        value = json.loads(raw) if "application/json" in response.getheader("Content-Type", "") else raw
        return response.status, value, dict(response.getheaders())
    finally:
        connection.close()


def start(data, public):
    server = SparkServer(("127.0.0.1", 0), data, public)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def stop(server, thread):
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def finished_job(server, cookie, identifier):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        status, job, _ = request(server, "GET", "/api/ai/jobs/" + identifier, cookie=cookie)
        assert status == 200
        if job["status"] in {"completed", "failed"}:
            return job
        time.sleep(0.01)
    raise AssertionError("Mock AI job did not finish")


def check():
    with tempfile.TemporaryDirectory(prefix="sparkspace-test-") as directory:
        root = Path(directory)
        public = root / "public"
        public.mkdir()
        (public / "index.html").write_text("<!doctype html><title>测试</title>", encoding="utf-8")
        (public / "core.mjs").write_text("export const ok = true;", encoding="utf-8")
        server, thread = start(root / "data", public)
        run_inputs, model_queries = [], []

        def fake_run(settings, mode, context):
            run_inputs.append((deepcopy(settings), deepcopy(context)))
            target = next(item for item in context["ideas"] if item["role"] == "target")
            return {"summary": "仅为测试的 AI 建议", "suggestions": [{"type": "new" if mode == "develop" else "rewrite",
                    "ideaId": None if mode == "develop" else target["id"], "topicId": target["topicId"], "parentId": None,
                    "title": "测试分支", "body": "建议正文", "kind": "idea", "tags": [], "reason": "验证处理范围"}]}

        def fake_models(provider):
            model_queries.append(provider)
            return {"models": [{"id": "fictional-model", "name": "Fictional Model"}], "source": "codex-cache" if provider == "codex" else "api"}

        # Never let route tests dispatch a real generation, even if an assertion fails.
        server.ai._run = fake_run
        server.ai.list_models = fake_models
        try:
            assert request(server, "GET", "/api/health")[1] == {"app": "sparkspace", "ok": True}
            assert request(server, "GET", "/api/state")[:2] == (401, {"error": "请在电脑上生成配对码后连接", "code": "PAIR_REQUIRED"})
            remote_host = f"phone.example:{server.server_port}"
            assert "Set-Cookie" not in request(server, "GET", "/", host=remote_host)[2]
            status, _, headers = request(server, "GET", "/")
            assert status == 200 and "HttpOnly" in headers["Set-Cookie"] and "SameSite=Strict" in headers["Set-Cookie"]
            owner = headers["Set-Cookie"].split(";", 1)[0]
            assert request(server, "GET", "/api/state", cookie=owner, host=remote_host)[0] == 401
            assert request(server, "GET", "/api/state", cookie=owner)[1] == {"revision": 0, "workspace": EMPTY_WORKSPACE}
            assert request(server, "GET", "/api/connection", cookie=owner)[1]["localOwner"] is True
            assert request(server, "GET", "/data/workspace.sqlite3", cookie=owner)[0] == 404
            assert request(server, "GET", "/../data/workspace.sqlite3", cookie=owner)[0] == 404
            assert request(server, "GET", "/core.mjs")[0] == 200
            assert request(server, "POST", "/api/pair-code", cookie=owner, headers={"Origin": "http://attacker.example"})[0] == 403
            assert request(server, "POST", "/api/pair-code", cookie=owner, headers={"Origin": ""})[0] == 403
            assert request(server, "POST", "/api/pair-code", cookie=owner, headers={"Content-Type": "text/plain"})[0] == 415
            assert request(server, "PUT", "/api/state", cookie=owner, headers={"Content-Length": str(MAX_BYTES + 1)})[0] == 413

            code = request(server, "POST", "/api/pair-code", cookie=owner)[1]["code"]
            assert len(code) == 8 and code.isdigit()
            status, value, headers = request(server, "POST", "/api/pair", {"code": code})
            assert status == 200 and value == {"ok": True}
            phone = headers["Set-Cookie"].split(";", 1)[0]
            assert request(server, "POST", "/api/pair", {"code": code})[0] == 400
            assert request(server, "GET", "/api/connection", cookie=phone)[1]["localOwner"] is False
            assert request(server, "POST", "/api/pair-code", cookie=phone)[0] == 403
            assert request(server, "GET", "/api/connection", cookie=owner)[1]["pairedDevices"] == 1
            settings = request(server, "GET", "/api/ai/settings", cookie=phone)
            assert settings[0] == 200 and "apiKey" not in settings[1] and settings[1]["customPrompt"] == ""
            assert request(server, "PUT", "/api/ai/settings", {}, phone)[0] == 403
            assert request(server, "PUT", "/api/ai/settings", {"customPrompt": "默认写作要求"}, owner)[1]["customPrompt"] == "默认写作要求"
            assert request(server, "PUT", "/api/ai/settings", {"customPrompt": None}, owner)[0] == 400
            assert request(server, "GET", "/api/ai/models?provider=codex")[0] == 401
            assert request(server, "GET", "/api/ai/models?provider=codex", cookie=phone)[1]["models"][0]["id"] == "fictional-model"
            assert request(server, "GET", "/api/ai/models?provider=api", cookie=phone)[0] == 403
            assert model_queries == ["codex"]
            assert request(server, "GET", "/api/ai/models?provider=api", cookie=owner)[1]["source"] == "api"
            for query in ("", "?provider=wrong", "?provider=codex&provider=api", "?provider=codex&command=x"):
                assert request(server, "GET", "/api/ai/models" + query, cookie=owner)[0] == 400
            assert request(server, "GET", "/api/ai/jobs", cookie=phone)[1] == {"jobs": []}
            assert request(server, "GET", "/api/ai/jobs/missing", cookie=phone)[0] == 404
            assert request(server, "POST", "/api/ai/jobs", {"mode": "run-command"}, phone)[0] == 400
            assert request(server, "POST", "/api/ai/jobs", {"mode": "organize", "topicId": "missing"}, phone)[0] == 400
            assert request(server, "POST", "/api/ai/jobs", {"mode": "organize", "command": "unexpected"}, phone)[0] == 400
            assert request(server, "POST", "/api/quick-window", cookie=phone)[0] == 403
            code = request(server, "POST", "/api/pair-code", cookie=owner)[1]["code"]
            wrong = "00000000" if code != "00000000" else "11111111"
            for _ in range(7):
                assert request(server, "POST", "/api/pair", {"code": wrong})[0] == 400
            assert request(server, "POST", "/api/pair", {"code": wrong})[0] == 429
            assert request(server, "POST", "/api/pair", {"code": code})[0] == 429
            code = request(server, "POST", "/api/pair-code", cookie=owner)[1]["code"]
            server.store.pair_expires = 0
            assert request(server, "POST", "/api/pair", {"code": code})[0] == 400

            workspace = example()
            workspace["topics"].append({**workspace["topics"][0], "id": "topic-2", "title": "其他主题"})
            workspace["ideas"] += [{**workspace["ideas"][0], "id": "idea-2", "topicId": "topic-2"},
                                   {**workspace["ideas"][0], "id": "idea-child", "parentId": "idea-1"},
                                   {**workspace["ideas"][0], "id": "idea-other"},
                                   {**workspace["ideas"][0], "id": "idea-deleted", "deletedAt": "2026-09-11T00:00:00Z"}]
            saved = request(server, "PUT", "/api/state", {"revision": 0, "workspace": workspace}, owner)
            assert saved[0] == 200 and saved[1] == {"revision": 1, "workspace": workspace}
            assert request(server, "PUT", "/api/state", {"revision": 0, "workspace": workspace}, phone)[0] == 409
            assert request(server, "GET", "/api/state", cookie=phone)[1] == saved[1]
            assert saved[1]["workspace"]["ideas"][0]["body"] == '<script>alert("仅作为文本")</script>'
            job_request = {"mode": "organize", "topicId": "topic-1", "ideaIds": ["idea-1"], "includeDescendants": True, "model": "fictional-override", "prompt": "本次补充要求"}
            status, submitted, _ = request(server, "POST", "/api/ai/jobs", job_request, phone)
            assert status == 202
            job = finished_job(server, phone, submitted["id"])
            assert job["status"] == "completed" and job["baseRevision"] == 1
            assert job["ideaIds"] == ["idea-1"] and job["includeDescendants"] is True
            assert set(job["targetIdeaIds"]) == {"idea-1", "idea-child"}
            assert job["model"] == "fictional-override" and job["prompt"] == "本次补充要求"
            assert {item["id"] for item in run_inputs[-1][1]["ideas"]} == {"idea-1", "idea-child"}
            assert run_inputs[-1][0]["model"] == "fictional-override" and run_inputs[-1][0]["customPrompt"] == "本次补充要求"
            _, submitted, _ = request(server, "POST", "/api/ai/jobs", {"mode": "develop", "topicId": "topic-1", "ideaIds": ["idea-child"]}, phone)
            job = finished_job(server, phone, submitted["id"])
            assert job["status"] == "completed" and job["prompt"] == "默认写作要求"
            assert job["targetIdeaIds"] == ["idea-child"] and job["result"]["suggestions"][0]["parentId"] == "idea-child"
            assert job["contextStats"]["targetIdeas"] == job["contextStats"]["backgroundIdeas"] == 1
            _, submitted, _ = request(server, "POST", "/api/ai/jobs", {"mode": "organize", "topicId": "topic-1", "ideaIds": ["idea-1"], "model": "", "prompt": ""}, phone)
            job = finished_job(server, phone, submitted["id"])
            assert job["status"] == "completed" and job["model"] == job["prompt"] == ""
            for overrides in ({"ideaIds": []}, {"ideaIds": None}, {"ideaIds": [123]}, {"ideaIds": ["idea-1", "idea-1"]},
                              {"ideaIds": ["idea-2"]}, {"ideaIds": ["idea-deleted"]}, {"topicId": None},
                              {"includeDescendants": "true"}, {"model": None}, {"model": "bad\nmodel"}, {"prompt": None}, {"prompt": "文" * 12001}):
                assert request(server, "POST", "/api/ai/jobs", {**job_request, **overrides}, phone)[0] == 400
            assert request(server, "GET", "/api/state", cookie=phone)[1] == saved[1]
            for mutate in (
                lambda data: data["ideas"][0].update(topicId="missing"),
                lambda data: data["ideas"][0].update(parentId="missing"),
                lambda data: data["ideas"][0].update(parentId="idea-1"),
                lambda data: data.update(schemaVersion=2),
                lambda data: data["topics"][0].update(archived=1),
                lambda data: data["ideas"][0].update(title="a" * 201),
            ):
                invalid = deepcopy(workspace)
                mutate(invalid)
                assert request(server, "PUT", "/api/state", {"revision": 1, "workspace": invalid}, owner)[0] == 400
                assert request(server, "POST", "/api/restore", {"revision": 1, "workspace": invalid}, owner)[0] == 400
                assert request(server, "GET", "/api/state", cookie=owner)[1]["revision"] == 1

            backup = request(server, "GET", "/api/backup", cookie=phone)
            assert backup[0] == 200 and backup[1]["format"] == "sparkspace-backup"
            assert backup[1]["workspace"] == workspace and "attachment" in backup[2]["Content-Disposition"]
            changed = deepcopy(workspace)
            changed["topics"][0]["title"] = "修改后"
            assert request(server, "PUT", "/api/state", {"revision": 1, "workspace": changed}, phone)[1]["revision"] == 2
            restored = request(server, "POST", "/api/restore", {"revision": 2, "workspace": backup[1]["workspace"]}, owner)
            assert restored[:2] == (200, {"revision": 3, "workspace": workspace})
            with closing(sqlite3.connect(server.store.path)) as db, db:
                assert json.loads(db.execute("SELECT document FROM snapshots WHERE revision=2").fetchone()[0]) == changed
            for revision in range(3, 35):
                assert request(server, "PUT", "/api/state", {"revision": revision, "workspace": workspace}, owner)[0] == 200
            with closing(sqlite3.connect(server.store.path)) as db, db:
                assert db.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0] == 30
                assert db.execute("SELECT MIN(revision), MAX(revision) FROM snapshots").fetchone() == (5, 34)
            with ThreadPoolExecutor(max_workers=2) as executor:
                submissions = [executor.submit(request, server, "PUT", "/api/state", {"revision": 35, "workspace": workspace}, client) for client in (owner, phone)]
                assert sorted(submission.result()[0] for submission in submissions) == [200, 409]
            final = request(server, "GET", "/api/state", cookie=owner)[1]
            assert final["revision"] == 36
        finally:
            stop(server, thread)

        server, thread = start(root / "data", public)
        try:
            assert request(server, "GET", "/api/state", cookie=phone)[1] == final
            assert request(server, "POST", "/api/logout", cookie=phone)[0] == 200
            assert request(server, "GET", "/api/state", cookie=phone)[0] == 401
            code = request(server, "POST", "/api/pair-code", cookie=owner)[1]["code"]
            phone = request(server, "POST", "/api/pair", {"code": code})[2]["Set-Cookie"].split(";", 1)[0]
            assert request(server, "POST", "/api/revoke-devices", cookie=owner)[0] == 200
            assert request(server, "GET", "/api/state", cookie=phone)[0] == 401
            assert request(server, "GET", "/api/state", cookie=owner)[1] == final
        finally:
            stop(server, thread)

        deep = example()
        for number in range(2, 1500):
            child = deepcopy(deep["ideas"][0])
            child.update(id=f"idea-{number}", parentId=f"idea-{number - 1}")
            deep["ideas"].append(child)
        validate_workspace(deep)
        deep["ideas"][0]["parentId"] = "idea-1499"
        try:
            validate_workspace(deep)
            raise AssertionError("Deep cycle must be rejected")
        except APIError as error:
            assert error.status == 400

        (public / "seed.json").write_text(json.dumps(example(), ensure_ascii=False), encoding="utf-8")
        seeded = Store(root / "seeded", public)
        assert seeded.state()["workspace"] == example()
        with closing(sqlite3.connect(seeded.path)) as db, db:
            db.execute("UPDATE workspace SET document='broken-json'")
        try:
            Store(root / "seeded", public)
            raise AssertionError("Corrupt existing data must stop startup")
        except (ValueError, RuntimeError, APIError):
            pass
        with closing(sqlite3.connect(seeded.path)) as db, db:
            assert db.execute("SELECT document FROM workspace").fetchone()[0] == "broken-json"
        incomplete = root / "incomplete"
        incomplete.mkdir()
        (incomplete / "workspace.sqlite3").touch()
        try:
            Store(incomplete, public)
            raise AssertionError("Existing empty database must not be rebuilt")
        except RuntimeError:
            pass
        assert (incomplete / "workspace.sqlite3").read_bytes() == b""
    print("PASS: authentication, pairing/replay/expiry/rate limit, concurrent CAS, backup/restore, validation, deep branches, AI selection/model/prompt routes and permissions, persistent sessions, restart and corrupt-data protection")


if __name__ == "__main__":
    check()
