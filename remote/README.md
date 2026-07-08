# 基于 RK3588 的端云协同智能导览眼镜系统

## 项目定位

本项目运行在 RK3588 边缘计算平台上，使用 RKNN 量化 YOLOv8 模型完成实时目标检测，并结合导览知识库、DeepSeek 问答、讯飞 ASR、Edge TTS、Qt 显示和 Web 上传，形成智能导览眼镜的端云协同演示系统。

当前正式版本以 `sum` 合并识别模式为主线，统一支持 21 类导览目标：

- 建筑/地标 11 类：故宫、长城、兵马俑、布达拉宫、莫高窟、埃菲尔铁塔、狮身人面像、比萨斜塔、悉尼歌剧院、自由女神像、东方明珠塔
- 动物 10 类：大象、猴子、羊驼、老虎、熊猫、狮子、狐狸、骆驼、浣熊、熊

## 目录结构

```text
.
├── main.py                       # 正式主入口
├── main_camera_fps_v8.py          # 早期独立回退入口
├── config/config.yaml             # 运行配置
├── rknnModel/best.rknn            # RKNN YOLOv8 合并模型
├── data/class_map/                # class_id 到类别名称/展示名映射
├── knowledge/                     # 导览知识库
├── core/                          # 摄像头、配置、推理调度、事件触发、结果格式化
├── func/                          # YOLOv8 后处理
├── rknnpool/                      # RKNNLite 推理池
├── agent/                         # Prompt、知识检索、DeepSeek、ASR/QA 编排
├── audio/                         # 录音、TTS、Redmi USB Audio 初始化
├── ui/                            # Qt/OpenCV 展示
├── web/                           # 本地记录 API 与远端 Web 上传
├── scripts/                       # 启动和检查脚本
└── tests/                         # 硬件/链路测试脚本
```

## 正式启动

推荐使用正式演示脚本：

```bash
cd /home/elf/Documents/sum
bash scripts/run_smart_guide.sh
```

等价命令：

```bash
cd /home/elf/Documents/sum
unset QT_QPA_PLATFORM_PLUGIN_PATH
XAUTHORITY=/run/user/1000/gdm/Xauthority DISPLAY=:0 \
  python3 -u main.py --mode sum --ui qt
```

静态检查，不启动摄像头：

```bash
cd /home/elf/Documents/sum
bash scripts/check_release.sh
```

## 关键配置

主要配置文件是 `config/config.yaml`。

| 配置节 | 关键项 | 说明 |
|---|---|---|
| `runtime` | `mode` | 当前正式值为 `sum` |
| `modes.sum` | `model_path` | 合并 RKNN 模型路径 |
| `modes.sum` | `class_map` | `classes_sum.json` |
| `modes.sum` | `knowledge` | `sum_knowledge.json` |
| `camera` | `id` | 当前摄像头设备 `/dev/video21` |
| `inference` | `conf_threshold`, `thread_num` | 置信度阈值、RKNN 推理线程数 |
| `audio` | `input_source`, `output_sink` | Redmi USB Audio 输入/输出 |
| `deepseek` | `model`, `timeout` | DeepSeek 问答配置 |
| `web_upload` | `base_url`, `device_id` | 上传到电脑端 Web 后端 |

## 功能状态

已接入并用于演示：

- MIPI CSI 摄像头实时采集
- RK3588 NPU / RKNNLite YOLOv8 推理
- DFL + NMS 后处理
- FPS 与分项耗时统计
- 结构化检测结果
- 事件触发与冷却机制
- 合并类别映射与中文导览知识库
- Qt 可视化界面
- Edge TTS 语音播报
- Redmi USB Audio 输入/输出配置
- 讯飞 ASR 语音问答入口
- DeepSeek 问答，未配置 API Key 时自动降级到本地 mock
- 本地 JSONL 记录与 Web 上传

保留但不作为正式主线：

- `main_camera_fps_v8.py` 早期独立入口
- `scenic` / `animal` 启动参数兼容入口，当前均使用 `sum` 合并模型和合并类别表

## Web 演示链路

RK3588 端负责识别和上传，电脑端负责 Web 后端和前端展示。

RK3588 配置中的上传地址：

```yaml
web_upload:
  enabled: true
  base_url: "http://10.147.102.48:8000"
  device_id: "elf2-01"
```

演示时先启动电脑端 Web 后端/前端，再启动 RK3588 主程序。RK3588 日志中应出现：

```text
[web_upload] enabled
[web_upload] heartbeat ok
```

## 注意事项

1. 推理必须使用 RK3588 NPU，不改为 CPU 推理。
2. `rknnModel/best.rknn` 是真实模型文件，不要把显示名称写回模型路径。
3. `classes_sum.json` 的 `class_id` 顺序必须与模型输出一致。
4. 摄像头、音频、NPU 都是硬件相关能力，普通电脑无法完整运行主程序。
5. 演示前先执行 `bash scripts/check_release.sh`，再启动正式入口。
