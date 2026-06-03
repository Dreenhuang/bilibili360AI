# B站视频 → 360AI → Docx 自动化 Skill 阶段总结

> **项目代号**：bili2doc
> **目标**：输入 B站视频 URL → 自动通过 360AI 浏览器调用「全文」转录 → 自动点击「导出」 → 下载 docx 文档
> **最后更新**：2026-06-02 11:25

---

## 一、项目目标与范围

**最终交付物**：
- 一个可复用的 Skill（位于 `C:\Users\Administrator\.workbuddy\skills\bilibili-360ai-video-to-doc\`）
- 接受一个 B站视频 URL 作为输入
- 自动完成：B站打开 → 触发 360AI 助手 → 切到 yue.360.com iframe → 点击「全文」tab → 等待转录完成 → 点击「导出」→ 下载 docx → 保存到指定目录

**核心难点**：
- 360AI 助手嵌在 360AI 浏览器（Chromium 114）内，通过 Shadow DOM + iframe 双重隔离
- yue.360.com 内部用 Ant Design Vue 渲染，DOM 复杂且懒加载
- 全部操作需要 Selenium WebDriver 程序化完成

---

## 二、当前进度总览

| 阶段 | 状态 | 说明 |
|------|------|------|
| 浏览器+扩展环境搭建 | ✅ 完成 | ChromeDriver 114 + 360AI Browser 启动成功 |
| B站视频打开 | ✅ 完成 | 能正确加载 B站视频页 |
| Shadow DOM 突破 | ✅ 完成 | `ai-assist-root-new` Shadow DOM 可访问 |
| 顶层 iframe 识别 | ✅ 完成 | 发现 `ai-bilibili-iframe`（id, 顶层 index=4） |
| 切到 yue.360.com iframe | ✅ 完成 | `driver.switch_to.frame("ai-bilibili-iframe")` 成功 |
| 触发 AI 转录 | ✅ 完成 | 点击「开始识别」后 AI 开始分析视频 |
| 等待字幕生成 | ✅ 完成 | 实时字幕：没输过液 / 是药三分毒 / 输液相关 |
| **找到「全文」按钮** | ❌ **未完成** | 扫描代码漏掉了它 |
| 点击「全文」 | ❌ 未开始 | |
| 等待全文转录完成 | ❌ 未开始 | |
| 找到「导出」按钮 | ❌ 未开始 | |
| docx 下载与保存 | ❌ 未开始 | |
| 完整 Skill 封装 | ❌ 未开始 | |
| 端到端多视频测试 | ❌ 未开始 | |

---

## 三、关键技术发现

### 3.1 浏览器与驱动配置

| 项目 | 值 |
|------|-----|
| 360AI 浏览器路径 | `D:\360AI\360aibrowser\Application\360aibrowser.exe` |
| User Data 目录 | `d:\360ai\360aibrowser\User Data` |
| Profile | `Default` |
| ChromeDriver | `G:\AIAI\zaza\chromedriver114\chromedriver.exe` (v114.0.5735.16) |
| 每次启动前 | 必须先 `taskkill /IM 360aibrowser.exe /F` |

**关键报错**：`InvalidArgumentException: user data directory is already in use`
- 原因：360AI 浏览器已打开（其他进程占用）
- 解决：脚本开头强制 kill 进程

### 3.2 B站页面 → 360AI 助手的入口链

```
bilibili.com/video/BVxxx
  └─ <div id="ai-assist-root-new">  (Shadow DOM, open mode)
       └─ Vue App 渲染
            ├─ ai-webSite-iframe (我们自己注入的, /browser/chat?...)
            └─ ai-bilibili-iframe (顶层, 360AI扩展自动创建)
                 src: https://yue.360.com/browser/video?...
                 rect: 846×375, 位置 (24, 520)  ← 视频下方条状面板
