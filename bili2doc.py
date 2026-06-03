# -*- coding: utf-8 -*-
"""
bili2doc - B站视频AI转文字工具 (夜间无人值守版)
================================================
使用360AI浏览器的全文AI分析功能，将B站视频内容自动转录为.docx文档。

夜间运行特性：
- 处理完每个视频后自动最小化浏览器窗口
- 需要操作时自动恢复窗口到前台
- 完成后自动生成状态报告
- 无GUI交互，全日志驱动
- 支持定时启动和后台运行

核心技术：
- 360AI浏览器扩展的「全文」AI分析功能
- pyautogui屏幕级坐标点击（扩展UI不在DOM内）
- win32gui窗口管理（确保浏览器焦点）
- PIL图像分析（AI结果检测）

作者：GLM-5V-Turbo + Trae IDE
创建日期：2026-06-03
"""

import subprocess
import time
import os
import sys
import json
import pyautogui
import win32gui
import win32con
import ctypes
from datetime import datetime
from PIL import Image, ImageStat
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import logging
import threading

# ==================== 停止控制 ====================
class StopController:
    """
    停止控制器 - 三种方式同时生效：
    方式A: 创建 STOP.txt 文件（文件信号）
    方式B: 点击浮动GUI停止按钮（直观）
    方式C: 在控制台窗口按 S 键（非阻塞键盘检测）
    """
    def __init__(self):
        self.should_stop = False
        self._lock = threading.Lock()
        self.stop_file = Config.PROJECT_ROOT / "STOP.txt"
    
    def start_listener(self, logger=None):
        """启动所有停止监听方式"""
        self._logger = logger
        
        # 启动后台检测线程（方案A: 文件检测）
        def _file_listener():
            while True:
                if self.should_stop:
                    break
                if self.stop_file.exists():
                    self._on_stop()
                    break
                time.sleep(0.5)
        
        # 启动后台键盘检测线程（方案C: msvcrt）
        def _keyboard_listener():
            """非阻塞检测控制台按S键"""
            try:
                import msvcrt
                while True:
                    if self.should_stop:
                        break
                    if msvcrt.kbhit():
                        key = msvcrt.getch().lower()
                        if key in (b's', b'S'):
                            self._on_stop()
                            break
                    time.sleep(0.3)
            except:
                pass  # 非Windows或不可用时忽略
        
        # 启动GUI浮动按钮（方案B）
        self._start_gui_button()
        
        # 启动后台线程
        t1 = threading.Thread(target=_file_listener, daemon=True)
        t1.start()
        t2 = threading.Thread(target=_keyboard_listener, daemon=True)
        t2.start()
        
        if self._logger:
            self._logger.info(f"🛑 停止监听已启动（三种方式）")
            self._logger.info(f"   方式A: 创建文件 {self.stop_file}")
            self._logger.info(f"   方式B: 点击浮动按钮窗口")
            self._logger.info(f"   方式C: 在控制台窗口按 S 键")
    
    def _start_gui_button(self):
        """启动浮动停止按钮GUI窗口（独立进程，避免线程崩溃）"""
        try:
            stop_button_script = Config.PROJECT_ROOT / "stop_button.py"
            if stop_button_script.exists():
                import subprocess
                subprocess.Popen(
                    [sys.executable, str(stop_button_script), str(self.stop_file)],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    close_fds=True
                )
        except Exception as e:
            if self._logger:
                self._logger.debug(f"GUI按钮启动失败: {e}")
    
    def _on_stop(self):
        """触发停止"""
        with self._lock:
            self.should_stop = True
        # 同时创建停止文件，让GUI按钮进程也能检测到
        try:
            with open(self.stop_file, 'w') as f:
                f.write('stop')
        except:
            pass
        if self._logger:
            self._logger.info("\n 收到停止请求！程序将在当前操作完成后安全退出...")
    
    def check_stop(self, log=True):
        """检查是否需要停止，返回 True 表示应该退出"""
        if self.stop_file.exists():
            self._on_stop()
        with self._lock:
            result = self.should_stop
        if result and log and self._logger:
            self._logger.info(" 程序正在安全退出，保存进度...")
        return result
    
    def request_stop(self):
        """手动请求停止（供代码内部调用）"""
        with self._lock:
            self.should_stop = True
        if self._logger:
            self._logger.info(" 程序内部请求停止...")

# ==================== 配置类 ====================
class Config:
    """项目配置管理"""
    
    # === 360AI扩展坐标（用户实测确认）===
    COORDS = {
        "全文":   (1070, 95),
        "AI模式": (1193, 86),
        "导出":   (1733, 163),
        "地址栏": (400, 55),
        "下载关闭": (1328, 300),  # 下载窗口X关闭按钮
    }
    
    # === 路径配置 ===
    BROWSER_PATH = r"D:\360AI\360aibrowser\Application\360aibrowser.exe"
    DOWNLOAD_DIR = r"D:\360AI浏览器\下载"
    
    # === 项目根目录 ===
    PROJECT_ROOT = Path(__file__).parent
    
    SCREENSHOT_DIR = PROJECT_ROOT / "screenshots"
    VIDEO_LIST_FILE = PROJECT_ROOT / "video_list.json"
    STATE_FILE = PROJECT_ROOT / "batch_state.json"
    REPORT_FILE = PROJECT_ROOT / "night_run_report.json"
    EXECUTION_LOG_FILE = PROJECT_ROOT / "execution_log.json"  # 执行状态记录
    
    # === 流程参数 ===
    WAIT_AI_SECONDS = 120          # AI分析等待时间
    NAVIGATE_WAIT = 8              # 页面加载等待
    NAVIGATE_MAX_RETRY = 3         # 导航最大重试
    
    # === 批量处理参数 ===
    BATCH_SIZE = 5                 # 每批处理数量
    RESTART_EVERY_N = 15           # 每N个视频重启浏览器
    INTER_VIDEO_DELAY = 30         # 视频间隔（秒）- 用户要求快速连续处理
    
    # === 频率限制参数 ===
    RATE_LIMIT_BASE_COOLDOWN = 1800  # 基础冷却30分钟
    RATE_LIMIT_MAX_COOLDOWN = 7200   # 最大冷却2小时
    
    # === AI检测参数 ===
    SIDEBAR_REGION = (810, 130, 1150, 550)  # 侧边栏截图区域
    AI_ERROR_BRIGHTNESS = 100      # 错误页面亮度阈值
    AI_OK_BRIGHTNESS = 180         # 成功页面亮度阈值
    
    # === 下载检测 ===
    DOWNLOAD_MONITOR_SECONDS = 90  # 下载监控时间
    MIN_FILE_SIZE = 1000           # 最小文件大小
    
    # === 夜间运行配置 ===
    NIGHT_MODE = True              # 夜间模式：自动最小化浏览器
    BROWSER_MINIMIZE_AFTER_VIDEO = True  # 处理完每个视频后最小化
    
    @classmethod
    def ensure_dirs(cls):
        """确保所有目录存在"""
        cls.SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        Path(cls.DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)
        (cls.PROJECT_ROOT / "logs").mkdir(exist_ok=True)


# ==================== 日志配置 ====================
def setup_logging():
    """配置日志系统"""
    log_dir = Config.PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    
    log_file = log_dir / f"bili2doc_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    # 配置根日志器
    logger = logging.getLogger("bili2doc")
    logger.setLevel(logging.DEBUG)
    
    # 文件处理器（详细）
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    ))
    
    # 控制台处理器（简洁）
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("  [%(asctime)s] %(message)s", datefmt="%H:%M:%S"))
    
    logger.addHandler(fh)
    logger.addHandler(ch)
    
    return logger


