#!/usr/bin/env python3
"""
main.py — 智能导览眼镜主入口（模块化版本）

通过 core/ 模块组装完整的摄像头 → 检测 → 显示管线。
支持两种运行模式：
  - 同步模式（默认）：主线程串行 read→infer→display
  - 异步模式：Camera 线程 + Feeder 线程 + 主线程 Display
支持三种识别模式：
  - sum（合并，默认）：21类（11景点 + 10动物），使用合并模型
  - scenic（景点）：21类（合并模型 + 合并类别表）
  - animal（动物）：21类（合并模型 + 合并类别表）

运行：
    cd ~/Documents/sum
    export DISPLAY=:0
    python3 main.py --mode sum      # 推荐
    python3 main.py --mode scenic
    python3 main.py --mode animal
"""

import argparse
import os
import sys
import time

import cv2

from core.config import load_config, print_config
from core.camera import CameraCapture
from core.detector import Detector
from core.perf import get_stats, format_summary, draw_stats_on_frame
from core.async_pipeline import AsyncPipeline
from core.result_formatter import get_detection_store, format_summary_text, format_detection
from core.visualizer import get_display_state, draw_detection_overlay
from core.postprocess import set_classes
import core.postprocess as _pp  # 模块引用（CLASSES 通过 _pp.CLASSES 动态访问，避免 from-import 引用不更新）
from core.event_trigger import EventTrigger, format_trigger_text
from core.mode_manager import ModeManager
from core.guide_session import get_session
from core.input_thread import InputThread
from agent.knowledge_base import (get_landmark_by_raw_class,
                                   set_knowledge_path, set_class_map_path)
from agent.qa_manager import QAManager
from agent.voice_handler import VoiceHandler
from audio.speaker import Speaker
from audio.audio_init import ensure_redmi_audio
from core.class_validator import (is_valid_class_id, is_valid_class_name,
                                   is_valid_display_name, is_valid_guide_target,
                                   warn_invalid_class)
from ui.display_manager import DisplayManager
from web.guide_record import GuideRecorder
from web.web_uploader import WebUploader


