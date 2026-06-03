# -*- coding: utf-8 -*-
"""
下载清单管理模块
================
功能：
1. 生成下载清单（从video_list.json）
2. 核对已下载文件
3. 查漏、去重
4. 生成进度总结报告

作者：GLM-5V-Turbo + Trae IDE
创建日期：2026-06-03
"""

import os
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple


# ==================== 配置 ====================
class ManifestConfig:
    """清单配置"""
    PROJECT_ROOT = Path(__file__).parent.parent
    VIDEO_LIST_FILE = PROJECT_ROOT / "video_list.json"
    BATCH_STATE_FILE = PROJECT_ROOT / "batch_state.json"
    MANIFEST_FILE = PROJECT_ROOT / "download_manifest.json"
    DOWNLOAD_DIR = r"D:\360AI浏览器\下载"
    SUMMARY_FILE = PROJECT_ROOT / "download_summary.json"


# ==================== 下载清单管理 ====================
class DownloadManifest:
    """下载清单管理器"""
    
    def __init__(self):
        self.video_list = []
        self.completed = []
        self.failed = []
        self.downloaded_files = set()
        self.manifest = {
            "generated_at": "",
            "total_videos": 0,
            "videos": [],
            "download_mapping": {},
            "status": {}
        }
    
    def load_video_list(self) -> List[Dict]:
        """加载视频列表"""
        if not ManifestConfig.VIDEO_LIST_FILE.exists():
            raise FileNotFoundError(f"视频列表文件不存在: {ManifestConfig.VIDEO_LIST_FILE}")
        
        with open(ManifestConfig.VIDEO_LIST_FILE, "r", encoding="utf-8") as f:
            self.video_list = json.load(f)
        
        return self.video_list
    
    def load_batch_state(self) -> Dict:
        """加载批量处理状态"""
        if ManifestConfig.BATCH_STATE_FILE.exists():
            with open(ManifestConfig.BATCH_STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
            self.completed = state.get("completed", [])
            self.failed = state.get("failed", [])
        return {"completed": self.completed, "failed": self.failed}
    
    def scan_downloaded_files(self) -> Set[str]:
        """扫描下载目录，获取已下载的docx文件"""
        download_dir = ManifestConfig.DOWNLOAD_DIR
        if not os.path.exists(download_dir):
            return set()
        
        files = set()
        for f in os.listdir(download_dir):
            if f.endswith('.docx'):
                files.add(f)
        
        self.downloaded_files = files
        return files
    
    def extract_bvid_from_filename(self, filename: str) -> Optional[str]:
        """从文件名提取BV号（文件名通常包含BV号）"""
        # 常见格式：BV1Vb9hBVE4C.docx 或 视频标题_BV1Vb9hBVE4C.docx
        match = re.search(r'(BV[a-zA-Z0-9]{10})', filename)
        if match:
            return match.group(1)
        return None
    
    def generate_manifest(self) -> Dict:
        """生成完整下载清单"""
        # 加载数据
        self.load_video_list()
        self.load_batch_state()
        self.scan_downloaded_files()
        
        # 构建清单
        self.manifest = {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_videos": len(self.video_list),
            "download_dir": ManifestConfig.DOWNLOAD_DIR,
            "videos": [],
            "download_mapping": {},
            "status": {
                "completed": [],
                "downloaded": [],
                "failed": [],
                "pending": [],
                "duplicate_files": []
            }
        }
        
        # 构建BV号到文件名的映射
        bvid_to_files = {}
        for filename in self.downloaded_files:
            bvid = self.extract_bvid_from_filename(filename)
            if bvid:
                if bvid not in bvid_to_files:
                    bvid_to_files[bvid] = []
                bvid_to_files[bvid].append(filename)
        
        self.manifest["download_mapping"] = bvid_to_files
        
        # 构建每个视频的状态
        completed_set = set(self.completed)
        failed_set = set(self.failed)
        
        for video in self.video_list:
            bvid = video["bvid"]
            title = video.get("title", "")
            index = video.get("index", 0)
            url = video.get("url", "")
            
            # 判断状态并填充downloaded状态
            if bvid in completed_set:
                status = "completed"
            elif bvid in failed_set:
                status = "failed"
            elif bvid in bvid_to_files:
                status = "downloaded"  # 填充downloaded状态
            else:
                status = "pending"
            
            video_entry = {
                "index": index,
                "bvid": bvid,
                "title": title,
                "url": url,
                "status": status,
                "downloaded_files": bvid_to_files.get(bvid, []),
                "file_count": len(bvid_to_files.get(bvid, []))
            }
            
            self.manifest["videos"].append(video_entry)
            self.manifest["status"][status].append(bvid)
        
        # 检测重复文件
        duplicates = []
        for bvid, files in bvid_to_files.items():
            if len(files) > 1:
                duplicates.append({
                    "bvid": bvid,
                    "files": files,
                    "count": len(files)
                })
        
        self.manifest["status"]["duplicate_files"] = duplicates
        
        # 保存清单
        self.save_manifest()
        
        return self.manifest
    
    def save_manifest(self):
        """保存清单到文件"""
        with open(ManifestConfig.MANIFEST_FILE, "w", encoding="utf-8") as f:
            json.dump(self.manifest, f, ensure_ascii=False, indent=2)
    
    def check_and_report(self) -> Dict:
        """核对清单并生成报告"""
        if not self.manifest.get("videos"):
            self.generate_manifest()
        
        total = self.manifest["total_videos"]
        status = self.manifest["status"]
        
        completed_count = len(status["completed"])
        downloaded_count = len(status["downloaded"])
        failed_count = len(status["failed"])
        pending_count = len(status["pending"])
        duplicate_count = len(status["duplicate_files"])
        
        # 计算实际已处理（包含已下载但未标记完成的）
        actual_done = completed_count + downloaded_count
        
        report = {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "summary": {
                "total_videos": total,
                "completed_marked": completed_count,
                "downloaded_not_marked": downloaded_count,
                "actual_done": actual_done,
                "failed": failed_count,
                "pending": pending_count,
                "duplicates": duplicate_count,
                "progress_percent": round(actual_done / total * 100, 1) if total > 0 else 0
            },
            "duplicates": status["duplicate_files"],
            "failed_list": [],
            "pending_list": []
        }
        
        # 生成失败列表详情
        for bvid in status["failed"]:
            video = next((v for v in self.manifest["videos"] if v["bvid"] == bvid), None)
            if video:
                report["failed_list"].append({
                    "index": video["index"],
                    "bvid": bvid,
                    "title": video["title"][:50]
                })
        
        # 生成待处理列表详情
        for bvid in status["pending"]:
            video = next((v for v in self.manifest["videos"] if v["bvid"] == bvid), None)
            if video:
                report["pending_list"].append({
                    "index": video["index"],
                    "bvid": bvid,
                    "title": video["title"][:50]
                })
        
        # 保存总结报告
        with open(ManifestConfig.SUMMARY_FILE, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        return report
    
    def get_pending_videos(self) -> List[Dict]:
        """获取待处理视频列表（排除已完成和已下载的）"""
        if not self.manifest.get("videos"):
            self.generate_manifest()
        
        pending = []
        for video in self.manifest["videos"]:
            if video["status"] == "pending":
                pending.append(video)
        
        return pending
    
    def get_next_batch(self, batch_size: int = 5) -> List[Dict]:
        """获取下一批待处理视频"""
        pending = self.get_pending_videos()
        return pending[:batch_size]
    
    def mark_completed(self, bvid: str, filename: str = ""):
        """标记视频为已完成"""
        # 更新batch_state.json
        if ManifestConfig.BATCH_STATE_FILE.exists():
            with open(ManifestConfig.BATCH_STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
        else:
            state = {"completed": [], "failed": []}
        
        if bvid not in state["completed"]:
            state["completed"].append(bvid)
        if bvid in state["failed"]:
            state["failed"].remove(bvid)
        
        with open(ManifestConfig.BATCH_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        
        # 更新清单
        for video in self.manifest["videos"]:
            if video["bvid"] == bvid:
                video["status"] = "completed"
                if filename:
                    if filename not in video["downloaded_files"]:
                        video["downloaded_files"].append(filename)
                    video["file_count"] = len(video["downloaded_files"])
                break
    
    def print_summary(self):
        """打印可读的总结报告"""
        report = self.check_and_report()
        summary = report["summary"]
        
        print("\n" + "=" * 60)
        print(f"📋 B站视频下载清单核对报告")
        print(f"   生成时间: {report['generated_at']}")
        print("=" * 60)
        print(f"  总视频数: {summary['total_videos']}")
        print(f"  已完成(已标记): {summary['completed_marked']}")
        print(f"  已下载(未标记): {summary['downloaded_not_marked']}")
        print(f"  实际已完成: {summary['actual_done']}")
        print(f"  失败: {summary['failed']}")
        print(f"  待处理: {summary['pending']}")
        print(f"  重复文件: {summary['duplicates']} 组")
        print(f"  进度: {summary['progress_percent']}%")
        print("=" * 60)
        
        if report["duplicates"]:
            print(f"\n⚠️ 重复文件 ({len(report['duplicates'])}组):")
            for dup in report["duplicates"][:5]:
                print(f"  {dup['bvid']}: {dup['count']}个文件")
                for f in dup["files"][:3]:
                    print(f"    - {f}")
                if dup['count'] > 3:
                    print(f"    ... 等{dup['count']}个文件")
        
        if report["failed_list"]:
            print(f"\n❌ 失败视频 ({len(report['failed_list'])}个):")
            for v in report["failed_list"][:10]:
                print(f"  #{v['index']} {v['bvid']} - {v['title']}")
            if len(report["failed_list"]) > 10:
                print(f"  ... 等{len(report['failed_list'])}个")
        
        if report["pending_list"]:
            print(f"\n⏳ 待处理视频 ({len(report['pending_list'])}个):")
            for v in report["pending_list"][:10]:
                print(f"  #{v['index']} {v['bvid']} - {v['title']}")
            if len(report["pending_list"]) > 10:
                print(f"  ... 等{len(report['pending_list'])}个")
        
        print("\n" + "=" * 60)
        
        return report


# ==================== 主函数 ====================
def main():
    """主函数：生成清单并打印报告"""
    manifest = DownloadManifest()
    
    try:
        print("🔍 正在生成下载清单...")
        manifest.generate_manifest()
        report = manifest.print_summary()
        
        print(f"\n📁 清单已保存: {ManifestConfig.MANIFEST_FILE}")
        print(f"📊 报告已保存: {ManifestConfig.SUMMARY_FILE}")
        
        return report
        
    except FileNotFoundError as e:
        print(f"❌ 错误: {e}")
        print("请先运行视频列表提取脚本: python scripts/extract_videos.py")
        return None


if __name__ == "__main__":
    main()
