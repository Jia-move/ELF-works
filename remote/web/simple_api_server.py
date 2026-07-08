#!/usr/bin/env python3
"""
web/simple_api_server.py — 智能导览眼镜 Web 交互记录服务

基于 Python 标准库 http.server，无需额外依赖。
读取 data/guide_interactions.jsonl，通过浏览器展示识别介绍和问答记录。

启动方式：
    cd /home/elf/Documents/sum
    python3 web/simple_api_server.py
    # 或指定 host/port：
    python3 web/simple_api_server.py --host 0.0.0.0 --port 8080

访问：
    http://<IP>:8080

API 接口：
    GET /api/interactions              — 最近 50 条记录（全部）
    GET /api/interactions?event_type=intro  — 只返回 intro
    GET /api/interactions?event_type=qa     — 只返回 qa
    GET /api/interactions?limit=100         — 指定返回条数
    GET /api/status                         — 服务状态
"""

import argparse
import json
import os
import subprocess
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler


# ============================================================================
# 配置
# ============================================================================

# 项目根目录（web/ 的上一级）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# JSONL 交互记录路径（与 InteractionLogger 默认值一致）
DEFAULT_LOG_PATH = os.path.join(PROJECT_ROOT, "data", "guide_interactions.jsonl")

# 静态文件目录
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

# 服务元信息
SERVER_START_TIME = time.time()
SERVER_VERSION = "1.0.0"


# ============================================================================
# JSONL 读取
# ============================================================================

