# 以下代码改自https://github.com/rockchip-linux/rknn-toolkit2/tree/master/examples/onnx/yolov5
import cv2
import numpy as np
import time
from copy import copy
from utils.perf_timer import get_stats
from core.result_formatter import get_detection_store
OBJ_THRESH, NMS_THRESH, IMG_SIZE = 0.25, 0.45, 640
out_win = "output_style_full_screen"
CLASSES = ("The Forbidden City","The Great Wall","Terracotta Army","Potala Palace",
            "Mogao Caves" ,"The Eiffel Tower","The Sphinx","The Leaning Tower of Pisa",
            "Sydney Opera House","The Statue of Liberty","Shanghai Oriental Pearl Tower",
            "elephant","monkey","alpaca","tiger","panda","lion","fox","camel","raccoon","bear")
INTERESTED_CLASSES = ("The Forbidden City","The Great Wall","Terracotta Army","Potala Palace",
            "Mogao Caves" ,"The Eiffel Tower","The Sphinx","The Leaning Tower of Pisa",
            "Sydney Opera House","The Statue of Liberty","Shanghai Oriental Pearl Tower",
            "elephant","monkey","alpaca","tiger","panda","lion","fox","camel","raccoon","bear")

CLASS_INDICES = {cls: idx for idx, cls in enumerate(CLASSES)}
INTERESTED_CLASS_INDICES = [CLASS_INDICES[cls] for cls in INTERESTED_CLASSES]


# 运行时开关（由 apply_detection_config 设置）
DRAW_BOXES = True


def set_classes(classes: tuple) -> None:
    """设置当前检测模式的类别表。

    Args:
        classes: 类别名元组，如 ("elephant", "monkey", ...)
    """
    global CLASSES, INTERESTED_CLASSES, CLASS_INDICES, INTERESTED_CLASS_INDICES
    CLASSES = tuple(classes)
    INTERESTED_CLASSES = tuple(classes)
    CLASS_INDICES = {cls: idx for idx, cls in enumerate(CLASSES)}
    INTERESTED_CLASS_INDICES = [CLASS_INDICES[cls] for cls in INTERESTED_CLASSES]


def apply_detection_config(config: dict) -> None:
    """将配置文件中的检测参数应用到模块级变量。

    在创建推理池之前调用。如果 config 中缺少对应键，保持当前值不变。

    Args:
        config: load_config() 返回的完整配置字典
    """
    global OBJ_THRESH, NMS_THRESH, IMG_SIZE, DRAW_BOXES
    try:
        OBJ_THRESH = float(config.get("inference", {}).get("conf_threshold", OBJ_THRESH))
        NMS_THRESH = float(config.get("inference", {}).get("iou_threshold", NMS_THRESH))
        img_w = int(config.get("model", {}).get("input_width", IMG_SIZE))
        img_h = int(config.get("model", {}).get("input_height", IMG_SIZE))
        if img_w != img_h:
            print(f"[config] WARNING: input_width({img_w}) != input_height({img_h}), using width={img_w}")
        IMG_SIZE = img_w
        DRAW_BOXES = bool(config.get("display", {}).get("draw_boxes", DRAW_BOXES))
    except (ValueError, TypeError) as e:
        print(f"[config] WARNING: Invalid detection config value: {e}, keeping defaults")
def filter_boxes(boxes, box_confidences, box_class_probs):
    """Filter boxes with object threshold.
    """
    box_confidences = box_confidences.reshape(-1)
    candidate, class_num = box_class_probs.shape

    class_max_score = np.max(box_class_probs, axis=-1)
    classes = np.argmax(box_class_probs, axis=-1)

    _class_pos = np.where(class_max_score * box_confidences >= OBJ_THRESH)
    scores = (class_max_score * box_confidences)[_class_pos]

    boxes = boxes[_class_pos]
    classes = classes[_class_pos]

    return boxes, classes, scores


