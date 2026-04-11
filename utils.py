"""
utils.py - Các hàm tiện ích phụ trợ
====================================
Cung cấp các hàm tính toán khoảng cách, góc, và các utility dùng chung.
"""

import math
import numpy as np


def calculate_distance(point1, point2):
    """
    Tính khoảng cách Euclidean giữa 2 điểm trong không gian 2D.

    Args:
        point1: Tuple (x, y) - điểm thứ nhất
        point2: Tuple (x, y) - điểm thứ hai

    Returns:
        float: Khoảng cách giữa 2 điểm (pixels)

    Example:
        >>> calculate_distance((100, 200), (150, 250))
        70.71...
    """
    return math.sqrt((point1[0] - point2[0]) ** 2 +
                     (point1[1] - point2[1]) ** 2)


def calculate_angle(point1, point2, point3):
    """
    Tính góc tại point2 tạo bởi 3 điểm (đơn vị: độ).

    Sử dụng công thức:
        angle = arctan2(y3-y2, x3-x2) - arctan2(y1-y2, x1-x2)

    Args:
        point1: Tuple (x, y) - điểm đầu
        point2: Tuple (x, y) - điểm đỉnh (vertex)
        point3: Tuple (x, y) - điểm cuối

    Returns:
        float: Góc tại point2 (0° - 360°)
    """
    angle = math.degrees(
        math.atan2(point3[1] - point2[1], point3[0] - point2[0]) -
        math.atan2(point1[1] - point2[1], point1[0] - point2[0])
    )

    # Chuẩn hóa góc về khoảng [0, 360)
    if angle < 0:
        angle += 360

    return angle


def calculate_midpoint(point1, point2):
    """
    Tính điểm giữa (midpoint) của 2 điểm.

    Args:
        point1: Tuple (x, y)
        point2: Tuple (x, y)

    Returns:
        Tuple (int, int): Tọa độ điểm giữa
    """
    return (
        (point1[0] + point2[0]) // 2,
        (point1[1] + point2[1]) // 2
    )


def map_range(value, in_min, in_max, out_min, out_max):
    """
    Ánh xạ một giá trị từ khoảng đầu vào sang khoảng đầu ra.
    Sử dụng np.interp cho việc chuyển tọa độ camera -> màn hình.

    Args:
        value: Giá trị cần ánh xạ
        in_min: Giá trị nhỏ nhất khoảng đầu vào
        in_max: Giá trị lớn nhất khoảng đầu vào
        out_min: Giá trị nhỏ nhất khoảng đầu ra
        out_max: Giá trị lớn nhất khoảng đầu ra

    Returns:
        float: Giá trị đã ánh xạ sang khoảng đầu ra

    Example:
        # Map tọa độ X từ camera (100-540) sang màn hình (0-1920)
        >>> map_range(320, 100, 540, 0, 1920)
        960.0
    """
    return np.interp(value, [in_min, in_max], [out_min, out_max])


def clamp(value, min_val, max_val):
    """
    Giới hạn giá trị trong khoảng [min_val, max_val].

    Args:
        value: Giá trị cần giới hạn
        min_val: Giá trị tối thiểu
        max_val: Giá trị tối đa

    Returns:
        Giá trị đã được giới hạn
    """
    return max(min_val, min(value, max_val))


def smooth_value(current, target, factor):
    """
    Làm mượt giá trị bằng phương pháp nội suy tuyến tính (linear interpolation).

    Công thức: new_value = current + (target - current) / factor

    Factor càng lớn -> chuyển động càng mượt nhưng phản hồi chậm hơn.

    Args:
        current: Giá trị hiện tại
        target: Giá trị đích
        factor: Hệ số làm mượt (>= 1)

    Returns:
        float: Giá trị đã được làm mượt
    """
    if factor <= 0:
        return target
    return current + (target - current) / factor


