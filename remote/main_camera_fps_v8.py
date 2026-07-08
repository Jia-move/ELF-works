import cv2
import time
import numpy as np
# 图像处理函数，实际应用过程中需要自行修改
from rknnpool.rknnpool_ld import rknnPoolExecutor
from func.func_yolov8_optimize import myFunc
from ui.theme import (
    HUD_TITLE_BAR_BGR, HUD_TEXT_BGR, HUD_FPS_BGR,
    PAGE_BG_BGR,
    HUD_FONT_SCALE, HUD_FONT_THICK,
    HUD_TITLE_SCALE, HUD_MARGIN,
)

out_win = "Smart Guide | RK3588 NPU"
cap = cv2.VideoCapture("/dev/video21")
# cap = cv2.VideoCapture(0)
modelPath = "./rknnModel/best.rknn"
# 线程数, 增大可提高帧率
TPEs = 8


def draw_hud(frame, fps, frame_count):
    """在帧上绘制主题 HUD 浮层。

    顶部标题栏（暖桃粉底 + 暖棕字）覆盖整个画面宽度；
    右侧信息面板显示 FPS、帧计数、模型状态。
    所有绘制操作均为 in-place，不影响推理管线。
    """
    h, w = frame.shape[:2]

    # ---- 顶部标题栏 ----
    bar_h = 40
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, bar_h), HUD_TITLE_BAR_BGR, -1)
    cv2.addWeighted(overlay, 0.88, frame, 0.12, 0, frame)

    # 标题文字
    cv2.putText(frame, "Smart Guide", (HUD_MARGIN, bar_h - 12),
                cv2.FONT_HERSHEY_SIMPLEX, HUD_TITLE_SCALE,
                HUD_TEXT_BGR, HUD_FONT_THICK)
    # 右侧 NPU 标签
    npu_label = "RK3588 NPU"
    (lw, _), _ = cv2.getTextSize(npu_label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    cv2.putText(frame, npu_label, (w - lw - HUD_MARGIN, bar_h - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                HUD_TEXT_BGR, 1)

    # ---- 右侧信息面板 ----
    panel_w, panel_h = 200, 120
    panel_x, panel_y = w - panel_w - HUD_MARGIN, bar_h + HUD_MARGIN

    # 面板半透明背景
    roi = frame[panel_y:panel_y + panel_h, panel_x:panel_x + panel_w]
    panel_bg = np.full_like(roi, PAGE_BG_BGR)
    blended = cv2.addWeighted(roi, 0.25, panel_bg, 0.75, 0)
    frame[panel_y:panel_y + panel_h, panel_x:panel_x + panel_w] = blended

    # 面板边框
    cv2.rectangle(frame, (panel_x, panel_y),
                  (panel_x + panel_w, panel_y + panel_h),
                  HUD_TITLE_BAR_BGR, 1)

    # FPS
    cv2.putText(frame, f"FPS: {fps:.1f}", (panel_x + 10, panel_y + 30),
                cv2.FONT_HERSHEY_SIMPLEX, HUD_FONT_SCALE,
                HUD_FPS_BGR, HUD_FONT_THICK)
    # 帧计数
    cv2.putText(frame, f"Frames: {frame_count}", (panel_x + 10, panel_y + 58),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                HUD_TEXT_BGR, 1)
    # 模型状态
    cv2.putText(frame, "Model: best.rknn", (panel_x + 10, panel_y + 82),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                HUD_TEXT_BGR, 1)
    # NPU 状态
    cv2.putText(frame, "NPU: OK", (panel_x + 10, panel_y + 106),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                HUD_FPS_BGR, 1)


# 初始化rknn池
pool = rknnPoolExecutor(
    rknnModel=modelPath,
    TPEs=TPEs,
    func=myFunc
)

# 初始化异步所需要的帧
if (cap.isOpened()):
    for i in range(TPEs + 1):
        ret, frame = cap.read()
        if not ret:
            cap.release()
            del pool
            exit(-1)
        pool.put(frame)

frames, loopTime, initTime = 0, time.time(), time.time()
current_fps = 0.0

while (cap.isOpened()):
    frames += 1
    ret, frame = cap.read()
    if not ret:
        break
    pool.put(frame)
    frame, flag = pool.get()
    if flag == False:
        break
    cv2.namedWindow(out_win, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(out_win, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    frame = cv2.resize(frame, (1420, 800))

    # 绘制 HUD 浮层（主题配色）
    draw_hud(frame, current_fps, frames)

    cv2.imshow(out_win, frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
    if frames % 30 == 0:
        current_fps = 30 / (time.time() - loopTime)
        print("30帧平均帧率:\t", current_fps, "帧")
        loopTime = time.time()

print("总平均帧率\t", frames / (time.time() - initTime))
# 释放cap和rknn线程池
cap.release()
cv2.destroyAllWindows()
pool.release()
