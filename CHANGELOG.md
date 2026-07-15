# Changelog

---

## [3.0.1] - 2026-07-11

### Added
- **核心工具** (`core/`):
  - `core/sign.py` – 用于生成请求签名和公共参数的辅助工具。
  - `core/retry.py` – 所有 API 调用的通用指数退避重试包装器。
- **服务模块** (`services/`):
  - `services/chat.py` – 基于 SSE 的 AI 对话 (`chat_sse`) 和对话清理 (`delete_chat`)。
  - `services/faq.py` – 常见问题获取器，支持阶段/类别过滤 (`fetch_faq`)。
  - `services/tts.py` – TTS 编排 (`split_text`, `request_tts`, `synthesize`, `delayed_delete`)。

### Changed
- **重大重构** – `main.py` 从约 325 行精简到约 150 行，现在仅负责串联核心和服务模块。
- 所有 API 调用现在使用 **retry** 辅助函数，提供自动指数退避和稳健的错误处理。
- AI 回复成功后，对话历史会自动删除。
- FAQ 命令现在显示带编号的列表；用户可以通过回复编号来触发对应问题，使用交互式会话等待器，超时时间为 120 秒。
- 添加了 `event.stop_event()` 调用，以防止响应后继续处理。
- 通过将插件目录插入 `sys.path` 修复了模块导入路径问题。

### Fixed
- 修复了新包布局导致的导入错误。

---

## [2.0.0] - 2026-07-11

### Added
- **AI 对话** (`/yd chat <问题>`):
  - 通过 SSE 流式传输答案，支持多轮上下文，处理 JSON 转义。
- **常见问题浏览** (`/yd 常见问法`):
  - 从有道服务器获取预定义的常见问题列表，支持 `education_stage` 和 `category_type` 过滤参数。
- **命令组** `yd` – 将所有命令统一到公共前缀下。
- **README** – 完整的功能、安装和使用文档。
- **配置扩展** – 在配置模式中增加了 `education_stage` 和 `category_type`。

### Changed
- 集中式配置验证 (`_check_config`)。
- 统一处理默认语音、最大长度和发送模式。
- 清理了 TTS 实现（签名生成、请求参数）。
- 基础 URL 现在会去除尾部斜杠以提高健壮性。

### Fixed
- 修复了命令解析中的几个错误（语音选择、空文本处理、平台特定前缀）。
- 改进了日志记录以便调试。

---

## [1.0.0] - 2026-05-30

### Added
- **TTS 核心** (`/tts` 及后续 `/yd tts`):
  - 使用有道词典笔 `/zhiyun/tts` 端点的文本转语音。
  - 支持两种语音：`youxiaoshi` 和 `youxiaojin` 。
  - 根据标点符号和 `max_length` 自动分割长文本。
  - 发送语音消息 (`voice`) 或 MP3 文件 (`file`)。
  - 临时音频文件在 10 秒后自动删除。
- **配置模式** (`_conf_schema.json`) 包含字段：
  - `device_sn`, `key_id`, `fixed_key`, `base_url`, `default_voice`, `max_length`, `send_mode`。
- **签名生成** – 基于设备 SN、密钥 ID、mysticTime 和固定密钥的 MD5 算法。

### Fixed
- 添加了缺失的配置验证，并在缺少必需字段时提示用户。
- 修复了解析可选语音参数的问题。
- 调整默认值以防止 `max_length` 或 `send_mode` 未设置时崩溃。
- 将metadata.yaml中的插件名称从 `astrbot_plugin_youdaoxiaop` 更新为 `astrbot_plugin_youdaolittlep`。