```

**关键洞察**：
- `ai-webSite-iframe` 是早期 v3-v5 错误的目标（这是 chat 面板，不是 video 面板）
- **`ai-bilibili-iframe` 是正确目标**（v6 发现并验证）
- 这个 iframe 是 360AI 扩展检测到 B站页面后自动注入的，不在 Shadow DOM 内

### 3.3 yue.360.com 内部结构（v6 confirmed）

| 项目 | 值 |
|------|-----|
| URL | `https://yue.360.com/browser/video?srcg=browserAI&vip_source=browserAI&src=seai-auto_browserAI&mod=video&scene=&from=bilibili&t=...` |
| 页面标题 | `360AI浏览器` |
| 元素总数 | 652 |
| Shadow Roots | 651（深度嵌套） |
| readyState | complete |

**初始可见的 4 个文本元素**（v6 扫描结果）:
1. `发言人` （SPAN）— 顶部 tab 的内容
2. `AI 助手可以帮您识别视频中的不同发言人` （DIV）— 提示语
3. `开始识别` （SPAN）— 触发按钮
4. `识别成功后，AI助手将重新生成全部内容` （DIV）— 提示语

**关键限制**：
- 顶层只有 4 个可见文本！整个 yue.360.com 主体内容都需要 scroll 或等待懒加载
- 「全文」tab 据用户说"从一开始就存在"在顶部导航栏，但 v6/v7 扫描未发现

### 3.4 顶部导航栏结构（用户口述，v9 待验证）

> 顶部导航栏有「**回原文 / 自简介 / 古脑图 / 重点 / 分析 全文 追问 / ▲字幕 / 生成PPT**」需要点击「**全文**」按钮

> 「**全文**」按钮是**从一开始就在的**

**导航栏 tab 推测结构**：
- 不是 `ant-tabs`（v6 扫描 ant-tabs-* class 只发现"发言人"）
- 应该是自定义 class 的 navigation bar
- 推测位置：iframe 顶部，但初始可能 `display: none` 或在 iframe 视口外

### 3.5 「开始识别」按钮（已解决）

```python
# 工作代码（v6/v7 已验证）
SPAN文本 = "开始识别" 
↓ 向上找 BUTTON 父节点
BUTTON.outerHTML = '<button class="ant-btn css-m4timi ant-btn-default operate-button">...</button>'
↓ target.click()  即可触发 AI 分析
```

### 3.6 AI 视频分析行为（v7 已验证）

- 点击「开始识别」后，360AI 后端开始调用 ASR
- 视频继续播放（0:00 → 1:00 → 2:00 → 3:00），AI 实时识别
- 字幕流式出现在 B站播放器旁边：`没输过液` → `是药三分毒` → `看到这儿就明白up是要步步引出输液是直接进入体内而非吸收了` → `很快（指至少上千万年）`
- 同时 B站评论区也活跃，证明 iframe 完整存活
- **「全文」tab 据用户说从一开始就存在，不需要等待 AI 完成**（但 AI 完成后内容会更全）

### 3.7 完整的关键词清单（v9 需要用）

| 类别 | 关键词 |
|------|--------|
| 顶部 tab | `回原文`, `自简介`, `古脑图`, `重点`, `分析`, `全文`, `追问`, `字幕`, `生成PPT` |
| 导出按钮 | `导出`, `下载`, `复制`, `Word`, `docx`, `导出Word`, `下载Word`, `复制全文`, `下载文档` |
| 转录状态 | `全文`, `文稿`, `文字稿`, `转录`, `文字版`, `总结`, `摘要` |
| 触发按钮 | `开始识别`, `开始分析`, `一键识别`, `识别`, `分析视频` |

---

## 四、版本演进史

### v1-v2：早期 API 客户端思路（`api_client.py` / `bilibili_360ai_v2.py`）
- 尝试绕过浏览器，直接调用 360AI 后端 API
- 反编译 `common.js` (622KB) 找到 API endpoint
- **结论**：API 路径过于复杂，转向浏览器自动化

### v3-v4：Shadow DOM 探索（`06_diagnose_v3.py` / `07_diagnose_v4.py`）
- 成功访问 `ai-assist-root-new` Shadow DOM
- 错误地认为需要 `ai-webSite-iframe`（chat 面板，不是 video 面板）
- 错误地尝试了 User Data 路径 `d:\360ai\360aibrowser\User Data`，发现是 `d:\360ai\360aibrowser\User Data`（注意大小写）

