'''
@作者: weimo
@创建日期: 2020-03-26 19:17:52
@上次编辑时间: 2020-05-13 19:48:29
@一个人的命运啊,当然要靠自我奋斗,但是...
'''
import cv2
import numpy as np
from pathlib import Path

from util.calc import get_white_ratio
from logs.logger import get_logger

ratio_logger = get_logger(Path(r"logs\frame_white_ratio.log"))

MIN_SPACE = 300
MAX_HEIGHT = 60

def draw_box(img: np.ndarray, bboxes: list, title="+_+"):
    print(bboxes)
    img_bak = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
    for x, y, w, h in bboxes:
        cv2.rectangle(img_bak, (x, y), (x + w, y + h), (255, 255, 0), 2)
    cv2.imshow(f"{title}_{len(bboxes)}_boxes", img_bak)
    # cv2.waitKey(0)

def get_box_weight(bboxes, half_width):
    left_boxes = [half_width - (x + w / 2) for x, y, w, h in bboxes if x + w / 2 < half_width]
    if len(left_boxes) == 0:
        return 0, 0
    left_weight = sum(left_boxes) / len(left_boxes)
    right_boxes = [x + w / 2 - half_width for x, y, w, h in bboxes if x + w / 2 > half_width]
    if len(right_boxes) == 0:
        return 0, 0
    right_weight = sum(right_boxes) / len(right_boxes)
    return left_weight, right_weight

def filter_extreme_box(bboxes, half_width):
    # 通过box位置分布去除异常box
    data = [x if x + w / 2 < half_width else x + w for x, y, w, h in bboxes]
    target_max = half_width + 2 * np.std(data)
    target_min = half_width - 2 * np.std(data)
    # print(data, target_max, target_min, np.std(data))
    # 过滤处理一些box
    bboxes = [(x, y, w, h) for index, (x, y, w, h) in enumerate(bboxes) if x >= target_min and x + w <= target_max]
    # 检查box是否平衡
    left_weight, right_weight = get_box_weight(bboxes, half_width)
    # print(len(bboxes), left_weight, right_weight)
    if left_weight > right_weight * 1.5:
        while left_weight > right_weight * 1.5:
            rindex = None
            minxw = half_width
            for index, (x, y, w, h) in enumerate(bboxes):
                if x + w / 2 < minxw:
                    minxw = x + w / 2
                    rindex = index
            bboxes = [box for index, box in enumerate(bboxes) if index != rindex]
            left_weight, right_weight = get_box_weight(bboxes, half_width)
    if right_weight > left_weight * 1.5:
        while right_weight > left_weight * 1.5:
            rindex = None
            maxyh = half_width
            for index, (x, y, w, h) in enumerate(bboxes):
                if x + w / 2 > maxyh:
                    minxw = x + w / 2
                    rindex = index
            bboxes = [box for index, box in enumerate(bboxes) if index != rindex]
            left_weight, right_weight = get_box_weight(bboxes, half_width)
    # print("___+++____", len(bboxes), left_weight, right_weight)
    return bboxes

