#import hid #换了硬件，改用串口,删除了所有hid相关代码
#
from serial import Serial
from serial import SerialException
from serial.tools import list_ports
from ch9329 import keyboard
from ch9329 import mouse
from ch9329.config import get_product
from ch9329.config import get_serial_number
from loguru import logger
from PySide6.QtWidgets import *
import os
import sys
import yaml  # type: ignore
import time
import random

product_id = 0x2107 #换了硬件，dummy
vendor_id = 0x413D  #换了硬件，dummy
usage_page = 0xFF00 #换了硬件，dummy

DEBUG = False
VERBOSE = False
COM_PORT=' '
SCREEN_SIZE=[0,0]
KEYBOARD_CH9329CODE2KEY = {}
PATH = os.path.dirname(os.path.abspath(__file__))
ARGV_PATH = os.path.dirname(os.path.abspath(sys.argv[0]))

def set_debug(debug):
    global DEBUG
    DEBUG = debug

def set_verbose(verbose):
    global VERBOSE
    VERBOSE = verbose

def set_com_port(com_port):
    global COM_PORT
    COM_PORT = com_port

def set_screen_size(screen_size):
    global SCREEN_SIZE
    SCREEN_SIZE = screen_size

def scan_com_ports():
    """扫描所有 COM 口, 返回 (端口列表, CH340端口或None)。
    列表元素为 device 名如 'COM10'; CH340(沁恒 VID 0x1A86) 排最前。"""
    ch340 = None
    items = []
    for p in list_ports.comports():
        if p.vid == 0x1A86:  # wch CH340/CH341
            if ch340 is None:
                ch340 = p.device
            items.insert(0, p.device)
        else:
            items.append(p.device)
    items.sort(key=lambda d: (not d.upper().startswith("COM"), d))
    # 保证 CH340 在首位
    if ch340 is not None:
        items.remove(ch340)
        items.insert(0, ch340)
    return items, ch340

def read_config_hid():
    default_config_hid="""COM_port: COM8
Screen size X: 1920
Screen size Y: 1080
"""
# 默认设置 "COM_port: COM8, Screen size X: 1920, Screen size Y :1080"
    return_read_config_hid=['COM0',100,100]
    if not os.path.exists(os.path.join(ARGV_PATH, "config_hid.yaml")):
        with open(os.path.join(ARGV_PATH, "config_hid.yaml"), "w") as f:
            f.write(default_config_hid)
    else:
        with open(os.path.join(ARGV_PATH, "config_hid.yaml"), "r") as load_f:
            config_hid_yaml = yaml.safe_load(load_f)
#        print ("line 57 config_hid.yaml file: ",config_hid_yaml)
        return_read_config_hid = [config_hid_yaml.get("COM_port"),config_hid_yaml.get("Screen size X"),config_hid_yaml.get("Screen size Y")]   
    return return_read_config_hid

# 建立COM口连接
hid_setting_cfg = read_config_hid()
set_com_port(hid_setting_cfg[0])
set_screen_size(hid_setting_cfg[1:3])
# 扫描 COM 口: 配置里的口打不开时自动回退到 CH340 (启动时默认选中)
COM_PORT_LIST, COM_PORT_CH340 = scan_com_ports()
try:
    K_M = Serial(COM_PORT, 9600, timeout=0.05)
except (SerialException, TypeError):
    if COM_PORT_CH340 is not None and COM_PORT_CH340 != COM_PORT:
        # 配置的口失效, 自动改用 CH340
        print(COM_PORT, "is not available, fallback to CH340:", COM_PORT_CH340)
        set_com_port(COM_PORT_CH340)
        COM_PORT = COM_PORT_CH340
    try:
        K_M = Serial(COM_PORT, 9600, timeout=0.05)
    except SerialException:
        print(COM_PORT, " is not in use, please edit the config_hid.yaml file")
        COM_PORT = COM_PORT + " fail"
except Exception:
    print(COM_PORT, " is not in use, please edit the config_hid.yaml file")
    COM_PORT = COM_PORT + " fail"