def _read_interactions(log_path: str = None) -> list:
    """读取 JSONL 文件，返回 dict 列表。

    遇到损坏行时跳过，不影响整体返回。
    文件不存在时返回空列表。
    """
    path = log_path or DEFAULT_LOG_PATH
    records = []
    try:
        if not os.path.exists(path):
            return records
        with open(path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    # 损坏行：跳过，不崩溃
                    print(f"[web] WARNING: skip corrupt line {line_num} in {path}")
                    continue
    except Exception as e:
        print(f"[web] ERROR reading {path}: {e}")
    return records


# ============================================================================
# USB Audio 检测
# ============================================================================

# USB Audio 检测缓存（避免每次 API 请求都执行命令）
_usb_audio_cache = {"available": False, "method": None, "details": "", "checked_at": 0}
_USB_CACHE_TTL = 30  # 缓存有效期（秒）


def _check_usb_audio() -> dict:
    """检测 USB Audio 设备是否可用。

    检测方法（按优先级）：
      1. pactl list short sinks — 查找 usb/USB/Redmi/MV-SILICON/analog-stereo 关键字
      2. aplay -l — 查找 "USB Audio" 字符串

    Returns:
        {
            "available": bool,
            "method": str | None,    # "pactl" | "aplay" | None
            "details": str,          # 匹配到的行（用于日志排查）
        }

    缓存 30 秒，避免频繁调用系统命令。
    """
    global _usb_audio_cache
    now = time.time()
    if now - _usb_audio_cache["checked_at"] < _USB_CACHE_TTL:
        return {
            "available": _usb_audio_cache["available"],
            "method": _usb_audio_cache["method"],
            "details": _usb_audio_cache["details"],
        }

    available = False
    method = None
    details = ""

    # ---- 方法 1: pactl list short sinks ----
    try:
        proc = subprocess.run(
            ["pactl", "list", "short", "sinks"],
            capture_output=True, text=True, timeout=5,
        )
        if proc.returncode == 0:
            keywords = ["usb", "USB", "Redmi", "MV-SILICON", "analog-stereo"]
            for line in proc.stdout.splitlines():
                line_stripped = line.strip()
                if not line_stripped:
                    continue
                for kw in keywords:
                    if kw in line_stripped:
                        available = True
                        method = "pactl"
                        details = line_stripped
                        print(f"[web] USB Audio 检测成功 (pactl): {line_stripped}")
                        break
                if available:
                    break
        else:
            print(f"[web] pactl 返回非0: rc={proc.returncode} stderr={proc.stderr.strip()[:200]}")
    except FileNotFoundError:
        print("[web] pactl 命令未找到，跳过 pactl USB Audio 检测")
    except subprocess.TimeoutExpired:
        print("[web] pactl 命令超时，跳过 pactl USB Audio 检测")
    except Exception as e:
        print(f"[web] pactl USB Audio 检测异常: {e}")

    # ---- 方法 2: aplay -l（pactl 未找到时） ----
    if not available:
        try:
            proc = subprocess.run(
                ["aplay", "-l"],
                capture_output=True, text=True, timeout=5,
            )
            output = proc.stdout + proc.stderr
            if "USB Audio" in output:
                available = True
                method = "aplay"
                # 提取包含 "USB Audio" 的行
                for line in output.splitlines():
                    if "USB Audio" in line:
                        details = line.strip()
                        break
                print(f"[web] USB Audio 检测成功 (aplay): {details}")
            elif proc.returncode != 0:
                print(f"[web] aplay 返回非0: rc={proc.returncode}")
        except FileNotFoundError:
            print("[web] aplay 命令未找到，跳过 aplay USB Audio 检测")
        except subprocess.TimeoutExpired:
            print("[web] aplay 命令超时，跳过 aplay USB Audio 检测")
        except Exception as e:
            print(f"[web] aplay USB Audio 检测异常: {e}")

    if not available:
        print("[web] USB Audio 未检测到（pactl 和 aplay 均未找到匹配设备）")

    # 更新缓存
    _usb_audio_cache = {
        "available": available,
        "method": method,
        "details": details,
        "checked_at": now,
    }
    return {"available": available, "method": method, "details": details}


# ============================================================================
# HTTP 请求处理
# ============================================================================

class GuideWebHandler(BaseHTTPRequestHandler):
    """处理 Web 页面和 API 请求。"""

    # ---- 日志静默 ----
    def log_message(self, format, *args):
        """只打印 API 请求，跳过静态资源。"""
        if "/api/" in (args[0] if args else ""):
            print(f"[web] {self.client_address[0]} - {args[0]}")
        # 静态资源请求不打印

    # ================================================================
    # GET
    # ================================================================

    def do_GET(self):
        """路由分发。"""
        path = self.path.split("?")[0]

        if path == "/" or path == "/index.html":
            self._serve_static("index.html", "text/html; charset=utf-8")
        elif path == "/api/interactions":
            self._handle_interactions()
        elif path == "/api/status":
            self._handle_status()
        elif path.startswith("/static/"):
            self._serve_static_file(path)
        elif path in ("/style.css", "/app.js"):
            # 简便访问（可选）
            self._serve_static(path.lstrip("/"), self._guess_mime(path))
        else:
            self._send_json(404, {"error": "not found", "path": self.path})

    # ================================================================
    # API 端点
    # ================================================================

    def _handle_interactions(self):
        """GET /api/interactions?event_type=intro|qa&limit=50"""
        try:
            # 解析查询参数
            params = self._parse_query()

            event_type = params.get("event_type", "").strip()
            try:
                limit = int(params.get("limit", "50"))
            except ValueError:
                limit = 50
            limit = max(1, min(limit, 500))  # 限制 1-500

            # 读取 JSONL
            all_records = _read_interactions()

            # 筛选
            if event_type in ("intro", "qa"):
                filtered = [r for r in all_records if r.get("event_type") == event_type]
            else:
                filtered = all_records

            # 倒序取最新
            filtered.reverse()
            result = filtered[:limit]

            self._send_json(200, {
                "count": len(result),
                "total": len(all_records),
                "limit": limit,
                "event_type": event_type or "all",
                "records": result,
            })
        except Exception as e:
            print(f"[web] ERROR in /api/interactions: {e}")
            self._send_json(500, {"error": str(e), "records": []})

    def _handle_status(self):
        """GET /api/status"""
        all_records = _read_interactions()
        intro_count = sum(1 for r in all_records if r.get("event_type") == "intro")
        qa_count = sum(1 for r in all_records if r.get("event_type") == "qa")

        # 最新的记录
        latest = all_records[-1] if all_records else None

        # USB Audio 设备检测
        usb_audio = _check_usb_audio()

        self._send_json(200, {
            "server": "guide-web-server",
            "version": SERVER_VERSION,
            "uptime_seconds": round(time.time() - SERVER_START_TIME, 1),
            "log_path": DEFAULT_LOG_PATH,
            "log_exists": os.path.exists(DEFAULT_LOG_PATH),
            "total_records": len(all_records),
            "intro_count": intro_count,
            "qa_count": qa_count,
            "latest_record": latest,
            "usb_audio": {
                "available": usb_audio["available"],
                "method": usb_audio["method"],
            },
        })

    # ================================================================
    # 静态文件
    # ================================================================

    def _serve_static(self, filename: str, mime: str):
        """从 STATIC_DIR 提供静态文件。"""
        filepath = os.path.join(STATIC_DIR, filename)
        self._serve_file(filepath, mime)

    def _serve_static_file(self, path: str):
        """提供 /static/* 请求的文件。"""
        # 安全：防止路径遍历
        rel = path.replace("/static/", "", 1).lstrip("/")
        safe = os.path.normpath(rel)
        if safe.startswith(".."):
            self._send_json(403, {"error": "forbidden"})
            return
        filepath = os.path.join(STATIC_DIR, safe)
        mime = self._guess_mime(filepath)
        self._serve_file(filepath, mime)

    def _serve_file(self, filepath: str, mime: str):
        """通用文件服务。"""
        if not os.path.isfile(filepath):
            self._send_json(404, {"error": "file not found"})
            return
        try:
            with open(filepath, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    # ================================================================
    # 工具
    # ================================================================

    def _parse_query(self) -> dict:
        """解析 URL 查询参数。"""
        params = {}
        if "?" in self.path:
            query = self.path.split("?", 1)[1]
            for pair in query.split("&"):
                if "=" in pair:
                    key, val = pair.split("=", 1)
                    from urllib.parse import unquote
                    params[unquote(key)] = unquote(val)
        return params

    @staticmethod
    def _guess_mime(path: str) -> str:
        """根据扩展名猜测 MIME 类型。"""
        ext = os.path.splitext(path)[1].lower()
        return {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".svg": "image/svg+xml",
        }.get(ext, "application/octet-stream")

    def _send_json(self, code: int, data: dict):
        """发送 JSON 响应。"""
        body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


# ============================================================================
# 启动
# ============================================================================

def main():
    global DEFAULT_LOG_PATH

    parser = argparse.ArgumentParser(description="智能导览眼镜 Web 交互记录服务")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址 (默认 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8080, help="监听端口 (默认 8080)")
    parser.add_argument("--log", default=DEFAULT_LOG_PATH, help=f"JSONL 文件路径 (默认 {DEFAULT_LOG_PATH})")
    args = parser.parse_args()

    # 更新全局路径
    DEFAULT_LOG_PATH = args.log

    print("=" * 56)
    print("  智能导览眼镜 — Web 交互记录服务")
    print("=" * 56)
    print(f"  监听地址:  http://{args.host}:{args.port}")
    print(f"  JSONL 文件: {DEFAULT_LOG_PATH}")
    print(f"  JSONL 存在: {os.path.exists(DEFAULT_LOG_PATH)}")
    print(f"  静态目录:   {STATIC_DIR}")
    print()
    print("  访问页面:  http://<IP>:{}/".format(args.port))
    print("  API 接口:")
    print("    GET /api/interactions")
    print("    GET /api/interactions?event_type=intro")
    print("    GET /api/interactions?event_type=qa&limit=20")
    print("    GET /api/status")
    print()

    server = HTTPServer((args.host, args.port), GuideWebHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[web] 服务已停止")
        server.server_close()


if __name__ == "__main__":
    main()
