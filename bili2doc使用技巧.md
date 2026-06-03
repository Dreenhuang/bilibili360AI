# bili2doc 使用技巧与常见问题

## 作者备注
作者：GLM-5V-Turbo+Trae IDE+20260603

## 一、快速使用指南

### 1. 最简单的方式
直接双击 `启动bili2doc.bat` 文件，程序会自动检查环境并运行。

### 2. 命令行使用
```bash
# 处理全部待处理视频
python bili2doc.py

# 测试模式：只处理5个
python bili2doc.py --count 5

# 查看帮助
python bili2doc.py --help
```

### 3. 提取视频列表
```bash
# 使用UID
python scripts/extract_videos.py --uid 315846984

# 使用空间URL
python scripts/extract_videos.py --space-url https://space.bilibili.com/315846984
```

## 二、核心技巧

### 技巧1：断点续传
程序会自动保存进度到 `batch_state.json`，中断后重新运行即可从断点继续。

### 技巧2：频率限制应对
- 当触发频率限制时，程序会自动冷却30-120分钟
- 可以通过调整 `bili2doc.py` 中的配置项来改变冷却策略
- 最佳策略：等待次日00:00重置（每日约33次配额）

### 技巧3：提高成功率
1. 运行前关闭其他全屏应用
2. 确保360AI浏览器窗口可以正常最大化
3. 不要操作电脑，让程序自动运行
4. 确保网络连接稳定

### 技巧4：自定义配置
所有配置在 `bili2doc.py` 的 `Config` 类中，可根据实际情况调整：
- `WAIT_AI_SECONDS` - AI分析等待时间
- `INTER_VIDEO_DELAY` - 视频间隔时间
- `RATE_LIMIT_BASE_COOLDOWN` - 基础冷却时间

## 三、常见问题

### Q1: 提示"操作过于频繁"怎么办？
**原因：** 360AI有每日调用次数限制（约33次/天）
**解决：** 等待冷却或次日重置

### Q2: 下载的文件为空？
**原因：** AI分析失败
**解决：** 检查频率限制状态，增加等待时间

### Q3: 导航到错误页面？
**原因：** 地址栏坐标不正确
**解决：** 重新测量坐标，确认浏览器最大化

### Q4: 浏览器无法置顶？
**原因：** 其他应用抢占焦点
**解决：** 关闭其他全屏应用，不操作电脑

### Q5: 如何查看运行日志？
**解决：** 查看 `logs/` 目录下的日志文件

## 四、高级用法

### 1. 修改下载目录
```python
DOWNLOAD_DIR = r"D:\我的文档\bili2doc输出"
```

### 2. 增加AI等待时间
```python
WAIT_AI_SECONDS = 180  # 3分钟
```

### 3. 更保守的频率限制保护
```python
INTER_VIDEO_DELAY = 900          # 15分钟间隔
RATE_LIMIT_BASE_COOLDOWN = 3600  # 1小时基础冷却
```

## 五、Git仓库

- GitHub: https://github.com/Dreenhuang/bilibili360AI
- Gitee: https://gitee.com/woshiboss666/bilibili360AI

## 六、更新日志

### v48 (2026-06-03)
- 重构为模块化架构
- 添加PIL AI结果检测
- 修复频率限制冷却bug
- 添加结构化日志系统
- 完善错误处理
- 添加一键启动脚本

---

**教程版本：** v1.0
**更新日期：** 2026-06-03
**适用版本：** bili2doc v48+
