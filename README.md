# 有道小P (astrbot_plugin_youdaolittlep)

**AstrBot 插件**，基于有道词典笔的 AI 能力，实现以下核心功能：

- **AI 对话**：通过 SSE 流式接口与有道词典笔 AI 引擎对话，支持学科答疑、知识问答。
- **文字转语音 (TTS)**：将任意文本转换为 MP3，支持 `youxiaoshi` 与 `youxiaojin` 两种音色，长文本自动分段合成并在发送后自动清理临时文件。
- **常见问题 (FAQ)**：从有道服务器获取预设常见问题列表，可按学段和分类筛选，并支持交互式序号选择。

---

## 📦 安装
```bash
# 将插件克隆到 AstrBot 插件目录下
cd $ASTRBOT_ROOT/data/plugins
git clone https://github.com/Jinhong270/astrbot_plugin_youdaolittlep.git
```
依赖会在插件加载时自动通过 `requirements.txt` 安装（`aiohttp`）。

---

## ⚙️ 配置
在 AstrBot WebUI → 插件管理 → 有道小P 中填写以下必填项（标记 ✅）：

| 配置项 | 说明 | 必填 |
|--------|------|:----:|
| `device_sn` | 有道词典笔设备序列号 | ✅ |
| `key_id` | Key ID | ✅ |
| `fixed_key` | 固定密钥 | ✅ |
| `base_url` | API 基础地址（如 `https://openapi.youdao.com`） | ✅ |
| `education_stage` | FAQ 学段筛选：`全部`/`小学`/`初中`/`高中` | ❌ |
| `category_type` | FAQ 分类筛选：`全部`/`题目答疑`/`趣味知识` | ❌ |
| `default_voice` | 默认 TTS 音色：`youxiaoshi` / `youxiaojin` | ❌ |
| `max_length` | TTS 单次请求最大字符数（建议 100） | ❌ |
| `send_mode` | TTS 发送方式：`voice`（语音消息）或 `file`（文件） | ❌ |

> **提示**：若未填写 `default_voice`，使用指令时必须显式指定音色，例如 `youxiaoshi 你好`。

---

## 🚀 使用指南
### 1. AI 对话
```text
/yd chat <你的问题>
```
**示例**：
```
/yd chat 如何求解一元二次方程？
/yd chat 光合作用的过程是什么？
```
系统会返回 AI 的实时回答，并在对话结束后自动删除服务器端的会话记录。

### 2. 查看常见问题
```text
/yd 常见问法
```
插件会展示已筛选的 FAQ 列表，每条前面有序号，直接回复该序号即可让机器人发送对应的提问并返回答案。

### 3. 文字转语音 (TTS)
```text
/yd tts <文本>
/yd tts <音色> <文本>
```
**示例**：
```
/yd tts 你好世界
/yd tts youxiaojin 今天天气真好
```
生成的 MP3 将以语音消息或文件形式发送（取决于 `send_mode`），并在 10 秒后自行删除。

---

## 📜 命令速查表
| 命令 | 功能 |
|------|------|
| `/yd chat <问题>` | AI 对话答疑 |
| `/yd tts <文本>` | TTS（默认音色） |
| `/yd tts <音色> <文本>` | 指定音色的 TTS |
| `/yd 常见问法` | 查看并交互式选择 FAQ |

---

## ⚠️ 注意事项
- 必须使用有效的有道词典笔设备，否则所有接口都会返回错误。
- `mysticTime` 与 `sign` 会在每次请求时自动重新生成，确保请求安全。
- FAQ 数据实时从有道服务器获取，不会本地缓存，故网络波动时可能出现延迟。
- TTS 生成的临时音频文件会在发送后 10 秒自动清理，避免磁盘泄漏。

---

## 📄 许可
MIT License