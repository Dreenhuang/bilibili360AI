# bili2doc - B站视频AI转文字工具

## 项目简介

bili2doc 是一款自动化工具，使用 **360AI浏览器** 的「全文」AI分析功能，将B站视频内容自动转录为 `.docx` 文档。

## 核心功能

- 自动打开B站视频页面
- 触发360AI扩展的「全文」功能
- 等待AI分析生成视频文字稿
- 自动导出并下载为 `.docx` 文件
- 批量处理整个博主的所有视频
- 断点续传支持
- 智能频率限制保护

## 快速开始

### 方式一：一键启动
双击 `启动bili2doc.bat`

### 方式二：命令行
```bash
python bili2doc.py              # 处理全部
python bili2doc.py --count 5    # 测试5个
```

## 系统要求

- Windows 10/11
- Python 3.8+
- 360AI浏览器 1.1+

## 安装依赖

```bash
pip install pyautogui pywin32 pillow bilibili-api-python
```

## 详细教程

请参阅 [bili2doc使用教程.md](./docs/bili2doc使用教程.md)

## 项目结构

```
bili2doc/
├── bili2doc.py              # 主程序
├── 启动bili2doc.bat         # 一键启动器
├── install.bat              # 全局安装程序
├── README.md                # 项目说明
├── requirements.txt         # 依赖列表
├── .gitignore               # Git忽略规则
├── docs/
│   └── bili2doc使用教程.md   # 详细教程
└── scripts/
    └── extract_videos.py    # 视频列表提取
```

## Git仓库

- GitHub: https://github.com/Dreenhuang/bilibili360AI
- Gitee: https://gitee.com/woshiboss666/bilibili360AI

## 当前进度

| 指标 | 数值 |
|------|------|
| 总视频数 | 95 |
| 已成功 | 32 |
| 待处理 | 57 |
| 失败原因 | 360AI频率限制（每日配额） |

## 作者

GLM-5V-Turbo + Trae IDE
2026-06-03
