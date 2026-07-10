# 有道小P (astrbot_plugin_youdaolittlep)

接入有道词典笔 AI 能力的 AstrBot 插件，支持 AI 对话答疑、文字转语音（TTS）和常见问题（FAQ）查看。

## 功能

| 功能 | 说明 |
|------|------|
| AI 对话 | 通过 SSE 流式接口与有道词典笔 AI 引擎对话，支持学科答疑、知识问答 |
| 文字转语音 | 将文本转换为 MP3 音频，支持 youxiaoshi / youxiaojin 两种音色，长文本自动分段合成 |
| 常见问题 | 从有道服务器获取预设常见问题列表，支持按学段和分类筛选 |

## 安装

将本插件放入 AstrBot 的 `data/plugins/` 目录下。

```bash
cd AstrBot/data/plugins
git clone https://github.com/Jinhong270/astrbot_plugin_youdaolittlep.git
```

依赖通过 `requirements.txt` 自动安装（`aiohttp`）。

## 配置

在 AstrBot WebUI 的插件管理页面配置以下参数：

| 配置项 | 说明 | 必填 |
|--------|------|:----:|
| `device_sn` | 有道词典笔设备序列号 | ✅ |
| `key_id` | Key ID | ✅ |
| `fixed_key` | 固定密钥 | ✅ |
| `base_url` | API 基础地址 | ✅ |
| `education_stage` | 常见问题学段筛选：全部 / 小学 / 初中 / 高中 | ❌ |
| `category_type` | 常见问题分类筛选：全部 / 题目答疑 / 趣味知识 | ❌ |
| `default_voice` | 默认 TTS 音色：youxiaoshi / youxiaojin | ❌ |
| `max_length` | TTS 单次请求最大文本长度（字符） | ❌ |
| `send_mode` | TTS 发送方式：voice（语音消息）/ file（文件） | ❌ |

## 使用

### AI 对话

```
/yd chat <你的问题>
```

示例：

```
/yd chat 如何求解一元二次方程？
/yd chat 光合作用的过程是什么？
```

支持多轮对话（上下文自动维护）。

### 查看常见问题

```
/yd 常见问法
```

根据配置中的「学段筛选」和「分类筛选」过滤显示结果。每个问题包含展示文本（show）和发送文本（send），可直接点击或复制发送。

### 文字转语音

```
/yd tts <文本>
/yd tts <音色> <文本>
```

示例：

```
/yd tts 你好世界
/yd tts youxiaojin 今天天气真好
```

## 命令列表

| 命令 | 说明 |
|------|------|
| `/yd chat <问题>` | AI 对话答疑 |
| `/yd tts <文本>` | 文字转语音 |
| `/yd 常见问法` | 查看常见问题 |

## 注意事项

- 需要有效的有道词典笔设备方可使用
- `mysticTime` 和 `sign` 每次请求自动重新生成
- 常见问题数据从有道服务器实时获取，不做本地缓存
- TTS 生成的临时音频文件会在发送后自动清理

## 许可

MIT
