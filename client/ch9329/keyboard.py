from __future__ import annotations

import time

from serial import Serial

from ch9329.exceptions import InvalidKeyException, InvalidModifier
from ch9329.utils import get_packet

HEAD = b"\x57\xab"
ADDR = b"\x00"
CMD = b"\x02"  # 键盘普通数据
LEN = b"\x08"

# 修饰键名 -> HID 位码 (bit0=左ctrl, 1=左shift, 2=左alt, 3=左win,
#                     bit4=右ctrl, 5=右shift, 6=右alt, 7=右win)
MODIFIERS = {
    "ctrl": 0x01, "control": 0x01, "ctrl_left": 0x01, "control_left": 0x01,
    "shift": 0x02, "shift_left": 0x02,
    "alt": 0x04, "alt_left": 0x04,
    "lwin": 0x08, "win": 0x08, "win_left": 0x08, "gui_left": 0x08, "meta": 0x08,
    "ctrl_right": 0x10, "control_right": 0x10,
    "shift_right": 0x20,
    "alt_right": 0x40,
    "rwin": 0x80, "win_right": 0x80, "gui_right": 0x80,
}

# HID 键码表: 键名 -> HID usage id (十进制)
KEY_CODES = {
    "a": 4, "b": 5, "c": 6, "d": 7, "e": 8, "f": 9, "g": 10, "h": 11,
    "i": 12, "j": 13, "k": 14, "l": 15, "m": 16, "n": 17, "o": 18,
    "p": 19, "q": 20, "r": 21, "s": 22, "t": 23, "u": 24, "v": 25,
    "w": 26, "x": 27, "y": 28, "z": 29,
    "1": 30, "2": 31, "3": 32, "4": 33, "5": 34,
    "6": 35, "7": 36, "8": 37, "9": 38, "0": 39,
    "enter": 40, "return": 40, "esc": 41, "escape": 41, "backspace": 42,
    "tab": 43, "space": 44,
    "-": 45, "=": 46, "[": 47, "bracket_left": 47,
    "]": 48, "bracket_right": 48, "\\": 49, "backslash": 49,
    ";": 51, "semicolon": 51, "'": 52, "apostrophe": 52,
    "`": 53, "grave": 53,
    ",": 54, "comma": 54, ".": 55, "period": 55, "/": 56, "slash": 56,
    "caps_lock": 57, "capslock": 57,
    "f1": 58, "f2": 59, "f3": 60, "f4": 61, "f5": 62, "f6": 63,
    "f7": 64, "f8": 65, "f9": 66, "f10": 67, "f11": 68, "f12": 69,
    "printscreen": 70, "print_screen": 70, "printscreen": 70, "sysreq": 70,
    "scrolllock": 71, "scroll_lock": 71,
    "pause": 72,
    "insert": 73, "home": 74, "pageup": 75, "page_up": 75,
    "delete": 76, "del": 76, "end": 77, "pagedown": 78, "page_down": 78,
    "right": 79, "arrow_right": 79, "left": 80, "arrow_left": 80,
    "down": 81, "arrow_down": 81, "up": 82, "arrow_up": 82,
    "num_lock": 83, "numlock": 83,
}

# ASCII 可打印字符 -> (需shift, 键名); 大写字母转小写+shift
_ASCII_MAP = {" ": (False, "space"), "space": (False, "space")}
for _c in range(0x20, 0x7F):
    _ch = chr(_c)
    if _ch.isalpha():
        _ASCII_MAP[_ch.lower()] = (False, _ch.lower())
        _ASCII_MAP[_ch.upper()] = (True, _ch.lower())
    else:
        _ASCII_MAP[_ch] = (False, _ch)
_SHIFT_SYMBOLS = {
    ")": "0", "!": "1", "@": "2", "#": "3", "$": "4", "%": "5",
    "^": "6", "&": "7", "*": "8", "(": "9",
    "~": "`", "_": "-", "+": "=", "{": "[", "}": "]", "|": "\\",
    ":": ";", '"': "'", "<": ",", ">": ".", "?": "/",
}
for _sym, _base in _SHIFT_SYMBOLS.items():
    _ASCII_MAP[_sym] = (True, _base)
_ASCII_MAP["\n"] = (False, "enter")
_ASCII_MAP["\r"] = (False, "enter")
_ASCII_MAP["\t"] = (False, "tab")
_ASCII_MAP[" "] = (False, "space")  # 覆盖循环里的默认项


def _resolve_key(key: str):
    """键名/字符 -> (shift布尔, HID键码); 找不到抛 InvalidKeyException"""
    if key in KEY_CODES:
        return False, KEY_CODES[key]
    if key in _ASCII_MAP:
        shift, name = _ASCII_MAP[key]
        return shift, KEY_CODES[name]
    if len(key) == 1 and key.lower() in _ASCII_MAP and key != key.lower():
        pass
    raise InvalidKeyException(f"unknown key: {key!r}")


def _resolve_modifiers(modifiers) -> int:
    mods = modifiers if isinstance(modifiers, (list, tuple)) else [modifiers]
    value = 0
    for m in mods:
        if m is None or m == "" or m == "null":
            continue
        if m not in MODIFIERS:
            raise InvalidModifier(f"unknown modifier: {m!r}")
        value |= MODIFIERS[m]
    return value


def send(ser: Serial, key: str = "", modifiers=None) -> None:
    # modifiers 可以是单个字符串或列表 (hid_def.py 传列表)
    # CH9329 键盘帧数据固定 8 字节: [修饰键位图][保留0][键码x6]
    mod_value = _resolve_modifiers(modifiers if modifiers is not None else [])
    keycode = 0
    if key:
        try:
            shift, keycode = _resolve_key(key)
        except InvalidKeyException:
            return  # 未知键名: 跳过, 不打断调用方
        if shift:
            mod_value |= 0x02
    data = bytes([mod_value, 0x00, keycode]) + b"\x00" * 5
    packet = get_packet(HEAD, ADDR, CMD, LEN, data)
    ser.write(packet)


def send_hid_state(ser: Serial, modifier_bits: int = 0, keycodes=None) -> None:
    # 直接发送 HID 键盘状态帧 (与真实键盘语义一致):
    # 按住=状态保持(目标机自动重复), 松开=从状态中移除, 不做动作翻译
    keys = [k & 0xFF for k in (keycodes or []) if k][:6]
    data = bytes([modifier_bits & 0xFF, 0x00] + keys + [0x00] * (6 - len(keys)))
    packet = get_packet(HEAD, ADDR, CMD, LEN, data)
    ser.write(packet)


def press(ser: Serial, key: str, modifiers=None) -> None:
    send(ser, key, modifiers)


def release(ser: Serial) -> None:
    send(ser, "")


def press_and_release(ser: Serial, key: str, modifiers=None) -> None:
    # hid_def.py 的调用形式: keyboard.press_and_release(K_M, keyname, function_keys)
    press(ser, key, modifiers)
    time.sleep(0.01)
    release(ser)


def write(ser: Serial, text: str, interval: float = 0.1) -> None:
    for char in text:
        press_and_release(ser, char)
        time.sleep(interval)
