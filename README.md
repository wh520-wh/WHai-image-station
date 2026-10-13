# WHai Image Station

<img src="src/ui/assets/logo.png" width="96" height="96" alt="WHai 图片生成 Logo">

使用 QML / Qt Quick 构建的桌面图片创作工作台，Python 负责 API、队列和本地存储。支持 Windows 10/11，Python 3.10+。

## 开始使用

双击 `start.bat`，或在虚拟环境中安装并启动：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m src.main
```

首次启动提供 OpenAI、Google Gemini、Black Forest Labs 和 MiniMax 的无密钥预置。进入「来源」，填写服务商的 API Key 后保存，回到「创作」选择模型并提交提示词。打开软件和保存配置不会发送生图请求。生图需要你自己的 API 访问权限，费用由对应服务商收取。

兼容来源可以自行设置地址、模型、认证方式、代理和请求头；「自定义完整地址」按 OpenAI 图像格式直接请求填写的 URL。预置模型只是入口，实际可用性取决于服务商账号和区域。

## 工作台

- **创作**：来源和模型切换、能力对应的参数、参考图、输出格式、透明背景、提示词模板；Ctrl + Enter 加入队列。
- **作品库**：数据库搜索与分页、按视口加载缩略图、查看多张结果、缩放和旋转、另存与复制图片、复用参数、批量导出 / 分类 / 标签 / 删除；失败记录保留诊断。
- **提示词**：保存当前画面、参数和模型绑定，搜索并复用。
- **工具**：可保存的顺序生成流程，每行一个独立提示词，支持运行、暂停、继续和停止。每一步独立生成。
- **设置**：深色外观、减少动态效果、并发限制、备份和迁移、本地目录。

队列在后台线程执行。等待任务可取消；正在提交或生成的任务无法保证在服务商端取消。关闭软件不会自动重试或恢复付费任务，重试前请检查服务商是否已经完成。

## 当前来源

预置核对日期：2026-10-12。官方 DALL·E 2/3、Imagen 和非官方 Midjourney 地址不再作为新增来源推荐，已有自定义配置与历史记录保留。

| 来源 | 预置模型 | 接口文档 |
| --- | --- | --- |
| OpenAI | GPT Image 2.5 Flare / Sunburst、GPT Image 2、GPT Image 1 Mini | [图像生成](https://developers.openai.com/api/docs/guides/image-generation) |
| Google Gemini | Nano Banana 2.1、Nano Banana Pro、Nano Banana 2 Lite | [图像生成](https://ai.google.dev/gemini-api/docs/image-generation) |
| Black Forest Labs | FLUX.2 Pro / Max / Klein 4B | [生成与轮询](https://docs.bfl.ai/quick_start/generating_images) |
| MiniMax | Image-01 | [图像 API](https://platform.minimax.io/docs/api-reference/image-generation-t2i) |

## 数据与备份

默认数据库：`~/.imageMaker/data.db`。图片：`~/Pictures/imageMaker/generations`。旧数据原位迁移。

`.imbackup` 包含实际图片、历史、模板、来源、模型、生成流程和设置。默认排除密钥及敏感请求头；可选择使用至少 8 位密码加密携带密钥。导入默认保留现有冲突配置，并重新建立本机图片路径，流程导入后等待手动启动。带密钥的备份可迁移到另一台机器。批量作品导出的 ZIP 包含每条记录的所有结果图片与参数。

本地 API Key 使用 AES-GCM 加密，密钥来自机器标识，这主要减少明文暴露，不能抵御拥有本机访问权限的人。迁移密钥请使用密码加密备份。

## 开发与验证

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
$env:QT_QPA_PLATFORM='offscreen'
$env:QT_QUICK_BACKEND='software'
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src
.\.venv\Scripts\python.exe -m pyright --pythonpath .\.venv\Scripts\python.exe src
```

测试使用模拟 HTTP 和临时数据库，不进行真实付费生图。运行界面截图工具：`python tools/preview_ui.py --output <截图目录>`。旧 Widgets 界面可用 `python -m src.main --widgets` 临时启动，供旧流程对照。

新页面放在 `src/ui/pages`，共用组件和主题放在 `src/ui/components`。页面通过 `src/desktop.py` 的属性、信号和槽调用 Python 服务；新增工具无需改变 API 和存储层。Qt 的设计可参考 [Python 与 QML 集成文档](https://doc.qt.io/qtforpython-6/tutorials/qmlintegration/qmlintegration.html)。

品牌图片位于 `src/ui/assets/logo.png`，用于侧栏、开屏和设置页；替换图片后运行 `python tools/prepare_icon.py` 更新 Windows 多尺寸图标，再重新打包即可同步 EXE 和任务栏图标。

## 打包

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[build]'
.\.venv\Scripts\python.exe build.py
```

输出 `dist/WHai-image-station/WHai-image-station.exe`。分发整个文件夹，包含旁边的 `_internal`；不需要目标机器安装 Python。采用目录打包以避免每次启动解压 Qt 资源。

## License

MIT
