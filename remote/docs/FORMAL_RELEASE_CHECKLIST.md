# 正式版交付检查清单

## 当前正式入口

```bash
cd /home/elf/Documents/sum
bash scripts/run_smart_guide.sh
```

该入口固定使用 `sum` 合并识别模式，加载：

- 模型：`/home/elf/Documents/sum/rknnModel/best.rknn`
- 类别映射：`data/class_map/classes_sum.json`
- 知识库：`knowledge/sum_knowledge.json`

## 启动前静态检查

```bash
cd /home/elf/Documents/sum
bash scripts/check_release.sh
```

该检查不会启动摄像头、NPU、音频或 Web 上传，只验证文件、语法、配置和类别数量。

## 演示启动顺序

1. 电脑端启动 Web 后端和前端。
2. 确认 RK3588 能访问电脑端后端地址。
3. RK3588 端运行 `bash scripts/run_smart_guide.sh`。
4. 手机或第二台电脑打开 Web 前端页面查看状态和记录。

## 不应改动的稳定链路

- RKNN/NPU 推理初始化和释放逻辑。
- YOLOv8 后处理数学逻辑。
- `rknnModel/best.rknn` 模型文件。
- `data/class_map/classes_sum.json` 的 class_id 顺序。
- ASR、TTS、Web 上传的运行逻辑。

## 回滚

本次整理前已在远端生成备份：

```text
/home/elf/Documents/sum_formal_backup_clean_20260709_022756.tar.gz
```

需要回滚时，先停止正在运行的主程序，再从该备份恢复。

