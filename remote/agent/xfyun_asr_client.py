"""
agent/xfyun_asr_client.py — 讯飞实时语音转写大模型 WebSocket 客户端

通过 WebSocket 将 PCM 音频流式发送到讯飞 ASR 服务，并解析返回的识别文本。

鉴权：
  - 从环境变量读取 appId / accessKeyId / accessKeySecret
  - 按讯飞规则生成 signature（HmacSHA1 + Base64）
  - 密钥全程不打印、不落盘

使用方式：
    from agent.xfyun_asr_client import XfyunAsrClient

    client = XfyunAsrClient()
    text = client.recognize("/tmp/smart_guide_question_16k.pcm")
    print(text)
"""

import os
import sys
import time
import json
import hmac
import hashlib
import base64
import uuid
import threading
from datetime import datetime
from urllib.parse import urlencode, quote

try:
    import websocket
except ImportError:
    websocket = None

# ============================================================================
# 默认配置
# ============================================================================

DEFAULT_ASR_URL = "wss://office-api-ast-dx.iflyaisol.com/ast/communicate/v1"

# 音频参数
AUDIO_SAMPLE_RATE = 16000
AUDIO_BIT_DEPTH = 16
AUDIO_CHANNELS = 1
CHUNK_SIZE = 1280          # 每片字节数（40ms × 16000Hz × 2bytes）
CHUNK_INTERVAL = 0.04      # 每片发送间隔（秒）


# ============================================================================
# XfyunAsrClient
# ============================================================================