### v5：iframe 三种方案对比（`08_diagnose_v5.py`）
- 尝试了 Method A/B/C 三种进入 iframe 的方式
- 失败：所有方法都没有进入 yue.360.com 的正确 iframe

### v6 ✅：突破（`09_diagnose_v6.py`）
- **关键改动**：直接用 `driver.switch_to.frame("ai-bilibili-iframe")`
- **结果**：成功进入 yue.360.com，看到 652 个元素
- **关键发现**：初始只有 4 个可见文本
- **未发现**：「全文」tab

### v7 ✅：触发 AI 分析（`10_diagnose_v7.py`）
- 成功点击「开始识别」按钮
- 循环等待 200+ 秒
- AI 开始分析视频，实时字幕生成成功
- 字幕被识别为「字幕」关键词（属于顶部导航）
- **未发现**：「全文」tab（即使 AI 转录中）

### v8 ❌：未运行（`11_diagnose_v8.py`）
- 计划扩大关键词、增加 scroll、等待 10 分钟
- 脚本就绪但未执行
- 用户中途要求做阶段总结

---

## 五、未解决问题清单

### 🔴 P0：找到「全文」按钮

**症状**：v6/v7 扫描全部可见文本，只找到"发言人"和"开始识别"，没有"全文"。

**可能的根因**：
1. 「全文」tab 在 iframe 视口外（iframe 高度只有 375px，导航栏可能需要 scroll）
2. 「全文」tab 用了自定义 class（不是 ant-tabs-*），被 v6/v7 的 class 过滤逻辑漏掉
3. 「全文」tab 是图片或 SVG 渲染（无文本）
4. 「全文」tab 在另一个嵌套 iframe 里（v6 扫描时未进入）

**v9 行动计划**：
- [ ] 进入 iframe 后 `driver.execute_script("window.scrollTo(0, 0)")` 确保顶部可见
- [ ] 扩大等待到 10s
- [ ] 用更宽泛的扫描：所有元素 textContent 包含「全文」
- [ ] 打印所有 class 不含 ant-tabs 的导航元素
- [ ] 打印所有 `display !== 'none'` 的 tab-like 元素（class 含 nav/tab/menu/item）

### 🟡 P1：导出按钮与 docx 下载

**预期位置**：「全文」tab 激活后，右侧或底部会出现「复制/导出/下载/Word」按钮组。

**v9 行动计划**：
- [ ] 点击「全文」成功后，扫描所有可见按钮
- [ ] 找含「导出/下载/Word/docx」文本的按钮
- [ ] 监听 Network（CDP）截获 blob: URL 下载
- [ ] 配置 Chrome download dir 并改写 blob URL → base64 → 保存为 .docx

### 🟢 P2：完整 Skill 封装