def _print_detection_summary(frame_count: int, trigger: EventTrigger,
                             speaker: Speaker,
                             recorder: GuideRecorder,
                             qa_manager: QAManager,
                             prompt_type: str = "scenic",
                             domain: str = "landmark",
                             uploader: WebUploader = None,
                             perf_stats=None):
    """读取最新检测结果并打印结构化摘要 + 触发判断 + 智能体响应。

    触发流程：
      1. EventTrigger 判断是否应触发
      2. KnowledgeBase 查询景点知识
      3. QAManager 生成自动介绍文本（优先来自知识库）
      4. 更新 GuideSession 当前景点上下文
      5. Speaker 播报介绍
      6. 写入 InteractionLogger
      7. 设置 qa_active 进入问答状态
    """
    store = get_detection_store()
    boxes, classes, scores, img_w, img_h = store.get_latest()
    result = format_detection(boxes, classes, scores, img_w, img_h,
                              frame_id=frame_count, class_names=_pp.CLASSES)
    print(format_summary_text(result))

    # 评估是否应触发智能体/语音
    trigger_result = trigger.evaluate(result)
    print(format_trigger_text(trigger_result))

    # 触发时：查询知识库 → 生成介绍 → 播报 → 进入 QA 状态
    if trigger_result["should_trigger"]:
        # ---- 过滤非法类别（防御纵深）----
        # format_detection 已按 class_id 做了第一层过滤，这里对 class_name 做第二层校验
        valid_objects = []
        for obj in result.get("objects", []):
            raw_name = obj.get("class_name", "")
            if not raw_name:
                warn_invalid_class(class_name="(empty)", reason="empty class_name in trigger flow")
                continue
            if not is_valid_class_name(raw_name):
                warn_invalid_class(class_name=raw_name, reason="invalid class_name in trigger flow")
                continue
            valid_objects.append(obj)

        if not valid_objects:
            # 所有检测目标均为非法类别，不触发任何下游动作
            print("[warn] all detected objects have invalid class names, skip trigger")

        else:
            # ---- 查询知识库（仅遍历合法目标）----
            class_names_cn = {}
            first_knowledge = None
            first_raw_name = ""
            first_display_name = ""

            for obj in valid_objects:
                raw_name = obj.get("class_name", "")
                info = get_landmark_by_raw_class(raw_name)
                if info:
                    class_names_cn[raw_name] = info["display_name"]
                    if first_knowledge is None:
                        first_knowledge = info
                        first_raw_name = raw_name
                        first_display_name = info["display_name"]
                    break  # 只取第一个有知识库的目标

            # 如果知识库没命中，取第一个检测结果
            if not first_display_name and valid_objects:
                first_obj = valid_objects[0]
                first_raw_name = first_obj.get("class_name", "")
                first_display_name = first_raw_name  # 无中文名时用英文名

            # 打印中文识别结果
            if class_names_cn:
                cn_list = ", ".join(class_names_cn.values())
                print(f"[knowledge] 识别到: {cn_list}")

            # ---- 使用 QAManager 生成自动介绍 ----
            intro_result = qa_manager.build_intro_text(
                raw_name=first_raw_name,
                display_name=first_display_name,
                knowledge=first_knowledge,
            )

            # build_intro_text 返回 None 表示类别非法，跳过播报
            if intro_result is None:
                warn_invalid_class(class_name=first_raw_name,
                                   display_name=first_display_name,
                                   reason="build_intro_text rejected invalid target")
            else:
                intro_text = intro_result.get("answer", "")
                intro_source = intro_result.get("source", "local")
                knowledge_used = (intro_source == "knowledge_base")

                print(f"[intro] {intro_text}")

                # ---- 播报介绍 ----
                speak_key = (first_knowledge.get("class_name", first_raw_name)
                             if first_knowledge else first_raw_name)
                tts_ok = speaker.speak(intro_text, class_name=speak_key)

                # ---- 更新 GuideSession ----
                session = get_session()
                session.update_current_object(
                    raw_name=first_raw_name,
                    display_name=first_display_name,
                    knowledge=first_knowledge,
                    confidence=(valid_objects[0].get("confidence", 0)
                                if valid_objects else 0),
                )
                session.record_intro(intro_text)
                session.set_qa_active(True)

                # 打印 QA 入口提示
                print("[qa] 导览介绍完成。你可以输入问题进一步了解"
                      "（如'建于什么时候？'），"
                      "输入 q 退出问答模式。")

                # ---- 写入日志 ----
                qa_manager.log_intro(
                    raw_name=first_raw_name,
                    display_name=first_display_name,
                    intro_text=intro_text,
                    knowledge_used=knowledge_used,
                    confidence=(valid_objects[0].get("confidence", 0)
                                if valid_objects else 0),
                    source=intro_source,
                )

                # ---- 写入导览记录（兼容旧格式）----
                try:
                    record = GuideRecorder.build_record(
                        domain=domain,
                        class_name=(first_knowledge.get("class_name", first_raw_name)
                                    if first_knowledge else first_raw_name),
                        display_name=first_display_name,
                        confidence=(valid_objects[0].get("confidence", 0)
                                    if valid_objects else 0),
                        guide_text=intro_text,
                        tts_played=tts_ok,
                    )
                    recorder.append(record)
                except Exception:
                    pass

                # ---- 更新画面展示信息 ----
                det_info = [(obj.get("class_name", "?"), obj.get("confidence", 0))
                            for obj in valid_objects]
                get_display_state().update(det_info, intro_text)

                # ---- Web 上传识别事件（非阻塞）----
                if uploader is not None and uploader.enabled:
                    try:
                        summary = perf_stats.get_summary() if perf_stats else {}
                        worker = summary.get("worker", {})
                        event = WebUploader.build_event(
                            device_id=uploader.device_id,
                            class_name=first_raw_name,
                            display_name=first_display_name,
                            confidence=(valid_objects[0].get("confidence", 0)
                                        if valid_objects else 0),
                            fps=summary.get("fps_instant", 0),
                            inference_ms=worker.get("inference_ms", 0),
                            postprocess_ms=worker.get("postprocess_ms", 0),
                            narration_triggered=tts_ok,
                            source="rknn",
                        )
                        if event is not None:
                            uploader.enqueue(event)
                    except Exception:
                        pass  # Web 上传失败绝不影响本地功能

    else:
        # ---- 无触发：检查目标是否消失 ----
        if not result.get("objects"):
            session = get_session()
            if session.qa_active:
                # 目标消失但保持 QA 一小段时间（用户可能还在问问题）
                pass  # QA 状态由用户手动退出或超时退出