# ==================== 浏览器管理 ====================
class BrowserManager:
    """360AI浏览器窗口管理"""
    
    @staticmethod
    def find_browser() -> Optional[Tuple[int, str, int, int]]:
        """查找360AI浏览器窗口（严格匹配360AI，排除其他浏览器）"""
        result = []
        all_windows = []  # 调试用：记录所有窗口
        
        def enum_callback(hwnd, lst):
            if not win32gui.IsWindowVisible(hwnd):
                return True
            
            title = win32gui.GetWindowText(hwnd)
            cls_name = win32gui.GetClassName(hwnd)
            rect = win32gui.GetWindowRect(hwnd)
            w, h = rect[2] - rect[0], rect[3] - rect[1]
            
            # 排除IDE
            if "Trae" in title or "trae" in title.lower():
                return True
            
            # 记录所有尺寸合理的窗口（用于调试）
            if w > 800 and h > 500 and len(title) > 0:
                all_windows.append(f"  窗口: {title[:50]} | 类名: {cls_name} | 尺寸: {w}x{h}")
            
            # 【严格匹配】只识别360AI浏览器
            # 标题包含"360AI"或进程名包含"360aibrowser"
            is_360ai_browser = (
                "360AI" in title or 
                "360ai" in title.lower() or 
                "360aibrowser" in cls_name.lower()
            )
            
            # 必须是360AI浏览器，且窗口尺寸合理
            if w > 800 and h > 500 and is_360ai_browser:
                lst.append((hwnd, title, w, h))
            
            return True
        
        win32gui.EnumWindows(enum_callback, result)
        
        # 调试日志
        logger = logging.getLogger("bili2doc")
        if not result:
            logger.debug("未找到360AI浏览器窗口")
            if all_windows:
                logger.debug(f"当前其他窗口:\n" + "\n".join(all_windows[:5]))
        
        if not result:
            return None
        
        logger.debug(f"找到 {len(result)} 个360AI浏览器窗口")
        
        # 优先选择包含bilibili标题的窗口（当前正在处理视频）
        preferred = [r for r in result if "bilibili" in r[1].lower()]
        if preferred:
            logger.debug(f"选择含bilibili标题的窗口: {preferred[0][1][:60]}")
            return preferred[0]
        
        # 否则返回第一个360AI浏览器窗口
        logger.debug(f"选择第一个360AI窗口: {result[0][1][:60]}")
        return result[0]
    
    @staticmethod
    def minimize_trae():
        """最小化所有Trae IDE窗口"""
        def enum_callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if "Trae" in title or "trae" in title.lower():
                    try:
                        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                    except Exception:
                        pass
            return True
        
        win32gui.EnumWindows(enum_callback, None)
    
    @classmethod
    def minimize_browser(cls) -> bool:
        """最小化浏览器窗口（夜间模式用）"""
        info = cls.find_browser()
        if not info:
            return False
        
        hwnd = info[0]
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
            return True
        except Exception:
            return False
    
    @classmethod
    def maximize_browser(cls) -> bool:
        """强制最大化浏览器窗口（确保坐标正确）"""
        info = cls.find_browser()
        if not info:
            return False
        
        hwnd = info[0]
        try:
            # 先恢复（如果最小化了）
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.3)
            # 强制最大化
            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
            time.sleep(0.5)
            
            # 验证是否真的最大化了
            placement = win32gui.GetWindowPlacement(hwnd)
            if placement[1] == win32con.SW_SHOWMAXIMIZED:
                return True
            else:
                logging.getLogger("bili2doc").warning("️ 窗口最大化失败，尝试第二次...")
                time.sleep(0.5)
                win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
                time.sleep(0.3)
                return True
        except Exception as e:
            logging.getLogger("bili2doc").error(f"最大化窗口失败: {e}")
            return False
    
    @classmethod
    def restore_browser(cls) -> bool:
        """恢复浏览器窗口到前台（并强制最大化）"""
        info = cls.find_browser()
        if not info:
            return False
        
        hwnd = info[0]
        try:
            # 先恢复（如果最小化了）
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.3)
            # 强制最大化 - 确保坐标系统正确
            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
            time.sleep(0.5)
            
            # 验证最大化状态
            placement = win32gui.GetWindowPlacement(hwnd)
            logger = logging.getLogger("bili2doc")
            if placement[1] == win32con.SW_SHOWMAXIMIZED:
                logger.debug("✅ 浏览器窗口已最大化")
            else:
                logger.warning("⚠️ 浏览器窗口未最大化，尝试第二次...")
                time.sleep(0.5)
                win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
                time.sleep(0.3)
            
            # 置顶并获取焦点
            win32gui.BringWindowToTop(hwnd)
            ctypes.windll.user32.AllowSetForegroundWindow(-1)
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.3)
            
            # 点击中心确保焦点
            rect = win32gui.GetWindowRect(hwnd)
            cx = (rect[0] + rect[2]) // 2
            cy = (rect[1] + rect[3]) // 2
            pyautogui.click(cx, cy)
            time.sleep(0.5)
            
            return True
        except Exception:
            return False
    
    @classmethod
    def force_foreground(cls) -> bool:
        """强制浏览器到前台"""
        cls.minimize_trae()
        time.sleep(0.5)
        
        info = cls.find_browser()
        if not info:
            return False
        
        hwnd = info[0]
        
        for attempt in range(3):
            try:
                # 最小化再最大化刷新Z序
                win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                time.sleep(0.2)
                win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
                time.sleep(0.3)
                
                # 置顶
                win32gui.BringWindowToTop(hwnd)
                ctypes.windll.user32.AllowSetForegroundWindow(-1)
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.3)
                
                # 点击中心确保焦点
                rect = win32gui.GetWindowRect(hwnd)
                cx = (rect[0] + rect[2]) // 2
                cy = (rect[1] + rect[3]) // 2
                pyautogui.click(cx, cy)
                time.sleep(0.5)
                
                # 验证
                fg = win32gui.GetForegroundWindow()
                fg_title = win32gui.GetWindowText(fg)
                if "360" in fg_title or "bilibili" in fg_title.lower():
                    return True
                    
            except Exception:
                if attempt < 2:
                    time.sleep(1)
        
        # 兜底
        cls.minimize_trae()
        time.sleep(0.5)
        rect = win32gui.GetWindowRect(hwnd)
        pyautogui.click((rect[0]+rect[2])//2, (rect[1]+rect[3])//2)
        time.sleep(0.5)
        return True
    
    @classmethod
    def restart(cls, reason="重启") -> bool:
        """重启360AI浏览器"""
        logger = logging.getLogger("bili2doc")
        logger.info(f"360AI浏览器{reason}...")
        
        # 杀掉所有360AI浏览器进程
        try:
            subprocess.run(
                ["taskkill", "/IM", "360aibrowser.exe", "/F"],
                capture_output=True, timeout=10
            )
        except Exception:
            pass
        
        # 也杀掉可能残留的其他360进程
        try:
            subprocess.run(
                ["taskkill", "/IM", "360chrome.exe", "/F"],
                capture_output=True, timeout=5
            )
        except Exception:
            pass
        
        time.sleep(5)  # 等待进程完全清理
        
        # 启动360AI浏览器
        logger.info(f"启动: {Config.BROWSER_PATH}")
        subprocess.Popen([Config.BROWSER_PATH])
        
        # 等待窗口出现 - 增加到90秒
        for attempt in range(90):
            time.sleep(1)
            info = cls.find_browser()
            if info:
                # 【严格验证】必须是360AI浏览器
                title = info[1]
                if "360AI" in title or "360ai" in title.lower():
                    logger.info(f"✅ 360AI浏览器就绪 ({attempt+1}秒): {title}")
                    # 启动后立即最大化（关键修复！）
                    cls.maximize_browser()
                    cls.force_foreground()
                    time.sleep(2)  # 给浏览器充分渲染时间
                    return True
                else:
                    if attempt % 10 == 0:
                        logger.warning(f"⚠️ 找到非360AI浏览器窗口: {title}，继续等待...")
            elif attempt % 10 == 0:
                logger.info(f"  等待360AI浏览器启动... ({attempt+1}秒)")
        
        logger.error("❌ 360AI浏览器启动超时（90秒未检测到）")
        return False
    
    @classmethod
    def ensure_ready(cls) -> bool:
        """确保360AI浏览器可用"""
        info = cls.find_browser()
        if not info:
            return cls.restart("首次启动")
        
        # 验证当前窗口确实是360AI浏览器
        title = info[1]
        if "360AI" not in title and "360ai" not in title.lower():
            logger = logging.getLogger("bili2doc")
            logger.warning(f"⚠️ 当前窗口不是360AI浏览器: {title}")
            return cls.restart("非360AI浏览器，重新")
        
        cls.force_foreground()
        return True
    
    @classmethod
    def ensure_maximized_and_focused(cls) -> bool:
        """
        【完整版】确保浏览器已恢复、最大化、且是前台窗口
        仅在关键节点调用（启动后、关闭豆包后、等待结束后）
        返回: True=就绪, False=失败
        """
        logger = logging.getLogger("bili2doc")
        
        # 1. 先找到浏览器窗口
        info = cls.find_browser()
        if not info:
            logger.warning("⚠️ 未找到360AI浏览器，准备启动...")
            if not cls.restart("操作前未找到"):
                return False
            info = cls.find_browser()
            if not info:
                return False
        
        hwnd = info[0]
        title = info[1]
        
        # 2. 验证确实是360AI浏览器
        if "360AI" not in title and "360ai" not in title.lower():
            logger.warning(f"⚠️ 找到非360AI窗口: {title}，尝试重启...")
            if not cls.restart("非360AI浏览器"):
                return False
            info = cls.find_browser()
            if not info:
                return False
            hwnd = info[0]
        
        # 3. 最大化（直接最大化，不需要先还原）
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
            time.sleep(0.5)
        except Exception as e:
            logger.warning(f"最大化异常: {e}")
        
        # 4. 最小化Trae（避免抢焦点）
        cls.minimize_trae()
        time.sleep(0.2)
        
        # 5. 强制置顶+获取焦点（最多尝试2次）
        for attempt in range(2):
            try:
                win32gui.BringWindowToTop(hwnd)
                ctypes.windll.user32.AllowSetForegroundWindow(-1)
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.3)
                
                # 6. 验证焦点
                fg_hwnd = win32gui.GetForegroundWindow()
                fg_title = win32gui.GetWindowText(fg_hwnd)
                
                if "360" in fg_title or "AI" in fg_title or "bilibili" in fg_title.lower() or "doubao" in fg_title.lower():
                    return True
                else:
                    if attempt < 1:
                        time.sleep(0.5)
            except Exception as e:
                if attempt < 1:
                    time.sleep(0.5)
        
        # 兜底：直接返回（不点中心了，太浪费时间）
        return True
    
    @staticmethod
    def ensure_browser_ready() -> bool:
        """
        【轻量版】日常操作前快速检查浏览器是否存在
        不最大化、不点中心、不验证焦点，只做最基础的检查
        用于：Ctrl+T、Ctrl+Tab、点击按钮等常规操作前
        返回: True=浏览器存在, False=浏览器丢失
        """
        info = BrowserManager.find_browser()
        if not info:
            logging.getLogger("bili2doc").warning("⚠️ 浏览器未找到，尝试重启...")
            return BrowserManager.restart("日常操作前未找到")
        return True
    
    @staticmethod
    def safe_click_coord(name: str):
        """
        安全的坐标点击：先确保浏览器就绪，再点击
        """
        # 确保浏览器已最大化+前台
        BrowserManager.ensure_maximized_and_focused()
        time.sleep(0.5)
        x, y = Config.COORDS[name]
        pyautogui.click(x, y)
        time.sleep(1.5)
    
    @staticmethod
    def safe_hotkey(*keys, desc: str = ""):
        """
        安全的快捷键：先确保浏览器就绪，再按键
        """
        BrowserManager.ensure_maximized_and_focused()
        time.sleep(0.5)
        pyautogui.hotkey(*keys)
        time.sleep(1.0)
    
    @staticmethod
    def safe_press(key: str, desc: str = ""):
        """
        安全的按键：先确保浏览器就绪，再按
        """
        BrowserManager.ensure_maximized_and_focused()
        time.sleep(0.3)
        pyautogui.press(key)
        time.sleep(0.5)