# 初始化HID设备设置
def init_usb(vendor_id, usage_page):
    global KEYBOARD_CH9329CODE2KEY
    try:
        with open(os.path.join(PATH, "data", "KEYBOARD_CH9329CODE2KEY.yaml"), "r") as load_f:
            KEYBOARD_CH9329CODE2KEY = yaml.safe_load(load_f)
            print ("line78, KEYBOARD_CH9329CODE2KEY.yaml:\n" , KEYBOARD_CH9329CODE2KEY)
    except Exception as e:
        print (f"Import config error:\n {e}\n\n")
        print ("Check the KEYBOARD_CH9329CODE2KEY.yaml and restart the program")
        sys.exit(1)
    if DEBUG:
        logger.debug(f"init_usb(vendor_id={vendor_id}, usage_page={usage_page})") # 老代码，新硬件没有使用vendor_id 

    if (COM_PORT[-3:]=="ail"):
        print ("COM_PORT",COM_PORT)
        set_hid_dialog=HID_Setting_Dialog()
        set_hid_dialog.exec()
        return 1
    elif (len(get_product(K_M))<3):
        print("Key board and mouse connection error.")
        set_hid_dialog=HID_Setting_Dialog()
        set_hid_dialog.exec()
        return 1
    return 0

def check_connection() -> bool:
    # 注意: 不能用 GET_INFO 探测 -- 键盘状态帧的 ACK(0x82)会积压在 RX 缓冲,
    # 与探测应答(0x81)交错导致误判断连, 键盘会被静默禁用。
    # 保持原版语义: 始终报告在线, 断连由写失败暴露。
    # 同时不再像旧版那样每秒盲发键盘/鼠标释放帧(会打断长按)。
    return True

# 读写HID设备
def hid_report(buffer=[], r_mode=False, report=0):
    if DEBUG:
        logger.debug(f"hid_report(buffer={buffer}, r_mode={r_mode}, report={report})")
        return 0
    buffer = buffer[-1:] + buffer[:-1]
    buffer[0] = 0
    if VERBOSE:
        logger.debug(f"hid < {buffer}")
    match buffer[1]:
        case 1:
            hid_report_key(buffer)
        case 2:
            hid_report_mouse(buffer)
        case 7:
            hid_report_mouse(buffer)
            pass
        case 3:
            buffer_indicator=[3,0,0]
            buffer_indicator[2]=hid_report_get_keyboard_light_status()
            print("line 122, Reporting the Keyboard indicator lights' status: ",buffer_indicator[2])
            return (buffer_indicator)
        case 4:
            print("line125,This hardware does not have MCU reset function.")
            msgBox = QMessageBox()
            msgBox.setText("更换了硬件,改用ch9329, 没有 重载MCU 功能.\n\n现在使用的硬件产品名是: "+ get_product(K_M) + "\n\n产品序列号是:  "+get_serial_number(K_M))
            msgBox.exec()
            return 0
        case 5:
            if ((buffer[5] == 30) | (buffer[3] == 30))& (buffer[4] == 30): 
                set_hid_dialog=HID_Setting_Dialog()
                set_hid_dialog.exec()
                reset_k_m('all')
            else:
                print("line 136, Reset keyboard and mouse, code error.")
            return 0
        case _:
            print("line 139, This buffer number is not in the cases list:", buffer)
    return 0


def hid_report_key(buffer_key):
    if buffer_key[1]== 1:
        # 状态透传: buffer[2]=修饰键位图(HID标准位序), buffer[4:10]=最多6个HID键码。
        # 与真实键盘语义一致: 按住即状态保持(目标机OS自己处理长按重复),
        # 快速打字重叠按键也不会重复触发字符。
        keyboard.send_hid_state(K_M, buffer_key[2], buffer_key[4:10])
        if len (buffer_key) > 10:
            if buffer_key[9]==43:
               keyboard.press_and_release(K_M, 'tab')
            if buffer_key[10]==70:
               keyboard.press_and_release(K_M, 'printscreen')
    else:
        print("line 165, buffer_key error:", buffer_key)
    return 0