def _handle_qa_input(input_thread: InputThread, qa_manager: QAManager,
                     speaker: Speaker, stats,
                     display_mgr=None,
                     voice_handler: VoiceHandler = None,
                     uploader: WebUploader = None):
    """检查是否有用户输入的问题，有则调用 QAManager 或 VoiceHandler 处理。

    在主循环每帧调用，非阻塞。

    支持：
    - 直接文字输入 → 文本问答
    - /voice → 语音问答（录音 → ASR → QA → 播报）

    Returns:
        是否处理了问题
    """
    question = input_thread.get_question()
    if not question:
        return False

    session = get_session()

    # 退出问答模式
    if question == input_thread.QA_EXIT:
        session.set_qa_active(False)
        get_display_state().update_full(qa_status="ready")
        print("[qa] 已退出问答模式，继续导览。")
        return True

    # ---- 语音问答 ----
    if question == input_thread.VOICE_TRIGGER:
        return _handle_voice_question(
            voice_handler, qa_manager, speaker, stats, display_mgr,
            uploader=uploader,
        )

    # ---- 文本问答 ----
    # 没有识别目标
    if not session.current_display_name:
        result = qa_manager.handle_unknown_target_question(question)
    else:
        fps_val = stats.get_summary().get('fps_instant', 0)
        get_display_state().update_full(qa_status="answering", user_question=question)
        result = qa_manager.handle_question(question, fps=fps_val)

    if result:
        answer = result.get("answer", "")
        source = result.get("source", "unknown")
        model = result.get("model", "unknown")
        print(f"[qa] Q: {question}")
        print(f"[qa] A: {answer}")
        print(f"[qa]   source={source} model={model}")

        # 播报回答
        speaker.speak(answer, class_name=session.current_display_name or "qa")

        # 更新 DisplayState（含问答信息）
        det_info = [(session.current_object_raw or "—", session.current_confidence)]
        get_display_state().update_full(
            detections=det_info,
            guide_text=answer,
            user_question=question,
            last_answer=answer,
            qa_status="ready",
        )

        # Qt viewer 更新
        if display_mgr and display_mgr.is_qt:
            try:
                display_mgr.update_guide_text(answer)
            except Exception:
                pass

        # ---- 上传问答记录到 Windows 后端（非阻塞）----
        if uploader is not None and uploader.enabled:
            try:
                uploader.upload_qa_record(
                    question=question,
                    answer=answer,
                    scenic_name=session.current_display_name or "",
                    provider="text_deepseek",
                )
            except Exception:
                pass  # 上传失败不影响本地功能

    return True