# ==================== 页面导航 ====================
class Navigator:
    """页面导航控制"""
    
    @staticmethod
    def navigate_to(url: str) -> bool:
        """导航到指定URL"""
        # 复制URL到剪贴板
        subprocess.run(['clip'], input=url.encode('gbk'), check=True, timeout=3)
        time.sleep(0.3)
        
        # 点击地址栏
        x, y = Config.COORDS["地址栏"]
        pyautogui.click(x, y)
        time.sleep(0.5)
        
        # 全选→粘贴→回车
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.3)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.5)
        pyautogui.press('enter')
        
        return True
    
    @staticmethod
    def verify_navigation(wait_seconds: int = 10) -> bool:
        """验证导航是否成功"""
        time.sleep(wait_seconds)
        info = BrowserManager.find_browser()
        if not info:
            return False
        return "bilibili" in info[1].lower()


# ==================== AI分析检测 ====================
class AIAnalyzer:
    """AI分析结果检测"""
    
    @staticmethod
    def check_result(screenshot_path: str) -> str:
        """
        检测AI分析结果
        
        返回:
            'error' - AI失败（频率限制）
            'likely_ok' - 可能有内容
            'unknown' - 不确定
        """
        try:
            img = Image.open(screenshot_path)
            left, top, right, bottom = Config.SIDEBAR_REGION
            sidebar = img.crop((left, top, right, bottom))
            gray = sidebar.convert('L')
            stat = ImageStat.Stat(gray)
            mean = stat.mean[0]
            stddev = stat.stddev[0]
            
            logger = logging.getLogger("bili2doc")
            
            if mean < Config.AI_ERROR_BRIGHTNESS:
                logger.debug(f"AI检测: 亮度={mean:.0f}<{Config.AI_ERROR_BRIGHTNESS} → 频率限制")
                return 'error'
            elif mean > Config.AI_OK_BRIGHTNESS:
                logger.debug(f"AI检测: 亮度={mean:.0f}>{Config.AI_OK_BRIGHTNESS} → 可能有内容")
                return 'likely_ok'
            else:
                logger.debug(f"AI检测: 亮度={mean:.0f} 标准差={stddev:.1f} → 不确定")
                return 'unknown'
                
        except Exception as e:
            return 'unknown'


# ==================== 下载检测 ====================
class DownloadMonitor:
    """下载状态监控"""
    
    @staticmethod
    def get_current_files() -> set:
        """获取当前下载目录文件列表"""
        if os.path.exists(Config.DOWNLOAD_DIR):
            return set(os.listdir(Config.DOWNLOAD_DIR))
        return set()
    
    @staticmethod
    def check_new_download(bvid: str, before_files: set) -> Optional[Dict]:
        """检查是否有新的docx文件下载"""
        after_files = DownloadMonitor.get_current_files()
        new_files = after_files - before_files
        
        for filename in new_files:
            if filename.endswith('.docx'):
                filepath = os.path.join(Config.DOWNLOAD_DIR, filename)
                size = os.path.getsize(filepath)
                if size > Config.MIN_FILE_SIZE:
                    return {
                        "filename": filename,
                        "path": filepath,
                        "size": size
                    }
        return None


