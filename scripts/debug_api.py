# -*- coding: utf-8 -*-
"""调试：看看B站API返回了什么"""
import requests

uid = "2026173074"
url = "https://api.bilibili.com/x/space/arc/search"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://space.bilibili.com/",
}
params = {"mid": uid, "ps": 30, "pn": 1, "order": "pubdate", "jsonp": "jsonp"}

resp = requests.get(url, headers=headers, params=params, timeout=15)
print(f"状态码: {resp.status_code}")
print(f"Content-Type: {resp.headers.get('content-type', 'unknown')}")
print(f"响应内容(前500字):")
print(resp.text[:500])
