from __future__ import annotations

HEAD = b"\x57\xab"  # Frame header
ADDR = b"\x00"  # Address


def get_packet(
    head: bytes, addr: bytes, cmd: bytes, length: bytes, data: bytes
) -> bytes:
    # CH9329 校验和 = 帧头+地址+命令+长度+数据 之和的低 8 位
    checksum = (
        sum(head) + sum(addr) + sum(cmd) + sum(length) + sum(data)
    ) % 256
    return head + addr + cmd + length + data + bytes([checksum])
