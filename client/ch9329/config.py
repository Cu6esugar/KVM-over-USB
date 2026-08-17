from __future__ import annotations

import time

from serial import Serial

from ch9329.utils import get_packet

HEAD = b"\x57\xab"
ADDR = b"\x00"

CMD_GET_INFO = 0x01
CMD_GET_USB_STRING = 0x0A
CMD_SET_USB_STRING = 0x0B


def _transact(ser: Serial, cmd: int, length: int, data: bytes,
              read_len: int = 64, settle: float = 0.3) -> bytes:
    packet = get_packet(HEAD, ADDR, bytes([cmd]), bytes([length]), data)
    ser.reset_input_buffer()
    ser.write(packet)
    time.sleep(settle)
    return ser.read(read_len)


def _transact_retry(ser: Serial, cmd: int, length: int, data: bytes,
                    expect_cmd: int, tries: int = 3) -> bytes:
    # 设备偶发回校验错包(0xEx), 重试几次
    for _ in range(tries):
        resp = _transact(ser, cmd, length, data)
        if len(resp) >= 4 and resp[3] == expect_cmd:
            return resp
    return resp


def _parse_usb_string(resp: bytes) -> str:
    if len(resp) < 7:
        return ""
    # 回包: 57 ab 00 8a LEN [子命令 字符串长度 字符串...] SUM
    str_len = resp[6]
    return resp[7 : 7 + str_len].decode("utf-8", "ignore")


def get_product(ser: Serial) -> str:
    # GET_USB_STRING, 子命令 0x01 = 产品字符串
    return _parse_usb_string(
        _transact_retry(ser, CMD_GET_USB_STRING, 0x01, b"\x01", 0x8A)
    )


def get_serial_number(ser: Serial) -> str:
    # GET_USB_STRING, 子命令 0x02 = 序列号字符串
    return _parse_usb_string(
        _transact_retry(ser, CMD_GET_USB_STRING, 0x01, b"\x02", 0x8A)
    )