def _handle_voice_question(voice_handler: VoiceHandler,
                           qa_manager: QAManager,
                           speaker: Speaker,
                           stats,
                           display_mgr=None,
                           uploader: WebUploader = None) -> bool:
    """处理语音问答流程。

    流程：录音 → ASR 识别 → QA 回答 → 播报 → 更新 UI → 上传 Windows 后端
    """
    if voice_handler is None:
        print("[voice] ❌ VoiceHandler 未初始化")
        return False

    session = get_session()

    # ---- 更新 UI: 正在聆听 ----
    get_display_state().update_full(
        qa_status="listening",
        user_question="🎤 正在聆听...",
    )
    if display_mgr and display_mgr.is_qt:
        try:
            display_mgr.update_guide_text("🎤 正在聆听...")
        except Exception:
            pass

    # ---- 执行语音问答 ----
    result = voice_handler.process_voice_question()

    question_text = result.get("question", "")
    answer_text = result.get("answer", "")
    success = result.get("success", False)
    error = result.get("error", "")

    if success and question_text:
        # ---- 成功：播报回答 ----
        print(f"[voice] ✅ 语音问答完成")
        print(f"[voice] Q: {question_text}")
        print(f"[voice] A: {answer_text}")

        speaker.speak(answer_text, class_name=session.current_display_name or "voice_qa")

        # 更新 UI
        det_info = [(session.current_object_raw or "—", session.current_confidence)]
        get_display_state().update_full(
            detections=det_info,
            guide_text=answer_text,
            user_question=question_text,
            last_answer=answer_text,
            qa_status="ready",
        )

        if display_mgr and display_mgr.is_qt:
            try:
                display_mgr.update_guide_text(answer_text)
            except Exception:
                pass

        # ---- 写入 Web 导览记录 ----
        try:
            from web.guide_record import GuideRecorder
            recorder = GuideRecorder({"web": {}})
            record = GuideRecorder.build_record(
                domain="qa",
                class_name=session.current_object_raw or "voice_qa",
                display_name=session.current_display_name or "语音问答",
                confidence=session.current_confidence,
                guide_text=answer_text,
                tts_played=True,
            )
            record["question"] = question_text
            record["input_mode"] = "voice"
            recorder.append(record)
        except Exception:
            pass

        # ---- 上传问答记录到 Windows 后端（非阻塞）----
        if uploader is not None and uploader.enabled:
            try:
                uploader.upload_qa_record(
                    question=question_text,
                    answer=answer_text,
                    scenic_name=session.current_display_name or "",
                    provider="voice_xfyun_deepseek",
                )
            except Exception:
                pass  # 上传失败不影响本地功能

    else:
        # ---- 失败：显示错误 ----
        print(f"[voice] ❌ 语音问答失败: {error}")

        # 尝试播报错误提示
        speaker.speak(
            "语音识别失败，请重试或使用文本输入",
            class_name="voice_error",
        )

        # 更新 UI
        get_display_state().update_full(
            qa_status="ready",
            user_question="",
            last_answer="语音识别失败，请重试或使用文本输入",
        )

        if display_mgr and display_mgr.is_qt:
            try:
                display_mgr.update_guide_text("语音识别失败，请重试或使用文本输入")
            except Exception:
                pass

    return True


# 记录状态缓存（避免每帧读取 JSONL 文件）
_record_status_cache = {"count": 0, "last_check": 0.0}


def _get_record_status() -> str:
    """获取记录状态字符串。每 5 秒最多读取一次 JSONL 文件。"""
    now = time.time()
    if now - _record_status_cache["last_check"] < 5.0:
        count = _record_status_cache["count"]
    else:
        try:
            log_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "data", "guide_interactions.jsonl",
            )
            if os.path.exists(log_path):
                with open(log_path, "r") as f:
                    count = sum(1 for _ in f)
            else:
                count = 0
        except Exception:
            count = _record_status_cache["count"]
        _record_status_cache["count"] = count
        _record_status_cache["last_check"] = now

    if count > 0:
        return f"已记录 {count} 条"
    return "记录就绪"


