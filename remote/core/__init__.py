# core package — 智能导览眼镜核心模块
#
# 模块职责：
#   camera.py      — 摄像头采集
#   detector.py    — RKNN YOLO 检测器
#   postprocess.py — YOLO 后处理（重导出，后续可替换为本机实现）
#   visualizer.py  — 检测框 / 性能信息绘制
#   perf.py        — 性能统计（重导出）
#   config.py      — 配置加载（重导出）
