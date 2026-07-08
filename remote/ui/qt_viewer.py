"""
ui/qt_viewer.py -- RK3588 智能导览眼镜 Qt 展示界面

本文件只负责 Qt 展示层：视频帧、导览讲解、问答交互、系统状态和性能指标。
推理、后处理、DeepSeek、业务逻辑不在这里处理。
"""

# ============================================================================
# Qt imports
# ============================================================================
_QT_AVAILABLE = False
_QT_BACKEND = None

try:
    from PyQt5 import QtWidgets, QtGui, QtCore
    from PyQt5.QtCore import Qt as QtFlag
    _QT_AVAILABLE = True
    _QT_BACKEND = "PyQt5"
except ImportError:
    try:
        from PySide6 import QtWidgets, QtGui, QtCore
        from PySide6.QtCore import Qt as QtFlag
        _QT_AVAILABLE = True
        _QT_BACKEND = "PySide6"
    except ImportError:
        pass


def is_qt_available():
    return _QT_AVAILABLE


def get_qt_backend():
    return _QT_BACKEND or "none"


# ============================================================================
# 颜色 / 字体 / 布局 Token
# 配色方案: SMART_GUIDE_UI_THEME_SPEC.md
# 奶油白 / 暖桃粉 / 浅杏色 / 暖棕文字 / 交互蓝
# ============================================================================
COLORS = {
    # Backgrounds: 奶油白 / 暖桃粉 / 浅杏色
    "bg_main": "#FFF8F0",
    "bg_page": "#FFF8F0",
    "bg_card": "#FFFFFF",
    "bg_card_hover": "#FCE8DC",
    "bg_card_alt": "#FFF5EE",
    "bg_status": "#FFF5EE",
    "bg_footer": "#E8B5A3",
    "bg_video_bar": "#FFF5EE",
    "bg_video_frame": "#FFF8F0",

    # Borders
    "border": "#F0D6C8",
    "border_soft": "#F0D6C8",
    "border_focus": "#E8B5A3",

    # Text
    "text_title": "#4F352D",
    "text_accent": "#E8B5A3",
    "text_main": "#5F4A42",
    "text_secondary": "#9B8177",
    "text_muted": "#9B8177",
    "text_disabled": "#B8AAA4",

    # Accent
    "accent_orange": "#E6A23C",
    "accent_orange_dark": "#D4882A",
    "accent_blue": "#409EFF",
    "accent_blue_dark": "#3A8DE6",

    # States (from theme spec)
    "success": "#3D8B2D",
    "success_dark": "#67C23A",
    "success_bg": "#EEF8E9",
    "warning": "#A66A13",
    "warning_dark": "#E6A23C",
    "warning_bg": "#FFF4DF",
    "error": "#B54A4A",
    "error_dark": "#F56C6C",
    "error_bg": "#FDECEC",
    "cloud_bg": "#EEF8E9",
    "cloud_border": "#67C23A",
    "cloud_text": "#3D8B2D",

    # QA bubbles
    "q_bg": "#FFF5EE",
    "q_border": "#F0D6C8",
    "q_text": "#5F4A42",
    "a_bg": "#FFF8F0",
    "a_border": "#409EFF",
    "a_text": "#5F4A42",
}

C = COLORS  # 兼容旧变量名

FONT_FAMILY = '"M PLUS Rounded 1c", "Arial Rounded MT Bold", "Hiragino Sans GB", "Noto Sans CJK SC", "Microsoft YaHei", sans-serif'
FONT = {
    "title": 25,
    "subtitle": 14,
    "video_bar": 14,
    "card_title": 19,
    "object_name": 36,
    "object_meta": 16,
    "guide_text": 20,
    "guide_meta": 13,
    "qa_text": 18,
    "qa_hint": 15,
    "qa_label": 15,
    "status_badge": 13,
    "metric": 14,
    "footer": 13,
}
F = FONT

PANEL_W = 480
TITLE_H = 72
FOOTER_H = 38
CARD_RADIUS = 28
CARD_SPACING = 10
PAGE_MARGIN = 14