# ==================== 视频处理 ====================
class VideoProcessor:
    """单个视频处理"""
    
    def __init__(self, controller=None):
        self.logger = logging.getLogger("bili2doc")
        self.controller = controller  # 停止控制器
    
    def _wait_with_progress(self, seconds: int):
        """带进度输出的等待（每15秒检查停止信号）"""
        for i in range(seconds // 15):
            if self.controller and self.controller.check_stop(log=False):
                self.logger.info("⛔ 收到停止请求，中断等待...")
                return True
            time.sleep(15)
            if (i+1) % 2 == 0:
                self.logger.debug(f"  {(i+1)*15}s...")
        return False
    
    def process(self, video: Dict, attempt: int = 0) -> Dict:
        """
        处理单个视频
        
        返回:
            {'success': bool, 'rate_limited': bool, 'download': dict|None}
        """
        bvid = video["bvid"]
        title = video["title"][:35]
        url = video["url"]
        tag = f"#{video['index']} {bvid}"
        
        self.logger.info(f"处理: {tag} {title} (第{attempt+1}次)")
        
        try:
            # 1. 确保浏览器可用（恢复窗口）
            if Config.NIGHT_MODE:
                BrowserManager.restore_browser()
            else:
                BrowserManager.force_foreground()
            
            if not BrowserManager.ensure_ready():
                return {"success": False, "rate_limited": False}
            
            # 2. 导航到视频页
            nav_ok = False
            for nav_try in range(Config.NAVIGATE_MAX_RETRY):
                self.logger.debug(f"导航尝试 {nav_try+1}/{Config.NAVIGATE_MAX_RETRY}")
                if Config.NIGHT_MODE:
                    BrowserManager.restore_browser()
                else:
                    BrowserManager.force_foreground()
                Navigator.navigate_to(url)
                time.sleep(Config.NAVIGATE_WAIT)
                if Config.NIGHT_MODE:
                    BrowserManager.restore_browser()
                else:
                    BrowserManager.force_foreground()
                time.sleep(2)
                
                if Navigator.verify_navigation():
                    self.logger.info("✅ 导航成功")
                    nav_ok = True
                    break
                time.sleep(3)
            
            if not nav_ok:
                self.logger.error("❌ 导航失败")
                return {"success": False, "rate_limited": False}
            
            # 3. 点击AI模式
            self.logger.info("点击AI模式...")
            self._click_coord("AI模式")
            
            # 4. 点击「全文」
            self.logger.info("★ 点击「全文」...")
            self._click_coord("全文")
            
            # 5. 等待AI分析（夜间模式可最小化）
            self.logger.info(f"等待AI分析({Config.WAIT_AI_SECONDS}s)...")
            
            if Config.NIGHT_MODE:
                BrowserManager.minimize_browser()
                self.logger.info("浏览器已最小化，AI分析中不打扰...")
                # 分秒等待，支持中断
                for s in range(Config.WAIT_AI_SECONDS, 0, -1):
                    if self.controller and self.controller.check_stop(log=False):
                        self.logger.info("⛔ 收到停止请求，中断AI等待...")
                        return {"success": False, "rate_limited": False}
                    time.sleep(1)
                BrowserManager.restore_browser()
                time.sleep(2)
            else:
                interrupted = self._wait_with_progress(Config.WAIT_AI_SECONDS)
                if interrupted:
                    self.logger.info(" AI等待被中断...")
                    return {"success": False, "rate_limited": False}
            
            # 6. AI结果检测 - 关键修复：确保截图的是浏览器不是桌面
            self.logger.info("截取AI分析结果...")
            
            # 再次确保浏览器在前台且最大化
            BrowserManager.restore_browser()
            time.sleep(2)  # 等待窗口完全恢复
            
            # 验证截图正确性：截图后检查亮度
            screenshot_path = self._screenshot(f"{bvid}_pre_exp")
            
            # 调试：立即检查截图亮度
            try:
                debug_img = Image.open(screenshot_path)
                debug_gray = debug_img.convert('L')
                debug_stat = ImageStat.Stat(debug_gray)
                self.logger.info(f"调试-全图亮度: {debug_stat.mean[0]:.0f}")
            except:
                pass
            
            ai_status = AIAnalyzer.check_result(screenshot_path)
            
            if ai_status == 'error':
                self.logger.info("❌ AI失败(频率限制)，跳过导出")
                if Config.NIGHT_MODE:
                    BrowserManager.minimize_browser()
                return {"success": False, "rate_limited": True}
            
            # 7. 记录导出前文件
            before_files = DownloadMonitor.get_current_files()
            
            # 8. 点击导出
            self.logger.info("点击「导出」...")
            self._click_coord("导出")
            
            # 9. 下载确认
            self.logger.info("回车确认下载...")
            time.sleep(2)
            if Config.NIGHT_MODE:
                BrowserManager.restore_browser()
            pyautogui.press('enter')
            time.sleep(5)
            
            # 10. 检查下载
            dl = DownloadMonitor.check_new_download(bvid, before_files)
            if dl:
                self.logger.info(f"✅ 下载成功: {dl['filename']} ({dl['size']} bytes)")
                if Config.NIGHT_MODE:
                    BrowserManager.minimize_browser()
                return {"success": True, "download": dl, "rate_limited": False}
            
            # 11. 备用方案
            self.logger.info("备用下载确认...")
            if Config.NIGHT_MODE:
                BrowserManager.restore_browser()
            pyautogui.click(960, 520)
            time.sleep(1)
            pyautogui.press('enter')
            time.sleep(3)
            
            dl = DownloadMonitor.check_new_download(bvid, before_files)
            if dl:
                self.logger.info(f"✅ 备用下载成功")
                if Config.NIGHT_MODE:
                    BrowserManager.minimize_browser()
                return {"success": True, "download": dl, "rate_limited": False}
            
            # 12. 长时间监控
            self.logger.info(f"监控下载({Config.DOWNLOAD_MONITOR_SECONDS}s)...")
            for i in range(Config.DOWNLOAD_MONITOR_SECONDS // 5):
                time.sleep(5)
                dl = DownloadMonitor.check_new_download(bvid, before_files)
                if dl:
                    break
                # 定期确认
                if (i+1) % 6 == 0 and i < 15:
                    if Config.NIGHT_MODE:
                        BrowserManager.restore_browser()
                    pyautogui.press('enter')
                    time.sleep(2)
            
            if dl:
                self.logger.info(f"✅ 延迟下载成功: {dl['filename']}")
                if Config.NIGHT_MODE:
                    BrowserManager.minimize_browser()
                return {"success": True, "download": dl, "rate_limited": False}
            
            self.logger.error("❌ 下载超时")
            self._screenshot(f"{bvid}_timeout")
            if Config.NIGHT_MODE:
                BrowserManager.minimize_browser()
            return {"success": False, "rate_limited": False}
            
        except Exception as e:
            self.logger.error(f"❌ 异常: {type(e).__name__}: {str(e)[:60]}")
            if Config.NIGHT_MODE:
                BrowserManager.minimize_browser()
            return {"success": False, "rate_limited": False}
    
    def _click_coord(self, name: str):
        """点击指定坐标"""
        if Config.NIGHT_MODE:
            BrowserManager.restore_browser()
        time.sleep(1)
        pyautogui.click(*Config.COORDS[name])
        time.sleep(2)
    
    def _screenshot(self, name: str) -> str:
        """截图"""
        path = str(Config.SCREENSHOT_DIR / f"v49_{name}.png")
        try:
            pyautogui.screenshot(path)
        except Exception:
            pass
        return path


# ==================== 报告生成 ====================
class ReportGenerator:
    """运行报告生成"""
    
    @staticmethod
    def generate_report(stats: Dict, state: Dict, start_time: float, total_videos: int) -> Dict:
        """生成运行报告"""
        elapsed = (time.time() - start_time) / 60
        
        report = {
            "run_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_videos": total_videos,
            "processed": stats["success"] + stats["failed"],
            "success": stats["success"],
            "failed": stats["failed"],
            "attempts": stats["attempts"],
            "elapsed_minutes": round(elapsed, 1),
            "state": {
                "completed": state.get("completed", []),
                "failed": state.get("failed", [])
            }
        }
        
        # 保存报告
        with open(Config.REPORT_FILE, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        return report


# ==================== 批量处理 ====================
class BatchProcessor:
    """批量视频处理（并行模式）"""
    
    def __init__(self):
        self.logger = logging.getLogger("bili2doc")
        self.controller = StopController()  # 停止控制器
        self.processor = VideoProcessor(controller=self.controller)
    
    def load_state(self) -> Dict:
        """加载处理状态"""
        if Config.STATE_FILE.exists():
            with open(Config.STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"completed": [], "failed": [], "last_index": 0}
    
    def save_state(self, state: Dict):
        """保存处理状态"""
        with open(Config.STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    
    def load_video_list(self) -> List[Dict]:
        """加载视频列表"""
        with open(Config.VIDEO_LIST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def load_selected_videos(self) -> Optional[List[Dict]]:
        """加载用户选中的视频列表（如有）"""
        selection_file = Config.PROJECT_ROOT / "selected_videos.json"
        if selection_file.exists():
            with open(selection_file, "r", encoding="utf-8") as f:
                selection = json.load(f)
            return selection.get("videos", [])
        return None
    
    def _scan_downloaded_bvids(self, videos: List[Dict]) -> set:
        """
        扫描下载目录，找出已下载的文件对应的BVID
        返回: 已下载的BVID集合
        """
        import re
        
        if not os.path.exists(Config.DOWNLOAD_DIR):
            return set()
        
        files = [f for f in os.listdir(Config.DOWNLOAD_DIR) if f.endswith('.docx')]
        if not files:
            return set()
        
        # 构建BVID-标题映射
        bvid_map = {}
        for v in videos:
            # 清理标题中的特殊字符，用于模糊匹配
            title_clean = re.sub(r'[|？！，。、\u200b\u3000\s\[\]【】《》（）]', '', v['title'])
            bvid_map[v['bvid']] = title_clean.lower()
        
        matched_bvids = set()
        
        for f in files:
            # 清理文件名: 去掉"360AI_"前缀和"_全文"后缀
            name = f.replace('360AI_', '').replace('.docx', '')
            name = re.sub(r'_全文$', '', name)
            name = re.sub(r'_简介$', '', name)
            name = re.sub(r' \(\d+\)$', '', name)  # 去掉重复文件的"(N)"
            name_clean = re.sub(r'[|？！，。、\u200b\u3000\s\[\]【】《》（）]', '', name).lower()
            
            if not name_clean:
                continue
            
            # 尝试匹配每个视频的标题
            for bvid, title_clean in bvid_map.items():
                if bvid in matched_bvids:
                    continue
                # 文件名包含标题（或反之）
                if name_clean in title_clean or title_clean in name_clean:
                    matched_bvids.add(bvid)
                    break
                # 尝试前20个字符匹配
                if len(name_clean) >= 20 and name_clean[:20] in title_clean:
                    matched_bvids.add(bvid)
                    break
                if len(title_clean) >= 20 and title_clean[:20] in name_clean:
                    matched_bvids.add(bvid)
                    break
        
        return matched_bvids
    
    def _batch_parallel_process(self, batch_videos: List[Dict]) -> List[Dict]:
        """
        并行处理一批视频（5个）
        
        流程（方案B）：
        1. 依次打开5个视频标签页，直接点击"全文"（不点AI模式，用户已提前点好）
        2. 集中等待AI分析（120秒）
        3. 用Ctrl+Tab依次切换到每个标签页，导出下载
        4. 检测下载目录文件数量，验证是否真正新增
        5. 关闭所有标签页，清理浏览器状态
        """
        import os
        results = []
        
        # 记录导出前的文件数和文件列表
        if os.path.exists(Config.DOWNLOAD_DIR):
            initial_files = set(f for f in os.listdir(Config.DOWNLOAD_DIR) if f.endswith('.docx'))
            initial_count = len(initial_files)
        else:
            initial_files = set()
            initial_count = 0
        
        self.logger.info(f"  导出前文件数: {initial_count}")
        
        # === 阶段1：依次打开每个视频，点击"全文" ===
        for i, video in enumerate(batch_videos):
            # 【停止检查】
            if self.controller and self.controller.check_stop():
                self.logger.info("⛔ 收到停止请求，中止本批处理...")
                results.append({"video": video, "success": False, "rate_limited": False})
                for remaining in batch_videos[i+1:]:
                    results.append({"video": remaining, "success": False, "rate_limited": False})
                return results
            
            bvid = video["bvid"]
            title = video["title"][:30]
            url = video["url"]
            
            self.logger.info(f"\n  [{i+1}/{len(batch_videos)}] 打开: {bvid} {title}")
            
            try:
                # 轻量检查：浏览器存在即可
                if not BrowserManager.ensure_browser_ready():
                    results.append({"video": video, "success": False, "rate_limited": False})
                    continue
                
                # 导航到视频页
                if i == 0:
                    # 第一个视频：当前标签页导航
                    nav_ok = False
                    for nav_try in range(Config.NAVIGATE_MAX_RETRY):
                        self.logger.debug(f"    导航尝试 {nav_try+1}/{Config.NAVIGATE_MAX_RETRY}")
                        if Navigator.navigate_to(url):
                            if Navigator.verify_navigation(Config.NAVIGATE_WAIT):
                                nav_ok = True
                                break
                        if nav_try < Config.NAVIGATE_MAX_RETRY - 1:
                            time.sleep(3)
                    
                    if not nav_ok:
                        self.logger.error(f"    ❌ 导航失败")
                        results.append({"video": video, "success": False, "rate_limited": False})
                        continue
                else:
                    # 后续视频：Ctrl+T新标签页 + 导航
                    BrowserManager.ensure_browser_ready()
                    time.sleep(0.3)
                    pyautogui.hotkey('ctrl', 't')
                    time.sleep(2)
                    
                    # 粘贴URL导航
                    subprocess.run(['clip'], input=url.encode('gbk'), check=True, timeout=3)
                    time.sleep(0.3)
                    x, y = Config.COORDS["地址栏"]
                    pyautogui.click(x, y)
                    time.sleep(0.5)
                    pyautogui.hotkey('ctrl', 'a')
                    time.sleep(0.3)
                    pyautogui.hotkey('ctrl', 'v')
                    time.sleep(0.5)
                    pyautogui.press('enter')
                    
                    # 验证导航
                    time.sleep(Config.NAVIGATE_WAIT)
                    info = BrowserManager.find_browser()
                    if not info or "bilibili" not in info[1].lower():
                        self.logger.error(f"    ❌ 导航失败")
                        results.append({"video": video, "success": False, "rate_limited": False})
                        continue
                
                # 导航后等待页面完全加载，再点击"全文"
                self.logger.info(f"    等待页面完全加载...")
                time.sleep(5)
                BrowserManager.ensure_browser_ready()
                time.sleep(1)
                
                # 直接点击"全文"（不点AI模式，用户已提前点好）
                self.logger.info(f"    ★ 点击「全文」...")
                BrowserManager.safe_click_coord("全文")
                
                self.logger.info(f"    ✅ 已提交AI分析请求")
                results.append({"video": video, "success": False, "rate_limited": False})
                
            except Exception as e:
                self.logger.error(f"    ❌ 异常: {type(e).__name__}: {str(e)[:50]}")
                results.append({"video": video, "success": False, "rate_limited": False})
        
        # === 阶段2：集中等待AI分析（所有视频并行）===
        self.logger.info(f"\n  🕐 集中等待AI分析 ({Config.WAIT_AI_SECONDS}秒)...")
        if Config.NIGHT_MODE:
            BrowserManager.minimize_browser()
            self.logger.info(f"  浏览器已最小化，AI分析中不打扰...")
            # 分秒等待，支持中断
            for s in range(Config.WAIT_AI_SECONDS, 0, -1):
                if self.controller and self.controller.check_stop(log=False):
                    self.logger.info("⛔ 收到停止请求，中断AI等待...")
                    break
                time.sleep(1)
            # 【关键节点】等待结束后必须恢复+最大化+确认焦点
            self.logger.info(f"  等待结束，正在恢复浏览器到前台...")
            BrowserManager.ensure_maximized_and_focused()
            time.sleep(2)
        else:
            interrupted = self._wait_with_progress(Config.WAIT_AI_SECONDS)
            if interrupted:
                self.logger.info("⛔ AI等待被中断，跳过导出...")
                return results  # 返回未完成的结果
        
        # === 阶段3：依次导出每个视频 ===
        self.logger.info(f"\n  📥 开始依次导出...")
        pending_export = []
        
        # 【关键节点】导出前确保浏览器在前台
        BrowserManager.ensure_maximized_and_focused()
        time.sleep(1)
        
        # 【关键】从第一个标签页开始，依次导出（不需要切换第一个）
        for i, item in enumerate(results):
            # 【停止检查】
            if self.controller and self.controller.check_stop():
                self.logger.info("⛔ 收到停止请求，中止导出...")
                for remaining_item in results[i:]:
                    pending_export.append({"item": remaining_item, "bvid": remaining_item["video"]["bvid"], "title": remaining_item["video"]["title"][:30]})
                break
            
            video = item["video"]
            bvid = video["bvid"]
            title = video["title"][:30]
            
            self.logger.info(f"  [{i+1}/{len(results)}] 导出: {bvid} {title}")
            
            # 切换到下一个标签页（第一个视频不需要切换）
            if i > 0:
                self.logger.info(f"    切换到下一个标签页...")
                # 【关键1】确保浏览器在前台且最大化
                BrowserManager.ensure_maximized_and_focused()
                time.sleep(0.5)
                # 【关键2】点击下载窗口关闭按钮（用户实测坐标）
                pyautogui.click(*Config.COORDS["下载关闭"])
                time.sleep(0.5)
                # 【关键3】按Esc再确保关闭
                pyautogui.press('esc')
                time.sleep(0.3)
                # 【关键4】点击浏览器视频区域获取焦点
                pyautogui.click(480, 540)
                time.sleep(0.5)
                # 【关键5】分解按键切换标签
                pyautogui.keyDown('ctrl')
                time.sleep(0.15)
                pyautogui.keyDown('shift')
                time.sleep(0.15)
                pyautogui.press('tab')
                time.sleep(0.15)
                pyautogui.keyUp('shift')
                time.sleep(0.15)
                pyautogui.keyUp('ctrl')
                time.sleep(3)
                # 【关键6】再次点击视频区域确保焦点
                pyautogui.click(480, 540)
                time.sleep(0.5)
            
            # 截图（调试用）
            BrowserManager.ensure_browser_ready()
            time.sleep(1)
            screenshot_path = self._screenshot(f"{bvid}_pre_exp")
            ai_status = self._check_ai_result(screenshot_path, bvid)
            self.logger.info(f"    AI检测结果: {ai_status}")
            
            if ai_status == 'error':
                self.logger.info(f"    ️ AI返回频率限制，但尝试继续导出...")
            
            # 点击导出
            self.logger.info(f"    ️ 点击导出...")
            pyautogui.click(*Config.COORDS["导出"])
            time.sleep(2)
            
            # 回车确认下载
            pyautogui.press('enter')
            time.sleep(5)
            
            # 备用确认
            pyautogui.click(960, 520)
            time.sleep(1)
            pyautogui.press('enter')
            time.sleep(3)
            
            pending_export.append({"item": item, "bvid": bvid, "title": title})
            self.logger.info(f"    已点击导出，待验证")
        
        # === 阶段4：批量验证下载结果 ===
        self.logger.info(f"\n  🔍 验证下载结果...")
        if os.path.exists(Config.DOWNLOAD_DIR):
            final_files = set(f for f in os.listdir(Config.DOWNLOAD_DIR) if f.endswith('.docx'))
            new_files = final_files - initial_files
            self.logger.info(f"  新增文件: {len(new_files)}个")
            for nf in sorted(new_files):
                self.logger.info(f"    + {nf}")
        else:
            new_files = set()
        
        # 分配新文件给对应视频
        if new_files:
            new_files_list = sorted(new_files)
            success_count = 0
            failed_bvids = []
            
            for idx, export_info in enumerate(pending_export):
                item = export_info["item"]
                bvid = export_info["bvid"]
                
                if idx < len(new_files_list):
                    filename = new_files_list[idx]
                    filepath = os.path.join(Config.DOWNLOAD_DIR, filename)
                    size = os.path.getsize(filepath)
                    item["success"] = True
                    item["download"] = {"filename": filename, "path": filepath, "size": size}
                    success_count += 1
                    self.logger.info(f"    ✅ {bvid} → {filename} ({size/1024:.1f}KB)")
                else:
                    item["success"] = False
                    item["rate_limited"] = True
                    failed_bvids.append(bvid)
                    self.logger.info(f"    ❌ {bvid} → 未导出成功")
            
            self.logger.info(f"  本批结果: ✅{success_count} ❌{len(failed_bvids)}")
        else:
            self.logger.info(f"  ⚠️ 无新增文件")
            for export_info in pending_export:
                item = export_info["item"]
                item["success"] = False
                item["rate_limited"] = True
                self.logger.info(f"    ❌ {export_info['bvid']} → 未导出")
        
        # === 阶段5：关闭整个浏览器（防止标签堆积影响下一批）===
        self.logger.info(f"\n   关闭整个浏览器，清理所有标签页...")
        try:
            subprocess.run(["taskkill", "/F", "/IM", "360aibrowser.exe"], 
                          capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            time.sleep(2)
            self.logger.info(f"  ✅ 浏览器已关闭")
        except:
            # 备用方案：用 Ctrl+Shift+W 关闭窗口
            self.logger.info(f"  备用方案：快捷键关闭窗口...")
            BrowserManager.ensure_browser_ready()
            time.sleep(0.5)
            pyautogui.hotkey('ctrl', 'shift', 'w')
            time.sleep(2)
        
        return results
    
    def _check_ai_result(self, screenshot_path: str, bvid: str = "") -> str:
        """检测AI分析结果（简化版）"""
        try:
            from PIL import Image, ImageStat
            img = Image.open(screenshot_path)
            gray = img.convert('L')
            stat = ImageStat.Stat(gray)
            mean = stat.mean[0]
            
            if mean < Config.AI_ERROR_BRIGHTNESS:
                self.logger.debug(f"  AI检测({bvid}): 亮度={mean:.0f} → 可能无内容")
                return 'error'
            elif mean > Config.AI_OK_BRIGHTNESS:
                self.logger.debug(f"  AI检测({bvid}): 亮度={mean:.0f} → 可能有内容")
                return 'likely_ok'
            else:
                self.logger.debug(f"  AI检测({bvid}): 亮度={mean:.0f} → 不确定")
                return 'unknown'
        except:
            return 'unknown'
    
    def _check_download(self, bvid: str) -> Optional[Dict]:
        """检查下载结果（简单版）"""
        import os
        if not os.path.exists(Config.DOWNLOAD_DIR):
            return None
        
        files = [f for f in os.listdir(Config.DOWNLOAD_DIR) if f.endswith('.docx')]
        if not files:
            return None
        
        # 找最新的docx文件
        latest = max(files, key=lambda f: os.path.getmtime(os.path.join(Config.DOWNLOAD_DIR, f)))
        filepath = os.path.join(Config.DOWNLOAD_DIR, latest)
        size = os.path.getsize(filepath)
        
        if size > Config.MIN_FILE_SIZE:
            return {"filename": latest, "path": filepath, "size": size}
        return None
    
    def _screenshot(self, name: str) -> str:
        """截图"""
        import pyautogui
        path = str(Config.SCREENSHOT_DIR / f"v51_{name}.png")
        try:
            pyautogui.screenshot(path)
        except:
            pass
        return path
    
    def _wait_with_progress(self, seconds: int):
        """等待并显示进度（每15秒检查一次停止信号）"""
        for i in range(seconds, 0, -15):
            if i % 30 == 0:
                self.logger.info(f"    {i}s...")
            if self.controller and self.controller.check_stop(log=False):
                self.logger.info("⛔ 收到停止请求，中断等待...")
                return True  # 返回True表示被中断
            time.sleep(15)
        return False  # 正常完成
    
    def run(self, max_count: int = None, selected_only: bool = False):
        """执行批量处理
        
        Args:
            max_count: 最大处理数量（测试用）
            selected_only: True=只处理用户选中的视频, False=处理所有待处理
        """
        # 检查是否有用户选中的视频
        if selected_only:
            videos = self.load_selected_videos()
            if not videos:
                self.logger.warning("⚠️ 未找到选中视频列表(selected_videos.json)")
                self.logger.info("提示: 请先运行 scripts/view_manifest.py --select 选择视频")
                return
            mode_name = "选中视频处理"
            total_all = len(self.load_video_list())
        else:
            videos = self.load_video_list()
            mode_name = "全量批量处理"
            total_all = len(videos)
        
        total = len(videos)
        self.logger.info(f"=" * 60)
        self.logger.info(f"bili2doc 批量处理 v51 (并行模式)")
        self.logger.info(f"=" * 60)
        self.logger.info(f"处理模式: {mode_name}")
        self.logger.info(f"总视频数: {total_all}")
        self.logger.info(f"本次处理: {total}个")
        self.logger.info(f"夜间模式: {'开启' if Config.NIGHT_MODE else '关闭'}")
        self.logger.info(f"并行策略: 每批5个，先集中点击全文，再集中等待，最后依次导出")
        
        # 【关键改动】不再依赖 batch_state.json 判断已完成，改为扫描下载目录
        # 1. 扫描下载目录，找出已下载的文件
        downloaded_bvids = self._scan_downloaded_bvids(videos)
        self.logger.info(f"📂 下载目录已存在: {len(downloaded_bvids)}个文件")
        
        # 2. 加载状态文件（仅用于获取失败列表）
        state = self.load_state()
        failed_set = set(state.get("failed", []))
        
        # 3. 构建待处理队列：排除已下载的文件
        if selected_only:
            # 选中模式：直接处理选中列表，不过滤
            pending = videos
            self.logger.info(f"选中视频: {len(pending)}个")
        else:
            # 全量模式：过滤已下载的（不依赖 batch_state.json 的 completed）
            pending = [
                v for v in videos 
                if v["bvid"] not in downloaded_bvids and v["bvid"] not in failed_set
            ]
            self.logger.info(f"下载目录已匹配: {len(downloaded_bvids)}个，失败列表: {len(failed_set)}个")
        
        if max_count:
            pending = pending[:max_count]
        
        if not pending:
            self.logger.info("✅ 没有待处理视频！全部已完成。")
            return
        
        self.logger.info(f"待处理: {len(pending)}个 (已下载{len(downloaded_bvids)}, 失败{len(failed_set)})")
        
        batches = (len(pending) + Config.BATCH_SIZE - 1) // Config.BATCH_SIZE
        self.logger.info(f"计划: {batches}批 | 每批{Config.BATCH_SIZE}个")
        
        # 启动浏览器
        self.logger.info("\n启动浏览器...")
        BrowserManager.restart("启动前重启")
        
        # 启动停止监听
        self.controller.start_listener(self.logger)
        
        # 关键修复：关闭豆包主页标签（Tab 1），让视频占据Tab 1-5
        self.logger.info("★ 关闭豆包主页标签...")
        # 【关键】先确认浏览器已打开、最大化、前台激活，再操作
        BrowserManager.ensure_maximized_and_focused()
        time.sleep(0.5)
        pyautogui.hotkey('ctrl', 'w')  # 关闭豆包标签
        time.sleep(2)
        # 关闭后再次确认浏览器就绪
        BrowserManager.ensure_maximized_and_focused()
        time.sleep(0.5)
        
        # 注意：关闭豆包后，后续打开的5个视频会自动占据Tab 1-5
        
        # 夜间模式：初始最小化
        if Config.NIGHT_MODE:
            BrowserManager.minimize_browser()
            self.logger.info("浏览器已最小化，夜间模式运行中...")
        
        # 统计
        stats = {"success": 0, "failed": 0, "attempts": 0}
        rl_retry = 0  # 频率限制累计计数
        since_restart = 0
        start_time = time.time()
        
        for batch_num in range(batches):
            bs = batch_num * Config.BATCH_SIZE
            be = min(bs + Config.BATCH_SIZE, len(pending))
            batch_videos = pending[bs:be]
            
            # 【停止检查】每批开始前检查
            if self.controller.check_stop():
                self.logger.info("⛔ 收到停止请求，退出批量处理...")
                break
            
            self.logger.info(f"\n{'='*55}")
            self.logger.info(f"【第{batch_num+1}/{batches}批】 #{bs+1}-{be}")
            self.logger.info(f"{'='*55}")
            
            # 频率限制冷却
            if rl_retry > 0:
                cooldown = self._get_cooldown(rl_retry - 1)
                self.logger.info(f"\n 频率限制冷却: {cooldown//60}分钟")
                interrupted = self._countdown(cooldown, "冷却恢复")
                if interrupted:
                    self.logger.info("⛔ 冷却期间收到停止请求，退出...")
                    break
            
            # 定期重启浏览器
            if since_restart >= Config.RESTART_EVERY_N:
                self.logger.info(f"\n🔄 定期重启浏览器 (已处理{since_restart}个)")
                BrowserManager.restart("定期")
                since_restart = 0
            
            # 并行处理本批视频
            batch_results = self._batch_parallel_process(batch_videos)
            
            # 更新统计
            for item in batch_results:
                video = item["video"]
                bvid = video["bvid"]
                stats["attempts"] += 1
                since_restart += 1
                
                if item["success"]:
                    stats["success"] += 1
                    rl_retry = 0
                    
                    # 【关键】不再更新 batch_state.json，停止时不会留下错误状态
                    # 下次启动时通过扫描下载目录判断已完成
                    
                    elapsed = (time.time() - start_time) / 60
                    self.logger.info(f"\n  🎉 第{stats['success']}个完成! 用时{elapsed:.0f}分")
                else:
                    stats["failed"] += 1
                    is_rl = item.get("rate_limited", False)
                    if is_rl:
                        rl_retry += 1
                        next_cd = self._get_cooldown(rl_retry)
                        self.logger.info(f"  ⚠️ 频率限制(第{rl_retry}次)")
                        self.logger.info(f"  ⏳ 立即冷却 {next_cd//60}分钟...")
                        interrupted = self._countdown(next_cd, "频限冷却")
                        if interrupted:
                            self.logger.info(" 冷却期间收到停止请求，退出...")
                            break
                    else:
                        self.logger.info(f"  ❌ 处理失败 (非频率限制)")
                        interrupted = self._countdown(300, "失败冷却")
                        if interrupted:
                            self.logger.info("⛔ 冷却期间收到停止请求，退出...")
                            break
            
            # 批次间无需额外延迟（浏览器已关闭重启，自带5秒冷却）
            
            # 保存执行状态记录
            self._save_execution_log(batch_num, batch_results, stats, f"第{batch_num+1}批完成")
        
        # 生成报告
        report = ReportGenerator.generate_report(stats, state, start_time, total)
        
        # 失败重试：收集所有未成功的视频
        completed_set = set(state.get("completed", []))
        failed_bvids = [v for v in pending if v["bvid"] not in completed_set]
        
        if failed_bvids:
            self.logger.info(f"\n{'='*55}")
            self.logger.info(f"🔄 失败重试阶段")
            self.logger.info(f"待重试: {len(failed_bvids)}个视频")
            self.logger.info(f"{'='*55}")
            
            # 冷却10秒后开始重试
            interrupted = self._countdown(10, "重试前冷却")
            if interrupted:
                self.logger.info(" 冷却期间收到停止请求，跳过重试...")
                failed_bvids = []
            
            # 重启浏览器
            BrowserManager.restart("重试阶段重启")
            
            # 重新执行重试（最多2轮）
            for retry_round in range(2):
                retry_batches = (len(failed_bvids) + Config.BATCH_SIZE - 1) // Config.BATCH_SIZE
                self.logger.info(f"\n--- 重试第{retry_round+1}轮: {len(failed_bvids)}个视频, {retry_batches}批 ---")
                
                still_failed = []
                
                for rb in range(retry_batches):
                    rbs = rb * Config.BATCH_SIZE
                    rbe = min(rbs + Config.BATCH_SIZE, len(failed_bvids))
                    retry_batch = failed_bvids[rbs:rbe]
                    
                    self.logger.info(f"\n  重试批 [{rb+1}/{retry_batches}] #{rbs+1}-{rbe}")
                    batch_results = self._batch_parallel_process(retry_batch)
                    
                    for item in batch_results:
                        bvid = item["video"]["bvid"]
                        if item["success"]:
                            stats["success"] += 1
                            # 【关键】不再更新 batch_state.json
                            self.logger.info(f"    🎉 {bvid} 重试成功!")
                        else:
                            still_failed.append(item["video"])
                            self.logger.info(f"    ❌ {bvid} 重试仍失败")
                    
                    # 批次间延迟
                    if rb < retry_batches - 1:
                        self._countdown(30, "重试批间延迟")
                
                failed_bvids = still_failed
                if not failed_bvids:
                    self.logger.info(f"\n✅ 所有重试完成，全部成功!")
                    break
                
                # 如果不是最后一轮，冷却后继续
                if retry_round < 1:
                    self.logger.info(f"\n⏳ 冷却后进入下一轮重试...")
                    self._countdown(120, "轮间冷却")
            
            # 最终失败列表
            if failed_bvids:
                state["failed"] = list(set(state.get("failed", []) + [v["bvid"] for v in failed_bvids]))
                self.save_state(state)
                self.logger.info(f"\n⚠️ {len(failed_bvids)}个视频重试后仍失败，已记录")
        
        # 最终报告
        total_time = (time.time() - start_time) / 60
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"批量处理完成!")
        self.logger.info(f"{'='*60}")
        self.logger.info(f"  成功: {stats['success']}")
        self.logger.info(f"  失败: {stats['failed']}")
        self.logger.info(f"  总尝试: {stats['attempts']}")
        self.logger.info(f"  总耗时: {total_time:.0f}分({total_time/60:.1f}h)")
        self.logger.info(f"  报告已保存: {Config.REPORT_FILE}")
        
        # 保存最终执行状态记录
        self._save_execution_log(-1, [], stats, "全部完成")
        
        # 夜间模式：最后最小化浏览器
        if Config.NIGHT_MODE:
            BrowserManager.minimize_browser()
            self.logger.info("浏览器已最小化，任务完成！")
    
    def _save_execution_log(self, batch_num: int, batch_results: List[Dict], 
                           stats: Dict, label: str = "批次完成"):
        """保存执行状态记录"""
        try:
            log = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "label": label,
                "batch": batch_num + 1,
                "batch_results": [
                    {
                        "bvid": r["video"]["bvid"],
                        "success": r["success"],
                        "rate_limited": r.get("rate_limited", False),
                        "download": r.get("download", {}).get("filename", None) if r.get("download") else None
                    }
                    for r in batch_results
                ],
                "stats": stats,
                "done": [
                    "重写_batch_parallel_process流程",
                    "去掉AI模式点击（用户已提前点好）",
                    "用Ctrl+Tab替代Ctrl+数字切换标签页",
                    "删除重复关闭豆包标签代码",
                    "safe_click_coord/safe_hotkey/safe_press改为@staticmethod",
                    f"本次处理{len(batch_results)}个视频",
                ],
                "uncertain": [
                    "Ctrl+Tab在360AI浏览器中是否能稳定切换标签（待验证）",
                    "下载文件与视频的对应关系是按顺序匹配，可能不准确",
                ],
                "pending": [
                    "验证Ctrl+Tab切换标签是否正常工作",
                    "验证5个视频并行AI分析是否都能成功导出",
                    "优化下载文件与视频的精确匹配逻辑",
                ]
            }
            
            # 追加到日志文件
            logs = []
            if Config.EXECUTION_LOG_FILE.exists():
                try:
                    with open(Config.EXECUTION_LOG_FILE, "r", encoding="utf-8") as f:
                        logs = json.load(f)
                except:
                    pass
            
            logs.append(log)
            
            with open(Config.EXECUTION_LOG_FILE, "w", encoding="utf-8") as f:
                json.dump(logs, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"📝 执行状态已保存: {Config.EXECUTION_LOG_FILE}")
        except Exception as e:
            self.logger.error(f"保存执行日志失败: {e}")

    def _get_cooldown(self, retry_count: int) -> int:
        """计算冷却时间（指数退避）"""
        return min(
            Config.RATE_LIMIT_BASE_COOLDOWN * (retry_count + 1),
            Config.RATE_LIMIT_MAX_COOLDOWN
        )
    
    def _countdown(self, seconds: int, label: str = "等待"):
        """带进度显示的倒计时（每1秒检查一次停止信号）"""
        self.logger.info(f"  {label}: {seconds}s ({seconds//60}分{seconds%60}s)")
        start = time.time()
        while time.time() - start < seconds:
            if self.controller and self.controller.check_stop(log=False):
                self.logger.info("⛔ 收到停止请求，中断倒计时...")
                return True  # 返回True表示被中断
            elapsed = int(time.time() - start)
            if elapsed % 60 == 0 and elapsed > 0:
                remaining = seconds - elapsed
                self.logger.info(f"    已等{elapsed//60}分/还需{remaining//60}分")
            time.sleep(1)
        return False  # 正常完成


# ==================== 文档整合模块 ====================
def ask_and_merge(download_dir=None):
    """
    在文档识别导出完成后，主动询问用户是否需要整合+统一格式处理
    如果用户同意，则执行文档整合操作
    
    也可以单独调用：用户说"统一格式"或"整合"时直接使用
    """
    logger = logging.getLogger("bili2doc")
    
    # 默认下载目录
    if not download_dir:
        download_dir = Config.DOWNLOAD_DIR
    
    if not os.path.exists(download_dir):
        logger.warning(f"目录不存在: {download_dir}")
        return None
    
    # 检查是否有docx文件
    docx_files = []
    for root, dirs, files in os.walk(download_dir):
        for f in files:
            if f.endswith('.docx') and not f.startswith('~'):
                docx_files.append(os.path.join(root, f))
    
    if not docx_files:
        logger.info(f"未在 {download_dir} 中找到.docx文件")
        return None
    
    logger.info(f"\n{'='*60}")
    logger.info(f"发现 {len(docx_files)} 个.docx文档")
    logger.info(f"{'='*60}")
    
    # 交互询问
    try:
        user_input = input("\n是否对这些文档进行【整合+统一格式处理】？（是/否，直接回车默认为是）: ").strip().lower()
    except (EOFError, Exception):
        # 非交互模式下自动执行
        user_input = 'y'
    
    if user_input in ('n', 'no', '否', '不用', '不需要'):
        logger.info("跳过文档整合")
        return None
    
    # 执行整合
    logger.info("\n开始文档整合...")
    try:
        from doc_merger import DocMerger
        merger = DocMerger(download_dir)
        base = os.path.basename(download_dir)
        output_name = f"{base}B站博主文章总结（整合打印版）.docx"
        result = merger.unify(output_name)
        
        if result:
            logger.info(f"\n整合完成！")
            logger.info(f"输出文件: {result}")
            
            # 自动打开文件
            try:
                import subprocess
                subprocess.Popen(['start', '', result], shell=True)
                logger.info("已自动打开文件供查看")
            except Exception:
                pass
        else:
            logger.error("整合失败")
        
        return result
        
    except ImportError as e:
        logger.error(f"缺少doc_merger模块: {e}")
        logger.error("请确保 doc_merger.py 在项目目录中")
        return None
    except Exception as e:
        logger.error(f"整合异常: {e}")
        return None


def merge_documents_standalone(target_path):
    """
    单独使用文档整合功能
    当用户说"统一格式"或"整合"时调用
    
    参数:
        target_path: 目录路径（合并目录下所有docx）或文件路径（仅格式化单个文件）
    """
    logger = logging.getLogger("bili2doc")
    logger.info(f"\n{'='*60}")
    logger.info(f"文档整合模式")
    logger.info(f"{'='*60}")
    
    if not os.path.exists(target_path):
        logger.error(f"路径不存在: {target_path}")
        return None
    
    try:
        from doc_merger import DocMerger
        
        if os.path.isdir(target_path):
            # 目录：整合目录下所有docx
            merger = DocMerger(target_path)
            base = os.path.basename(target_path)
            output_name = f"{base}B站博主文章总结（整合打印版）.docx"
            return merger.unify(output_name)
        else:
            # 单个文件：仅格式化
            merger = DocMerger()
            return merger.format_document(target_path)
            
    except Exception as e:
        logger.error(f"整合失败: {e}")
        return None


# ==================== 主入口 ====================
def main():
    """主函数"""
    # 初始化
    Config.ensure_dirs()
    logger = setup_logging()
    
    # 解析命令行
    args = sys.argv[1:]
    
    # 检查是否是本地媒体处理模式
    is_local_mode = False
    local_target = None
    if args and args[0] in ('--local-file', '--local-dir', '--local', '本地文件', '本地目录'):
        is_local_mode = True
        local_target = args[1] if len(args) > 1 else None
        
        if not local_target:
            logger.error("❌ 请指定本地文件路径或目录路径")
            logger.info("用法: python bili2doc.py --local-file <文件路径>")
            logger.info("      python bili2doc.py --local-dir <目录路径>")
            return
    
    # 检查是否是文档整合模式
    if args and args[0] in ('--merge', '--format', '--unify', '整合', '统一格式'):
        mode = args[0].lstrip('-')
        target = args[1] if len(args) > 1 else Config.DOWNLOAD_DIR
        merge_documents_standalone(target)
        return
    
    max_count = None
    night_mode = True  # 默认夜间模式
    selected_only = False
    i = 0
    while i < len(args):
        if args[i] == "--count" and i+1 < len(args):
            max_count = int(args[i+1])
            i += 2
        elif args[i] == "--day-mode":
            night_mode = False
            Config.NIGHT_MODE = False
            i += 1
        elif args[i] == "--select" or args[i] == "-s":
            selected_only = True
            i += 1
        elif args[i] == "--help" or args[i] == "-h":
            print(__doc__)
            print("用法:")
            print("  python bili2doc.py              # 夜间模式运行（默认）")
            print("  python bili2doc.py --day-mode   # 白天模式运行")
            print("  python bili2doc.py --count 5    # 只处理5个（测试用）")
            print("  python bili2doc.py --select     # 只处理用户选中的视频")
            print("  python bili2doc.py --local-file <路径> # 处理单个本地音视频文件")
            print("  python bili2doc.py --local-dir <路径>  # 处理目录下所有本地音视频")
            print("  python bili2doc.py --merge <目录> # 整合目录下所有docx")
            print("  python bili2doc.py --format <文件> # 格式化单个docx文件")
            print("  python bili2doc.py 整合          # 交互式整合文档")
            print("")
            print("本地媒体处理:")
            print("  支持格式: mp4, avi, mkv, mov, wmv, flv, webm (视频)")
            print("           mp3, wav, flac, aac, m4a, wma (音频)")
            print("  示例:")
            print("    python bili2doc.py --local-file D:\\videos\\test.mp4")
            print("    python bili2doc.py --local-dir D:\\videos\\")
            print("")
            print("交互选择流程:")
            print("  1. python scripts/view_manifest.py --select  # 选择视频")
            print("  2. python bili2doc.py --select               # 处理选中视频")
            return
        else:
            i += 1
    
    # 执行批量处理
    if is_local_mode:
        # 本地媒体处理模式
        from local_media_processor import LocalMediaBatchProcessor
        processor = LocalMediaBatchProcessor()
        processor.run(local_target, max_count=max_count)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"本地媒体处理完成！")
        logger.info(f"{'='*60}")
        ask_and_merge(Config.DOWNLOAD_DIR)
    else:
        # B站视频处理模式
        processor = BatchProcessor()
        processor.run(max_count, selected_only=selected_only)
        
        # 处理完成后，主动询问是否需要整合文档
        logger.info(f"\n{'='*60}")
        logger.info(f"视频处理全部完成！")
        logger.info(f"{'='*60}")
        
        # 询问整合
        ask_and_merge(Config.DOWNLOAD_DIR)


if __name__ == "__main__":
    main()
