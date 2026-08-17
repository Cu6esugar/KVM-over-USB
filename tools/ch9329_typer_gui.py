#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CH9329 键盘文本发送器 - GUI 版。

一个端口选择下拉 (自动定位 CH340), 一个多行输入框, 传输/停止按钮。
点击"传输"后把输入框内容逐字符通过 CH9329 模拟键盘打到目标机。
本机打字/拷贝进输入框即可, 键盘事件只发往 CH9329 所插的目标机。

依赖: pyserial + ch9329 (pip install git+https://github.com/sakar111/ch9329.git)
运行: py -3.12 ch9329_typer_gui.py
"""
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

from serial import Serial, SerialException
from serial.tools import list_ports

from ch9329 import keyboard

BAUD = 9600  # CH9329 出厂默认, 与 client/hid_def.py 一致
TYPE_INTERVAL = 0.08  # 每字符间隔, 出现重复字符时调大


def list_com_ports():
    """返回 [(port, description)], CH340 排最前并标注。"""
    ports = list_ports.comports()
    items = []
    ch340 = []
    for p in ports:
        name = f"{p.device}  -  {p.description}"
        if p.vid == 0x1A86:  # 沁恒 wch (CH340/CH341)
            ch340.append((p.device, name))
        else:
            items.append((p.device, name))
    # CH340 放最前作为默认项, 其余按端口号排序
    items.sort(key=lambda x: x[0])
    return ch340 + items, (ch340[0][0] if ch340 else None)


class TyperApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.ser = None
        self.stop_flag = threading.Event()
        self.worker = None

        root.title("CH9329 键盘文本发送器")
        root.geometry("520x360")
        root.minsize(420, 280)

        main = ttk.Frame(root, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        # ---- 端口选择 ----
        port_row = ttk.Frame(main)
        port_row.pack(fill=tk.X)
        ttk.Label(port_row, text="串口:").pack(side=tk.LEFT)
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(
            port_row, textvariable=self.port_var, state="readonly", width=30
        )
        self.port_combo.pack(side=tk.LEFT, padx=6)
        ttk.Button(port_row, text="刷新", command=self.refresh_ports).pack(side=tk.LEFT)

        # ---- 文本输入 ----
        self.text = tk.Text(main, wrap=tk.CHAR, undo=True)
        self.text.pack(fill=tk.BOTH, expand=True, pady=8)
        self.text.insert("1.0", "在这里输入或粘贴文本...")

        # ---- 按钮 + 状态 ----
        btn_row = ttk.Frame(main)
        btn_row.pack(fill=tk.X)
        self.send_btn = ttk.Button(btn_row, text="传输", command=self.on_send)
        self.send_btn.pack(side=tk.LEFT)
        self.stop_btn = ttk.Button(
            btn_row, text="停止", command=self.on_stop, state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.LEFT, padx=6)
        self.status_var = tk.StringVar(value="就绪。选择串口, 输入文本, 点\"传输\"。")
        ttk.Label(main, textvariable=self.status_var, anchor=tk.W).pack(fill=tk.X, pady=(6, 0))

        self.refresh_ports()

    # ---------- 端口 ----------
    def refresh_ports(self):
        items, ch340_port = list_com_ports()
        display = [name for _, name in items]
        self.port_combo["values"] = display
        if display:
            # 默认选 CH340 (列表第一项), 否则选第一项
            self.port_combo.current(0)
        else:
            self.port_var.set("")
            self.status_var.set("未找到串口设备, 请插入 CH340 后点\"刷新\"。")

    def get_selected_port(self):
        name = self.port_var.get()
        if not name:
            return None
        return name.split("  -  ")[0].strip()

    # ---------- 传输 ----------
    def on_send(self):
        if self.worker and self.worker.is_alive():
            return
        port = self.get_selected_port()
        if not port:
            messagebox.showerror("错误", "请先选择串口。")
            return
        text = self.text.get("1.0", tk.END).rstrip("\n")
        if not text:
            messagebox.showwarning("提示", "输入框为空。")
            return

        try:
            self.ser = Serial(port, BAUD, timeout=0.05)
        except SerialException as e:
            messagebox.showerror("错误", f"无法打开 {port}:\n{e}")
            return

        self.stop_flag.clear()
        self.send_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_var.set(f"3 秒后开始输入, 请切到目标机窗口...")
        self.worker = threading.Thread(
            target=self.type_worker, args=(port, text), daemon=True
        )
        self.worker.start()

    def type_worker(self, port: str, text: str):
        skipped = set()
        total = len(text)
        try:
            time.sleep(3)  # 切窗口缓冲
            for i, ch in enumerate(text):
                if self.stop_flag.is_set():
                    break
                if ord(ch) > 127:
                    skipped.add(ch)
                    continue
                if ch == "\r":
                    continue
                keyboard.press_and_release(self.ser, ch)
                if i % 20 == 0:
                    self.status_var.set(f"输入中... {i}/{total}")
                time.sleep(TYPE_INTERVAL)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("错误", f"发送失败:\n{e}"))
        finally:
            try:
                keyboard.release(self.ser)  # 松开所有键, 防卡键
                self.ser.close()
            except Exception:
                pass
            done = "已停止" if self.stop_flag.is_set() else "完成"
            skipped_msg = (
                f"\n跳过非 ASCII 字符: {''.join(sorted(skipped))}" if skipped else ""
            )
            self.root.after(
                0,
                lambda: self.on_finished(done, skipped_msg),
            )

    def on_finished(self, done: str, skipped_msg: str):
        self.send_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_var.set(done + skipped_msg)

    def on_stop(self):
        self.stop_flag.set()
        self.status_var.set("正在停止...")


def main():
    root = tk.Tk()
    TyperApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
