from __future__ import annotations

import random
import time

from serial import Serial

from ch9329.utils import get_packet

HEAD = b"\x57\xab"
ADDR = b"\x00"
CMD_ABS = b"\x04"  # 鼠标绝对移动
CMD_REL = b"\x05"  # 鼠标相对移动
LEN_ABS = b"\x07"
LEN_REL = b"\x05"

BUTTONS = {
    "null": 0x00, "none": 0x00, "": 0x00,
    "left": 0x01,
    "right": 0x02,
    "center": 0x04, "middle": 0x04,
}


def _button_value(button: str) -> int:
    if button not in BUTTONS:
        raise ValueError(f"unknown mouse button: {button!r}")
    return BUTTONS[button]


def send_data_absolute(
    ser: Serial, x: int, y: int, ctrl: str = "null",
    x_max: int = 1920, y_max: int = 1080,
) -> None:
    x_cur = (4096 * x) // x_max
    y_cur = (4096 * y) // y_max
    data = (
        b"\x02"
        + bytes([_button_value(ctrl)])
        + x_cur.to_bytes(2, "little")
        + y_cur.to_bytes(2, "little")
        + b"\x00"  # 滚轮
    )
    ser.write(get_packet(HEAD, ADDR, CMD_ABS, LEN_ABS, data))


def send_data_relative(
    ser: Serial, x: int, y: int, ctrl: str = "null",
) -> None:
    data = (
        b"\x01"
        + bytes([_button_value(ctrl)])
        + int(x).to_bytes(1, "big", signed=True)
        + int(y).to_bytes(1, "big", signed=True)
        + b"\x00"  # 滚轮
    )
    ser.write(get_packet(HEAD, ADDR, CMD_REL, LEN_REL, data))


def _send_relative_with_wheel(ser: Serial, wheel_value: int) -> None:
    data = (
        b"\x01" + b"\x00"
        + b"\x00" + b"\x00"
        + int(wheel_value).to_bytes(1, "big", signed=True)
    )
    ser.write(get_packet(HEAD, ADDR, CMD_REL, LEN_REL, data))


def send_absolute_state(
    ser: Serial, x: int, y: int, button_bits: int = 0,
    x_max: int = 1920, y_max: int = 1080, wheel: int = 0,
) -> None:
    # 状态帧: 按键位图(1左2右4中, HID位序)+坐标+滚轮同帧携带, 支持按住拖动
    x_cur = (4096 * x) // x_max
    y_cur = (4096 * y) // y_max
    data = (
        b"\x02"
        + bytes([button_bits & 0x07])
        + x_cur.to_bytes(2, "little")
        + y_cur.to_bytes(2, "little")
        + int(wheel).to_bytes(1, "big", signed=True)
    )
    ser.write(get_packet(HEAD, ADDR, CMD_ABS, LEN_ABS, data))


def send_relative_state(
    ser: Serial, dx: int, dy: int, button_bits: int = 0, wheel: int = 0,
) -> None:
    data = (
        b"\x01"
        + bytes([button_bits & 0x07])
        + int(dx).to_bytes(1, "big", signed=True)
        + int(dy).to_bytes(1, "big", signed=True)
        + int(wheel).to_bytes(1, "big", signed=True)
    )
    ser.write(get_packet(HEAD, ADDR, CMD_REL, LEN_REL, data))


def move(
    ser: Serial, x: int, y: int, relative: bool = False,
    monitor_width: int = 1920, monitor_height: int = 1080,
) -> None:
    if relative:
        send_data_relative(ser, x, y, "null")
    else:
        send_data_absolute(ser, x, y, "null", monitor_width, monitor_height)


def press(ser: Serial, button: str = "left") -> None:
    # 用相对零位移状态帧: 按钮在当前位置按下, 不移动光标。
    # (旧版用绝对坐标(0,0)会把手柄光标甩到左上角, Ubuntu/相对模式下点击失效)
    send_relative_state(ser, 0, 0, BUTTONS.get(button, 0))


def release(ser: Serial) -> None:
    send_relative_state(ser, 0, 0, 0)


def click(ser: Serial, button: str = "left") -> None:
    press(ser, button)
    time.sleep(random.uniform(0.1, 0.45))
    release(ser)


def wheel(ser: Serial, value: int = 1) -> None:
    # 1=向上滚, -1=向下滚
    _send_relative_with_wheel(ser, value)