class XfyunAsrClient:
    """讯飞实时语音转写大模型客户端。

    工作流程：
    1. 从环境变量加载鉴权信息
    2. 生成签名 URL
    3. 建立 WebSocket 连接
    4. 按 1280 字节分片发送 PCM 音频
    5. 发送结束标记
    6. 收集并拼接识别文本
    """

    def __init__(self, url: str = None):
        """
        Args:
            url: 讯飞 ASR WebSocket URL，默认从环境变量 XFYUN_ASR_URL 读取，
                 未设置则使用内置默认地址

        Raises:
            RuntimeError: 缺少必需的环境变量
        """
        # ---- 从环境变量加载鉴权信息 ----
        self._app_id = os.environ.get("XFYUN_ASR_APP_ID", "").strip()
        self._access_key_id = os.environ.get("XFYUN_ASR_ACCESS_KEY_ID", "").strip()
        self._access_key_secret = os.environ.get("XFYUN_ASR_ACCESS_KEY_SECRET", "").strip()

        # ---- WebSocket URL ----
        if url:
            self._base_url = url
        else:
            self._base_url = os.environ.get("XFYUN_ASR_URL", "").strip() or DEFAULT_ASR_URL

        # ---- 验证必需参数 ----
        missing = []
        if not self._app_id:
            missing.append("XFYUN_ASR_APP_ID")
        if not self._access_key_id:
            missing.append("XFYUN_ASR_ACCESS_KEY_ID")
        if not self._access_key_secret:
            missing.append("XFYUN_ASR_ACCESS_KEY_SECRET")

        if missing:
            raise RuntimeError(
                f"缺少必需的环境变量: {', '.join(missing)}。"
                f"请设置后重试。"
            )

        print(f"[xfyun_asr] APPID         → appId:       {self._mask(self._app_id)}")
        print(f"[xfyun_asr] APIKey        → accessKeyId: {self._mask(self._access_key_id)}")
        print(f"[xfyun_asr] APISecret     → 签名密钥:     **** (长度 {len(self._access_key_secret)})")
        print(f"[xfyun_asr] URL:           {self._base_url}")

        # ---- 识别状态 ----
        self._final_text = ""
        self._lock = threading.Lock()
        self._error = None

    # ================================================================
    # 公共接口
    # ================================================================

    def recognize(self, pcm_path: str, session_id: str = None) -> dict:
        """识别 PCM 音频文件。

        Args:
            pcm_path:    PCM 音频文件路径（16000 Hz, 16bit, mono）
            session_id:  会话 ID，默认自动生成

        Returns:
            {"text": str, "success": bool, "error": str|None}
        """
        if not os.path.exists(pcm_path):
            return {
                "text": "",
                "success": False,
                "error": f"PCM 文件不存在: {pcm_path}",
            }

        pcm_size = os.path.getsize(pcm_path)
        if pcm_size == 0:
            return {
                "text": "",
                "success": False,
                "error": f"PCM 文件为空: {pcm_path}",
            }

        session_id = session_id or str(uuid.uuid4())
        print(f"[xfyun_asr] ========== 开始识别 ==========")
        print(f"[xfyun_asr] PCM 文件:  {pcm_path}")
        print(f"[xfyun_asr] PCM 大小:  {pcm_size} 字节 ({pcm_size/1024:.1f} KB)")
        print(f"[xfyun_asr] 音频时长:  {pcm_size / (AUDIO_SAMPLE_RATE * 2):.2f} 秒")
        print(f"[xfyun_asr] sessionId:  {session_id}")

        # 重置状态
        self._final_text = ""
        self._error = None

        # 建立 WebSocket 连接并发送音频
        try:
            ws_url = self._build_url()
            self._run_websocket(ws_url, pcm_path, pcm_size, session_id)
        except Exception as e:
            err_msg = str(e)
            # 确保不泄露密钥
            for secret in [self._access_key_secret, self._access_key_id, self._app_id]:
                if secret and secret in err_msg:
                    err_msg = err_msg.replace(secret, "***")
            return {
                "text": self._final_text,
                "success": False,
                "error": err_msg,
            }

        if self._error:
            return {
                "text": self._final_text,
                "success": False,
                "error": self._error,
            }

        return {
            "text": self._final_text.strip(),
            "success": True,
            "error": None,
        }

    # ================================================================
    # 签名生成
    # ================================================================

    def _format_utc(self) -> str:
        """生成带时区偏移的时间字符串，如 2026-07-08T17:30:00+0800。"""
        now = datetime.now()
        # time.timezone 是 UTC 以西的秒数（如 CST +0800 → -28800）
        offset_sec = -(time.timezone if not time.daylight else time.altzone)
        sign = "+" if offset_sec >= 0 else "-"
        abs_sec = abs(offset_sec)
        hours = abs_sec // 3600
        minutes = (abs_sec % 3600) // 60
        tz_str = f"{sign}{hours:02d}{minutes:02d}"
        return now.strftime("%Y-%m-%dT%H:%M:%S") + tz_str

    def _build_url(self) -> str:
        """生成带鉴权签名的 WebSocket URL。

        签名规则：
        1. 构建全部请求参数（除 signature）
        2. 按参数名升序排序
        3. key 和 value 分别 URL 编码后用 & 拼接 → baseString
        4. 使用 APISecret 对 baseString 做 HmacSHA1 → Base64 → signature
        """
        utc = self._format_utc()
        request_uuid = str(uuid.uuid4())

        # 构建参数字典（除 signature 外的全部请求参数）
        params = {
            "appId": self._app_id,
            "accessKeyId": self._access_key_id,
            "uuid": request_uuid,
            "utc": utc,
            "audio_encode": "pcm_s16le",
            "lang": "autodialect",
            "samplerate": "16000",
        }

        # 按参数名升序排序
        sorted_keys = sorted(params.keys())

        # URL 编码并拼接为 baseString（key 和 value 分别 encode）
        encoded_pairs = []
        for key in sorted_keys:
            encoded_key = quote(key, safe="")
            encoded_value = quote(str(params[key]), safe="")
            encoded_pairs.append(f"{encoded_key}={encoded_value}")

        base_string = "&".join(encoded_pairs)

        # HmacSHA1 签名（密钥 = APISecret）
        signature_bytes = hmac.new(
            self._access_key_secret.encode("utf-8"),
            base_string.encode("utf-8"),
            hashlib.sha1,
        ).digest()

        signature = base64.b64encode(signature_bytes).decode("utf-8")

        # 构建完整 URL（所有参数升序 + signature）
        params["signature"] = signature
        final_keys = sorted(params.keys())
        query_string = urlencode({k: params[k] for k in final_keys})
        full_url = f"{self._base_url}?{query_string}"

        # 打印调试信息（不泄露 APISecret）
        print(f"[xfyun_asr] utc:          {utc}")
        print(f"[xfyun_asr] uuid:         {request_uuid}")
        print(f"[xfyun_asr] baseString:   {base_string}")
        print(f"[xfyun_asr] APIKey:       {self._mask(self._access_key_id)}")
        print(f"[xfyun_asr] signature:    {self._mask(signature)}")

        return full_url

    # ================================================================
    # WebSocket 通信
    # ================================================================

    def _run_websocket(self, ws_url: str, pcm_path: str,
                       pcm_size: int, session_id: str):
        """建立 WebSocket 连接，发送音频，收集结果。"""
        if websocket is None:
            raise RuntimeError(
                "缺少 websocket-client 库。请安装: pip install websocket-client"
            )

        ws = None
        try:
            print(f"[xfyun_asr] 正在连接 WebSocket...")
            # 设置连接超时
            ws = websocket.create_connection(
                ws_url,
                timeout=10,
            )
            print(f"[xfyun_asr] ✅ WebSocket 已连接")

            # 1. 先接收服务端握手确认帧
            ws.settimeout(5)
            try:
                opcode, data = ws.recv_data()
                if opcode == websocket.ABNF.OPCODE_TEXT:
                    text = data.decode("utf-8")
                    print(f"[xfyun_asr] 服务端握手: {text[:300]}")
                    self._parse_frame(text, 0)
                    if self._error:
                        # 握手阶段就出错了，不再继续
                        ws.close()
                        return
                else:
                    print(f"[xfyun_asr] 服务端握手 opcode={opcode}, len={len(data)}")
            except websocket.WebSocketTimeoutException:
                print(f"[xfyun_asr] ⚠️ 服务端握手超时，继续发送音频...")

            # 2. 发送音频数据
            if not self._error:
                self._send_audio(ws, pcm_path, pcm_size, session_id)

            # 3. 接收识别结果
            self._receive_results(ws, session_id)

        except websocket.WebSocketBadStatusException as e:
            raise RuntimeError(
                f"WebSocket 鉴权失败 (HTTP {e.status_code})。"
                f"请检查 appId / accessKeyId / accessKeySecret 是否正确。"
            )
        except websocket.WebSocketTimeoutException:
            raise RuntimeError("WebSocket 连接超时，请检查网络")
        except websocket.WebSocketConnectionClosedException:
            raise RuntimeError("WebSocket 连接被服务端关闭，可能鉴权失败")
        except ConnectionRefusedError:
            raise RuntimeError("WebSocket 连接被拒绝，请检查 URL 和网络")
        except OSError as e:
            raise RuntimeError(f"网络错误: {e}")
        finally:
            if ws:
                try:
                    ws.close()
                    print(f"[xfyun_asr] WebSocket 已关闭")
                except Exception:
                    pass

    def _send_audio(self, ws, pcm_path: str, pcm_size: int,
                    session_id: str):
        """按 1280 字节分片发送 PCM 音频。"""
        total_sent = 0
        chunk_count = 0

        with open(pcm_path, "rb") as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break

                ws.send_binary(chunk)
                total_sent += len(chunk)
                chunk_count += 1

                # 每片间隔 40ms（模拟实时流）
                time.sleep(CHUNK_INTERVAL)

                # 每 50 片打印一次进度
                if chunk_count % 50 == 0:
                    progress = total_sent / pcm_size * 100
                    print(f"[xfyun_asr] 发送进度: {total_sent}/{pcm_size} "
                          f"({progress:.0f}%), {chunk_count} 片")

        print(f"[xfyun_asr] ✅ 音频发送完成: {total_sent} 字节, {chunk_count} 片")

        # 发送结束标记
        end_msg = json.dumps({"end": True, "sessionId": session_id})
        ws.send(end_msg)
        print(f"[xfyun_asr] 已发送结束标记: {end_msg}")

    def _receive_results(self, ws, session_id: str):
        """接收 WebSocket 返回的识别结果并拼接文本。"""
        print(f"[xfyun_asr] 等待识别结果...")

        received_frames = 0
        timeout_per_frame = 10  # 每帧最多等 10 秒

        while True:
            try:
                ws.settimeout(timeout_per_frame)
                opcode, data = ws.recv_data()
                received_frames += 1

                if opcode == websocket.ABNF.OPCODE_TEXT:
                    text = data.decode("utf-8")
                    self._parse_frame(text, received_frames)

                elif opcode == websocket.ABNF.OPCODE_CLOSE:
                    print(f"[xfyun_asr] 收到关闭帧")
                    break

            except websocket.WebSocketTimeoutException:
                print(f"[xfyun_asr] 接收超时（已收 {received_frames} 帧），结束等待")
                break
            except websocket.WebSocketConnectionClosedException:
                print(f"[xfyun_asr] 连接已关闭（已收 {received_frames} 帧）")
                break
            except Exception as e:
                print(f"[xfyun_asr] 接收异常: {e}")
                break

        print(f"[xfyun_asr] 共收到 {received_frames} 帧")

    def _parse_frame(self, text: str, frame_num: int):
        """解析一帧 JSON 识别结果。

        讯飞 AST 大模型 API 返回格式：
        - 握手帧: {"msg_type":"action", "data":{"action":"started","sessionId":"..."}}
        - 结果帧: {"msg_type":"result", "data":{"cn":{"st":{"rt":{"ws":[...]}}}}}
        - 错误帧: {"code": 非0, "message": "..."}
        """
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            print(f"[xfyun_asr] 第 {frame_num} 帧 JSON 解析失败: {e}")
            print(f"[xfyun_asr]   raw: {text[:500]}")
            return

        # 打印原始 JSON 用于调试（前 300 字符）
        print(f"[xfyun_asr] 第 {frame_num} 帧: {text[:300]}")

        # ---- 错误检测：只有 code 字段存在且非 0 才算错误 ----
        if "code" in data and data["code"] != 0:
            message = data.get("message", "") or data.get("desc", "") or "未知错误"
            self._error = f"讯飞返回错误 (code={data['code']}): {message}"
            print(f"[xfyun_asr] ❌ {self._error}")
            return

        # ---- 处理 action 帧（握手/状态帧） ----
        msg_type = data.get("msg_type", "")
        if msg_type == "action":
            action_data = data.get("data", {})
            action = action_data.get("action", "")
            if action == "started":
                server_session_id = action_data.get("sessionId", "")
                if server_session_id:
                    print(f"[xfyun_asr] ✅ 服务端已就绪, sessionId={server_session_id}")
                else:
                    print(f"[xfyun_asr] ✅ 服务端已就绪")
            else:
                print(f"[xfyun_asr] 服务端 action: {action}")
            return

        # ---- 处理 result 帧（识别结果） ----
        # 路径: data → cn → st → rt[] (数组) → ws[] → cw[] → w
        try:
            result_data = data.get("data", data)
            cn = result_data.get("cn", {})
            st = cn.get("st", {})
            rt = st.get("rt", [])

            # rt 可能是数组 [{ws: [...]}] 或对象 {ws: [...]}
            if isinstance(rt, dict):
                rt_segments = [rt]
            elif isinstance(rt, list):
                rt_segments = rt
            else:
                return

            frame_words = []
            for segment in rt_segments:
                ws_list = segment.get("ws", [])
                for ws_item in ws_list:
                    cw_list = ws_item.get("cw", [])
                    for cw_item in cw_list:
                        w = cw_item.get("w", "")
                        if w:
                            frame_words.append(w)

            frame_text = "".join(frame_words)
            if frame_text:
                with self._lock:
                    self._final_text += frame_text
                print(f"[xfyun_asr] 第 {frame_num} 帧 识别: {frame_text}")
            else:
                # 打印空词信息帮助排查
                ls = result_data.get("ls", False)
                seg_id = result_data.get("seg_id", "?")
                print(f"[xfyun_asr] 第 {frame_num} 帧 空词 (seg_id={seg_id}, ls={ls})")

        except (KeyError, AttributeError, TypeError) as e:
            print(f"[xfyun_asr] 第 {frame_num} 帧 解析跳过: {e}")

    # ================================================================
    # 工具方法
    # ================================================================

    @staticmethod
    def _mask(s: str) -> str:
        """遮盖敏感字符串，只显示前 4 位和后 4 位。"""
        if len(s) <= 8:
            return s[:2] + "****"
        return s[:4] + "****" + s[-4:]


# ============================================================================
# 命令行入口
# ============================================================================

def main():
    """命令行测试入口。"""
    import argparse

    parser = argparse.ArgumentParser(
        description="讯飞实时语音转写大模型 ASR 测试"
    )
    parser.add_argument(
        "pcm_file",
        nargs="?",
        default="/tmp/smart_guide_question_16k.pcm",
        help="PCM 音频文件路径",
    )
    args = parser.parse_args()

    try:
        client = XfyunAsrClient()
    except RuntimeError as e:
        print(f"❌ 初始化失败: {e}", file=sys.stderr)
        sys.exit(1)

    result = client.recognize(args.pcm_file)

    print()
    print("=" * 50)
    if result["success"]:
        print(f"✅ 识别成功")
        print(f"   ASR text: {result['text']}")
    else:
        print(f"❌ 识别失败")
        print(f"   错误: {result['error']}")
        if result["text"]:
            print(f"   部分文本: {result['text']}")
    print("=" * 50)

    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