def _push_display_state(stats, display_mgr=None):
    """将当前系统状态推送到 DisplayState，供 Qt / OpenCV 叠层使用。

    每帧调用，非阻塞。识别目标从 detection_store 读取（反映实时检测），
    讲解/QA 状态从 GuideSession 读取（反映触发/问答流程）。
    """
    session = get_session()
    summary = stats.get_summary() if stats else {}

    # ---- 从 detection_store 读取最新检测（实时反映视频识别结果）----
    store = get_detection_store()
    boxes, classes, scores, img_w, img_h = store.get_latest()

    latest_obj_raw = ""
    latest_obj_name = ""
    latest_conf = 0.0
    if boxes is not None and len(boxes) > 0 and len(classes) > 0 and len(scores) > 0:
        try:
            cls_idx = int(classes[0])
            if not is_valid_class_id(cls_idx):
                warn_invalid_class(class_id=cls_idx,
                                   reason="invalid class_id in _push_display_state, falling back to session")
                # 不覆盖 latest_obj_raw/name，使用 session 中上一次正常目标
            else:
                latest_obj_raw = _pp.CLASSES[cls_idx]
                latest_conf = float(scores[0])
                # 额外校验 class_name 合法性
                if not is_valid_class_name(latest_obj_raw):
                    warn_invalid_class(class_id=cls_idx, class_name=latest_obj_raw,
                                       reason="invalid class_name in _push_display_state")
                else:
                    # 映射到中文显示名
                    info = get_landmark_by_raw_class(latest_obj_raw)
                    latest_obj_name = info["display_name"] if info else latest_obj_raw
        except (IndexError, ValueError, TypeError):
            pass

    # ---- 当前显示对象：优先使用检测结果（实时的），
    #      但讲解文本和 QA 状态仍从 session 读取 ----
    obj_name = latest_obj_name or session.current_display_name or ""
    obj_raw = latest_obj_raw or session.current_object_raw or ""
    display_conf = latest_conf if latest_obj_name else session.current_confidence

    # ---- 检测对象与上次触发对象不匹配时，清除旧讲解，避免张冠李戴 ----
    session_triggered_raw = session.current_object_raw or ""
    if latest_obj_raw and session_triggered_raw and latest_obj_raw != session_triggered_raw:
        # 对象已变化但尚未触发新讲解：清空旧讲解文本，等待下次触发
        intro_text = ""
        guide_text = ""
    else:
        intro_text = session.last_intro_text or ""
        guide_text = session.last_intro_text or ""

    # QA 状态推导
    if not obj_name:
        qa_status = "idle"
    elif session.qa_active:
        qa_status = "ready"
    else:
        qa_status = "intro"

    # 云端模式
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "")
    cloud_mode = "deepseek" if deepseek_key else "mock"

    # 记录状态（低频：从 JSONL 文件行数读取）
    record_status = _get_record_status()

    # 检测列表：有对象时提供数据，无对象时传空列表
    if obj_name and display_conf > 0:
        detections = [(obj_raw, display_conf)]
    else:
        detections = []

    # Worker 耗时指标
    worker = summary.get("worker", {})
    frame_m = summary.get("frame", {})

    get_display_state().update_full(
        detections=detections,
        current_object=obj_name,
        current_object_raw=obj_raw,
        guide_text=guide_text,
        intro_text=intro_text,
        qa_status=qa_status,
        cloud_mode=cloud_mode,
        fps=summary.get("fps_instant", 0),
        mode="sum",
        record_status=record_status,
        inference_ms=worker.get("inference_ms", 0),
        postprocess_ms=worker.get("postprocess_ms", 0),
        total_ms=(frame_m.get("frame_period_ms", 0) or worker.get("worker_total_ms", 0)),
    )

    # 推送到 Qt viewer
    if display_mgr and display_mgr.is_qt:
        try:
            state = get_display_state().get_all()
            display_mgr.update_full(state)
        except Exception:
            pass


def _print_exit_summary(stats):
    """打印退出时的性能统计摘要。"""
    total_elapsed = stats.elapsed
    print(f"\n===== 性能统计摘要 =====")
    print(f"总帧数:    {stats.total_frames}")
    print(f"总时长:    {total_elapsed:.1f}s")
    print(
        f"总平均FPS: {stats.total_frames / total_elapsed:.2f}"
        if total_elapsed > 0
        else "N/A"
    )
    final = stats.get_summary()
    worker = final.get("worker", {})
    frame_m = final.get("frame", {})
    if worker:
        print(f"推理耗时:  {worker.get('inference_ms', 0):.0f}ms (avg)")
        print(f"预处理:    {worker.get('preprocess_ms', 0):.1f}ms (avg)")
        print(f"后处理:    {worker.get('postprocess_ms', 0):.1f}ms (avg)")
    if frame_m:
        print(f"采集耗时:  {frame_m.get('capture_ms', 0):.1f}ms (avg)")
        print(f"池获取:    {frame_m.get('pool_get_ms', 0):.1f}ms (avg)")
        print(f"显示耗时:  {frame_m.get('display_ms', 0):.1f}ms (avg)")


