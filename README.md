# WHai Image Station

轻量化桌面端图片生成工具，支持多平台 API 聚合（DALL·E、Stable Diffusion、Midjourney）。

## 功能特性

- **多平台支持**：一键切换 DALL·E 3 / Stable Diffusion / Midjourney
- **中转支持**：自定义 Base URL + 自定义请求头，完美支持各类 API 中转
- **队列生成**：连续添加任务，后台顺序执行
- **提示词库**：分类管理，快速复用常用 prompt
- **历史画廊**：缩略图预览，一键查看大图
- **图片浏览**：缩放、旋转、另存、复制到剪贴板
- **安全存储**：API Key AES-256 加密

## 环境要求

- Python 3.10+
- Windows 10/11

## 安装依赖

```bash
pip install -r requirements.txt
```

## 运行

```bash
python src/main.py
```

## 打包为 exe

```bash
pip install pyinstaller
python build.py
```

输出: `dist/WHai-image-station.exe`

## 配置

首次使用需在设置中配置 API：

1. 点击右上角 ⚙ 按钮打开设置
2. 选择平台标签页
3. 填入 API Base URL 和 API Key
4. 如使用中转，填入中转地址和自定义请求头
5. 点击"验证配置"确认可用
6. 点击"保存"

## 目录结构

```
WHai-image-station/
├── src/
│   ├── main.py              # 入口
│   ├── app.py               # 应用初始化
│   ├── config/              # 配置模块
│   ├── adapters/            # API 适配器
│   ├── managers/           # 业务管理器
│   ├── widgets/            # UI 组件
│   └── models/              # 数据模型
├── resources/               # 资源文件
├── requirements.txt         # 依赖
├── build.py                 # 打包脚本
└── README.md
```

## License

MIT