"""Run with python test_desktop.py; add --ui for a real, brief Tk window check."""

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import runpy
import socket
import sys
import tempfile
import threading
import time
from urllib.error import URLError

from server import SparkServer


PROJECT = Path(__file__).resolve().parent
quick = runpy.run_path(str(PROJECT / "quick_capture.pyw"), run_name="quick_test")
launcher = runpy.run_path(str(PROJECT / "launch.pyw"), run_name="launcher_test")


def check():
    with tempfile.TemporaryDirectory(prefix="sparkspace-desktop-") as temporary:
        data = Path(temporary).resolve()
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            startup_port = reservation.getsockname()[1]
        assert launcher["healthy"](startup_port) is False
        count = 2 if sys.platform == "win32" else 1
        barrier, owned = threading.Barrier(count), []

        def start():
            barrier.wait()
            return launcher["ensure_service"](startup_port, data / "first-launch")

        try:
            with ThreadPoolExecutor(max_workers=count) as pool:
                for process in pool.map(lambda _: start(), range(count)):
                    if process is not None:
                        owned.append(process)
            assert len(owned) == 1
            assert launcher["healthy"](startup_port) is True
            assert (data / "first-launch/workspace.sqlite3").is_file()
            assert quick["LocalAPI"](startup_port).state()["workspace"]["schemaVersion"] == 1
        finally:
            for process in owned:
                # This handle belongs only to the service spawned in our temporary test directory.
                process.terminate()
                process.wait(timeout=5)
        server = SparkServer(("127.0.0.1", 0), data / "server", PROJECT / "public")
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            port = server.server_port
            assert launcher["healthy"](port) is True
            class ForeignHandler(BaseHTTPRequestHandler):
                def do_GET(self):
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b'{"app":"another-program","ok":true}')

                def log_message(self, *args):
                    pass

            foreign = ThreadingHTTPServer(("127.0.0.1", 0), ForeignHandler)
            threading.Thread(target=foreign.serve_forever, daemon=True).start()
            try:
                launcher["ensure_service"](foreign.server_port, data / "must-not-start")
                raise AssertionError("foreign app was accepted")
            except RuntimeError:
                assert not (data / "must-not-start").exists()
            finally:
                foreign.shutdown()
                foreign.server_close()
            client, peer = quick["LocalAPI"](port), quick["LocalAPI"](port)
            save, pending = quick["save_capture"], quick["make_pending"]
            concurrent = pending("并行设备写入", "topic-inbox")
            original_replace, injected = client.replace, False

            def race(state):
                nonlocal injected
                if not injected:
                    injected = True
                    save(peer, concurrent)
                return original_replace(state)

            client.replace = race
            first = pending("悬浮速记\n保留中文与换行", "topic-inbox")
            result = save(client, first)
            identifiers = [idea["id"] for idea in result["state"]["workspace"]["ideas"]]
            assert injected and identifiers.count(first["id"]) == identifiers.count(concurrent["id"]) == 1

            lost_once = False

            def lost_response(state):
                nonlocal lost_once
                result = original_replace(state)
                if not lost_once:
                    lost_once = True
                    raise URLError("simulated response loss after commit")
                return result

            client.replace = lost_response
            second = pending("超时重试不应重复", "topic-inbox")
            result = save(client, second)
            revision = result["state"]["revision"]
            assert sum(idea["id"] == second["id"] for idea in result["state"]["workspace"]["ideas"]) == 1
            assert save(client, second)["state"]["revision"] == revision

            state = peer.state()
            inbox = next(topic for topic in state["workspace"]["topics"] if topic["id"] == "topic-inbox")
            inbox["deletedAt"] = quick["timestamp"]()
            peer.replace(state)
            client.replace = original_replace
            third = pending("被删除的收件箱不应复活", "topic-inbox")
            result = save(client, third)
            assert result["idea"]["topicId"] != "topic-inbox"
            assert next(topic for topic in result["state"]["workspace"]["topics"] if topic["id"] == "topic-inbox")["deletedAt"]

            draft_path = data / "quick-draft.json"
            draft = {"body": "中文草稿 🪴\n新的修改", "topicId": "topic-inbox", "pending": second}
            quick["write_json"](draft_path, draft)
            assert quick["load_draft"](draft_path) == draft
            draft_path.write_text("{broken", encoding="utf-8")
            try:
                quick["load_draft"](draft_path)
                raise AssertionError("corrupt draft was accepted")
            except RuntimeError:
                assert draft_path.read_text(encoding="utf-8") == "{broken"

            if "--ui" in sys.argv:
                import tkinter as tk
                handle, owned = quick["acquire_window"](port)
                assert owned
                root = tk.Tk()
                app = quick["CaptureWindow"](root, port, data / "window")
                root.update()
                assert root.overrideredirect() and root.attributes("-topmost")
                assert root.winfo_height() <= 64
                assert not app.header.winfo_ismapped() and not app.footer.winfo_ismapped()
                assert app.menu_button.winfo_ismapped()
                assert app.text.winfo_height() >= 30
                if sys.platform == "win32":
                    import ctypes
                    from ctypes import wintypes
                    find = ctypes.windll.user32.FindWindowW
                    find.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
                    find.restype = wintypes.HWND
                    assert find(None, quick["window_title"](port))
                    _, duplicate_owned = quick["acquire_window"](port)
                    assert not duplicate_owned
                app.topmost.set(False)
                app.toggle_topmost()
                root.update()
                assert not root.attributes("-topmost")
                app.show_panel()
                root.update()
                assert root.winfo_height() == 124 and app.header.winfo_ismapped() and app.footer.winfo_ismapped()
                app.text.insert("1.0", "真实 Tk 草稿检查")
                root.update()
                app.toggle_expanded()
                root.update()
                assert root.winfo_height() == 260
                app.show_compact()
                root.update()
                assert root.winfo_height() <= 64
                assert quick["read_json"](data / "window/quick-window.json", {})["compact"] is True
                app.close()
                if handle and sys.platform == "win32":
                    ctypes.windll.kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
                    ctypes.windll.kernel32.CloseHandle(handle)
                assert quick["load_draft"](data / "window/quick-draft.json")["body"] == "真实 Tk 草稿检查"
                time.sleep(0.1)
            print("PASS: real first launch with concurrent callers, occupied-port rejection, HTTP 409 merge, committed timeout dedupe, deleted inbox preservation, atomic draft round-trip, corrupt draft retention" + (", native Tk 60px/124px/260px/topmost/draft/single-instance" if "--ui" in sys.argv else ""))
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    check()
