# KVM over USB 现场支持方案
基于市售容易获得的HDMI采集卡和HID模拟芯片，搭建出的KVM over USB方案，方便现场支持搭建和试用

## 简介
这个项目是沿着这三位老哥走的路，整合出了一个 【方便】+【满足基本需求】的 **KVM over USB**  方案。

[binne](https://github.com/binnehot)/[KVM-over-USB](https://github.com/binnehot/KVM-over-USB)

[Jackadminx](https://github.com/Jackadminx)/[KVM-Card-Mini](https://github.com/Jackadminx/KVM-Card-Mini)

[ElluIFX](https://github.com/ElluIFX)/[KVM-Card-Mini-PySide6](https://github.com/ElluIFX/KVM-Card-Mini-PySide6)

## 硬件
三/四个常规小配件，不用做PCB板，淘宝/深圳随时可采购，花费100元左右就能搭出这个KVM over USB的方案。

1. 视频采集卡：理论上所USB视频采集卡采集卡都可以  (40-90+元）
2. CH9329虚拟键盘鼠标usb线：这是采用CH340+CH9329方案的usb转COM，再转USB模拟HID的线  (20元+）
3. HDMI线：1080P分辨率，没有特别要求  (10元+）
4. （usb3.0集线器）：如果电脑有两个usb口，可以省略。如果用usb2.0的集线器，也行。


【硬件图】
![image](https://github.com/binnehot/KVM-over-USB/blob/main/image/0_HW_KVM_photo.JPG)


【硬件框图】
![image](https://github.com/binnehot/KVM-over-USB/blob/main/image/1_HW_drawing.png)


## 软件
由于硬件改变，软件需要适配。
视频采集卡，即插即用，不用改东西。虚拟键鼠usb线，芯片方案都改了，原来的hid_def.py重新写了一遍，还有一个键盘码文件keyboard_ch9329code2Key.yaml。

**注意：PyPI 上的 `ch9329` 库已经下架**，本项目直接把 CH9329 串口协议实现内置到了 `client/ch9329/`（keyboard / mouse / config，按 `hid_def.py` 的调用接口编写）。

[CH9329 芯片串口通信协议]( https://www.wch.cn/uploads/file/20190508/1557278355473027.pdf) 想了解细节的可以看看。

## 当前功能支持情况

### 键盘
- 打字正常，无重复字符（状态帧透传，快速打字/重叠按键不会重复触发）
- 长按按键支持系统级自动重复（如长按 Backspace 连续删除）
- 组合键正常：Ctrl+C / Ctrl+V / Alt+Tab / Win 键等修饰键组合
- 中文输入：CH9329 模拟的是标准 HID 键盘，只能直接输入 ASCII 字符；中文需在目标机配合输入法

### 鼠标
- **Windows 目标机**：相对模式、绝对模式均可正常使用
  - 左/右键点击、按住拖动、滚轮正常
- **Ubuntu/Linux (X11) 目标机**：**只能使用相对模式**
  - 原因：CH9329 的 HID 描述符只向 X11 暴露了相对轴（`xinput set-mode ABSOLUTE` 会报 BadMatch），绝对坐标命令无法在 X11 上生效——这是硬件/驱动层面的限制
  - 使用：菜单 Mouse -> Relative mouse 开启相对模式（开启后状态栏会提示 "Relative mouse: 启用"）

### COM 口
- 启动时自动扫描所有 COM 口，**自动选中 CH340（沁恒 VID 0x1A86）**，无需手动配置
- 配置文件中的端口失效时自动回退到 CH340
- HID setting 对话框改为下拉选择，支持 COM10+（不再截断端口号）

### 服务端（被控制端）
HDMI和USB，即插即用，不用安装驱动，不挑操作系统，BIOS设置也支持。
注意：UI中 原项目留下来的某些功能需要原硬件支持，放在这里就没用了，比如，RGB灯，MCU重置…

【应用例子，修改BIOS设定】

![image](https://github.com/binnehot/KVM-over-USB/blob/main/image/4_BIOS_Gif.gif)

## 运行（开发）

```
cd client
python Mini-KVM.py debug
```

- 需要 Python 3.10 64 位 + `venv`，依赖见 `client/requirements.txt`（另需 `pyserial`；`numpy` 实际未使用）
- 末尾的 `debug` 参数必须带上，否则 `print` 会被屏蔽、日志进入应用内缓冲
- 首次使用需安装 CH340 驱动（见 `drivers/CH341SER/SETUP.EXE` 或 [官方驱动指导视频](https://www.wch.cn/videos/ch340.html)），在设备管理器确认 COM 口

## 打包（Windows 可执行文件）

```
cd client
./compiler.ps1
```

Nuitka onefile 打包，产物为 `Mini-KVM-Client/Mini-KVM.exe`。需要 `client/icons/`（已内置）。

## 独立工具

`tools/` 下提供不依赖主程序的 CH9329 打字小工具：
- `ch9329_typer.py`：命令行把一段文本通过 CH9329 模拟键盘输入
- `ch9329_typer_gui.py`：带 COM 口下拉（自动选中 CH340）+ 输入框 + 传输/停止按钮的 GUI 版

## 已知问题
- Ubuntu/X11 下绝对鼠标模式不可用（见上文"鼠标"部分），请使用相对模式
- 鼠标移动手感依赖相对模式速度设置（`config.yaml` 的 `relative_mouse_speed`），可自行调节


## 感谢
感谢 [ElluIFX](https://github.com/ElluIFX)。特别感谢[wevsty](https://github.com/wevsty) 制作的fork，优化了整个软件。 