def hid_report_mouse(buffer_mouse):
    # 旋转后布局: [3]=按键位图(1左2右4中), [4:8]=坐标, [8]=滚轮
    if buffer_mouse[1] == 2:
        if ((buffer_mouse[4] == 0) & (buffer_mouse[5] == 0) & (buffer_mouse[6] == 0) & (buffer_mouse[7] == 0)):
            if buffer_mouse[3] != 0:
                hid_report_mouse_click(buffer_mouse)
            # 坐标全零且无按键: 忽略空帧
        else:
            # 移动/拖动: 按键位图与坐标同帧透传(状态语义)
            hid_report_mouse_move_to(buffer_mouse)
        if buffer_mouse[8]!=0:
            hid_report_mouse_wheel(buffer_mouse[8])

    elif buffer_mouse[1] == 7:
        # 相对模式: [4]=dx [5]=dy (mouse_report_timeout 发完即清零)
        if ((buffer_mouse[4] == 0) & (buffer_mouse[5] == 0)):
            if buffer_mouse[3] != 0:
                hid_report_mouse_click(buffer_mouse)
        else:
            hid_report_mouse_move_rel(buffer_mouse)
        if buffer_mouse[6]!=0:
            hid_report_mouse_wheel(buffer_mouse[6])
    else:
        print("line 205, buffer_mouse error:", buffer_mouse)
    return 0

def hid_report_mouse_move_to(buffer_mouse):
    x= ((buffer_mouse[5] & 0xFF) << 8 )+ buffer_mouse[4]
    xx= int(x / 0x7FFF * SCREEN_SIZE[0])
    y= ((buffer_mouse[7] & 0xFF) << 8 ) + buffer_mouse[6]
    yy= int(y / 0x7FFF * SCREEN_SIZE[1])
    # 状态帧: 按键位图在 buffer[3](旋转后), 1左2右4中, 与坐标同帧发送支持拖动
    mouse.send_absolute_state(K_M,xx,yy,buffer_mouse[3],SCREEN_SIZE[0],SCREEN_SIZE[1])
    print ("line 214, mouse move to",xx,yy)
    return 0

def hid_report_mouse_click(buffer_mouse):
    # 原地点击: 按下->停留->释放 (保持原有人性化延迟)
    if buffer_mouse[3]== 1:
        mouse.press(K_M,'left')
    elif buffer_mouse[3]== 2:
        mouse.press(K_M,'right')
    elif buffer_mouse[3]== 4:
        mouse.press(K_M,'middle')
    else:
        print ("line 225, hid_report_mouse_click, mouse XButton? ",buffer_mouse)
        return 0
    time.sleep(random.uniform(0.1, 0.3))
    mouse.release(K_M)
    return 0

def hid_report_mouse_keyDown(buffer_mouse):
    if buffer_mouse[3]== 1:
        mouse.press(K_M,'left')
    elif buffer_mouse[3]== 2:
        mouse.press(K_M,'right')
    elif buffer_mouse[3]== 4:
        mouse.press(K_M,'middle')
    else:
        print ("line 237, hid_report_mouse_keyDown, mouse XButton? ",buffer_mouse)        
        return 0
    return 0

def hid_report_mouse_keyUp(buffer_mouse):
    if buffer_mouse[3]== 1 | buffer_mouse[3]== 2 | buffer_mouse[3]== 4:
        time.sleep(random.uniform(0.1, 0.45))
        mouse.release(K_M)
    else:
        print ("line 246, hid_report_mouse_keyUp, mouse XButton? ",buffer_mouse)        
    return 0

def hid_report_mouse_move_rel(buffer_mouse_rel):
    x_hid = buffer_mouse_rel[4]
    y_hid = buffer_mouse_rel[5]
    x_hid -= 0xFF if x_hid > 127 else 0
    y_hid -= 0xFF if y_hid > 127 else 0
    # 状态帧: 相对移动同样携带按键位图(buffer[3] 旋转后), 支持按住拖动
    mouse.send_relative_state(K_M,x_hid*3,y_hid*3,buffer_mouse_rel[3])
    print ("line 255, mouse move rel",x_hid,y_hid)
    return 0

def hid_report_mouse_wheel(buffer_wheel):
    if buffer_wheel==1:
        mouse.wheel(K_M,1)
    elif buffer_wheel==255:
        mouse.wheel(K_M,-1)
    else:
        print ("buffer wheel is incorrect",buffer_wheel)
    return 0

