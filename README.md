# llm-wiki-toolkit

维护「由 AI 持续编写的 markdown 知识库」时用得上的两个小工具 + 一份方法论。

> 理念：**知识编译一次、持续保鲜**，而不是每次提问时临时检索拼凑（与 RAG 的分野）。
> 方法论见 [`docs/llm-wiki-methodology.md`](docs/llm-wiki-methodology.md)。

## 工具

### 1. `append_only_guard.py` —— 「纯追加编辑」的机器护栏

当你做的改动本应是**只加不删**（追加注记、补字段、互指、标注）时，提交前跑一次，
用 git 证明所有改动文件的**删除列都为 0**。

```bash
python append_only_guard.py                 # 检查工作区未暂存改动
python append_only_guard.py --cached        # 检查已暂存改动
python append_only_guard.py --ref HEAD~1    # 与某提交比较
python append_only_guard.py --allow CHANGELOG.md   # 允许个别文件有删除（可重复）
python append_only_guard.py --quiet         # 仅失败时输出
```

**它挡的是什么**：把某一行当作「替换锚点」时，连带删掉了那一行本身。
这种事故**结构自检查不出来**（标题层级、链接、计数可能全都还对），只有逐字回读才能发现；
而本护栏用 `git diff --numstat` 判定，**机器可验、成本近零**。

- 二进制文件（numstat 中显示为 `-`）自动跳过
- 退出码：`0` 通过 / `1` 存在删除行 / `2` git 调用失败
- 零依赖，只用 Python 标准库

### 2. `chunked_asr.py` —— 分片 WAV → 文本（本地、离线）

长音频（讲座/播客/口播）切片后逐片识别，合并成一份 transcript。**纯本地，不联网**。

```bash
# 1) 切片：16kHz / 单声道 / 60 秒一片
ffmpeg -i input.mp3 -ar 16000 -ac 1 -vn -f segment -segment_time 60 chunks/chunk_%03d.wav

# 2) 识别
python chunked_asr.py --chunks ./chunks --model-dir ./sherpa-onnx-paraformer-zh-small --out transcript.txt
```

依赖：`pip install sherpa-onnx numpy` + 任意 sherpa-onnx 兼容的 Paraformer 模型目录。

**内置静音守卫**：峰值低于阈值（默认 `0.004`）的分片直接跳过 —— 既省算力，
也避免整段静音的输入触发 Paraformer 的 Conv/Reshape 形状异常（该崩溃可稳定复现）。

## 方法论

[`docs/llm-wiki-methodology.md`](docs/llm-wiki-methodology.md) 讲了这套知识库的组织方式：

- **四层结构**：`raw/`（不可变来源）/ `wiki/`（AI 全权维护）/ `_meta/`（运维元数据，版本化）/ `log.md`（append-only 时间线）
- **三个工作流**：ingest（摄取）/ query（带引用作答）/ lint（体检）
- **自检清单**：frontmatter、日期格式、计数对账、断链、index 覆盖、无入链页、页内重复标题、纯追加护栏、git 状态
- **多 AI 共用契约**：一人一主题、改完即 commit、追加优先于改写、共享文件只提交自己那行

## 适用范围与边界

- 适合：**markdown 知识库 / 文档仓库**（Obsidian、纯目录 + git 皆可），与具体笔记软件无关。
- 本仓库**只包含平台无关的能力**。不包含任何内容抓取、平台客户端模拟、cookie 管理、
  签名绕过之类的代码 —— 那些既绑定具体平台，也涉及平台协议与第三方权利。
- 转写与归档的内容由使用者自行负责：请确认你放入知识库的材料来源与授权。

## 关于本项目

- 本项目由 **AI（DeepSeek Harness）生成**，人类负责需求定义与验收。
- 这两个工具是从一套**自用知识库工作流**中提炼出来并做了通用化重写的：
  平台相关的部分（抓取、登录态等）已全部剔除，只保留与平台无关的能力。
- 代码未逐字复制任何第三方项目。

## License

MIT，见 [LICENSE](LICENSE)。
