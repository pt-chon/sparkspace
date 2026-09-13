"""灵感屿：仅使用 Python 标准库的个人文本工作台服务。"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import os
from pathlib import Path
import secrets
import socket
import sqlite3
import subprocess
import sys
import threading
import time
from urllib.parse import parse_qs, urlsplit

from ai_service import AIService


MAX_BYTES = 6 * 1024 * 1024
SESSION_SECONDS = 30 * 24 * 60 * 60
COOKIE = "sparkspace_session"
EMPTY_WORKSPACE = {"schemaVersion": 1, "topics": [], "ideas": []}
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/core.mjs": ("core.mjs", "text/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/icon.svg": ("icon.svg", "image/svg+xml"),
    "/favicon.ico": ("favicon.ico", "image/x-icon"),
    "/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json"),
    "/seed.json": ("seed.json", "application/json; charset=utf-8"),
}
TOPIC_TEXT = {
    "id": 120, "title": 200, "description": 50000, "goal": 50000,
    "context": 50000, "constraints": 50000, "output": 50000,
    "template": 30, "color": 30, "createdAt": 100, "updatedAt": 100,
}
IDEA_TEXT = {
    "id": 120, "topicId": 120, "title": 200, "body": 100000,
    "kind": 30, "status": 30, "source": 50000,
    "createdAt": 100, "updatedAt": 100,
}


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def encode(value) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def reject_json_constant(value):
    raise ValueError("Non-finite JSON numbers are not supported")


class APIError(Exception):
    def __init__(self, status: int, message: str, code: str):
        super().__init__(message)
        self.status, self.code = status, code


def invalid(message: str):
    raise APIError(400, message, "INVALID_STATE")


def fields(value, required: set[str], label: str):
    if not isinstance(value, dict) or set(value) != required:
        invalid(f"{label}字段不完整或含有不支持的字段")


def check_text(value, limit: int, label: str, nullable: bool = False):
    if nullable and value is None:
        return
    if not isinstance(value, str) or len(value) > limit:
        invalid(f"{label}必须是长度不超过 {limit} 的文本")
    try:
        value.encode("utf-8")
    except UnicodeError:
        invalid(f"{label}包含无效文本编码")


def validate_workspace(workspace):
    fields(workspace, {"schemaVersion", "topics", "ideas"}, "工作区")
    if type(workspace["schemaVersion"]) is not int or workspace["schemaVersion"] != 1:
        invalid("不支持此备份格式版本，请使用 schemaVersion 为 1 的工作区")
    for key, limit in (("topics", 500), ("ideas", 10000)):
        if not isinstance(workspace[key], list) or len(workspace[key]) > limit:
            invalid(f"{key}必须是最多包含 {limit} 项的列表")
    all_ids, topics, ideas = set(), set(), {}
    for collection, text_fields, extra in (
        (workspace["topics"], TOPIC_TEXT, {"archived", "deletedAt"}),
        (workspace["ideas"], IDEA_TEXT, {"parentId", "tags", "pinned", "deletedAt"}),
    ):
        is_topic = text_fields is TOPIC_TEXT
        label = "主题" if is_topic else "灵感"
        for item in collection:
            fields(item, set(text_fields) | extra, label)
            for key, limit in text_fields.items():
                check_text(item[key], limit, f"{label}.{key}")
            check_text(item["deletedAt"], 100, f"{label}.deletedAt", nullable=True)
            if not item["id"].strip() or item["id"] in all_ids:
                invalid("主题和灵感的 ID 必须非空且唯一")
            all_ids.add(item["id"])
            if is_topic:
                if type(item["archived"]) is not bool:
                    invalid("主题.archived 必须是布尔值")
                if item["template"] not in {"general", "worldbook", "character", "quant"}:
                    invalid("主题模板无效")
                if item["color"] not in {"sage", "clay", "blue", "lavender", "gold"}:
                    invalid("主题颜色无效")
                topics.add(item["id"])
            else:
                check_text(item["parentId"], 120, "灵感.parentId", nullable=True)
                if type(item["pinned"]) is not bool:
                    invalid("灵感.pinned 必须是布尔值")
                if item["kind"] not in {"idea", "question", "decision", "reference"}:
                    invalid("灵感类型无效")
                if item["status"] not in {"spark", "shaping", "settled"}:
                    invalid("灵感状态无效")
                if not isinstance(item["tags"], list) or len(item["tags"]) > 50:
                    invalid("每条灵感最多允许 50 个标签")
                for tag in item["tags"]:
                    check_text(tag, 100, "标签")
                ideas[item["id"]] = item
    for item in ideas.values():
        if item["topicId"] not in topics:
            invalid("灵感引用了不存在的主题")
        parent = item["parentId"]
        if parent is not None and (parent not in ideas or ideas[parent]["topicId"] != item["topicId"]):
            invalid("父级灵感必须存在并属于同一主题")
    # Iterative traversal also accepts very deep valid branches without recursion.
    checked = set()
    for identifier in ideas:
        path, current = set(), identifier
        while current is not None and current not in checked:
            if current in path:
                invalid("灵感分支不能循环引用")
            path.add(current)
            current = ideas[current]["parentId"]
        checked.update(path)
    if len(encode(workspace).encode("utf-8")) > MAX_BYTES:
        raise APIError(413, "工作区超过 6 MB 上限，请先整理或拆分内容", "TOO_LARGE")
    return workspace


def revision_number(value):
    if type(value) is not int or not 0 <= value < 2**53:
        raise APIError(400, "版本号无效，请重新读取工作区", "INVALID_REVISION")
    return value


class Store:
    def __init__(self, data_dir: Path, public_dir: Path):
        self.path = Path(data_dir) / "workspace.sqlite3"
        self.pair_lock = threading.Lock()
        self.pair_digest = None
        self.pair_expires = 0.0
        self.pair_attempts = 0
        existed = self.path.exists()
        initial = EMPTY_WORKSPACE
        if not existed:
            seed = public_dir / "seed.json"
            if seed.exists():
                if seed.stat().st_size > MAX_BYTES:
                    raise RuntimeError("初始示例数据超过大小限制")
                initial = json.loads(seed.read_text(encoding="utf-8-sig"))
            validate_workspace(initial)
            self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            if existed:
                expected = {
                    "workspace": {"id", "revision", "document"},
                    "snapshots": {"revision", "document", "saved_at"},
                    "sessions": {"digest", "owner", "expires"},
                }
                for table, columns in expected.items():
                    actual = {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
                    if actual != columns:
                        raise RuntimeError("现有数据文件格式无效，已停止启动并保留原文件")
                if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise RuntimeError("现有数据文件校验失败，已保留原文件")
                rows = db.execute("SELECT id, revision, document FROM workspace").fetchall()
                if len(rows) != 1 or rows[0][0] != 1:
                    raise RuntimeError("现有工作区数据无效，已保留原文件")
                revision_number(rows[0][1])
                validate_workspace(json.loads(rows[0][2]))
            else:
                db.executescript("""
                    CREATE TABLE workspace (
                        id INTEGER PRIMARY KEY CHECK(id = 1),
                        revision INTEGER NOT NULL CHECK(revision >= 0),
                        document TEXT NOT NULL
                    );
                    CREATE TABLE snapshots (
                        revision INTEGER PRIMARY KEY, document TEXT NOT NULL, saved_at TEXT NOT NULL
                    );
                    CREATE TABLE sessions (
                        digest TEXT PRIMARY KEY, owner INTEGER NOT NULL CHECK(owner IN (0, 1)),
                        expires REAL NOT NULL
                    );
                """)
                db.execute("INSERT INTO workspace VALUES (1, 0, ?)", (encode(initial),))
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        try:
            with db:
                yield db
        finally:
            db.close()

    def state(self):
        with self.connect() as db:
            revision, document = db.execute("SELECT revision, document FROM workspace WHERE id=1").fetchone()
        return {"revision": revision, "workspace": json.loads(document)}

    def replace(self, revision, workspace):
        revision_number(revision)
        validate_workspace(workspace)
        document = encode(workspace)
        # ponytail: one JSON row suits a personal text library; split rows if the 6 MB limit is outgrown.
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            current, previous = db.execute("SELECT revision, document FROM workspace WHERE id=1").fetchone()
            if current != revision:
                raise APIError(409, "其他设备已保存新内容，请保留当前草稿并读取最新版本", "CONFLICT")
            db.execute("INSERT INTO snapshots VALUES (?, ?, ?)", (current, previous, timestamp()))
            db.execute("UPDATE workspace SET revision=?, document=? WHERE id=1", (current + 1, document))
            db.execute("DELETE FROM snapshots WHERE revision NOT IN (SELECT revision FROM snapshots ORDER BY revision DESC LIMIT 30)")
        return {"revision": current + 1, "workspace": workspace}

    def session(self, token):
        if not token or len(token) > 200:
            return None
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self.connect() as db:
            row = db.execute("SELECT owner FROM sessions WHERE digest=? AND expires>?", (digest, time.time())).fetchone()
        return None if row is None else bool(row[0])

    def new_session(self, owner=False):
        token = secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode("ascii")).hexdigest()
        with self.connect() as db:
            db.execute("DELETE FROM sessions WHERE expires<=?", (time.time(),))
            db.execute("INSERT INTO sessions VALUES (?, ?, ?)", (digest, int(owner), time.time() + SESSION_SECONDS))
        return token

    def logout(self, token):
        if token:
            with self.connect() as db:
                db.execute("DELETE FROM sessions WHERE digest=?", (hashlib.sha256(token.encode("utf-8")).hexdigest(),))

    def revoke_devices(self):
        with self.connect() as db:
            db.execute("DELETE FROM sessions WHERE owner=0")
        with self.pair_lock:
            self.pair_digest = None

    def device_count(self):
        with self.connect() as db:
            return db.execute("SELECT COUNT(*) FROM sessions WHERE owner=0 AND expires>?", (time.time(),)).fetchone()[0]

    def new_pair_code(self):
        code = f"{secrets.randbelow(100_000_000):08d}"
        with self.pair_lock:
            self.pair_digest = hashlib.sha256(code.encode("ascii")).digest()
            self.pair_expires, self.pair_attempts = time.time() + 600, 0
            expires = datetime.fromtimestamp(self.pair_expires, timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        return {"code": code, "expiresAt": expires}

    def pair(self, code):
        with self.pair_lock:
            if self.pair_attempts >= 8:
                raise APIError(429, "尝试次数过多，请在电脑上重新生成配对码", "PAIR_RATE_LIMIT")
            if self.pair_digest is None or time.time() >= self.pair_expires:
                raise APIError(400, "配对码已失效，请在电脑上重新生成", "INVALID_PAIR_CODE")
            digest = hashlib.sha256(code.encode("utf-8")).digest() if isinstance(code, str) and len(code) == 8 and code.isascii() and code.isdigit() else b""
            if not secrets.compare_digest(digest, self.pair_digest):
                self.pair_attempts += 1
                if self.pair_attempts >= 8:
                    self.pair_digest = None
                    raise APIError(429, "尝试次数过多，请在电脑上重新生成配对码", "PAIR_RATE_LIMIT")
                raise APIError(400, "配对码不正确或已失效", "INVALID_PAIR_CODE")
            token = self.new_session()
            self.pair_digest = None
            return token


class SparkServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, data_dir: Path, public_dir: Path):
        self.public_dir = Path(public_dir).resolve()
        self.store = Store(Path(data_dir), self.public_dir)
        self.ai = AIService(Path(data_dir))
        try:
            super().__init__(address, Handler)
        except Exception:
            self.ai.close()
            raise

    def server_close(self):
        super().server_close()
        self.ai.close()

    def addresses(self):
        if self.server_address[0] in {"localhost", "127.0.0.1"}:
            return []
        try:
            candidates = {item[4][0] for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)}
        except OSError:
            candidates = set()
        return [f"http://{address}:{self.server_port}" for address in sorted(candidates)
                if ipaddress.ip_address(address).is_private and not ipaddress.ip_address(address).is_loopback
                and not ipaddress.ip_address(address).is_link_local]

    def handle_error(self, request, client_address):
        # No request details, credentials, or traceback are printed to the console.
        pass

    def quick_window(self):
        project_dir = Path(__file__).resolve().parent
        script = (project_dir / "quick_capture.pyw").resolve()
        if not script.is_relative_to(project_dir) or not script.is_file():
            raise APIError(409, "悬浮输入栏尚未安装完成，请稍后重试", "QUICK_WINDOW_UNAVAILABLE")
        allowed = {"SYSTEMROOT", "WINDIR", "USERPROFILE", "LOCALAPPDATA", "APPDATA", "TEMP", "TMP", "PATH", "PATHEXT"}
        environment = {key: value for key, value in os.environ.items() if key.upper() in allowed}
        environment["PYTHONUTF8"] = "1"
        try:
            subprocess.Popen(
                [sys.executable, str(script), "--port", str(self.server_port), "--data-dir", str(self.store.path.parent.resolve())],
                cwd=project_dir, env=environment, stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError:
            raise APIError(503, "无法启动悬浮输入栏，请检查本机 Python 安装", "QUICK_WINDOW_FAILED")
        return {"ok": True, "status": "launch_requested"}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "Sparkspace"
    sys_version = ""

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, format, *args):
        pass

    def send_error(self, code, message=None, explain=None):
        self.close_connection = True
        self.json_response(code, {"error": "请求无法处理", "code": "HTTP_ERROR"})

    def response(self, status, body: bytes, content_type, extra=None):
        self.send_response(status)
        for key, value in {
            "Content-Type": content_type,
            "Content-Length": str(len(body)),
            "Cache-Control": "no-store",
            "Referrer-Policy": "same-origin",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
            **(extra or {}),
        }.items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def json_response(self, status, value, extra=None):
        self.response(status, encode(value).encode("utf-8"), "application/json; charset=utf-8", extra)

    def authority(self):
        hosts = self.headers.get_all("Host", [])
        try:
            if len(hosts) != 1 or any(char.isspace() for char in hosts[0]):
                raise ValueError
            parts = urlsplit("http://" + hosts[0])
            if not parts.hostname or parts.username or parts.password or parts.path or parts.query or parts.fragment or (parts.port or 80) != self.server.server_port:
                raise ValueError
        except ValueError:
            raise APIError(400, "访问地址无效，请使用启动器显示的地址", "INVALID_HOST")
        return parts.hostname.lower(), f"http://{hosts[0]}"

    def local_request(self):
        host, _ = self.authority()
        return ipaddress.ip_address(self.client_address[0]).is_loopback and host in {"localhost", "127.0.0.1"}

    def token(self):
        try:
            cookie = SimpleCookie(self.headers.get("Cookie", ""))
            return cookie[COOKIE].value if COOKIE in cookie else None
        except Exception:
            return None

    def auth(self, owner_only=False):
        owner = self.server.store.session(self.token())
        if owner is None or (owner and not self.local_request()):
            raise APIError(401, "请在电脑上生成配对码后连接", "PAIR_REQUIRED")
        if owner_only and not owner:
            raise APIError(403, "此操作需要在本机窗口中完成", "OWNER_REQUIRED")
        return owner

    def cookie(self, token, expire=False):
        return {"Set-Cookie": f"{COOKIE}={token}; Path=/; Max-Age={0 if expire else SESSION_SECONDS}; HttpOnly; SameSite=Strict"}

    def ai_result(self, operation, *args, **kwargs):
        try:
            return operation(*args, **kwargs)
        except ValueError:
            raise APIError(400, "AI 配置或任务参数无效，请检查设置", "AI_INVALID_REQUEST")
        except RuntimeError:
            raise APIError(409, "AI 任务正忙，请等待当前任务完成", "AI_BUSY")

    def body(self):
        _, expected = self.authority()
        origins = self.headers.get_all("Origin", [])
        if origins != [expected]:
            self.close_connection = True
            raise APIError(403, "请从当前工作台页面提交请求", "ORIGIN_REQUIRED")
        content_types = self.headers.get_all("Content-Type", [])
        if len(content_types) != 1 or content_types[0].split(";", 1)[0].strip().lower() != "application/json":
            self.close_connection = True
            raise APIError(415, "请求必须使用 JSON 格式", "JSON_REQUIRED")
        lengths = self.headers.get_all("Content-Length", [])
        if self.headers.get("Transfer-Encoding") or len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdigit():
            self.close_connection = True
            raise APIError(400, "请求长度无效", "INVALID_LENGTH")
        if len(lengths[0]) > 10:
            self.close_connection = True
            raise APIError(413, "请求超过 6 MB 上限", "TOO_LARGE")
        length = int(lengths[0])
        if length > MAX_BYTES:
            self.close_connection = True
            raise APIError(413, "请求超过 6 MB 上限", "TOO_LARGE")
        try:
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError
            data = json.loads(raw.decode("utf-8"), parse_constant=reject_json_constant)
            if not isinstance(data, dict):
                raise ValueError
            return data
        except (ValueError, UnicodeError, RecursionError):
            raise APIError(400, "请求包含无效 JSON 数据", "INVALID_JSON")

    def do_GET(self):
        self.dispatch()

    def do_POST(self):
        self.dispatch()

    def do_PUT(self):
        self.dispatch()

    def dispatch(self):
        try:
            self.authority()
            path = urlsplit(self.path).path
            if self.command == "GET":
                if path == "/api/health":
                    return self.json_response(200, {"app": "sparkspace", "ok": True})
                if path.startswith("/api/"):
                    owner = self.auth()
                    if path == "/api/state":
                        return self.json_response(200, self.server.store.state())
                    if path == "/api/backup":
                        value = {"format": "sparkspace-backup", "exportedAt": timestamp(), "workspace": self.server.store.state()["workspace"]}
                        return self.json_response(200, value, {"Content-Disposition": 'attachment; filename="sparkspace-backup-' + datetime.now().strftime("%Y%m%d-%H%M%S") + '.json"'})
                    if path == "/api/connection":
                        return self.json_response(200, {"localOwner": owner, "addresses": self.server.addresses(), "port": self.server.server_port, "pairedDevices": self.server.store.device_count()})
                    if path == "/api/ai/settings":
                        return self.json_response(200, self.ai_result(self.server.ai.get_settings))
                    if path == "/api/ai/models":
                        try:
                            query = parse_qs(urlsplit(self.path).query, keep_blank_values=True, max_num_fields=2)
                        except ValueError:
                            raise APIError(400, "模型列表查询参数无效", "INVALID_AI_REQUEST")
                        if set(query) != {"provider"} or len(query["provider"]) != 1 or query["provider"][0] not in {"codex", "api"}:
                            raise APIError(400, "请选择 Codex 或 API 模型列表", "INVALID_AI_REQUEST")
                        provider = query["provider"][0]
                        if provider == "api":
                            self.auth(owner_only=True)
                        return self.json_response(200, self.ai_result(self.server.ai.list_models, provider))
                    if path == "/api/ai/jobs":
                        return self.json_response(200, self.ai_result(self.server.ai.list_jobs))
                    if path.startswith("/api/ai/jobs/"):
                        identifier = path.removeprefix("/api/ai/jobs/")
                        if not identifier or "/" in identifier or len(identifier) > 120:
                            raise APIError(404, "找不到此 AI 任务", "NOT_FOUND")
                        try:
                            return self.json_response(200, self.ai_result(self.server.ai.get_job, identifier))
                        except KeyError:
                            raise APIError(404, "找不到此 AI 任务", "NOT_FOUND")
                elif path in STATIC_FILES:
                    filename, mime = STATIC_FILES[path]
                    target = (self.server.public_dir / filename).resolve()
                    if target.is_relative_to(self.server.public_dir) and target.is_file():
                        extra = None
                        if path == "/" and self.local_request() and self.server.store.session(self.token()) is not True:
                            extra = self.cookie(self.server.store.new_session(owner=True))
                        return self.response(200, target.read_bytes(), mime, extra)
            else:
                data = self.body()
                if self.command == "POST" and path == "/api/pair":
                    fields(data, {"code"}, "配对请求")
                    token = self.server.store.pair(data["code"])
                    return self.json_response(200, {"ok": True}, self.cookie(token))
                if self.command == "POST" and path == "/api/logout":
                    fields(data, set(), "退出请求")
                    self.server.store.logout(self.token())
                    return self.json_response(200, {"ok": True}, self.cookie("", expire=True))
                self.auth(owner_only=path in {"/api/pair-code", "/api/revoke-devices", "/api/ai/settings", "/api/quick-window"})
                if (self.command, path) in {("PUT", "/api/state"), ("POST", "/api/restore")}:
                    fields(data, {"revision", "workspace"}, "保存请求")
                    state = self.server.store.replace(data["revision"], data["workspace"])
                    try:
                        self.server.ai.note_change(state["workspace"], state["revision"])
                    except Exception:
                        # A scheduling failure must not turn an already committed save into an apparent failure.
                        pass
                    return self.json_response(200, state)
                if self.command == "PUT" and path == "/api/ai/settings":
                    return self.json_response(200, self.ai_result(self.server.ai.update_settings, data))
                if self.command == "POST" and path == "/api/ai/jobs":
                    if "mode" not in data or set(data) - {"mode", "topicId", "ideaIds", "includeDescendants", "model", "prompt"}:
                        raise APIError(400, "AI 任务包含不支持的参数", "INVALID_AI_REQUEST")
                    if data["mode"] not in ("organize", "develop", "classify"):
                        raise APIError(400, "请选择整理、完善或分类模式", "INVALID_AI_REQUEST")
                    topic_id = data.get("topicId")
                    check_text(topic_id, 120, "主题 ID", nullable=True)
                    if "ideaIds" in data and (not isinstance(data["ideaIds"], list) or not 1 <= len(data["ideaIds"]) <= 80):
                        raise APIError(400, "一次请选择 1 至 80 条灵感，整个主题请省略 ideaIds", "INVALID_AI_REQUEST")
                    if "includeDescendants" in data and type(data["includeDescendants"]) is not bool:
                        raise APIError(400, "后代范围选项必须是布尔值", "INVALID_AI_REQUEST")
                    for key, limit in (("model", 200), ("prompt", 12000)):
                        if key in data:
                            check_text(data[key], limit, "本次模型" if key == "model" else "本次提示词")
                    state = self.server.store.state()
                    if topic_id is not None and not any(topic["id"] == topic_id and topic["deletedAt"] is None for topic in state["workspace"]["topics"]):
                        raise APIError(400, "所选主题不存在或已被删除", "INVALID_AI_REQUEST")
                    options = {key: data[key] for key in ("ideaIds", "includeDescendants", "model", "prompt") if key in data}
                    return self.json_response(202, self.ai_result(self.server.ai.submit, state["workspace"], state["revision"], data["mode"], topic_id, **options))
                if self.command == "POST" and path == "/api/quick-window":
                    fields(data, set(), "悬浮输入栏请求")
                    return self.json_response(200, self.server.quick_window())
                if self.command == "POST" and path == "/api/pair-code":
                    fields(data, set(), "配对码请求")
                    return self.json_response(200, self.server.store.new_pair_code())
                if self.command == "POST" and path == "/api/revoke-devices":
                    fields(data, set(), "撤销请求")
                    self.server.store.revoke_devices()
                    return self.json_response(200, {"ok": True})
            raise APIError(404, "找不到此页面或接口", "NOT_FOUND")
        except APIError as error:
            self.json_response(error.status, {"error": str(error), "code": error.code})
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            self.close_connection = True
        except Exception:
            self.close_connection = True
            self.json_response(500, {"error": "服务暂时无法完成请求，原有数据已保留", "code": "INTERNAL_ERROR"})


def main():
    parser = argparse.ArgumentParser(description="灵感屿本机与可信局域网服务")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=18478)
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parent / "user-data")
    args = parser.parse_args()
    try:
        server = SparkServer((args.host, args.port), args.data_dir, Path(__file__).resolve().parent / "public")
    except (OSError, sqlite3.Error, ValueError, APIError, RuntimeError):
        print("无法启动灵感屿：端口不可用或数据文件格式无效。原有数据未被重建，请检查端口与数据目录。")
        return 1
    print(f"灵感屿已启动：http://127.0.0.1:{server.server_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
