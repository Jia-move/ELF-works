"""
core/perf.py — 性能统计模块

当前从 utils.perf_timer 重导出。
"""

from utils.perf_timer import (  # noqa: F401
    PerfStats,
    get_stats,
    format_summary,
    draw_stats_on_frame,
)
