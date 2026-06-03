# -*- coding: utf-8 -*-
"""v38d: 直接调用get_videos看看返回什么"""
import asyncio
from bilibili_api import user

async def main():
    u = user.User(uid=315846984)
    try:
        result = await u.get_videos(pn=1, ps=10)
        print(f"返回类型: {type(result)}")
        if isinstance(result, dict):
            print(f"顶层keys: {list(result.keys())}")
            # 打印结构
            import json
            print(json.dumps(result, ensure_ascii=False, indent=2)[:2000])
    except Exception as e:
        print(f"异常: {type(e).__name__}: {e}")

asyncio.run(main())
