# -*- coding: utf-8 -*-
"""
视频列表提取工具
=================
使用 bilibili-api-python 库提取B站创作者的全部视频列表。

用法:
  python scripts/extract_videos.py --uid 315846984
  python scripts/extract_videos.py --space-url https://space.bilibili.com/315846984
"""

import sys
import json
import os
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
VIDEO_LIST_FILE = PROJECT_ROOT / "video_list.json"


def extract_uid_from_url(space_url: str) -> str:
    """从空间URL提取UID"""
    # 格式: https://space.bilibili.com/315846984
    parts = space_url.rstrip('/').split('/')
    return parts[-1]


def extract_videos(uid: str) -> list:
    """
    提取指定UID的全部视频列表
    
    参数:
        uid: B站用户UID
    
    返回:
        视频列表，每个视频包含: index, bvid, title, duration, play, url
    """
    try:
        from bilibili_api.user import User
        from bilibili_api.video import get_video_info
        from bilibili_api import sync
        from bilibili_api.user import UserOrder
    except ImportError:
        print("请先安装 bilibili-api-python:")
        print("  pip install bilibili-api-python")
        sys.exit(1)
    
    print(f"正在提取 UID={uid} 的视频列表...")
    
    # 创建用户对象
    user = User(uid=int(uid))
    
    # 获取视频列表（按最新发布排序）
    videos_data = sync(user.get_videos(order=UserOrder.PUBDATE))
    
    if not videos_data or "list" not in videos_data.get("vlist", {}):
        print("未找到视频！")
        return []
    
    video_list = []
    total = videos_data["page"]["count"]
    vlist = videos_data["vlist"]["vlist"]
    
    print(f"共找到 {total} 个视频")
    
    for idx, video in enumerate(vlist, 1):
        bvid = video.get("bvid", "")
        title = video.get("title", "")
        duration = video.get("length", "")
        play = video.get("play", 0)
        
        video_info = {
            "index": idx,
            "bvid": bvid,
            "title": title,
            "duration": duration,
            "play": play,
            "url": f"https://www.bilibili.com/video/{bvid}/"
        }
        video_list.append(video_info)
        
        if idx % 10 == 0:
            print(f"  已处理 {idx}/{total}...")
    
    return video_list


def save_video_list(video_list: list, output_file: str = None):
    """保存视频列表到JSON文件"""
    if output_file is None:
        output_file = VIDEO_LIST_FILE
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(video_list, f, ensure_ascii=False, indent=2)
    
    print(f"\n已保存到: {output_file}")
    print(f"共 {len(video_list)} 个视频")


def main():
    """主函数"""
    args = sys.argv[1:]
    uid = None
    
    i = 0
    while i < len(args):
        if args[i] == "--uid" and i+1 < len(args):
            uid = args[i+1]
            i += 2
        elif args[i] == "--space-url" and i+1 < len(args):
            uid = extract_uid_from_url(args[i+1])
            i += 2
        elif args[i] == "--help" or args[i] == "-h":
            print(__doc__)
            return
        else:
            i += 1
    
    if not uid:
        print("请提供UID或空间URL:")
        print("  python extract_videos.py --uid 315846984")
        print("  python extract_videos.py --space-url https://space.bilibili.com/315846984")
        return
    
    # 提取视频
    video_list = extract_videos(uid)
    
    if video_list:
        save_video_list(video_list)
    else:
        print("未提取到视频！")


if __name__ == "__main__":
    main()