def filter_box(bboxes: np.ndarray, img: np.ndarray, half_width: float):
    if bboxes.__len__() == 0:
        return bboxes, (0, 0, 0, 0), 0
    # 按x位置对box从左到右排序
    bboxes = sorted(bboxes, key=lambda box: box[0])
    # print(bboxes)
    # draw_box(img, bboxes, title="MSER")
    # 两个box相交 那么合并这两个box 注意box已经按x大小排序过了的
    _bboxes = [bboxes[0]]
    box_x, box_y, box_w, box_h = bboxes[0]
    for x, y, w, h in bboxes[1:]:
        if x >= box_x and x <= box_x + box_w:
            if y + h >= box_y and y + h <= box_y + box_h:
                box = [box_x, min(box_y, y), max(x + w, box_x + box_w) - box_x, box_y + box_h - min(box_y, y)]
                box_x, box_y, box_w, box_h = box
                _bboxes[-1] = box
            elif y >= box_y and y <= box_y + box_h:
                box = [box_x, box_y, max(x + w, box_x + box_w) - box_x, max(y + h, box_y + box_h) - box_y]
                box_x, box_y, box_w, box_h = box
                _bboxes[-1] = box
            else:
                # 说明这个box虽然在x方向与目标box有交集 在y方向没有 舍弃
                pass
        else:
            box_x, box_y, box_w, box_h = x, y, w, h
            _bboxes.append([x, y, w, h])
    # print(_bboxes)
    # draw_box(img, _bboxes, title="MSER_CONCAT")
    if len(_bboxes) > 1:
        # 只有一个box不需要进行这一步判断
        bboxes = filter_extreme_box(_bboxes, half_width)
        # draw_box(img, bboxes, title="MSER_RM_EXTREME")
    else:
        bboxes = _bboxes
    xs, ys, ws, hs, _xs, _wh = [], [], [], [], [], []
    _ = [(xs.append(x), ys.append(y), ws.append(x + w), hs.append(y + h), _xs.append([x, x + w]), _wh.append(w / h)) for x, y, w, h in bboxes]
    # 对称性判断 有的字幕不一定对称 暂时不加这个
    data_distances = [(((x + w) / 2) - half_width) / half_width for x, w in zip(xs, ws)]
    if data_distances.__len__() > 2:
        # 全部在一边 也认为是没有字幕的
        _data_distances = np.array(data_distances, dtype="float64")
        zero_reduce = _data_distances[_data_distances < 0].shape[0]
        zero_plus = _data_distances[_data_distances > 0].shape[0]
        if zero_plus == 0 or zero_reduce == 0:
            return (), (0, 0, 0, 0), 0
    # 很近的时候就不用加入了
    # data_distances = [abs(_) for _ in data_distances if abs(_) > 0.1]
    # if data_distances.__len__() > 1:
    #     max_distance = np.median(data_distances) * 1.5
    #     # print(f"data_distances -> {data_distances} max_distance -> {max_distance}")
    #     remove_indices = [index for index, distance in enumerate(data_distances) if distance > max_distance or _wh[index] > 4]
    #     bboxes = [box for index, box in enumerate(bboxes) if index not in remove_indices]
    if bboxes.__len__() == 0:
        return bboxes, (0, 0, 0, 0), 0
    if bboxes.__len__() == 1:
        max_space = 0
    if bboxes.__len__() > 1:
        # 只有大于1个box这样做才有意义
        xs, ys, ws, hs, _xs = [], [], [], [], []
        _ = [(xs.append(x), ys.append(y), ws.append(x + w), hs.append(y + h), _xs.append([x, x + w])) for x, y, w, h in bboxes]
        _xs = sorted(_xs, key=lambda x: x[0])
        max_space = max([_xs[i][0] - _xs[i - 1][1] for i in range(1, _xs.__len__())])
    return bboxes, (xs, ys, ws, hs), max_space

def get_mser(img: np.ndarray, frame_index: int, shape: tuple, min_area=100, isbase: bool = False):
    height, width, channels = shape # 注意这里的frame是彩色的
    half_width = width / 2
    # print(height, width)
    mser = cv2.MSER_create(_min_area=min_area)
    img = cv2.dilate(img, cv2.getStructuringElement(cv2.MORPH_RECT, (4, 4)))
    regions, bboxes = mser.detectRegions(img)
    
    # 给定一个字符最小的高度和宽度 排除比这小的box
    bboxes = [[x, y, w, h] for x, y, w, h in bboxes if w > 10 and h > 10 and (w * h) / (width * height) < 0.8]
    draw_box(img.copy(), bboxes)
    if bboxes.__len__() == 0:
        print(f"{frame_index} box is zero before filter box")
        return "no subtitle"
    bboxes, (xs, ys, ws, hs), max_space = filter_box(bboxes, img.copy(), half_width)
    if bboxes.__len__() == 0:
        print(f"{frame_index} box is zero after filter box")
        return "no subtitle"
    elif bboxes.__len__() == 1:
        if min(xs) < half_width and max(ws) > half_width:
            pass
        else:
            print(f"{frame_index} bboxes 不居中")
            return "no subtitle"
    elif bboxes.__len__() > 1 and max_space > MIN_SPACE:
        print(f"{frame_index} 间隔太远 不符合字幕的特征 {max_space} {xs} {ws}")
        return "no subtitle"
    # 高度占比过低 不符合字幕特征
    if (max(hs) - min(ys)) / MAX_HEIGHT < 0.2:
        print(f"{frame_index} 高度占比过低 不符合字幕特征")
        return "no subtitle"
    if isbase and min(xs) - 5 > 0 and min(ys) - 5 > 0 and max(ws) + 5 < width and max(hs) + 5 < height:
        x, y, w, h = min(xs) - 5, min(ys) - 5, max(ws) + 5, max(hs) + 5
    else:
        x, y, w, h = min(xs), min(ys), max(ws), max(hs)
    white_ratio = get_white_ratio(img[y:h, x:w])
    ratio_logger.info(f"{frame_index:>5} {white_ratio:>5.2f}")
    if white_ratio < 0.2:
        return "no subtitle"
    # 注意这里返回的w和h已经是实际坐标了
    return x, y, w, h