"""
SMART_GUIDE_UI_THEME 统一主题配色
来源: /home/elf/SMART_GUIDE_UI_THEME_SPEC.md

本模块集中维护所有界面颜色，不散落在其他文件中。
提供三种格式:
  - HEX  (Qt / QSS / CSS 使用)
  - RGB  (参考)
  - BGR  (OpenCV 使用)
"""

# ============================================================
# 1. 核心语义色 (RGB 格式，仅供参考)
# ============================================================

# fmt: off
TOP_BAR_RGB        = (232, 181, 163)   # #E8B5A3  暖桃粉顶栏
PAGE_BG_RGB        = (255, 248, 240)   # #FFF8F0  页面/主背景
SIDE_BAR_RGB       = (255, 245, 238)   # #FFF5EE  侧栏背景
CARD_BG_RGB        = (255, 255, 255)   # #FFFFFF  卡片背景
ACTIVE_MENU_RGB    = (247, 216, 198)   # #F7D8C6  活动菜单背景
HOVER_BG_RGB       = (252, 232, 220)   # #FCE8DC  悬停背景
WARM_BORDER_RGB    = (240, 214, 200)   # #F0D6C8  暖色边框
TITLE_TEXT_RGB     = (79,  53,  45)    # #4F352D  主标题文字
BODY_TEXT_RGB      = (95,  74,  66)    # #5F4A42  正文文字
SECONDARY_TEXT_RGB = (155, 129, 119)   # #9B8177  次级文字
DISABLED_TEXT_RGB  = (184, 170, 164)   # #B8AAA4  禁用文字
INTERACTIVE_BLUE_RGB = (64, 158, 255)  # #409EFF  交互蓝
SUCCESS_GREEN_RGB  = (103, 194, 58)    # #67C23A  成功绿
WARNING_ORANGE_RGB = (230, 162, 60)    # #E6A23C  警告橙
ERROR_RED_RGB      = (245, 108, 108)   # #F56C6C  错误红
# fmt: on


# ============================================================
# 2. OpenCV 使用色 (BGR 格式)
# ============================================================

# --- 面板 / 背景 ---
TOP_BAR_BGR        = (163, 181, 232)   # 暖桃粉顶栏
PAGE_BG_BGR        = (240, 248, 255)   # 主背景
SIDE_BAR_BGR       = (238, 245, 255)   # 侧栏背景
CARD_BG_BGR        = (255, 255, 255)   # 卡片背景
ACTIVE_MENU_BGR    = (198, 216, 247)   # 活动菜单背景
HOVER_BG_BGR       = (220, 232, 252)   # 悬停背景
WARM_BORDER_BGR    = (200, 214, 240)   # 暖色边框

# --- 文字 ---
TITLE_TEXT_BGR     = (45,  53,  79)    # 主标题文字
BODY_TEXT_BGR      = (66,  74,  95)    # 正文文字
SECONDARY_TEXT_BGR = (119, 129, 155)   # 次级文字

# --- 功能色 (Element-UI 风格) ---
INTERACTIVE_BLUE_BGR = (255, 158, 64)  # 交互蓝
SUCCESS_GREEN_BGR = (58,  194, 103)    # 成功绿
WARNING_ORANGE_BGR = (60, 162, 230)    # 警告橙
ERROR_RED_BGR     = (108, 108, 245)    # 错误红

# --- 检测专用色 (保持高对比，便于在视频画面上识别) ---
DETECTION_BOX_BGR      = (255, 158, 64)      # 检测框 — 交互蓝
DETECTION_CORNER_BGR   = (58,  194, 103)     # 角标 — 成功绿
DETECTION_LABEL_BG_BGR = (198, 216, 247)     # 标签背景 — 浅桃色
DETECTION_LABEL_TEXT_BGR = (45, 53, 79)      # 标签文字 — 暖棕

# --- HUD 浮层 ---
HUD_PANEL_BG_BGR    = (240, 248, 255)   # HUD 面板背景 — 奶油白
HUD_PANEL_ALPHA     = 0.75              # HUD 面板透明度
HUD_TITLE_BAR_BGR   = (163, 181, 232)   # HUD 标题栏 — 暖桃粉
HUD_TEXT_BGR        = (45,  53,  79)    # HUD 主文字
HUD_FPS_BGR         = (58,  194, 103)   # FPS 文字 — 成功绿
HUD_TRIGGER_ON_BGR  = (58,  194, 103)   # trigger 激活 — 绿
HUD_TRIGGER_OFF_BGR = (119, 129, 155)   # trigger 未激活 — 次级文字色


# ============================================================
# 3. 组件尺寸规范
# ============================================================

CORNER_LENGTH     = 15     # 检测框角标长度 (px)
BOX_THICKNESS     = 2      # 检测框线宽
LABEL_FONT_SCALE  = 0.6    # 标签字体缩放
LABEL_FONT_THICK  = 2      # 标签字体粗细
HUD_FONT_SCALE    = 0.55   # HUD 字体缩放
HUD_FONT_THICK    = 2      # HUD 字体粗细
HUD_TITLE_SCALE   = 0.7    # HUD 标题字体缩放
HUD_MARGIN        = 12     # HUD 边距
HUD_LINE_HEIGHT   = 28     # HUD 行高