def _run_sync(camera, detector, trigger, speaker, recorder,
              config, out_win, disp_w, disp_h, show_fps, print_interval,
              display_mgr=None, prompt_type="scenic", domain="landmark",
              qa_manager=None, input_thread=None, uploader=None,
              voice_handler=None):
    """同步模式：主线程串行 read→infer→display。"""
    tpes = detector.pool_size
    stats = get_stats()

    # 预填充
    print(f"[init] Pre-filling pipeline with {tpes + 1} frames...")
    for i in range(tpes + 1):
        ret, frame = camera.read()
        if not ret:
            print(f"[ERROR] Failed to read camera frame {i}")
            return
        detector.put(frame)
    print("[init] Pipeline ready (sync mode)")

    # ---- 窗口初始化（OpenCV 模式创建窗口，Qt 模式已在 DisplayManager 中完成）----
    if display_mgr is not None:
        display_mgr.setup_window(out_win, disp_w, disp_h)

    # ---- 启动输入线程 ----
    if input_thread is not None:
        input_thread.start()

    last_print_time = time.time()
    try:
        while camera.is_opened:
            t_frame_start = time.time()

            t0 = time.time()
            ret, frame = camera.read()
            t_capture_ms = (time.time() - t0) * 1000
            if not ret:
                break

            detector.put(frame)

            t0 = time.time()
            frame, ok = detector.get()
            t_pool_get_ms = (time.time() - t0) * 1000
            if not ok:
                break

            t0 = time.time()
            frame = display_mgr.resize_frame(frame, disp_w, disp_h) if display_mgr else cv2.resize(frame, (disp_w, disp_h))

            summary = stats.get_summary()
            # Qt 模式已经在右侧面板和视频信息条展示性能指标，避免在视频帧上叠加绿色调试文字。
            if show_fps and summary and not (display_mgr is not None and display_mgr.backend == "qt"):
                draw_stats_on_frame(frame, summary)

            # 检测信息叠层（OpenCV 模式画到 frame 上，Qt 模式通过 DisplayState 显示）
            det_info, guide_text = get_display_state().get()
            if display_mgr is None or display_mgr.backend == "opencv":
                draw_detection_overlay(frame, det_info, guide_text)

            # ---- 统一显示（Qt 模式走 QtViewer，OpenCV 模式走 cv2.imshow）----
            if display_mgr is not None:
                display_mgr.show_frame(frame)
                _push_display_state(stats, display_mgr)
                key = display_mgr.get_key()
            else:
                cv2.imshow(out_win, frame)
                key = cv2.waitKey(1) & 0xFF
            t_display_ms = (time.time() - t0) * 1000

            t_frame_period_ms = (time.time() - t_frame_start) * 1000
            try:
                stats.record_frame(capture_ms=t_capture_ms, pool_get_ms=t_pool_get_ms,
                                   display_ms=t_display_ms, frame_period_ms=t_frame_period_ms)
            except Exception:
                pass

            # ---- QA: 非阻塞检查用户输入 ----
            if input_thread is not None and qa_manager is not None:
                _handle_qa_input(input_thread, qa_manager, speaker, stats,
                                 display_mgr, voice_handler=voice_handler,
                                 uploader=uploader)

            # ---- 退出判断 ----
            if display_mgr is not None:
                if display_mgr.should_quit(key):
                    break
            elif key == ord("q"):
                break

            now = time.time()
            if now - last_print_time >= print_interval:
                print(format_summary(summary))
                _print_detection_summary(stats.total_frames, trigger,
                                         speaker, recorder, qa_manager,
                                         prompt_type, domain,
                                         uploader=uploader, perf_stats=stats)
                last_print_time = now
    finally:
        if input_thread is not None:
            input_thread.stop()

    _print_exit_summary(stats)


