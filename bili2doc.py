# -*- coding: utf-8 -*-
"""
bili2doc - B站视频AI转文字工具
================================
使用360AI浏览器的全文AI分析功能，将B站视频内容自动转录为.docx文档。

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

# ==================== 配置类 ====================
class Config:
    """项目配置管理"""
    
    # === 360AI扩展坐标（用户实测确认）===
    COORDS = {
        "全文":   (1070, 95),
        "AI模式": (1193, 86),
        "导出":   (1733, 163),
        "地址栏": (400, 55),
    }
    
    # === 路径配置 ===
    BROWSER_PATH = r"D:\360AI\360aibrowser\Application\360aibrowser.exe"
    DOWNLOAD_DIR = r"D:\360AI浏览器\下载"
    
    # === 项目根目录 ===
    PROJECT_ROOT = Path(__file__).parent.parent
    
    SCREENSHOT_DIR = PROJECT_ROOT / "screenshots"
    VIDEO_LIST_FILE = PROJECT_ROOT / "video_list.json"
    STATE_FILE = PROJECT_ROOT / "batch_state.json"
    
    # === 流程参数 ===
    WAIT_AI_SECONDS = 120          # AI分析等待时间
    NAVIGATE_WAIT = 8              # 页面加载等待
    NAVIGATE_MAX_RETRY = 3         # 导航最大重试
    
    # === 批量处理参数 ===
    BATCH_SIZE = 5                 # 每批处理数量
    RESTART_EVERY_N = 15           # 每N个视频重启浏览器
    INTER_VIDEO_DELAY = 600        # 视频间隔（秒）
    
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
    
    @classmethod
    def ensure_dirs(cls):
        """确保所有目录存在"""
        cls.SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        Path(cls.DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)


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
        """查找360AI浏览器窗口（排除Trae IDE）"""
        result = []
        
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
            
            # 识别浏览器
            is_browser = "Chrome" in cls_name or "360" in cls_name
            if w > 800 and h > 500 and len(title) > 0 and is_browser:
                lst.append((hwnd, title, w, h))
            
            return True
        
        win32gui.EnumWindows(enum_callback, result)
        
        if not result:
            return None
        
        # 优先选择360AI或包含bilibili标题的窗口
        preferred = [r for r in result if "360AI" in r[1] or "bilibili" in r[1].lower()]
        if preferred:
            return preferred[0]
        
        # 否则选择最大窗口
        result.sort(key=lambda x: x[2] * x[3], reverse=True)
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
        """重启浏览器"""
        logger = logging.getLogger("bili2doc")
        logger.info(f"浏览器{reason}...")
        
        try:
            subprocess.run(
                ["taskkill", "/IM", "360aibrowser.exe", "/F"],
                capture_output=True, timeout=10
            )
        except Exception:
            pass
        
        time.sleep(3)
        subprocess.Popen([Config.BROWSER_PATH])
        
        # 等待窗口出现
        for _ in range(30):
            time.sleep(1)
            info = cls.find_browser()
            if info:
                logger.info(f"浏览器就绪: {info[1]}")
                cls.force_foreground()
                return True
        
        logger.error("浏览器启动超时")
        return False
    
    @classmethod
    def ensure_ready(cls) -> bool:
        """确保浏览器可用"""
        info = cls.find_browser()
        if not info:
            return cls.restart("首次启动")
        cls.force_foreground()
        return True


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
    
    def __init__(self):
        self.logger = logging.getLogger("bili2doc")
    
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
            # 1. 确保浏览器可用
            if not BrowserManager.ensure_ready():
                return {"success": False, "rate_limited": False}
            
            # 2. 导航到视频页
            nav_ok = False
            for nav_try in range(Config.NAVIGATE_MAX_RETRY):
                self.logger.debug(f"导航尝试 {nav_try+1}/{Config.NAVIGATE_MAX_RETRY}")
                BrowserManager.force_foreground()
                Navigator.navigate_to(url)
                time.sleep(Config.NAVIGATE_WAIT)
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
            
            # 5. 等待AI分析
            self.logger.info(f"等待AI分析({Config.WAIT_AI_SECONDS}s)...")
            self._wait_with_progress(Config.WAIT_AI_SECONDS)
            
            BrowserManager.force_foreground()
            time.sleep(2)
            
            # 6. AI结果检测
            screenshot_path = self._screenshot(f"{bvid}_pre_exp")
            ai_status = AIAnalyzer.check_result(screenshot_path)
            
            if ai_status == 'error':
                self.logger.info("❌ AI失败(频率限制)，跳过导出")
                return {"success": False, "rate_limited": True}
            
            # 7. 记录导出前文件
            before_files = DownloadMonitor.get_current_files()
            
            # 8. 点击导出
            self.logger.info("点击「导出」...")
            self._click_coord("导出")
            
            # 9. 下载确认
            self.logger.info("回车确认下载...")
            time.sleep(2)
            BrowserManager.force_foreground()
            time.sleep(0.5)
            pyautogui.press('enter')
            time.sleep(5)
            
            # 10. 检查下载
            dl = DownloadMonitor.check_new_download(bvid, before_files)
            if dl:
                self.logger.info(f"✅ 下载成功: {dl['filename']} ({dl['size']} bytes)")
                return {"success": True, "download": dl, "rate_limited": False}
            
            # 11. 备用方案
            self.logger.info("备用下载确认...")
            BrowserManager.force_foreground()
            pyautogui.click(960, 520)
            time.sleep(1)
            pyautogui.press('enter')
            time.sleep(3)
            
            dl = DownloadMonitor.check_new_download(bvid, before_files)
            if dl:
                self.logger.info(f"✅ 备用下载成功")
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
                    BrowserManager.force_foreground()
                    pyautogui.press('enter')
                    time.sleep(2)
            
            if dl:
                self.logger.info(f"✅ 延迟下载成功: {dl['filename']}")
                return {"success": True, "download": dl, "rate_limited": False}
            
            self.logger.error("❌ 下载超时")
            self._screenshot(f"{bvid}_timeout")
            return {"success": False, "rate_limited": False}
            
        except Exception as e:
            self.logger.error(f"❌ 异常: {type(e).__name__}: {str(e)[:60]}")
            return {"success": False, "rate_limited": False}
    
    def _click_coord(self, name: str):
        """点击指定坐标"""
        BrowserManager.force_foreground()
        time.sleep(1)
        pyautogui.click(*Config.COORDS[name])
        time.sleep(2)
    
    def _screenshot(self, name: str) -> str:
        """截图"""
        path = str(Config.SCREENSHOT_DIR / f"v48_{name}.png")
        try:
            pyautogui.screenshot(path)
        except Exception:
            pass
        return path
    
    def _wait_with_progress(self, seconds: int):
        """带进度输出的等待"""
        for i in range(seconds // 15):
            time.sleep(15)
            if (i+1) % 2 == 0:
                self.logger.debug(f"  {(i+1)*15}s...")


# ==================== 批量处理 ====================
class BatchProcessor:
    """批量视频处理"""
    
    def __init__(self):
        self.logger = logging.getLogger("bili2doc")
        self.processor = VideoProcessor()
    
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
    
    def run(self, max_count: int = None):
        """执行批量处理"""
        videos = self.load_video_list()
        total = len(videos)
        self.logger.info(f"=" * 60)
        self.logger.info(f"bili2doc 批量处理 v48 (生产版)")
        self.logger.info(f"=" * 60)
        self.logger.info(f"总视频数: {total}")
        
        # 加载状态
        state = self.load_state()
        completed_set = set(state.get("completed", []))
        failed_set = set(state.get("failed", []))
        
        # 构建待处理队列
        pending = [
            v for v in videos 
            if v["bvid"] not in completed_set and v["bvid"] not in failed_set
        ]
        
        if max_count:
            pending = pending[:max_count]
        
        if not pending:
            self.logger.info("✅ 没有待处理视频！全部已完成。")
            return
        
        self.logger.info(f"待处理: {len(pending)}个 (已完成{len(completed_set)}, 失败{len(failed_set)})")
        
        batches = (len(pending) + Config.BATCH_SIZE - 1) // Config.BATCH_SIZE
        self.logger.info(f"计划: {batches}批 | 每批{Config.BATCH_SIZE}个")
        
        # 启动浏览器
        self.logger.info("\n启动浏览器...")
        BrowserManager.restart("启动前重启")
        
        # 统计
        stats = {"success": 0, "failed": 0, "attempts": 0}
        rl_retry = 0  # 频率限制累计计数
        since_restart = 0
        start_time = time.time()
        
        for batch_num in range(batches):
            bs = batch_num * Config.BATCH_SIZE
            be = min(bs + Config.BATCH_SIZE, len(pending))
            batch_videos = pending[bs:be]
            
            self.logger.info(f"\n{'='*55}")
            self.logger.info(f"【第{batch_num+1}/{batches}批】 #{bs+1}-{be}")
            self.logger.info(f"{'='*55}")
            
            for video in batch_videos:
                bvid = video["bvid"]
                
                # 频率限制冷却
                if rl_retry > 0:
                    cooldown = self._get_cooldown(rl_retry - 1)
                    self.logger.info(f"\n⏳ 频率限制冷却: {cooldown//60}分钟")
                    self._countdown(cooldown, "冷却恢复")
                
                # 定期重启浏览器
                if since_restart >= Config.RESTART_EVERY_N:
                    self.logger.info(f"\n🔄 定期重启浏览器 (已处理{since_restart}个)")
                    BrowserManager.restart("定期")
                    since_restart = 0
                
                # 处理循环（持续重试）
                done = False
                attempt = 0
                while not done:
                    stats["attempts"] += 1
                    result = self.processor.process(video, attempt)
                    since_restart += 1
                    attempt += 1
                    
                    if result["success"]:
                        done = True
                        stats["success"] += 1
                        rl_retry = 0
                        
                        # 更新状态
                        state["completed"].append(bvid)
                        if bvid in state.get("failed", []):
                            state["failed"].remove(bvid)
                        self.save_state(state)
                        
                        elapsed = (time.time() - start_time) / 60
                        self.logger.info(f"\n🎉 第{stats['success']}个完成! 用时{elapsed:.0f}分 总尝试{stats['attempts']}次")
                        
                        # 视频间延迟
                        if Config.INTER_VIDEO_DELAY > 0:
                            self._countdown(Config.INTER_VIDEO_DELAY, "间隔")
                    else:
                        is_rl = result.get("rate_limited", False)
                        if is_rl:
                            rl_retry += 1
                            next_cd = self._get_cooldown(rl_retry)
                            self.logger.info(f"⚠️ 频率限制(第{rl_retry}次)")
                            # 立即冷却
                            self.logger.info(f"⏳ 立即冷却 {next_cd//60}分钟...")
                            self._countdown(next_cd, "频限冷却")
                        else:
                            self.logger.info(f"❌ 处理失败 (非频率限制)")
                            self._countdown(300, "失败冷却")  # 5分钟
            
            # 批次小结
            elapsed = (time.time() - start_time) / 60
            remaining = len(pending) - (stats["success"] + stats["failed"])
            self.logger.info(f"\n--- 批次{batch_num+1}小结 --- ✅{stats['success']} ❌{stats['failed']} | 用时{elapsed:.0f}分")
            if remaining > 0:
                est = remaining * (elapsed / max(stats["success"] + stats["failed"], 1))
                self.logger.info(f"  剩余{remaining}个 ≈ {est:.0f}分({est/60:.1f}h)")
        
        # 最终报告
        total_time = (time.time() - start_time) / 60
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"批量处理完成!")
        self.logger.info(f"{'='*60}")
        self.logger.info(f"  成功: {stats['success']}")
        self.logger.info(f"  失败: {stats['failed']}")
        self.logger.info(f"  总尝试: {stats['attempts']}")
        self.logger.info(f"  总耗时: {total_time:.0f}分({total_time/60:.1f}h)")
    
    def _get_cooldown(self, retry_count: int) -> int:
        """计算冷却时间（指数退避）"""
        return min(
            Config.RATE_LIMIT_BASE_COOLDOWN * (retry_count + 1),
            Config.RATE_LIMIT_MAX_COOLDOWN
        )
    
    def _countdown(self, seconds: int, label: str = "等待"):
        """带进度显示的倒计时"""
        self.logger.info(f"  {label}: {seconds}s ({seconds//60}分{seconds%60}s)")
        start = time.time()
        while time.time() - start < seconds:
            elapsed = int(time.time() - start)
            if elapsed % 600 == 0 and elapsed > 0:
                remaining = seconds - elapsed
                self.logger.info(f"    已等{elapsed//60}分/还需{remaining//60}分")
            time.sleep(1)


# ==================== 主入口 ====================
def main():
    """主函数"""
    # 初始化
    Config.ensure_dirs()
    logger = setup_logging()
    
    # 解析命令行
    args = sys.argv[1:]
    max_count = None
    i = 0
    while i < len(args):
        if args[i] == "--count" and i+1 < len(args):
            max_count = int(args[i+1])
            i += 2
        elif args[i] == "--help" or args[i] == "-h":
            print(__doc__)
            print("用法:")
            print("  python bili2doc.py              # 处理全部待处理视频")
            print("  python bili2doc.py --count 5    # 只处理5个（测试用）")
            return
        else:
            i += 1
    
    # 执行批量处理
    processor = BatchProcessor()
    processor.run(max_count)


if __name__ == "__main__":
    main()