- [ ] 整理为可调用函数：`bili_to_docx(url, output_dir) -> str`
- [ ] 参数化 B站 URL 和输出目录
- [ ] 添加错误重试和超时控制
- [ ] 写入 Skill 目录 `C:\Users\Administrator\.workbuddy\skills\bilibili-360ai-video-to-doc\`

---

## 六、文件清单（已迁移至 bili2doc/）

```
G:\AIAI\zaza\bili2doc\
├── docs/
│   └── PROGRESS.md                        ← 本文件
├── scripts/
│   ├── 01_analyze_360ai_extension.py      ← 早期：分析 360AI 扩展
│   ├── 02_api_client.py                    ← 早期：直接调 API（已弃用思路）
│   ├── 03_bilibili_360ai_v2.py             ← 早期：v2 主控
│   ├── 04_debug_simple.py                  ← 早期：调试脚本
│   ├── 05_diagnose_browser.py              ← 早期：诊断浏览器
│   ├── 06_diagnose_v3.py                   ← v3：Shadow DOM 探索
│   ├── 07_diagnose_v4.py                   ← v4：iframe 路径探索
│   ├── 08_diagnose_v5.py                   ← v5：3 种进入 iframe 方法对比
│   ├── 09_diagnose_v6.py                   ← ⭐ v6：突破，定位 ai-bilibili-iframe
│   ├── 10_diagnose_v7.py                   ← ⭐ v7：成功触发 AI 转录
│   ├── 11_diagnose_v8.py                   ← v8：未运行（已废弃）
│   ├── 12_discover_360ai_elements.py       ← 早期：发现 360AI 元素
│   ├── 13_test_360ai_activate.py           ← 早期：测试激活
│   ├── 14_test_360ai_bilibili.py           ← 早期：B站测试
│   ├── 15_test_360ai_full.py               ← 早期：全流程测试
│   └── 16_test_360ai_shadow_dom.py         ← 早期：Shadow DOM 测试
├── reports/
│   ├── diagnose_v4_report.json
│   ├── diagnose_v5_report.json
│   ├── diagnose_v6_report.json
│   └── diagnose_v7_report.json
└── screenshots/                            ← 67 张诊断截图（v4-v8 全过程）
```

---

## 七、下一步行动计划（v9）

### v9 目标
**解决 P0：找到并点击「全文」按钮**

### v9 设计要点

1. **进入 iframe 后立即 scroll 顶部** + 等待 10s
2. **多维度扫描「全文」**：
   - 所有元素 textContent contains "全文"
   - 所有 `[role="tab"]` 元素
   - 所有 `class~=nav` 或 `class~=menu` 元素
   - 所有 `data-tab`、`data-key` 含 "full" 的元素
3. **打印 iframe 完整结构**（无过滤）：所有 div 和 span 节点 + 关键 class
4. **找到「全文」后**：
   - 截图标注
   - 点击
   - 等待 5s
   - 扫描「导出/下载/Word」按钮
   - 点击「导出」
   - 监听下载
5. **保存完整 JSON 报告** + 截图

### v9 文件
`bili2doc/scripts/17_diagnose_v9.py`

---

## 八、关键代码片段（复用参考）

### 8.1 浏览器启动 + 切到 ai-bilibili-iframe

```python
import subprocess
from selenium import webdriver
from selenium.common.exceptions import NoSuchFrameException

# 1. 先 kill 残留进程
subprocess.run(["taskkill", "/IM", "360aibrowser.exe", "/F"], capture_output=True)
import time; time.sleep(2)

# 2. 启动
options = webdriver.ChromeOptions()
options.binary_location = r"D:\360AI\360aibrowser\Application\360aibrowser.exe"
options.add_argument(r"user-data-dir=d:\360ai\360aibrowser\User Data")
options.add_argument(r"profile-directory=Default")
options.add_argument("--no-sandbox")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])

driver = webdriver.Chrome(
    executable_path=r"G:\AIAI\zaza\chromedriver114\chromedriver.exe",
    options=options
)
driver.maximize_window()

# 3. 打开 B站
driver.get("https://www.bilibili.com/video/BV1udLu6DE8p/")
time.sleep(5)

# 4. 切到 ai-bilibili-iframe
try:
    driver.switch_to.frame("ai-bilibili-iframe")
    print("✅ iframe switch OK")
except NoSuchFrameException:
    print("❌ iframe not found")
    driver.switch_to.default_content()