def _run_async(camera, detector, trigger, speaker, recorder, config,
               out_win, disp_w, disp_h,
               show_fps, print_interval, display_mgr=None, prompt_type="scenic", domain="landmark",
               qa_manager=None, input_thread=None, uploader=None,
               voice_handler=None):
    """异步模式：Camera 线程 + Feeder 线程 + 主线程 Display。"""
    tpes = detector.pool_size
    stats = get_stats()
    pipeline = AsyncPipeline(camera, detector, config)

    # 预填充 rknn 池（在启动流水线线程之前）
    print(f"[init] Pre-filling detector with {tpes + 1} frames...")
    for i in range(tpes + 1):
        ret, frame = camera.read()
        if not ret:
            print(f"[ERROR] Failed to read camera frame {i}")
            return
        detector.put(frame)
    print("[init] Pipeline ready (async mode)")

    # ---- 窗口初始化 ----
    if display_mgr is not None:
        display_mgr.setup_window(out_win, disp_w, disp_h)

    # ---- 启动输入线程 ----
    if input_thread is not None:
        input_thread.start()

    # 启动摄像头和喂料线程
    pipeline.start()

    last_frame = None
    last_print_time = time.time()

    try:
        while camera.is_opened:
            loop_start = time.time()

            # 非阻塞获取最新推理结果
            result = pipeline.get_display_frame()
            if result is not None:
                last_frame = result

            # 如果没有结果可用，显示上一帧（或黑屏等待）
            if last_frame is None:
                if display_mgr is not None:
                    key = display_mgr.get_key()
                else:
                    key = cv2.waitKey(1) & 0xFF
                if display_mgr is not None:
                    if display_mgr.should_quit(key):
                        break
                elif key == ord("q"):
                    break
                continue

            # 显示
            t0 = time.time()
            display_frame = (display_mgr.resize_frame(last_frame.copy(), disp_w, disp_h)
                             if display_mgr else cv2.resize(last_frame.copy(), (disp_w, disp_h)))

            summary = stats.get_summary()
            # Qt 模式已经在右侧面板和视频信息条展示性能指标，避免在视频帧上叠加绿色调试文字。
            if show_fps and summary and not (display_mgr is not None and display_mgr.backend == "qt"):
                draw_stats_on_frame(display_frame, summary)

            # 检测信息叠层（仅 OpenCV 模式画到 frame）
            det_info, guide_text = get_display_state().get()
            if display_mgr is None or display_mgr.backend == "opencv":
                draw_detection_overlay(display_frame, det_info, guide_text)

            # ---- 统一显示 ----
            if display_mgr is not None:
                display_mgr.show_frame(display_frame)
                _push_display_state(stats, display_mgr)
                key = display_mgr.get_key()
            else:
                cv2.imshow(out_win, display_frame)
                key = cv2.waitKey(1) & 0xFF
            t_display_ms = (time.time() - t0) * 1000

            # 主线程帧统计
            t_frame_period_ms = (time.time() - loop_start) * 1000
            try:
                stats.record_frame(display_ms=t_display_ms,
                                   frame_period_ms=t_frame_period_ms)
            except Exception:
                pass

            # ---- QA: 非阻塞检查用户输入 ----
            if input_thread is not None and qa_manager is not None:
                _handle_qa_input(input_thread, qa_manager, speaker, stats,
                                 display_mgr, voice_handler=voice_handler,
                                 uploader=uploader)

            # ---- 退出判断 ----
            if display_mgr is not None:
                if display_mgr.should_quit(key):
                    break
            elif key == ord("q"):
                break

            # 终端打印（含队列深度）
            now = time.time()
            if now - last_print_time >= print_interval:
                base = format_summary(summary) if summary else ""
                q_info = (f" | fq:{pipeline.frame_queue_depth}"
                          f" rq:{pipeline.result_queue_depth}")
                print(base + q_info)
                _print_detection_summary(stats.total_frames, trigger,
                                         speaker, recorder, qa_manager,
                                         prompt_type, domain,
                                         uploader=uploader, perf_stats=stats)
                last_print_time = now

    finally:
        if input_thread is not None:
            input_thread.stop()
        pipeline.stop()

    _print_exit_summary(stats)