def nms_boxes(boxes, scores):
    """Suppress non-maximal boxes.
    # Returns
        keep: ndarray, index of effective boxes.
    """
    x = boxes[:, 0]
    y = boxes[:, 1]
    w = boxes[:, 2] - boxes[:, 0]
    h = boxes[:, 3] - boxes[:, 1]

    areas = w * h
    order = scores.argsort()[::-1]

    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)

        xx1 = np.maximum(x[i], x[order[1:]])
        yy1 = np.maximum(y[i], y[order[1:]])
        xx2 = np.minimum(x[i] + w[i], x[order[1:]] + w[order[1:]])
        yy2 = np.minimum(y[i] + h[i], y[order[1:]] + h[order[1:]])

        w1 = np.maximum(0.0, xx2 - xx1 + 0.00001)
        h1 = np.maximum(0.0, yy2 - yy1 + 0.00001)
        inter = w1 * h1

        ovr = inter / (areas[i] + areas[order[1:]] - inter)
        inds = np.where(ovr <= NMS_THRESH)[0]
        order = order[inds + 1]
    keep = np.array(keep)
    return keep


# def dfl(position):
#     # Distribution Focal Loss (DFL)
#     import torch
#     x = torch.tensor(position)
#     n,c,h,w = x.shape
#     p_num = 4
#     mc = c//p_num
#     y = x.reshape(n,p_num,mc,h,w)
#     y = y.softmax(2)
#     acc_metrix = torch.tensor(range(mc)).float().reshape(1,1,mc,1,1)
#     y = (y*acc_metrix).sum(2)
#     return y.numpy()

# def dfl(position):
#     # Distribution Focal Loss (DFL)
#     n, c, h, w = position.shape
#     p_num = 4
#     mc = c // p_num
#     y = position.reshape(n, p_num, mc, h, w)
#     exp_y = np.exp(y)
#     y = exp_y / np.sum(exp_y, axis=2, keepdims=True)
#     acc_metrix = np.arange(mc).reshape(1, 1, mc, 1, 1).astype(float)
#     y = (y * acc_metrix).sum(2)
#     return y

def dfl(position):
    # Distribution Focal Loss (DFL)
    # x = np.array(position)
    n, c, h, w = position.shape
    p_num = 4
    mc = c // p_num
    y = position.reshape(n, p_num, mc, h, w)

    # Vectorized softmax
    e_y = np.exp(y - np.max(y, axis=2, keepdims=True))  # subtract max for numerical stability
    y = e_y / np.sum(e_y, axis=2, keepdims=True)

    acc_metrix = np.arange(mc).reshape(1, 1, mc, 1, 1)
    y = (y * acc_metrix).sum(2)
    return y


