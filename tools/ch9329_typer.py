#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ch9329_typer - 把一段文本通过 CH9329 串口模拟成 USB 键盘输入。

用法:
  python ch9329_typer.py "hello world"            # 打完即退 (默认 COM10)
  python ch9329_typer.py -c COM5 "text"           # 指定串口
  python ch9329_typer.py -f note.txt              # 从文件读
  echo text | python ch9329_typer.py              # 从管道读
  python ch9329_typer.py                          # 交互模式, 输一行打一行

依赖: pyserial + ch9329 (pip install git+https://github.com/sakar111/ch9329.git)
注意: CH9329 HID 键盘只能输入 ASCII; 中文等非 ASCII 字符会被跳过
      (除非目标机开着输入法且你想逐字母触发它)。
"""
import argparse
import sys
import time

from serial import Serial, SerialException

from ch9329 import keyboard

DEFAULT_PORT = "COM10"
BAUD = 9600  # CH9329 出厂默认波特率, 与 client/hid_def.py 一致


def check_connection(ser: Serial) -> bool:
    # 发"获取芯片信息"命令 (无按键副作用), 探测 CH9329 是否应答。
    # 注意: 很多 dongle 只接了 CH340 TX -> CH9329 RX 单向线,
    # 收不到应答不代表命令无效, 所以结果仅作提示, 不阻断发送。
    packet = b"\x57\xab\x00\x01\x00\x03"
    ser.reset_input_buffer()
    ser.write(packet)
    resp = ser.readline()
    return resp[:4] == b"\x57\xab\x00\x81"


def type_text(ser: Serial, text: str, interval: float):
    skipped = set()
    for ch in text:
        if ch == "\r":
            continue  # CRLF 里只发一次回车
        if ord(ch) > 127:
            skipped.add(ch)
            continue
        keyboard.press_and_release(ser, ch)
        time.sleep(interval)
    return skipped


def repl(ser: Serial, interval: float):
    print("交互模式: 每输入一行并回车, 就把该行打到目标机 (自动补回车)。")
    print("退出: Ctrl+C")
    while True:
        try:
            line = input("type> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        type_text(ser, line + "\n", interval)


def main():
    parser = argparse.ArgumentParser(
        description="通过 CH9329 串口把文本模拟成 USB 键盘输入",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("text", nargs="*", help="要输入的文本 (不加则读 stdin/交互)")
    parser.add_argument("-c", "--com", default=DEFAULT_PORT, help=f"串口号 (默认 {DEFAULT_PORT})")
    parser.add_argument("-f", "--file", help="从文件读取文本")
    parser.add_argument("-i", "--interval", type=float, default=0.08,
                        help="每个字符间隔秒数 (默认 0.08, 打字出现重复字符时调大)")
    args = parser.parse_args()

    if args.file:
        with open(args.file, "r", encoding="utf-8-sig") as f:
            text = f.read()
    elif args.text:
        text = " ".join(args.text)
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        text = None  # 交互模式

    try:
        ser = Serial(args.com, BAUD, timeout=0.05)
    except SerialException as e:
        print(f"[错误] 无法打开 {args.com}: {e}", file=sys.stderr)
        print("请检查端口号 (设备管理器 -> 端口) 或换 -c 参数指定。", file=sys.stderr)
        sys.exit(1)

    try:
        if check_connection(ser):
            print(f"[OK] {args.com} 上的 CH9329 已应答。3 秒后开始输入...")
        else:
            print(f"[警告] {args.com} 无 CH9329 应答, 仍尝试发送。3 秒后开始...", file=sys.stderr)
        time.sleep(3)  # 给用户切到目标机窗口的时间

        if text is None:
            repl(ser, args.interval)
        else:
            skipped = type_text(ser, text, args.interval)
            if skipped:
                print(f"[提示] 已跳过非 ASCII 字符: {''.join(sorted(skipped))}", file=sys.stderr)
            print(f"[完成] 共发送 {len(text)} 个字符。")
    finally:
        keyboard.release(ser)  # 确保没有按键卡住
        ser.close()


if __name__ == "__main__":
    main()