def hid_report_get_keyboard_light_status():
    keyboard_info=get_keyboard_info()
    print ("line 269,keyboard_info", keyboard_info)
    frame_data_location=keyboard_info.find('57ab008108')
    keyboard_light_status=int(keyboard_info[frame_data_location+15])
    return keyboard_light_status

def get_keyboard_info ():
    CMD_GET_INFO_packet= b"\x57" + b"\xab" + b"\x00" + b"\x01"  + b"\x00" + b"\x03"
    K_M.write (CMD_GET_INFO_packet)
    keyboard_info=K_M.readline()
    return keyboard_info.hex()

def reset_k_m(type ='key'):
    if type =='key':
        keyboard.release(K_M)
    elif type =='mouse':
        mouse.release(K_M)
    elif type =='all':
        keyboard.release(K_M)
        mouse.release(K_M)
    return 0

class HID_Setting_Dialog(QDialog):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.dialog = QDialog()
        layout = QFormLayout()
        label0=QLabel ()
        layout.addRow(label0)
        label1 = QLabel('HID COM 端口： ')
        # 下拉选择: 扫描所有 COM 口, CH340 排最前并默认选中
        self.cb1 = QComboBox()
        ports, ch340 = scan_com_ports()
        if not ports:
            ports = [COM_PORT.split()[0] if COM_PORT else ""]
        self.cb1.addItems(ports)
        current = COM_PORT.split()[0]  # 去掉可能带的 " fail" 后缀
        if current in ports:
            self.cb1.setCurrentText(current)
        # CH340 优先(已是列表首位); 当前口无效时落到 CH340
        elif ch340:
            self.cb1.setCurrentText(ch340)
        layout.addRow(label1,self.cb1)
        label2 = QLabel('服务器（被控端）屏幕分辨率 宽度: ')
        self.le2 = QLineEdit(str(SCREEN_SIZE[0]))
        layout.addRow(label2,self.le2)
        label3 = QLabel('服务器（被控端）屏幕分辨率 高度: ')
        self.le3 = QLineEdit(str(SCREEN_SIZE[1]))
        layout.addRow(label3,self.le3)
        label0=QLabel ()
        layout.addRow(label0)
        QBbox= QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        button_ok_cancel=QDialogButtonBox(QBbox)
        layout.addRow(button_ok_cancel)
        self.setting_text=[self.cb1.currentText(),self.le2.text(),self.le3.text()]
        button_ok_cancel.accepted.connect(self.save_hid_setting)
        button_ok_cancel.rejected.connect(self.reject)
        self.setLayout(layout)
        self.setWindowTitle('HID setting')
        return 0

    def save_hid_setting(self):
        input_com_port=self.cb1.currentText().strip()
        input_screen_x=self.le2.text()
        input_screen_y=self.le3.text()
        # 校验 COM 口名: COM + 数字 (不再截断, 支持 COM10+)
        if (input_com_port[0:3].upper()=="COM") and (input_com_port[3:].isdigit()) and (len(input_com_port)>3):
            if COM_PORT!=input_com_port:
                set_com_port(input_com_port)
                msgBox = QMessageBox()
                msgBox.setText("修改COM口,请关闭(或强制关闭)程序后 重新运行程序")
                msgBox.exec()
        else:
            msgBox = QMessageBox()
            msgBox.setText("COM口 格式是 大写COM和数字,例如:COM5")
            msgBox.exec()
        if (input_screen_x.isdigit())&(input_screen_y.isdigit()):
            set_screen_size([int(input_screen_x),int(input_screen_y)])
        else:
            msgBox = QMessageBox()
            msgBox.setText("屏幕分辨率为数字,例如:1080")
            msgBox.exec()

        self.setting_text=[input_com_port,input_screen_x,input_screen_y]
        print ("line 344 setting_text :" ,self.setting_text) 

        new_config_hid = 'COM_port: ' + COM_PORT +'\n' + 'Screen size X: ' + str(SCREEN_SIZE[0]) + '\n' + 'Screen size Y: '+ str(SCREEN_SIZE[1]) + '\n'
        print ('line 347 new config_hid:', new_config_hid)

        with open(os.path.join(ARGV_PATH, "config_hid.yaml"), "w", encoding="utf-8") as f:
            f.write(new_config_hid)  
        self.close()
        return 0