def box_process(position):
    grid_h, grid_w = position.shape[2:4]
    col, row = np.meshgrid(np.arange(0, grid_w), np.arange(0, grid_h))
    col = col.reshape(1, 1, grid_h, grid_w)
    row = row.reshape(1, 1, grid_h, grid_w)
    grid = np.concatenate((col, row), axis=1)
    stride = np.array([IMG_SIZE // grid_h, IMG_SIZE // grid_w]).reshape(1, 2, 1, 1)

    position = dfl(position)
    box_xy = grid + 0.5 - position[:, 0:2, :, :]
    box_xy2 = grid + 0.5 + position[:, 2:4, :, :]
    xyxy = np.concatenate((box_xy * stride, box_xy2 * stride), axis=1)

    return xyxy


def yolov8_post_process(input_data):
    boxes, scores, classes_conf = [], [], []
    defualt_branch = 3
    pair_per_branch = len(input_data) // defualt_branch
    # Python 忽略 score_sum 输出
    for i in range(defualt_branch):
        boxes.append(box_process(input_data[pair_per_branch * i]))
        classes_conf.append(input_data[pair_per_branch * i + 1])
        scores.append(np.ones_like(input_data[pair_per_branch * i + 1][:, :1, :, :], dtype=np.float32))

    def sp_flatten(_in):
        ch = _in.shape[1]
        _in = _in.transpose(0, 2, 3, 1)
        return _in.reshape(-1, ch)

    boxes = [sp_flatten(_v) for _v in boxes]
    classes_conf = [sp_flatten(_v) for _v in classes_conf]
    scores = [sp_flatten(_v) for _v in scores]

    boxes = np.concatenate(boxes)
    classes_conf = np.concatenate(classes_conf)
    scores = np.concatenate(scores)

    # filter according to threshold
    boxes, classes, scores = filter_boxes(boxes, scores, classes_conf)

    # nms
    nboxes, nclasses, nscores = [], [], []
    for c in set(classes):
        inds = np.where(classes == c)
        b = boxes[inds]
        c = classes[inds]
        s = scores[inds]
        keep = nms_boxes(b, s)

        if len(keep) != 0:
            nboxes.append(b[keep])
            nclasses.append(c[keep])
            nscores.append(s[keep])

    if not nclasses and not nscores:
        return None, None, None

    boxes = np.concatenate(nboxes)
    classes = np.concatenate(nclasses)
    scores = np.concatenate(nscores)

    return boxes, classes, scores

def draw_box_corner(draw_img, x1, y1, x2, y2, length, corner_color):
    """绘制克制的 L 形角标。坐标命名为 x1/y1/x2/y2。"""
    thickness = 2
    cv2.line(draw_img, (x1, y1), (x1 + length, y1), corner_color, thickness=thickness)
    cv2.line(draw_img, (x1, y1), (x1, y1 + length), corner_color, thickness=thickness)
    cv2.line(draw_img, (x2, y1), (x2 - length, y1), corner_color, thickness=thickness)
    cv2.line(draw_img, (x2, y1), (x2, y1 + length), corner_color, thickness=thickness)
    cv2.line(draw_img, (x1, y2), (x1 + length, y2), corner_color, thickness=thickness)
    cv2.line(draw_img, (x1, y2), (x1, y2 - length), corner_color, thickness=thickness)
    cv2.line(draw_img, (x2, y2), (x2 - length, y2), corner_color, thickness=thickness)
    cv2.line(draw_img, (x2, y2), (x2, y2 - length), corner_color, thickness=thickness)


def draw_label_type(draw_img, x1, y1, class_name, score=None, label_color=(97, 162, 244)):
    """绘制简洁检测标签。

    OpenCV 自带字体不支持中文，因此视频帧中仅保留克制的英文/ASCII 标签；
    中文导览信息统一交给 Qt 右侧面板显示。
    """
    label = str(class_name)
    if score is not None:
        try:
            label = f"{label} {float(score):.2f}"
        except Exception:
            pass

    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.55
    thickness = 1
    pad_x, pad_y = 7, 5
    (tw, th), base = cv2.getTextSize(label, font, font_scale, thickness)
    h, w = draw_img.shape[:2]

    bx1 = max(0, min(int(x1), w - tw - 2 * pad_x - 1))
    by2 = int(y1) - 6
    if by2 - th - 2 * pad_y < 0:
        by1 = min(h - th - 2 * pad_y - base - 1, int(y1) + 6)
        by2 = by1 + th + 2 * pad_y + base
    else:
        by1 = by2 - th - 2 * pad_y - base
    bx2 = min(w - 1, bx1 + tw + 2 * pad_x)
    by1 = max(0, by1)
    by2 = min(h - 1, by2)

    # 奶油粉标签底 + 暖橙边框，克制且亲和。
    bg_color = (241, 247, 255)    # BGR for #FFF7F1
    text_color = (49, 60, 74)     # BGR for #4A3C31
    cv2.rectangle(draw_img, (bx1, by1), (bx2, by2), bg_color, thickness=-1)
    cv2.rectangle(draw_img, (bx1, by1), (bx2, by2), label_color, thickness=1)
    cv2.putText(draw_img, label, (bx1 + pad_x, by2 - pad_y - base),
                font, font_scale, text_color, thickness=thickness, lineType=cv2.LINE_AA)


def draw(image, boxes, scores, classes, ratio, padding):
    """绘制克制的检测框。

    旧版使用巨大粉色标签和粗黑字，展示效果过于刺眼。
    这里改为暖橙边框 + 小型深色标签，中文信息仍由 Qt 面板负责。
    """
    box_color = (140, 178, 242)      # BGR: warm apricot #F2B28C
    corner_color = (229, 214, 169)  # BGR: soft blue #A9D6E5
    for box, score, cl in zip(boxes, scores, classes):
        x1, y1, x2, y2 = box
        x1 = int((x1 - padding[0]) / ratio[0])
        y1 = int((y1 - padding[1]) / ratio[1])
        x2 = int((x2 - padding[0]) / ratio[0])
        y2 = int((y2 - padding[1]) / ratio[1])

        cv2.rectangle(image, (x1, y1), (x2, y2), box_color, 2)
        draw_box_corner(image, x1, y1, x2, y2, 16, corner_color)

        # 防御性检查：类别 ID 必须在 CLASSES 范围内
        num_classes = len(CLASSES)
        cls_id = int(cl)
        if 0 <= cls_id < num_classes:
            cls_name = CLASSES[cls_id]
        else:
            cls_name = f"unknown_class_{cls_id}"
            print(f"[draw] WARNING: class_id={cls_id} out of range (CLASSES has {num_classes} entries), "
                  f"model may have more classes than current class_map. Using '{cls_name}' as fallback.")

        try:
            draw_label_type(image, x1, y1, cls_name, score, box_color)
        except Exception:
            draw_label_type(image, x1, y1, cls_name, None, box_color)


def letterbox(im, new_shape=(640, 640), color=(0, 0, 0)):
    shape = im.shape[:2]  # current shape [height, width]
    if isinstance(new_shape, int):
        new_shape = (new_shape, new_shape)

    r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])

    ratio = r, r  # width, height ratios
    new_unpad = int(round(shape[1] * r)), int(round(shape[0] * r))
    dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - \
             new_unpad[1]  # wh padding

    dw /= 2  # divide padding into 2 sides
    dh /= 2

    if shape[::-1] != new_unpad:  # resize——
        im = cv2.resize(im, new_unpad, interpolation=cv2.INTER_LINEAR)
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    im = cv2.copyMakeBorder(im, top, bottom, left, right,
                            cv2.BORDER_CONSTANT, value=color)  # add border
    # return im
    return im, ratio, (left, top)


