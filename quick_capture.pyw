"""A small native capture window; confirmed writes and local drafts stay separate."""

from __future__ import annotations

import argparse
import copy
import ctypes
from datetime import datetime, timezone
from http.cookiejar import CookieJar
import json
import os
from pathlib import Path
import queue
import runpy
import sys
import tempfile
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, ProxyHandler, Request, build_opener
from uuid import uuid4


PROJECT = Path(__file__).resolve().parent
PAPER, WHITE, INK, MUTED, GREEN, LINE = "#f4f6ee", "#fffefa", "#344c3c", "#7b896e", "#385b4b", "#d9e2d0"


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def read_json(path: Path, default):
    if not path.exists():
        return copy.deepcopy(default)
    try:
        if path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise RuntimeError(f"无法读取 {path.name}，已保留原文件。请先检查文件。") from error


def write_json(path: Path, value) -> None:
    """Replace atomically, so a crash cannot leave half a draft behind."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=path.name + ".", suffix=".tmp", delete=False) as output:
            temporary = Path(output.name)
            json.dump(value, output, ensure_ascii=False, allow_nan=False)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def load_draft(path: Path) -> dict:
    value = read_json(path, {"body": "", "topicId": "topic-inbox", "pending": None})
    try:
        if not isinstance(value, dict) or not isinstance(value["body"], str) or len(value["body"]) > 100000:
            raise ValueError
        if not isinstance(value["topicId"], str) or not 0 < len(value["topicId"]) <= 120:
            raise ValueError
        pending = value.get("pending")
        if pending is not None:
            if not isinstance(pending, dict):
                raise ValueError
            for key, limit in (("id", 120), ("body", 100000), ("topicId", 120), ("createdAt", 100)):
                if not isinstance(pending[key], str) or not 0 < len(pending[key]) <= limit:
                    raise ValueError
    except (ValueError, KeyError, TypeError) as error:
        raise RuntimeError("悬浮速记草稿格式无效，已保留 quick-draft.json，请先检查文件。") from error
    return value


def make_pending(body: str, topic_id: str) -> dict:
    if not body.strip() or len(body) > 100000:
        raise ValueError("请写下 1 到 100000 字的灵感。")
    return {"id": "idea-" + uuid4().hex, "body": body, "topicId": topic_id, "createdAt": timestamp()}


class LocalAPI:
    def __init__(self, port: int):
        self.base = f"http://127.0.0.1:{port}"
        self.opener = build_opener(ProxyHandler({}), HTTPCookieProcessor(CookieJar()))

    def authenticate(self):
        with self.opener.open(self.base + "/", timeout=5) as response:
            response.read(300000)

    def request(self, path: str, data=None):
        headers = {"Accept": "application/json"}
        payload = None
        if data is not None:
            headers.update({"Origin": self.base, "Content-Type": "application/json"})
            payload = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
        request = Request(self.base + path, data=payload, headers=headers, method="PUT" if data is not None else "GET")
        for attempt in range(2):
            try:
                with self.opener.open(request, timeout=7) as response:
                    raw = response.read(7 * 1024 * 1024 + 1)
                if len(raw) > 7 * 1024 * 1024:
                    raise RuntimeError("工作区响应超过大小限制，草稿仍在本机。")
                result = json.loads(raw)
                if not isinstance(result, dict) or type(result.get("revision")) is not int or not isinstance(result.get("workspace"), dict):
                    raise RuntimeError("工作区响应格式无效，草稿仍在本机。")
                return result
            except HTTPError as error:
                if error.code == 401 and attempt == 0:
                    self.authenticate()
                else:
                    raise

    def state(self):
        return self.request("/api/state")

    def replace(self, state):
        return self.request("/api/state", state)


def save_capture(client, pending: dict, attempts: int = 5) -> dict:
    """Merge one stable ID into the newest revision; never resend it as a new idea."""
    failure = None
    for attempt in range(attempts):
        try:
            state = client.state()
            existing = next((item for item in state["workspace"]["ideas"] if item["id"] == pending["id"]), None)
            if existing:
                return {"state": state, "idea": existing}
            workspace = copy.deepcopy(state["workspace"])
            live = [topic for topic in workspace["topics"] if not topic["deletedAt"] and not topic["archived"]]
            topic = next((topic for topic in live if topic["id"] == pending["topicId"]), None)
            if topic is None:
                topic = next((topic for topic in live if topic["id"] == "topic-inbox" or topic["id"].startswith("topic-inbox-")), None)
            if topic is None:
                identifier = "topic-inbox" if not any(topic["id"] == "topic-inbox" for topic in workspace["topics"]) else "topic-inbox-" + uuid4().hex
                topic = {"id": identifier, "title": "随手记", "description": "来不及分类的念头，先放在这里。", "goal": "", "context": "", "constraints": "保留原始表达。", "output": "", "template": "general", "color": "gold", "createdAt": timestamp(), "updatedAt": timestamp(), "archived": False, "deletedAt": None}
                workspace["topics"].append(topic)
            body = pending["body"]
            title = next(line.strip() for line in body.splitlines() if line.strip())
            idea = {"id": pending["id"], "topicId": topic["id"], "parentId": None, "title": title[:199] + "…" if len(title) > 200 else title, "body": body, "kind": "idea", "status": "spark", "tags": [], "pinned": False, "source": "悬浮速记", "createdAt": pending["createdAt"], "updatedAt": pending["createdAt"], "deletedAt": None}
            workspace["ideas"].append(idea)
            result = client.replace({"revision": state["revision"], "workspace": workspace})
            saved = next((item for item in result["workspace"]["ideas"] if item["id"] == pending["id"]), None)
            if saved is None:
                raise RuntimeError("保存结果尚未确认，草稿已保留。请重试核对。")
            return {"state": result, "idea": saved}
        except HTTPError as error:
            if error.code != 409 and error.code < 500:
                raise RuntimeError("服务没有接受这条灵感，草稿已保留。请在工作台检查数据状态。") from error
            failure = error
        except (URLError, TimeoutError, OSError) as error:
            failure = error
        if attempt + 1 < attempts:
            time.sleep(min(0.15 * (attempt + 1), 0.6))
    raise RuntimeError("保存结果尚未确认，草稿已保留。点击「重新核对」继续。") from failure


def window_title(port: int) -> str:
    return f"灵感屿 · 悬浮速记 [{port}]"


def acquire_window(port: int):
    if sys.platform != "win32":
        return None, True
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    handle = kernel.CreateMutexW(None, False, f"Local\\SparkspaceQuickCapture-{port}")
    if not handle:
        raise RuntimeError("无法创建悬浮输入栏。")
    if ctypes.get_last_error() != 183:
        return handle, True
    user = ctypes.windll.user32
    user.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user.FindWindowW.restype = wintypes.HWND
    user.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user.BringWindowToTop.argtypes = [wintypes.HWND]
    user.SetForegroundWindow.argtypes = [wintypes.HWND]
    for _ in range(30):
        hwnd = user.FindWindowW(None, window_title(port))
        if hwnd:
            user.ShowWindow(hwnd, 5)
            user.BringWindowToTop(hwnd)
            user.SetForegroundWindow(hwnd)
            break
        time.sleep(0.05)
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle(handle)
    return None, False


class CaptureWindow:
    def __init__(self, root: tk.Tk, port: int, data_dir: Path):
        self.root, self.port, self.data_dir = root, port, Path(data_dir)
        self.draft_path, self.prefs_path = self.data_dir / "quick-draft.json", self.data_dir / "quick-window.json"
        self.draft = load_draft(self.draft_path)
        self.prefs = read_json(self.prefs_path, {})
        if not isinstance(self.prefs, dict):
            raise RuntimeError("quick-window.json 格式无效，已保留原文件。")
        self.selected = self.draft["topicId"] if self.draft["body"] or self.draft.get("pending") else self.prefs.get("topicId", "topic-inbox")
        if not isinstance(self.selected, str) or not 0 < len(self.selected) <= 120:
            self.selected = "topic-inbox"
        self.expanded = self.prefs.get("expanded") is True
        self.compact = self.prefs.get("compact", not self.expanded) is True
        self.topmost = tk.BooleanVar(root, self.prefs.get("topmost", True) is True)
        self.busy, self.closed, self.draft_timer = False, False, None
        self.topics = [{"id": self.selected, "title": "随手记"}]
        self.tasks, self.results = queue.Queue(), queue.Queue()
        self.api = LocalAPI(port)
        self.launcher = runpy.run_path(str(PROJECT / "launch.pyw"), run_name="sparkspace_launcher")
        root.title(window_title(port))
        root.overrideredirect(True)
        root.attributes("-topmost", self.topmost.get())
        root.configure(bg=LINE)
        width = min(590, root.winfo_screenwidth() - 30)
        self.window_width = width
        x = self.prefs.get("x", (root.winfo_screenwidth() - width) // 2)
        y = self.prefs.get("y", 90)
        x = max(0, min(x if type(x) is int else 40, root.winfo_screenwidth() - width))
        y = max(0, min(y if type(y) is int else 90, root.winfo_screenheight() - 280))
        root.geometry(f"{width}x{60 if self.compact else 260 if self.expanded else 124}+{x}+{y}")
        shell = tk.Frame(root, bg=PAPER, padx=12, pady=8)
        self.shell = shell
        shell.pack(fill="both", expand=True, padx=1, pady=1)
        header = tk.Frame(shell, bg=PAPER)
        self.header = header
        header.pack(fill="x", pady=(0, 6))
        brand = tk.Label(header, text="✧  灵感屿", bg=PAPER, fg=GREEN, font=("Microsoft YaHei UI", 9, "bold"))
        brand.pack(side="left")
        tk.Label(header, text="QUICK NOTE", bg=PAPER, fg="#9aa58a", font=("Consolas", 7)).pack(side="left", padx=8)
        for widget in (shell, header, brand):
            widget.bind("<ButtonPress-1>", self.start_drag)
            widget.bind("<B1-Motion>", self.drag)
            widget.bind("<ButtonRelease-1>", lambda event: self.persist_preferences())
        self.small_button(header, "×", self.close, width=2).pack(side="right", padx=(7, 0))
        self.small_button(header, "—", self.show_compact, width=2).pack(side="right", padx=(5, 0))
        self.small_button(header, "↗ 工作台", self.open_full).pack(side="right", padx=8)
        tk.Checkbutton(header, text="置顶", variable=self.topmost, command=self.toggle_topmost, bg=PAPER, fg=MUTED, activebackground=PAPER, activeforeground=GREEN, selectcolor=WHITE, highlightthickness=0, borderwidth=0, font=("Microsoft YaHei UI", 8), cursor="hand2").pack(side="right")
        capture = tk.Frame(shell, bg=PAPER)
        self.capture = capture
        capture.pack(fill="both", expand=True)
        self.compact_handle = tk.Label(capture, text="✧", bg=PAPER, fg=GREEN, width=2, font=("Microsoft YaHei UI", 13), cursor="fleur")
        self.compact_handle.bind("<ButtonPress-1>", self.start_drag)
        self.compact_handle.bind("<B1-Motion>", self.drag)
        self.compact_handle.bind("<ButtonRelease-1>", lambda event: self.persist_preferences())
        self.menu_button = self.small_button(capture, "⋯", self.show_menu, width=2)
        self.save_button = tk.Button(capture, text="记下来", command=self.save, bg=GREEN, fg=WHITE, activebackground="#284437", activeforeground=WHITE, relief="flat", borderwidth=0, padx=15, font=("Microsoft YaHei UI", 10), cursor="hand2", disabledforeground="#b5c6a8")
        self.save_button.pack(side="right", fill="y", padx=(8, 0))
        input_frame = tk.Frame(capture, bg=WHITE, highlightthickness=1, highlightbackground=LINE, highlightcolor="#97ab80")
        self.input_frame = input_frame
        input_frame.pack(side="left", fill="both", expand=True)
        self.text = tk.Text(input_frame, height=1, bg=WHITE, fg=INK, insertbackground=GREEN, selectbackground="#dde8cc", selectforeground=INK, wrap="word", undo=True, relief="flat", borderwidth=0, padx=10, pady=8, font=("Microsoft YaHei UI", 10), spacing1=2, spacing3=2)
        self.text.pack(fill="both", expand=True)
        self.text.insert("1.0", self.draft["body"])
        self.placeholder = tk.Label(input_frame, text="想到什么，先留下来……", bg=WHITE, fg="#8a977b", font=("Microsoft YaHei UI", 10), cursor="xterm")
        self.placeholder.bind("<Button-1>", lambda event: self.text.focus_set())
        self.update_placeholder()
        self.text.edit_modified(False)
        self.text.bind("<<Modified>>", self.changed)
        self.text.bind("<Control-Return>", self.save)
        self.text.bind("<Control-KP_Enter>", self.save)
        footer = tk.Frame(shell, bg=PAPER)
        self.footer = footer
        footer.pack(fill="x", pady=(6, 0))
        style = ttk.Style(root)
        style.configure("Quick.TCombobox", font=("Microsoft YaHei UI", 8), padding=1)
        self.topic_select = ttk.Combobox(footer, state="readonly", width=15, style="Quick.TCombobox", values=["随手记"])
        self.topic_select.current(0)
        self.topic_select.pack(side="left")
        self.topic_select.bind("<<ComboboxSelected>>", self.change_topic)
        self.status = tk.Label(footer, text="正在连接工作台…", width=1, bg=PAPER, fg=MUTED, anchor="w", font=("Microsoft YaHei UI", 8))
        self.status.pack(side="left", fill="x", expand=True, padx=9)
        self.expand_button = self.small_button(footer, "收起 ↟" if self.expanded else "展开 ↡", self.toggle_expanded)
        self.expand_button.pack(side="right")
        self.apply_layout(persist=False)
        root.protocol("WM_DELETE_WINDOW", self.close)
        threading.Thread(target=self.worker, daemon=True).start()
        self.tasks.put(("load", self.connect, None))
        root.after(80, self.poll)
        root.after(100, self.text.focus_set)
        root.after(30000, self.refresh)

    def small_button(self, parent, text, command, **options):
        return tk.Button(parent, text=text, command=command, bg=PAPER, fg=MUTED, activebackground="#e5eddc", activeforeground=GREEN, relief="flat", borderwidth=0, highlightthickness=0, padx=3, pady=0, font=("Microsoft YaHei UI", 8), cursor="hand2", **options)

    def apply_layout(self, persist=True):
        for widget in (self.header, self.capture, self.footer):
            widget.pack_forget()
        if self.compact:
            self.shell.configure(padx=7, pady=6)
            self.capture.pack(fill="both", expand=True)
            self.compact_handle.pack(side="left", fill="y", padx=(0, 4), before=self.input_frame)
            self.menu_button.pack(side="right", fill="y", padx=(5, 0), before=self.save_button)
        else:
            self.shell.configure(padx=12, pady=8)
            self.compact_handle.pack_forget()
            self.menu_button.pack_forget()
            self.header.pack(fill="x", pady=(0, 6))
            self.capture.pack(fill="both", expand=True)
            self.footer.pack(fill="x", pady=(6, 0))
        self.text.configure(wrap="none" if self.compact else "word")
        self.root.geometry(f"{self.window_width}x{60 if self.compact else 260 if self.expanded else 124}")
        self.expand_button.configure(text="收起 ↟" if self.expanded else "展开 ↡")
        if persist:
            self.persist_preferences()

    def show_compact(self):
        self.compact, self.expanded = True, False
        self.apply_layout()
        self.text.focus_set()

    def show_panel(self):
        self.compact, self.expanded = False, False
        self.apply_layout()
        self.text.focus_set()

    def show_menu(self):
        if getattr(self, "popup_menu", None):
            self.popup_menu.destroy()
        menu = tk.Menu(self.root, tearoff=False, font=("Microsoft YaHei UI", 9))
        self.popup_menu = menu
        menu.add_command(label=self.status.cget("text"), state="disabled")
        menu.add_separator()
        menu.add_command(label="展开面板 · 选择主题", command=self.show_panel)
        menu.add_command(label="多行输入", command=self.toggle_expanded)
        menu.add_checkbutton(label="保持置顶", variable=self.topmost, command=self.toggle_topmost)
        menu.add_command(label="打开完整工作台", command=self.open_full)
        menu.add_separator()
        menu.add_command(label="关闭输入栏", command=self.close)
        try:
            menu.tk_popup(self.menu_button.winfo_rootx(), self.menu_button.winfo_rooty() + self.menu_button.winfo_height())
        finally:
            try:
                menu.grab_release()
            except tk.TclError:
                pass  # The Close menu item can destroy the root before popup returns.

    def connect(self):
        self.launcher["ensure_service"](self.port, self.data_dir)
        return self.api.state()

    def worker(self):
        while True:
            kind, operation, context = self.tasks.get()
            try:
                self.results.put((kind, operation(), None, context))
            except Exception as error:
                self.results.put((kind, None, str(error) if isinstance(error, (RuntimeError, ValueError)) else "连接暂时不可用，草稿仍在本机。", context))

    def body(self):
        return self.text.get("1.0", "end-1c")

    def update_placeholder(self):
        if self.body():
            self.placeholder.place_forget()
        else:
            self.placeholder.place(x=10, y=8)

    def changed(self, event=None):
        if not self.text.edit_modified():
            return
        self.text.edit_modified(False)
        if len(self.body()) > 100000:
            self.text.edit_undo()
            self.text.edit_modified(False)
            self.status.configure(text="每条灵感最多 100000 字，已保留此前内容", fg="#a05b49")
            return
        self.update_placeholder()
        if not self.busy:
            self.save_button.configure(text="重新核对" if self.draft.get("pending") else "记下来")
        if "\n" in self.body() and not self.expanded:
            self.toggle_expanded()
        if self.draft_timer:
            self.root.after_cancel(self.draft_timer)
        self.draft_timer = self.root.after(250, self.persist_draft)

    def persist_draft(self):
        self.draft_timer = None
        self.draft.update({"body": self.body(), "topicId": self.selected})
        try:
            write_json(self.draft_path, self.draft)
            if not self.busy:
                self.status.configure(text="草稿已在本机保留" if self.draft["body"] else "Ctrl + Enter 记下来", fg=MUTED)
            return True
        except (OSError, ValueError):
            if self.compact:
                self.show_panel()
            self.status.configure(text="草稿暂存失败，请保留窗口", fg="#a05b49")
            return False

    def persist_preferences(self):
        self.prefs.update({"topmost": self.topmost.get(), "compact": self.compact, "expanded": self.expanded, "topicId": self.selected, "x": self.root.winfo_x(), "y": self.root.winfo_y()})
        try:
            write_json(self.prefs_path, self.prefs)
        except (OSError, ValueError):
            self.status.configure(text="窗口偏好暂未保存", fg="#a05b49")

    def apply_state(self, state):
        live = [topic for topic in state["workspace"]["topics"] if not topic["deletedAt"] and not topic["archived"]]
        live.sort(key=lambda item: (not item["id"].startswith("topic-inbox"),))
        if not any(topic["id"] == "topic-inbox" or topic["id"].startswith("topic-inbox-") for topic in live):
            live.insert(0, {"id": "topic-inbox", "title": "随手记"})
        self.topics = live
        if not any(topic["id"] == self.selected for topic in live):
            self.selected = live[0]["id"]
        self.topic_select.configure(values=[topic["title"][:20] for topic in live])
        self.topic_select.current(next(i for i, topic in enumerate(live) if topic["id"] == self.selected))

    def change_topic(self, event=None):
        index = self.topic_select.current()
        if index >= 0:
            self.selected = self.topics[index]["id"]
            self.persist_preferences()
            self.persist_draft()

    def save(self, event=None):
        if self.busy:
            return "break"
        try:
            pending = self.draft.get("pending") or make_pending(self.body(), self.selected)
        except ValueError as error:
            self.status.configure(text=str(error), fg="#a05b49")
            self.text.focus_set()
            return "break"
        self.draft["pending"] = pending
        if not self.persist_draft():
            return "break"
        self.busy = True
        self.save_button.configure(state="disabled", text="保存中…")
        self.status.configure(text="正在确认保存…", fg=MUTED)
        self.tasks.put(("save", lambda: save_capture(self.api, pending), pending))
        return "break"

    def poll(self):
        if self.closed:
            return
        while not self.results.empty():
            kind, result, error, pending = self.results.get_nowait()
            if kind == "save":
                self.busy = False
                self.save_button.configure(state="normal", text="重新核对" if error else "记下来")
                if error:
                    self.status.configure(text=error, fg="#a05b49")
                    continue
                unchanged = self.body() == pending["body"] and self.selected == pending["topicId"]
                self.apply_state(result["state"])
                if unchanged:
                    self.text.delete("1.0", "end")
                    self.text.edit_modified(False)
                    self.update_placeholder()
                self.draft["pending"] = None
                if self.persist_draft():
                    saved_message = "记录已存在回收站" if result["idea"]["deletedAt"] else "已确认保存 · 继续记下一条"
                    self.status.configure(text=saved_message if unchanged else "上一条已保存，当前内容仍是草稿", fg=GREEN)
                    if self.compact and unchanged:
                        self.save_button.configure(text="已保存")
                self.text.focus_set()
            elif error:
                self.status.configure(text=error, fg="#a05b49")
            else:
                self.apply_state(result)
                if not self.busy:
                    self.status.configure(text="有一条待核对的保存" if self.draft.get("pending") else "草稿已在本机保留" if self.body() else "Ctrl + Enter 记下来", fg=MUTED)
        self.root.after(80, self.poll)

    def refresh(self):
        if not self.closed:
            if not self.busy:
                self.tasks.put(("load", self.api.state, None))
            self.root.after(30000, self.refresh)

    def toggle_topmost(self):
        self.root.attributes("-topmost", self.topmost.get())
        self.persist_preferences()

    def toggle_expanded(self):
        self.expanded = True if self.compact else not self.expanded
        self.compact = False
        self.apply_layout()

    def start_drag(self, event):
        self.drag_origin = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def drag(self, event):
        x, y = self.drag_origin
        self.root.geometry(f"+{max(0, event.x_root - x)}+{max(0, event.y_root - y)}")

    def open_full(self):
        try:
            self.launcher["open_workspace"](self.port)
        except (OSError, RuntimeError) as error:
            self.status.configure(text=str(error), fg="#a05b49")

    def close(self):
        if not self.persist_draft():
            messagebox.showerror("灵感屿", "草稿无法写入磁盘，请复制内容后再关闭。", parent=self.root)
            return
        self.persist_preferences()
        self.closed = True
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description="灵感屿悬浮速记")
    parser.add_argument("--port", type=int, default=18478)
    parser.add_argument("--data-dir", type=Path, default=PROJECT / "user-data")
    args = parser.parse_args()
    handle = None
    root = None
    try:
        if not 1 <= args.port <= 65535:
            raise ValueError("端口必须在 1 到 65535 之间。")
        handle, owned = acquire_window(args.port)
        if not owned:
            return 0
        root = tk.Tk()
        CaptureWindow(root, args.port, args.data_dir.resolve())
        root.mainloop()
    except (OSError, ValueError, RuntimeError, tk.TclError) as error:
        if root:
            messagebox.showerror("灵感屿", str(error), parent=root)
            root.destroy()
        elif sys.platform == "win32":
            ctypes.windll.user32.MessageBoxW(None, str(error), "灵感屿", 0x10)
        return 1
    finally:
        if handle and sys.platform == "win32":
            from ctypes import wintypes
            ctypes.windll.kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            ctypes.windll.kernel32.CloseHandle(handle)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