def main():
    # ---- 解析命令行参数 ----
    parser = argparse.ArgumentParser(description="智能导览眼镜")
    parser.add_argument("--mode", type=str, default=None,
                        choices=["sum", "scenic", "animal"],
                        help="识别模式: sum (合并) | scenic (建筑/地标) | animal (动物)")
    parser.add_argument("--ui", type=str, default=None,
                        choices=["opencv", "qt"],
                        help="显示后端: opencv | qt (默认根据 config.yaml ui.mode)")
    args = parser.parse_args()

    # ---- 加载配置 ----
    config_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "config", "config.yaml"
    )
    if not os.path.exists(config_path):
        config_path = "config/config.yaml"
    config = load_config(config_path)

    # ---- CLI 覆盖显示模式 ----
    if args.ui:
        config["ui"]["mode"] = args.ui
        print(f"[init] UI mode override: {args.ui}")

    # ---- 确定识别模式 ----
    mode_name = args.mode or config.get("runtime", {}).get("mode", "sum")
    mode_mgr = ModeManager(mode_name, config)
    print(f"[init] 识别模式: {mode_mgr.name} ({mode_name})")
    print(f"[init] 模型路径: {mode_mgr.model_path}")

    # ---- 设置类别表 ----
    classes = mode_mgr.load_classes()
    if classes:
        set_classes(classes)
        print(f"[init] 类别数量: {len(classes)}")
    else:
        print("[ERROR] Failed to load classes")
        sys.exit(1)

    # ---- 设置知识库路径 ----
    set_class_map_path(mode_mgr.class_map_path)
    set_knowledge_path(mode_mgr.knowledge_path)
    print(f"[init] 知识库: {mode_mgr.knowledge_path}")

    print_config(config)

    # ---- Redmi USB 音频自检 ----
    audio_ready = ensure_redmi_audio(force=True)
    if not audio_ready["ready"]:
        print("[audio] ⚠️ Redmi 音频设备未就绪，语音功能可能不可用")
        if audio_ready.get("errors"):
            for err in audio_ready["errors"]:
                print(f"[audio]   {err}")

    # ---- 读取参数 ----
    out_win = config["display"]["window_name"]
    disp_w = config["display"]["width"]
    disp_h = config["display"]["height"]
    show_fps = config["display"]["show_fps"]
    print_interval = config["performance"]["print_interval_sec"]
    async_mode = config.get("pipeline", {}).get("async_mode", False)

    # ---- 覆盖模型路径 ----
    config["model"]["path"] = mode_mgr.model_path

    # ---- 初始化 ----
    try:
        camera = CameraCapture(config["camera"]["id"])
    except RuntimeError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    detector = Detector(config)
    trigger = EventTrigger(config)
    speaker = Speaker(config)
    recorder = GuideRecorder(config)

    # ---- WebUploader（非阻塞，默认关闭）----
    uploader = WebUploader(config, mode=mode_mgr.mode)
    # 更新心跳状态
    qt_backend = config.get("ui", {}).get("mode", "opencv")
    uploader.update_status(
        qt_status="running" if qt_backend == "qt" else "stopped",
    )

    # ---- QA 模块 ----
    qa_manager = QAManager(config)
    voice_handler = VoiceHandler(config)
    input_thread = InputThread()

    # ---- UI 模式 ----
    display_mgr = DisplayManager(config)
    print(f"[init] Display backend: {display_mgr.backend}")

    # ---- 运行 ----
    mode_label = "ASYNC" if async_mode else "SYNC"
    print(f"[init] Running in {mode_label} mode")

    try:
        if async_mode:
            _run_async(camera, detector, trigger, speaker, recorder,
                       config, out_win, disp_w, disp_h, show_fps, print_interval,
                       display_mgr, prompt_type=mode_mgr.prompt_type, domain=mode_mgr.domain,
                       qa_manager=qa_manager, input_thread=input_thread,
                       uploader=uploader, voice_handler=voice_handler)
        else:
            _run_sync(camera, detector, trigger, speaker, recorder,
                      config, out_win, disp_w, disp_h, show_fps, print_interval,
                      display_mgr, prompt_type=mode_mgr.prompt_type, domain=mode_mgr.domain,
                      qa_manager=qa_manager, input_thread=input_thread,
                      uploader=uploader, voice_handler=voice_handler)
    except KeyboardInterrupt:
        print("\n[exit] Interrupted by user")
    finally:
        input_thread.stop()
        # WebUploader 安全退出（不阻塞主程序）
        try:
            uploader.shutdown()
        except Exception:
            pass
        camera.release()
        if display_mgr is not None:
            display_mgr.cleanup()
        else:
            cv2.destroyAllWindows()
        detector.release()
        # 重置会话状态
        get_session().clear_current_object()
        print("[exit] Cleanup complete")


if __name__ == "__main__":
    main()