def myFunc(rknn_lite, IMG):
    t0 = time.time()

    IMG2 = cv2.cvtColor(IMG, cv2.COLOR_BGR2RGB)
    # 等比例缩放
    IMG2, ratio, padding = letterbox(IMG2)
    # 强制放缩
    # IMG2 = cv2.resize(IMG, (IMG_SIZE, IMG_SIZE))
    IMG2 = np.expand_dims(IMG2, 0)

    t1 = time.time()

    outputs = rknn_lite.inference(inputs=[IMG2], data_format=['nhwc'])

    t2 = time.time()

    # print("oups1",len(outputs))
    # print("oups2",outputs[0].shape)

    boxes, classes, scores = yolov8_post_process(outputs)

    t3 = time.time()

    # ---- 存储结构化检测结果（不抛异常，不影响推理管线）----
    try:
        if boxes is not None and len(boxes) > 0:
            h, w = IMG.shape[:2]
            orig_boxes = []
            for box in boxes:
                x1 = int((box[0] - padding[0]) / ratio[0])
                y1 = int((box[1] - padding[1]) / ratio[1])
                x2 = int((box[2] - padding[0]) / ratio[0])
                y2 = int((box[3] - padding[1]) / ratio[1])
                orig_boxes.append([x1, y1, x2, y2])
            get_detection_store().update(orig_boxes, classes, scores, w, h)
        else:
            get_detection_store().update([], [], [], IMG.shape[1], IMG.shape[0])
    except Exception:
        pass

    if boxes is not None and DRAW_BOXES:
        draw(IMG, boxes, scores, classes, ratio, padding)

    t4 = time.time()

    # ---- 性能统计（不抛异常，不影响推理管线）----
    try:
        get_stats().record_worker(
            preprocess_ms=(t1 - t0) * 1000,
            inference_ms=(t2 - t1) * 1000,
            postprocess_ms=(t3 - t2) * 1000,
            draw_ms=(t4 - t3) * 1000,
            worker_total_ms=(t4 - t0) * 1000,
        )
    except Exception:
        pass

    return IMG

