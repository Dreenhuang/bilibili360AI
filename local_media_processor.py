# -*- coding: utf-8 -*-
"""
local_media_processor.py - 本地音视频转文字工具
================================================
使用360AI浏览器的全文AI分析功能，将本地视频/音频文件自动转录为.docx文档。

核心流程：
1. 启动360AI浏览器
2. 通过Ctrl+O打开本地文件对话框
3. 选择视频/音频文件
4. 等待文件加载
5. 点击「全文」按钮触发AI分析
6. 等待AI分析完成
7. 点击「导出」保存为.docx文档

支持的格式：
- 视频：mp4, avi, mkv, mov, wmv, flv, webm
- 音频：mp3, wav, flac, aac, m4a, wma

作者：Qwen3.6-Plus + Trae IDE
创建日期：2026-06-03
"""

import os
import sys
import time
import glob
from pathlib import Path
from typing import Optional, List, Dict

# 导入主程序的核心模块
from bili2doc import (
    Config,
    BrowserManager,
    AIAnalyzer,
    DownloadMonitor,
    setup_logging
)
import pyautogui
import win32gui
import win32con
import ctypes
import subprocess
import logging

# ==================== 本地媒体处理器 ====================

class LocalMediaProcessor:
    """本地音视频文件处理"""
    
    # 支持的文件格式
    SUPPORTED_VIDEO = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm'}
    SUPPORTED_AUDIO = {'.mp3', '.wav', '.flac', '.aac', '.m4a', '.wma'}
    SUPPORTED_FORMATS = SUPPORTED_VIDEO | SUPPORTED_AUDIO
    
    # 坐标配置（基于1920x1080）
    COORDS = {
        "打开文件": (100, 100),  # 浏览器菜单打开文件按钮坐标（需要实测校准）
        "全文": (1070, 95),      # 复用bili2doc的全文坐标
        "导出": (1733, 163),     # 复用bili2doc的导出坐标
    }
    
    def __init__(self):
        self.logger = logging.getLogger("bili2doc")
    
    def scan_local_files(self, source_path: str) -> List[Dict]:
        """
        扫描本地音视频文件
        
        参数:
            source_path: 单个文件路径 或 目录路径
            
        返回:
            文件列表 [{'index': 1, 'filename': 'test.mp4', 'path': '...'}, ...]
        """
        files = []
        
        if os.path.isfile(source_path):
            # 单文件模式
            ext = os.path.splitext(source_path)[1].lower()
            if ext in self.SUPPORTED_FORMATS:
                files.append({
                    'index': 1,
                    'filename': os.path.basename(source_path),
                    'path': os.path.abspath(source_path),
                    'type': 'video' if ext in self.SUPPORTED_VIDEO else 'audio'
                })
        elif os.path.isdir(source_path):
            # 目录模式：扫描目录下所有支持的音视频文件
            for root, dirs, filenames in os.walk(source_path):
                for filename in sorted(filenames):
                    ext = os.path.splitext(filename)[1].lower()
                    if ext in self.SUPPORTED_FORMATS:
                        files.append({
                            'index': len(files) + 1,
                            'filename': filename,
                            'path': os.path.abspath(os.path.join(root, filename)),
                            'type': 'video' if ext in self.SUPPORTED_VIDEO else 'audio'
                        })
        
        self.logger.info(f"扫描完成: 发现 {len(files)} 个音视频文件")
        return files
    
    def open_local_file(self, file_path: str) -> bool:
        """
        在地址栏粘贴本地文件路径打开文件（和B站导航一样的方式）
        
        参数:
            file_path: 要打开的文件绝对路径
            
        返回:
            是否成功打开
        """
        try:
            self.logger.info(f"打开本地文件: {file_path}")
            
            # 1. 确保浏览器在前台
            BrowserManager.restore_browser()
            time.sleep(1)
            
            # 2. 用 win32clipboard 复制中文路径到剪贴板（确保UTF-16编码）
            import win32clipboard
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(file_path, win32clipboard.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
            time.sleep(0.3)
            
            # 3. 点击地址栏
            x, y = Config.COORDS["地址栏"]
            pyautogui.click(x, y)
            time.sleep(0.5)
            
            # 4. 全选→粘贴→回车
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.3)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
            pyautogui.press('enter')
            
            # 5. 等待文件加载（短等待）
            self.logger.info("等待文件加载...")
            time.sleep(2)
            
            # 6. 如果弹出确认对话框，回车确认
            pyautogui.press('enter')
            time.sleep(1)
            
            self.logger.info("✅ 文件已打开并加载")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 打开文件失败: {type(e).__name__}: {str(e)}")
            return False
    
    def process_single_file(self, file_info: Dict) -> Dict:
        """
        处理单个本地媒体文件
        
        参数:
            file_info: {'index': 1, 'filename': 'test.mp4', 'path': '...', 'type': 'video'}
            
        返回:
            {'success': bool, 'rate_limited': bool, 'download': dict|None}
        """
        filename = file_info['filename']
        file_path = file_info['path']
        file_type = file_info['type']
        
        self.logger.info(f"\n{'='*50}")
        self.logger.info(f"处理: #{file_info['index']} {filename} ({file_type})")
        self.logger.info(f"{'='*50}")
        
        try:
            # 1. 确保浏览器可用
            if Config.NIGHT_MODE:
                BrowserManager.restore_browser()
            else:
                BrowserManager.force_foreground()
            
            if not BrowserManager.ensure_ready():
                return {"success": False, "rate_limited": False, "file": filename}
            
            # 2. 打开本地文件（地址栏粘贴路径）
            if not self.open_local_file(file_path):
                return {"success": False, "rate_limited": False, "file": filename}
            
            # 3. 等待页面渲染（短等待，让播放器加载完成）
            self.logger.info("等待页面渲染...")
            BrowserManager.restore_browser()
            time.sleep(5)
            
            # 4. 点击「全文」按钮（立即触发AI分析，与B站流程一致）
            self.logger.info("★ 点击「全文」触发AI分析...")
            BrowserManager.safe_click_coord("全文")
            
            # 5. 等待AI分析完成（与B站视频相同的等待时间）
            self.logger.info(f"等待AI全文分析({Config.WAIT_AI_SECONDS}s)...")
            
            if Config.NIGHT_MODE:
                BrowserManager.minimize_browser()
                self.logger.info("浏览器已最小化，AI分析中不打扰...")
                time.sleep(Config.WAIT_AI_SECONDS)
                BrowserManager.restore_browser()
                time.sleep(2)
            else:
                for i in range(Config.WAIT_AI_SECONDS // 15):
                    time.sleep(15)
                    if (i+1) % 4 == 0:
                        self.logger.debug(f"  {(i+1)*15}s...")
            
            # 6. AI结果检测（仅作参考，不拦截流程，始终执行导出）
            self.logger.info("截取AI分析结果（仅作参考）...")
            BrowserManager.restore_browser()
            time.sleep(2)
            
            screenshot_path = self._screenshot(f"{Path(filename).stem}_pre_exp")
            ai_status = AIAnalyzer.check_result(screenshot_path)
            
            if ai_status == 'error':
                self.logger.info("⚠️ AI检测疑似异常，但继续执行导出...")
            else:
                self.logger.info(f"AI检测结果: {ai_status}")
            
            # 7. 记录导出前文件列表
            before_files = DownloadMonitor.get_current_files()
            
            # 8. 点击「导出」（无论AI检测结果如何，都执行导出）
            self.logger.info("★ 点击「导出」...")
            x, y = Config.COORDS["导出"]
            pyautogui.click(x, y)
            time.sleep(2)
            
            # 9. 回车确认下载
            self.logger.info("回车确认下载...")
            if Config.NIGHT_MODE:
                BrowserManager.restore_browser()
            pyautogui.press('enter')
            time.sleep(5)
            
            # 10. 检查下载结果
            dl = DownloadMonitor.check_new_download(Path(filename).stem, before_files)
            if dl:
                self.logger.info(f"✅ 下载成功: {dl['filename']} ({dl['size']/1024:.1f}KB)")
                if Config.NIGHT_MODE:
                    BrowserManager.minimize_browser()
                return {"success": True, "download": dl, "rate_limited": False, "file": filename}
            
            # 11. 备用方案
            self.logger.info("备用下载确认...")
            if Config.NIGHT_MODE:
                BrowserManager.restore_browser()
            pyautogui.click(960, 520)
            time.sleep(1)
            pyautogui.press('enter')
            time.sleep(3)
            
            dl = DownloadMonitor.check_new_download(Path(filename).stem, before_files)
            if dl:
                self.logger.info(f"✅ 备用下载成功")
                if Config.NIGHT_MODE:
                    BrowserManager.minimize_browser()
                return {"success": True, "download": dl, "rate_limited": False, "file": filename}
            
            # 12. 长时间监控
            self.logger.info(f"监控下载({Config.DOWNLOAD_MONITOR_SECONDS}s)...")
            for i in range(Config.DOWNLOAD_MONITOR_SECONDS // 5):
                time.sleep(5)
                dl = DownloadMonitor.check_new_download(Path(filename).stem, before_files)
                if dl:
                    break
                if (i+1) % 6 == 0 and i < 15:
                    if Config.NIGHT_MODE:
                        BrowserManager.restore_browser()
                    pyautogui.press('enter')
                    time.sleep(2)
            
            if dl:
                self.logger.info(f"✅ 延迟下载成功: {dl['filename']}")
                if Config.NIGHT_MODE:
                    BrowserManager.minimize_browser()
                return {"success": True, "download": dl, "rate_limited": False, "file": filename}
            
            self.logger.error("❌ 下载超时")
            self._screenshot(f"{Path(filename).stem}_timeout")
            if Config.NIGHT_MODE:
                BrowserManager.minimize_browser()
            return {"success": False, "rate_limited": False, "file": filename}
            
        except Exception as e:
            self.logger.error(f"❌ 处理异常: {type(e).__name__}: {str(e)}")
            if Config.NIGHT_MODE:
                BrowserManager.minimize_browser()
            return {"success": False, "rate_limited": False, "file": filename}
    
    def _screenshot(self, name: str) -> str:
        """截图"""
        path = str(Config.SCREENSHOT_DIR / f"local_{name}.png")
        try:
            pyautogui.screenshot(path)
        except Exception:
            pass
        return path


# ==================== 批量处理 ====================

class LocalMediaBatchProcessor:
    """本地媒体批量处理"""
    
    def __init__(self):
        self.logger = logging.getLogger("bili2doc")
        self.processor = LocalMediaProcessor()
    
    def run(self, source_path: str, max_count: int = None):
        """
        执行本地媒体处理
        
        参数:
            source_path: 单个文件路径 或 目录路径
            max_count: 最大处理数量（测试用）
        """
        Config.ensure_dirs()
        
        # 1. 扫描文件
        files = self.processor.scan_local_files(source_path)
        if not files:
            self.logger.error(f"未找到支持的音视频文件: {source_path}")
            self.logger.info(f"支持的格式: {', '.join(sorted(LocalMediaProcessor.SUPPORTED_FORMATS))}")
            return
        
        # 2. 限制数量
        if max_count:
            files = files[:max_count]
        
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"本地媒体处理模式")
        self.logger.info(f"{'='*60}")
        self.logger.info(f"待处理文件: {len(files)}个")
        self.logger.info(f"夜间模式: {'开启' if Config.NIGHT_MODE else '关闭'}")
        
        # 3. 打印文件清单
        for f in files:
            self.logger.info(f"  #{f['index']} {f['filename']} ({f['type']})")
        
        # 4. 启动浏览器
        self.logger.info("\n启动浏览器...")
        BrowserManager.restart("本地媒体处理启动")
        
        # 5. 夜间模式：初始最小化
        if Config.NIGHT_MODE:
            BrowserManager.minimize_browser()
            self.logger.info("浏览器已最小化，夜间模式运行中...")
        
        # 6. 统计
        stats = {"success": 0, "failed": 0, "rate_limited": 0}
        start_time = time.time()
        
        # 7. 依次处理每个文件
        for i, file_info in enumerate(files):
            self.logger.info(f"\n【{i+1}/{len(files)}】处理: {file_info['filename']}")
            
            result = self.processor.process_single_file(file_info)
            
            if result['success']:
                stats['success'] += 1
            elif result.get('rate_limited'):
                stats['rate_limited'] += 1
                # 频率限制：冷却30分钟
                self.logger.info(f"⚠️ 频率限制，冷却30分钟...")
                time.sleep(1800)
            else:
                stats['failed'] += 1
            
            # 文件间延迟（避免频率限制）
            if i < len(files) - 1:
                self.logger.info(f"等待30秒后处理下一个文件...")
                time.sleep(30)
            
            # 每处理5个文件重启浏览器
            if (i + 1) % 5 == 0 and i < len(files) - 1:
                self.logger.info(f"\n🔄 定期重启浏览器...")
                BrowserManager.restart("定期重启")
        
        # 8. 完成报告
        total_time = (time.time() - start_time) / 60
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"本地媒体处理完成!")
        self.logger.info(f"{'='*60}")
        self.logger.info(f"  成功: {stats['success']}")
        self.logger.info(f"  失败: {stats['failed']}")
        self.logger.info(f"  频率限制: {stats['rate_limited']}")
        self.logger.info(f"  总耗时: {total_time:.0f}分({total_time/60:.1f}h)")
        
        # 9. 夜间模式：最后最小化
        if Config.NIGHT_MODE:
            BrowserManager.minimize_browser()
            self.logger.info("浏览器已最小化，任务完成！")