def is_point_in_roi(x, y, roi_x_min, roi_y_min, roi_x_max, roi_y_max):
    """
    Kiểm tra xem một điểm có nằm trong vùng ROI không.

    Args:
        x, y: Tọa độ điểm cần kiểm tra
        roi_x_min, roi_y_min: Góc trên-trái ROI
        roi_x_max, roi_y_max: Góc dưới-phải ROI

    Returns:
        bool: True nếu điểm nằm trong ROI
    """
    return roi_x_min <= x <= roi_x_max and roi_y_min <= y <= roi_y_max


def moving_average(values, window_size):
    """
    Tính trung bình trượt (moving average) cho một chuỗi giá trị.
    Dùng để làm mượt chuỗi tọa độ theo thời gian.

    Args:
        values: List các giá trị
        window_size: Kích thước cửa sổ trung bình

    Returns:
        float: Giá trị trung bình của window_size phần tử cuối cùng
    """
    if not values:
        return 0

    window = values[-window_size:]
    return sum(window) / len(window)


# ==============================================================================
# CÁC HÀM BỔ SUNG (theo review feedback)
# ==============================================================================

def normalize_distance(distance, palm_size):
    """
    Chuẩn hóa khoảng cách pixel theo kích thước bàn tay (palm_size).
    Giúp threshold ổn định khi tay gần/xa webcam.

    Công thức: normalized = distance / palm_size
    Khi palm_size thay đổi (tay xa/gần), khoảng cách chuẩn hóa
    vẫn giữ nguyên tỷ lệ -> threshold nhất quán.

    Args:
        distance: Khoảng cách pixel giữa 2 điểm
        palm_size: Kích thước bàn tay (pixel), từ HandDetector.get_palm_size()

    Returns:
        float: Khoảng cách chuẩn hóa (thường trong khoảng 0.0 - 1.0)
               Trả về distance gốc nếu palm_size = 0 (fallback)
    """
    if palm_size <= 0:
        return distance
    return distance / palm_size


def smooth_point(prev_x, prev_y, target_x, target_y, factor):
    """
    Làm mượt tọa độ 2D (x, y) bằng nội suy tuyến tính.
    Wrapper tiện lợi cho smooth_value() áp dụng lên cả 2 trục.

    Args:
        prev_x, prev_y: Tọa độ trước đó
        target_x, target_y: Tọa độ đích
        factor: Hệ số làm mượt (>= 1)

    Returns:
        Tuple (float, float): Tọa độ đã làm mượt
    """
    new_x = smooth_value(prev_x, target_x, factor)
    new_y = smooth_value(prev_y, target_y, factor)
    return (new_x, new_y)


def cooldown_passed(last_time, cooldown_duration, current_time=None):
    """
    Kiểm tra xem đã qua thời gian cooldown chưa.
    Dùng cho debounce click, scroll, zoom, v.v.

    Args:
        last_time: Thời điểm lần cuối action được thực hiện (time.time())
        cooldown_duration: Thời gian cooldown cần chờ (giây)
        current_time: Thời điểm hiện tại (mặc định = None -> tự lấy time.time())

    Returns:
        bool: True nếu đã qua cooldown, False nếu chưa
    """
    import time
    if current_time is None:
        current_time = time.time()
    return (current_time - last_time) >= cooldown_duration


def calculate_velocity(prev_point, current_point, dt=1.0):
    """
    Tính vận tốc di chuyển giữa 2 frame (pixels/frame hoặc pixels/giây).
    Dùng cho velocity-based scroll, swipe detection.

    Args:
        prev_point: Tuple (x, y) vị trí frame trước
        current_point: Tuple (x, y) vị trí frame hiện tại
        dt: Delta time giữa 2 frame (giây). Mặc định 1.0 = tính per-frame.

    Returns:
        Tuple (vx, vy, speed):
            vx: Vận tốc theo trục X
            vy: Vận tốc theo trục Y
            speed: Tốc độ tổng (magnitude)
    """
    if prev_point is None or current_point is None:
        return (0.0, 0.0, 0.0)

    dx = current_point[0] - prev_point[0]
    dy = current_point[1] - prev_point[1]

    if dt <= 0:
        dt = 1.0

    vx = dx / dt
    vy = dy / dt
    speed = math.sqrt(vx ** 2 + vy ** 2)

    return (vx, vy, speed)
