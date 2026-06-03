# -*- coding: utf-8 -*-
"""
鼠标坐标实时显示器
运行后，鼠标移动到任何位置，终端会实时显示 (X, Y) 坐标
按 Ctrl+C 退出
"""
import pyautogui
import time

print("=" * 40)
print("鼠标坐标实时显示器")
print("移动鼠标到目标位置，查看终端输出的坐标")
print("按 Ctrl+C 退出")
print("=" * 40)

try:
    while True:
        x, y = pyautogui.position()
        print(f"\r  鼠标位置: ({x:4d}, {y:4d})", end="", flush=True)
        time.sleep(0.3)
except KeyboardInterrupt:
    print("\n\n已退出")