```

### 8.2 找到「开始识别」并点击

```python
clicked = driver.execute_script("""
const target_text = '开始识别';
const all = document.querySelectorAll('*');
for (const el of all) {
    if (el.children.length === 0 && (el.textContent || '').trim() === target_text) {
        let r = el.getBoundingClientRect();
        if (r.width > 0) {
            let target = el;
            for (let i = 0; i < 5; i++) {
                if (!target.parentElement) break;
                target = target.parentElement;
                if (target.tagName === 'BUTTON') break;
            }
            target.click();
            return { ok: true, btn: target.outerHTML.slice(0, 200) };
        }
    }
}
return { ok: false };
""")
print(clicked)
```

### 8.3 全量扫描（v9 改进版）

```python
# 无过滤的 textContent 扫描
result = driver.execute_script("""
const KW = ['全文', '文稿', '文字', '转录', '导出', '下载', 'Word', 'docx', '复制'];
const matched = [];
const all = document.querySelectorAll('*');
for (const el of all) {
    const t = (el.textContent || '').trim();
    if (!t || t.length > 100) continue;  // 排除大块容器
    for (const k of KW) {
        if (t === k || t.includes(k)) {
            const r = el.getBoundingClientRect();
            if (r.width > 0) {
                matched.push({
                    keyword: k,
                    text: t,
                    tag: el.tagName,
                    cls: (el.className || '').slice(0, 100),
                    visible: r.width > 0 && r.height > 0,
                    rect: { x: r.x, y: r.y, w: r.width, h: r.height }
                });
                break;
            }
        }
    }
}
return { count: all.length, matched: matched.slice(0, 50) };
""")
```

### 8.4 tab 专项扫描

```python
tabs = driver.execute_script("""
const KW = ['回原文','自简介','古脑图','重点','分析','全文','追问','字幕','生成PPT'];
const result = [];
const all = document.querySelectorAll('*');
for (const el of all) {
    const cls = (el.className || '').toString();
    // 包含 nav/menu/tab/item 的元素
    if (cls.match(/nav|menu|tab|item|bar|header/i)) {
        const t = (el.textContent || '').trim();
        if (t && t.length < 50) {
            const r = el.getBoundingClientRect();
            if (r.width > 0 && r.height > 0) {
                for (const k of KW) {
                    if (t.includes(k)) {
                        result.push({ kw: k, text: t, tag: el.tagName, cls: cls.slice(0,80) });
                        break;
                    }
                }
            }
        }
    }
}
return result;
""")
```

---

## 九、风险与注意事项

| 风险 | 应对 |
|------|------|
| 360AI 浏览器版本升级 | 锁定 v114 ChromeDriver 兼容 |
| 360AI 助手接口变更 | 每次跑前先验证 v6 还能切到 iframe |
| B站反爬升级 | 用真实 User Data 目录规避（已生效） |
| 视频时长 < 30s | AI 转录可能过快，注意等待逻辑 |
| 视频时长 > 30min | 转录时间正比于视频长度，设动态超时 |
| 「全文」tab 在 scroll 外 | v9 必须 scroll iframe 顶部 + 滚动内部所有 scrollable |
| 「导出」按钮触发 blob URL | 需用 CDP `Page.setDownloadBehavior` 接管 |

---

## 十、Skill 最终封装草图

```python
# 目标 API
def bilibili_to_docx(
    url: str,
    output_dir: str = "./output",
    timeout: int = 600,
    keep_browser: bool = False
) -> str:
    """
    Convert a Bilibili video to a docx file via 360AI browser.
    
    Args:
        url: Bilibili video URL, e.g. https://www.bilibili.com/video/BVxxxxx
        output_dir: Where to save the .docx file
        timeout: Max wait for AI analysis (seconds)
        keep_browser: If True, do not close browser after download
    
    Returns:
        Absolute path to the saved .docx file
    """
    # 1. Kill residual browsers
    # 2. Launch 360AI browser
    # 3. Open B站 video
    # 4. Switch to ai-bilibili-iframe
    # 5. Scroll iframe top, wait 10s
    # 6. Click 「开始识别」if shown
    # 7. Click 「全文」tab
    # 8. Wait for AI analysis (or detect completion)
    # 9. Click 「导出」button
    # 10. Intercept blob download → save as .docx
    # 11. Return saved file path
```

---

## 十一、对话历史关键节点

1. **会话启动** — 用户从早期会话继续，方向是 B站视频 → 360AI → docx
2. **v6 突破** — 定位 `ai-bilibili-iframe` 顶层 iframe，成功进入 yue.360.com
3. **v7 验证** — AI 转录工作正常，实时字幕生成
4. **用户反馈 1** — 「顶部导航栏有...全文...」  告知有「全文」tab
5. **用户反馈 2** — 「'全文'按钮是从一开始就在的」  澄清「全文」不需要等待
6. **用户反馈 3** — 「继续做好记录 + 整理到 bili2doc + 继续完成所有任务」  当前的指令

---

**下次续接时，请先读这份 PROGRESS.md，然后从 v9 开始。**