# ============================================================================
# Helpers
# ============================================================================
def _set_label_text(label, text):
    """Qt label 安全写入，避免 None 造成显示异常。"""
    label.setText("" if text is None else str(text))


def _apply_soft_shadow(widget, *, blur=26, yoff=5, alpha=18):
    if not _QT_AVAILABLE or widget is None:
        return
    try:
        effect = QtWidgets.QGraphicsDropShadowEffect(widget)
        effect.setBlurRadius(blur)
        effect.setOffset(0, yoff)
        effect.setColor(QtGui.QColor(74, 60, 49, alpha))
        widget.setGraphicsEffect(effect)
    except Exception:
        pass


if _QT_AVAILABLE:

    class QtViewer(QtWidgets.QMainWindow):
        WIN_TITLE = "RK3588 智能导览眼镜 · 导览助手"

        def __init__(self, window_title=None, width=None, height=None):
            super().__init__()
            self._closed = False
            self._fullscreen = False
            self._frame_log_count = 0
            self._state_log_count = 0

            # 固定中文窗口标题，避免沿用 config 中的英文 window_name。
            self.setWindowTitle(self.WIN_TITLE)
            self.resize(width or 1440, height or 860)
            self._adjust_size_by_screen()

            self.setStyleSheet(self._app_qss())
            self._install_shortcuts()

            central = QtWidgets.QWidget()
            self.setCentralWidget(central)
            root = QtWidgets.QVBoxLayout(central)
            root.setContentsMargins(0, 0, 0, 0)
            root.setSpacing(0)
            root.addWidget(self._build_title_bar(), 0)
            root.addWidget(self._build_body(), 1)
            root.addWidget(self._build_footer(), 0)

            self._clock_timer = QtCore.QTimer(self)
            self._clock_timer.timeout.connect(self._update_clock)
            self._clock_timer.start(1000)
            self._update_clock()

            self.showMaximized()
            print("[qt_viewer] QtViewer initialized")

        # ------------------------------------------------------------------
        # Init helpers
        # ------------------------------------------------------------------
        def _adjust_size_by_screen(self):
            global PANEL_W
            try:
                screen = QtWidgets.QApplication.primaryScreen()
                screen_w = screen.size().width() if screen else 1920
            except Exception:
                screen_w = 1920

            if screen_w < 1200:
                self.setMinimumSize(960, 640)
                PANEL_W = 430
            else:
                self.setMinimumSize(1180, 720)
                PANEL_W = 480
            if screen_w >= 1600:
                PANEL_W = 520

        def _install_shortcuts(self):
            Shortcut = getattr(QtGui, "QShortcut", None) or getattr(QtWidgets, "QShortcut", None)
            if Shortcut is None:
                return
            Shortcut(QtGui.QKeySequence("F11"), self).activated.connect(self._toggle_fullscreen)
            Shortcut(QtGui.QKeySequence("Escape"), self).activated.connect(self._exit_fullscreen)
            Shortcut(QtGui.QKeySequence("Q"), self).activated.connect(self.close)

        def _app_qss(self):
            return f"""
            QMainWindow {{
                background: {C['bg_main']};
                color: {C['text_main']};
            }}
            QWidget {{
                font-family: {FONT_FAMILY};
                color: {C['text_main']};
            }}
            QLabel {{
                color: {C['text_main']};
            }}
            QScrollArea {{
                border: none;
                background: transparent;
            }}
            QScrollArea > QWidget > QWidget {{
                background: transparent;
            }}
            QScrollBar:vertical {{
                background: {C['bg_main']};
                width: 8px;
                margin: 2px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {C['border']};
                min-height: 24px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {C['accent_blue_dark']};
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            """

        # ------------------------------------------------------------------
        # Title / body / footer
        # ------------------------------------------------------------------
        def _build_title_bar(self):
            frame = QtWidgets.QFrame()
            frame.setFixedHeight(TITLE_H)
            frame.setStyleSheet(f"""
                QFrame {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                                stop:0 #E8B5A3, stop:1 {C['bg_main']});
                    border-bottom: 1px solid {C['border']};
                }}
            """)
            layout = QtWidgets.QHBoxLayout(frame)
            layout.setContentsMargins(24, 8, 20, 8)
            layout.setSpacing(16)

            title_box = QtWidgets.QVBoxLayout()
            title_box.setSpacing(2)
            title = QtWidgets.QLabel("RK3588 智能导览眼镜 · 导览小助手")
            title.setStyleSheet(f"""
                color: {C['text_title']};
                font-size: {F['title']}px;
                font-weight: 850;
                letter-spacing: 0.5px;
            """)
            subtitle = QtWidgets.QLabel("端云协同 · NPU 实时识别 · 智能问答 (◕‿◕)")
            subtitle.setStyleSheet(f"""
                color: #9B8177;
                font-size: {F['subtitle']}px;
                font-weight: 600;
            """)
            title_box.addWidget(title)
            title_box.addWidget(subtitle)
            layout.addLayout(title_box)
            layout.addStretch()

            version = QtWidgets.QLabel("v2.6")
            version.setStyleSheet(f"""
                color: {C['cloud_text']};
                background: {C['cloud_bg']};
                border: 1px solid {C['cloud_border']};
                border-radius: 999px;
                padding: 5px 11px;
                font-size: 12px;
                font-weight: 800;
            """)
            layout.addWidget(version)
            _apply_soft_shadow(frame, blur=24, yoff=2, alpha=14)
            return frame

        def _build_body(self):
            body = QtWidgets.QWidget()
            layout = QtWidgets.QHBoxLayout(body)
            layout.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
            layout.setSpacing(12)

            layout.addWidget(self._build_video_panel(), 1)
            layout.addWidget(self._build_right_panel(), 0)
            return body

        def _build_video_panel(self):
            panel = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(panel)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(8)

            info_frame = QtWidgets.QFrame()
            info_frame.setFixedHeight(34)
            info_frame.setStyleSheet(f"""
                QFrame {{
                    background: {C['bg_video_bar']};
                    border: 1px solid {C['border_soft']};
                    border-radius: 20px;
                }}
            """)
            info_layout = QtWidgets.QHBoxLayout(info_frame)
            info_layout.setContentsMargins(14, 0, 14, 0)
            self._video_info = QtWidgets.QLabel("正在观察前方导览目标 · RK3588 NPU 实时识别 | FPS: -- | 目标: 0  ✦")
            self._video_info.setStyleSheet(f"""
                color: {C['text_secondary']};
                font-size: {F['video_bar']}px;
                font-weight: 750;
            """)
            info_layout.addWidget(self._video_info)
            _apply_soft_shadow(info_frame, blur=18, yoff=2, alpha=12)
            layout.addWidget(info_frame, 0)

            video_frame = QtWidgets.QFrame()
            video_frame.setStyleSheet(f"""
                QFrame {{
                    background: #FFF2F7;
                    border: 1px solid {C['border_soft']};
                    border-radius: 30px;
                }}
            """)
            vf_layout = QtWidgets.QVBoxLayout(video_frame)
            vf_layout.setContentsMargins(0, 0, 0, 0)
            self._video_label = QtWidgets.QLabel("等待摄像头画面…")
            self._video_label.setAlignment(QtFlag.AlignCenter)
            self._video_label.setMinimumSize(520, 360)
            self._video_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
            self._video_label.setStyleSheet(f"background: {C['bg_video_frame']}; border-radius: 26px; color: {C['text_muted']}; font-size: 18px;")
            vf_layout.addWidget(self._video_label)
            deco_row = QtWidgets.QHBoxLayout()
            deco_row.setContentsMargins(0, 0, 8, 0)
            deco_row.addStretch()
            deco = QtWidgets.QLabel("⭐")
            deco.setStyleSheet(f"color: {C['text_title']}; font-size: 20px; background: transparent;")
            deco_row.addWidget(deco)
            vf_layout.insertLayout(0, deco_row)
            _apply_soft_shadow(video_frame, blur=26, yoff=5, alpha=14)
            layout.addWidget(video_frame, 1)
            return panel

        def _build_footer(self):
            footer = QtWidgets.QFrame()
            footer.setFixedHeight(FOOTER_H)
            footer.setStyleSheet(f"""
                QFrame {{
                    background: {C['bg_footer']};
                    border-top: 1px solid {C['border']};
                }}
            """)
            layout = QtWidgets.QHBoxLayout(footer)
            layout.setContentsMargins(20, 0, 20, 0)
            layout.setSpacing(16)
            self._footer_clock = QtWidgets.QLabel("")
            self._footer_update = QtWidgets.QLabel("")
            for label in (self._footer_clock, self._footer_update):
                label.setStyleSheet(f"color: {C['text_muted']}; font-size: {F['footer']}px; font-weight: 500;")
                layout.addWidget(label)
            layout.addStretch()
            hint = QtWidgets.QLabel("按 q 退出  |  F11 全屏  |  Esc 退出全屏")
            hint.setStyleSheet(f"color: {C['text_secondary']}; font-size: {F['footer']}px; font-weight: 750;")
            layout.addWidget(hint)
            return footer

        # ------------------------------------------------------------------
        # Right panel
        # ------------------------------------------------------------------
        def _build_right_panel(self):
            scroll = QtWidgets.QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFixedWidth(PANEL_W)
            container = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(CARD_SPACING)

            layout.addWidget(self._build_system_card(), 0)
            layout.addWidget(self._build_recognition_card(), 0)
            layout.addWidget(self._build_guide_card(), 1)
            layout.addWidget(self._build_qa_card(), 1)
            layout.addWidget(self._build_metric_card(), 0)
            layout.addStretch(0)

            scroll.setWidget(container)
            return scroll

        def _create_card(self, title, *, object_name="card", highlight=False, min_height=100):
            card = QtWidgets.QFrame()
            card.setObjectName(object_name)
            bg = C['bg_card_alt'] if highlight else C['bg_card']
            border = C['border_focus'] if highlight else C['border_soft']
            card.setMinimumHeight(min_height)
            card.setStyleSheet(f"""
                QFrame#{object_name} {{
                    background: {bg};
                    border: 1px solid {border};
                    border-radius: {CARD_RADIUS}px;
                }}
            """)
            layout = QtWidgets.QVBoxLayout(card)
            layout.setContentsMargins(16, 14, 16, 14)
            layout.setSpacing(10)
            title_label = QtWidgets.QLabel(title)
            title_label.setStyleSheet(f"""
                color: {C['text_accent']};
                font-size: {F['card_title']}px;
                font-weight: 850;
                padding-bottom: 2px;
            """)
            _apply_soft_shadow(card, blur=22, yoff=4, alpha=14)
            layout.addWidget(title_label, 0)
            return card, layout

        def _badge(self, text, kind="default"):
            label = QtWidgets.QLabel(text)
            styles = {
                "success": f"background:{C['success_bg']}; color:{C['success']}; border:1px solid {C['success_dark']};",
                "cloud": f"background:{C['cloud_bg']}; color:{C['cloud_text']}; border:1px solid {C['cloud_border']};",
                "warning": f"background:{C['warning_bg']}; color:{C['warning']}; border:1px solid {C['warning_dark']};",
                "error": f"background:{C['error_bg']}; color:{C['error']}; border:1px solid {C['error_dark']};",
            }
            extra = styles.get(kind, f"background:{C['bg_status']}; color:{C['text_secondary']}; border:1px solid #D7A9BA;")
            label.setStyleSheet(f"""
                QLabel {{
                    border-radius: 999px;
                    padding: 6px 12px;
                    font-size: {F['status_badge']}px;
                    font-weight: 800;
                    {extra}
                }}
            """)
            return label

        def _build_system_card(self):
            card, layout = self._create_card("系统状态 ✦", min_height=86)
            self._status_badge_layout = QtWidgets.QHBoxLayout()
            self._status_badge_layout.setSpacing(8)
            self._status_badge_layout.setContentsMargins(0, 0, 0, 0)
            layout.addLayout(self._status_badge_layout)
            self._set_status_badges([
                ("智能导览", "default"),
                ("NPU运行中", "success"),
                ("Mock问答", "default"),
                ("等待识别", "default"),
                ("记录就绪", "cloud"),
            ])
            return card

        def _build_recognition_card(self):
            card, layout = self._create_card("当前识别 ⭐", min_height=118)
            self._object_label = QtWidgets.QLabel("等待识别导览目标")
            self._object_label.setStyleSheet(f"""
                color: {C['text_title']};
                font-size: {F['object_name']}px;
                font-weight: 900;
            """)
            self._object_label.setWordWrap(True)
            self._confidence_label = QtWidgets.QLabel("请把镜头对准展品、动物或导览目标")
            self._confidence_label.setStyleSheet(f"""
                color: {C['text_muted']};
                font-size: {F['object_meta']}px;
                font-weight: 600;
            """)
            layout.addWidget(self._object_label)
            layout.addWidget(self._confidence_label)
            return card

        def _build_guide_card(self):
            card, layout = self._create_card("导览讲解 🌸", object_name="guideCard", highlight=True, min_height=240)
            self._guide_scene_label = QtWidgets.QLabel("")
            self._guide_scene_label.setStyleSheet(f"color: {C['text_title']}; font-size: 16px; font-weight: 850;")
            self._guide_scene_label.hide()
            layout.addWidget(self._guide_scene_label, 0)

            self._guide_text_label = QtWidgets.QLabel("识别到导览目标后，我会在这里送上一段温柔的小讲解呀。")
            self._guide_text_label.setWordWrap(True)
            self._guide_text_label.setAlignment(QtFlag.AlignTop | QtFlag.AlignLeft)
            self._guide_text_label.setStyleSheet(f"""
                color: {C['text_muted']};
                font-size: 18px;
                font-weight: 550;
                line-height: 150%;
            """)
            layout.addWidget(self._guide_text_label, 1)

            self._guide_source_label = QtWidgets.QLabel("")
            self._guide_source_label.setStyleSheet(f"""
                color: {C['cloud_text']};
                background: {C['cloud_bg']};
                border: 1px solid {C['cloud_border']};
                border-radius: 999px;
                padding: 4px 10px;
                font-size: {F['guide_meta']}px;
                font-weight: 750;
            """)
            self._guide_source_label.hide()
            layout.addWidget(self._guide_source_label, 0, QtFlag.AlignLeft)
            return card

        def _build_qa_card(self):
            card, layout = self._create_card("问答互动 (◕‿◕)", object_name="qaCard", min_height=280)
            header = QtWidgets.QHBoxLayout()
            header.setSpacing(8)
            self._qa_status_badge = self._badge("等待识别", "default")
            header.addWidget(self._qa_status_badge)
            header.addStretch()
            layout.addLayout(header)

            self._qa_hint = QtWidgets.QLabel("讲解结束后可以在终端提问哦。\n📝 直接输入文字 → 文本问答 | 🎤 输入 /voice → 语音问答\n例如：“它有什么历史？”  “它是什么时候建成的？”")
            self._qa_hint.setWordWrap(True)
            self._qa_hint.setStyleSheet(f"""
                color: {C['text_secondary']};
                font-size: {F['qa_hint']}px;
                font-weight: 550;
                line-height: 145%;
            """)
            layout.addWidget(self._qa_hint)

            self._question_bubble = self._create_qa_bubble("Q", is_answer=False)
            self._question_text = self._question_bubble.findChild(QtWidgets.QLabel, "bubbleText")
            self._question_bubble.hide()
            layout.addWidget(self._question_bubble)

            self._answer_bubble = self._create_qa_bubble("A", is_answer=True)
            self._answer_text = self._answer_bubble.findChild(QtWidgets.QLabel, "bubbleText")
            self._answer_bubble.hide()
            layout.addWidget(self._answer_bubble, 1)
            return card

        def _create_qa_bubble(self, label_text, *, is_answer):
            bubble = QtWidgets.QFrame()
            if is_answer:
                bg, border, label_color, body_color = C['a_bg'], C['a_border'], C['accent_blue'], C['a_text']
            else:
                bg, border, label_color, body_color = C['q_bg'], C['q_border'], C['text_accent'], C['q_text']
            bubble.setStyleSheet(f"""
                QFrame {{
                    background: {bg};
                    border: 1px solid {border};
                    border-radius: 30px;
                }}
            """)
            layout = QtWidgets.QVBoxLayout(bubble)
            layout.setContentsMargins(12, 10, 12, 10)
            layout.setSpacing(4)
            badge = QtWidgets.QLabel(label_text)
            badge.setStyleSheet(f"color: {label_color}; font-size: {F['qa_label']}px; font-weight: 900; border: none; background: transparent;")
            text = QtWidgets.QLabel("")
            text.setObjectName("bubbleText")
            text.setWordWrap(True)
            text.setStyleSheet(f"color: {body_color}; font-size: {F['qa_text']}px; font-weight: 600; border: none; background: transparent;")
            layout.addWidget(badge)
            layout.addWidget(text)
            return bubble

        def _build_metric_card(self):
            card, layout = self._create_card("性能指标 ☁", object_name="metricCard", min_height=102)
            card.setStyleSheet(f"""
                QFrame#metricCard {{
                    background: {C['bg_card']};
                    border: 1px solid {C['border_soft']};
                    border-radius: {CARD_RADIUS}px;
                }}
            """)
            row = QtWidgets.QHBoxLayout()
            row.setSpacing(8)
            self._metric_fps = self._metric_chip("FPS", "--")
            self._metric_infer = self._metric_chip("推理", "--")
            self._metric_post = self._metric_chip("后处理", "--")
            self._metric_total = self._metric_chip("总耗时", "--")
            for w in [self._metric_fps, self._metric_infer, self._metric_post, self._metric_total]:
                row.addWidget(w)
            layout.addLayout(row)
            return card

        def _metric_chip(self, name, value):
            frame = QtWidgets.QFrame()
            frame.setStyleSheet(f"""
                QFrame {{
                    background: {C['cloud_bg']};
                    border: 1px solid {C['cloud_border']};
                    border-radius: 18px;
                }}
            """)
            l = QtWidgets.QVBoxLayout(frame)
            l.setContentsMargins(10, 7, 10, 7)
            l.setSpacing(2)
            t1 = QtWidgets.QLabel(name)
            t1.setStyleSheet(f"color: {C['text_secondary']}; font-size: 12px; font-weight: 700; background: transparent; border: none;")
            t2 = QtWidgets.QLabel(value)
            t2.setObjectName("metricValue")
            t2.setStyleSheet(f"color: {C['accent_blue_dark']}; font-size: {F['metric']}px; font-weight: 900; background: transparent; border: none;")
            t2.setAlignment(QtFlag.AlignCenter)
            l.addWidget(t1, 0, QtFlag.AlignCenter)
            l.addWidget(t2, 0, QtFlag.AlignCenter)
            return frame

        # ------------------------------------------------------------------
        # Update state
        # ------------------------------------------------------------------
        def update_full(self, state):
            self._apply_state(state or {})

        def update_frame(self, frame):
            try:
                import cv2
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb.shape
                qimg = QtGui.QImage(rgb.data, w, h, ch * w, QtGui.QImage.Format_RGB888)
                pixmap = QtGui.QPixmap.fromImage(qimg).scaled(
                    self._video_label.size(), QtFlag.KeepAspectRatio, QtFlag.SmoothTransformation
                )
                self._video_label.setPixmap(pixmap)
                self._frame_log_count += 1
                if self._frame_log_count <= 3:
                    print(f"[qt_viewer] update_frame #{self._frame_log_count}")
            except Exception as exc:
                if self._frame_log_count < 3:
                    print(f"[qt_viewer] update_frame failed: {exc}")

        def _apply_state(self, state):
            detections = state.get("detections", []) or []
            fps = float(state.get("fps", 0.0) or 0.0)
            object_name = state.get("current_object", "") or ""
            qa_status = state.get("qa_status", "idle") or "idle"
            cloud_mode = state.get("cloud_mode", "mock") or "mock"
            record_status = state.get("record_status", "记录就绪") or "记录就绪"
            if record_status == "Ready":
                record_status = "记录就绪"
            inference_ms = state.get("inference_ms", 0) or 0
            post_ms = state.get("postprocess_ms", 0) or 0
            total_ms = state.get("total_ms", 0) or 0
            last_update = state.get("last_update_time", "") or ""

            # Top video bar
            self._video_info.setText(f"正在观察前方导览目标 · RK3588 NPU 实时识别 | FPS: {fps:.1f} | 目标: {len(detections)}  ✦")

            # System badges
            qa_text, qa_kind = self._qa_status_text(qa_status)
            cloud_text, cloud_kind = self._cloud_text(cloud_mode)
            self._set_status_badges([
                ("智能导览", "default"),
                ("NPU运行中", "success"),
                (cloud_text, cloud_kind),
                (qa_text, qa_kind),
                (record_status, "cloud"),
            ])

            # Recognition
            if object_name:
                self._object_label.setText(object_name)
                conf = 0.0
                if detections and len(detections[0]) > 1:
                    try:
                        conf = float(detections[0][1]) * 100
                    except Exception:
                        conf = 0.0
                self._confidence_label.setText(f"置信度：{conf:.0f}%")
                self._confidence_label.setStyleSheet(f"color: {C['text_secondary']}; font-size: {F['object_meta']}px; font-weight: 650;")
            else:
                self._object_label.setText("等待识别导览目标")
                self._confidence_label.setText("请把镜头对准展品、动物或导览目标")
                self._confidence_label.setStyleSheet(f"color: {C['text_muted']}; font-size: {F['object_meta']}px; font-weight: 600;")

            # Guide intro
            intro_text = state.get("intro_text", "") or state.get("guide_text", "") or ""
            if intro_text:
                self._guide_scene_label.setText(f"当前目标：{object_name}" if object_name else "")
                self._guide_scene_label.setVisible(bool(object_name))
                self._guide_text_label.setText(intro_text)
                self._guide_text_label.setStyleSheet(f"""
                    color: {C['text_main']};
                    font-size: {F['guide_text']}px;
                    font-weight: 650;
                    line-height: 150%;
                """)
                self._guide_source_label.setText("来源：本地知识库")
                self._guide_source_label.show()
            else:
                self._guide_scene_label.hide()
                self._guide_text_label.setText("识别到导览目标后，我会在这里送上一段温柔的小讲解呀。")
                self._guide_text_label.setStyleSheet(f"color: {C['text_muted']}; font-size: 18px; font-weight: 550; line-height: 150%;")
                self._guide_source_label.hide()

            # Q&A
            self._qa_status_badge.setText(qa_text)
            self._qa_status_badge.setStyleSheet(self._badge_style(qa_kind))
            question = state.get("user_question", "") or ""
            answer = state.get("last_answer", "") or ""
            if question:
                self._qa_hint.hide()
                self._question_bubble.show()
                self._question_text.setText(question)
            else:
                self._qa_hint.show()
                self._question_bubble.hide()
            if answer:
                self._answer_bubble.show()
                self._answer_text.setText(answer)
            else:
                self._answer_bubble.hide()

            # Metrics / footer
            self._metric_fps.findChild(QtWidgets.QLabel, "metricValue").setText(f"{fps:.1f}" if fps > 0 else "--")
            self._metric_infer.findChild(QtWidgets.QLabel, "metricValue").setText(f"{float(inference_ms):.0f}ms" if fps > 0 else "--")
            self._metric_post.findChild(QtWidgets.QLabel, "metricValue").setText(f"{float(post_ms):.0f}ms" if fps > 0 else "--")
            self._metric_total.findChild(QtWidgets.QLabel, "metricValue").setText(f"{float(total_ms):.0f}ms" if fps > 0 else "--")
            self._footer_update.setText(f"数据更新：{last_update}" if last_update else "")

            self._state_log_count += 1
            if self._state_log_count <= 3:
                print(f"[qt_viewer] update_full #{self._state_log_count}")

        def _set_status_badges(self, badges):
            while self._status_badge_layout.count():
                item = self._status_badge_layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
            for text, kind in badges:
                self._status_badge_layout.addWidget(self._badge(text, kind))
            self._status_badge_layout.addStretch()

        def _badge_style(self, kind):
            if kind == "success":
                extra = f"background:{C['success_bg']}; color:{C['success']}; border:1px solid {C['success_dark']};"
            elif kind == "cloud":
                extra = f"background:{C['cloud_bg']}; color:{C['cloud_text']}; border:1px solid {C['cloud_border']};"
            elif kind == "warning":
                extra = f"background:{C['warning_bg']}; color:{C['warning']}; border:1px solid {C['warning_dark']};"
            elif kind == "error":
                extra = f"background:{C['error_bg']}; color:{C['error']}; border:1px solid {C['error_dark']};"
            else:
                extra = f"background:{C['bg_status']}; color:{C['text_secondary']}; border:1px solid #D7A9BA;"
            return f"QLabel {{ border-radius:999px; padding:6px 12px; font-size:{F['status_badge']}px; font-weight:800; {extra} }}"

        @staticmethod
        def _qa_status_text(status):
            if status == "intro":
                return "讲解中", "warning"
            if status == "ready":
                return "问答可用", "success"
            if status == "answering":
                return "回答中", "cloud"
            # 语音问答状态
            if status == "listening":
                return "正在聆听 🎤", "cloud"
            if status == "recognizing":
                return "正在识别 🔍", "cloud"
            if status == "thinking":
                return "正在思考 💭", "cloud"
            if status == "speaking":
                return "正在播报 🔊", "warning"
            return "等待识别", "default"

        @staticmethod
        def _cloud_text(mode):
            if mode == "deepseek":
                return "DeepSeek在线", "cloud"
            if mode == "offline":
                return "云端离线", "warning"
            return "Mock问答", "default"

        # ------------------------------------------------------------------
        # Window / compatibility
        # ------------------------------------------------------------------
        @property
        def window_closed(self):
            return self._closed

        def closeEvent(self, event):
            self._closed = True
            super().closeEvent(event)

        def _toggle_fullscreen(self):
            if self._fullscreen:
                self.showMaximized()
                self._fullscreen = False
            else:
                self.showFullScreen()
                self._fullscreen = True

        def _exit_fullscreen(self):
            if self._fullscreen:
                self.showMaximized()
                self._fullscreen = False

        def _update_clock(self):
            from datetime import datetime
            self._footer_clock.setText(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        # ---- Legacy compatibility ----
        def update_info(self, detections=None, guide_text="", fps=0.0, mode=""):
            from datetime import datetime
            self._apply_state({
                "detections": detections or [],
                "guide_text": guide_text,
                "intro_text": guide_text,
                "fps": fps,
                "last_update_time": datetime.now().strftime("%H:%M:%S"),
            })

        def update_detection(self, detections=None):
            self._apply_state({"detections": detections or []})

        def update_guide_text(self, text=""):
            self._apply_state({"guide_text": text, "intro_text": text})

        def update_status(self, status_dict=None):
            if status_dict:
                self._apply_state(status_dict)

        def update_fps(self, fps=0.0):
            self._apply_state({"fps": fps})

else:
    QtViewer = None


# ============================================================================
# Factory
# ============================================================================
def create_viewer(config: dict):
    ui_cfg = config.get("ui", {})
    if ui_cfg.get("mode", "opencv") == "qt" or ui_cfg.get("enable_qt", False):
        if _QT_AVAILABLE:
            app = QtWidgets.QApplication.instance()
            if app is None:
                import sys as _sys
                app = QtWidgets.QApplication(_sys.argv)
            print(f"[ui] Qt mode active, backend: {_QT_BACKEND}")
            viewer = QtViewer(
                width=config.get("display", {}).get("width", 1440),
                height=config.get("display", {}).get("height", 860),
            )
            viewer._qapp = app
            return viewer
        print("[ui] Qt not available, fallback to OpenCV.")
        return None
    return None


def process_qt_events():
    if _QT_AVAILABLE:
        app = QtWidgets.QApplication.instance()
        if app:
            app.processEvents()
