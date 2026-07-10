import asyncio
import hashlib
import json
import re
import tempfile
import time
from pathlib import Path

import aiohttp
from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import File, Record
from astrbot.api.star import Context, Star

EDUCATION_STAGES = ["全部", "小学", "初中", "高中"]
CATEGORY_TYPES = ["全部", "题目答疑", "趣味知识"]


class YoudaoXiaoPPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.device_sn = config.get("device_sn", "")
        self.key_id = config.get("key_id", "")
        self.fixed_key = config.get("fixed_key", "")
        self.base_url = config.get("base_url", "").rstrip("/")
        self.education_stage = config.get("education_stage", "全部")
        self.category_type = config.get("category_type", "全部")
        self.default_voice = config.get("default_voice", "youxiaoshi")
        self.max_length = config.get("max_length", 100)
        self.send_mode = config.get("send_mode", "voice")

        missing = []
        if not self.device_sn:
            missing.append("device_sn")
        if not self.key_id:
            missing.append("key_id")
        if not self.fixed_key:
            missing.append("fixed_key")
        if not self.base_url:
            missing.append("base_url")
        if missing:
            logger.error(f"有道小P配置缺失: {', '.join(missing)}，请填写配置后重载插件")

    def _check_config(self):
        return all([self.device_sn, self.key_id, self.fixed_key, self.base_url])

    def _make_sign(self, mystic_time: str) -> str:
        sign_raw = f"deviceSn={self.device_sn}&keyid={self.key_id}&mysticTime={mystic_time}&key={self.fixed_key}"
        return hashlib.md5(sign_raw.encode()).hexdigest()

    def _common_params(self, mystic_time: str) -> dict:
        return {
            "deviceSn": self.device_sn,
            "keyid": self.key_id,
            "mysticTime": mystic_time,
            "sign": self._make_sign(mystic_time),
            "pointParam": "deviceSn,keyid,mysticTime",
            "product": "dictpen",
            "client": "y09",
            "appVersion": "4.13.1",
            "osAppVersion": "2.13.0",
            "mid": "Linux5.10.160",
            "screen": "640x172",
            "model": "YDPA7-1",
            "imei": self.device_sn,
            "deviceSku": "OVERHEAD_Y09_SKU_CHN_PRO",
            "deviceId": self.device_sn,
        }

    async def _chat_sse(self, question: str) -> str:
        mystic_time = str(int(time.time() * 1000))
        params = self._common_params(mystic_time)

        escaped = question.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        message_contents = json.dumps([{"text": {"content": escaped}, "type": "text"}], ensure_ascii=False)
        message_info = json.dumps({"subscribe": "strategy", "sensitiveScope": "message", "responseStyle": "offical"}, ensure_ascii=False)

        params["messageContents"] = message_contents
        params["messageInfo"] = message_info
        params["messageScene"] = "dayiPracticeAsk"
        params["messageSource"] = "yd_gpt_dictpen"

        timeout = aiohttp.ClientTimeout(total=60)
        full_answer = []

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(f"{self.base_url}/teacherp/chat/ask/sse", data=params) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise Exception(f"API 请求失败 ({resp.status}): {error_text[:200]}")

                buffer = ""
                async for chunk in resp.content.iter_chunked(1024):
                    text = chunk.decode("utf-8", errors="replace")
                    buffer += text
                    while "\n\n" in buffer:
                        part, buffer = buffer.split("\n\n", 1)
                        for line in part.split("\n"):
                            if line.startswith("data:"):
                                data_str = line[5:].strip()
                                if data_str == "[DONE]":
                                    continue
                                try:
                                    data = json.loads(data_str)
                                    lists = data.get("data", {}).get("list", [])
                                    for item in lists:
                                        if item.get("type") == "text":
                                            content = item.get("text", {}).get("content", "")
                                            full_answer.append(content)
                                except (json.JSONDecodeError, KeyError, TypeError):
                                    continue

        result = "".join(full_answer).strip()
        if not result:
            raise Exception("AI 未返回有效回答")
        return result

    async def _fetch_faq(self) -> str:
        mystic_time = str(int(time.time() * 1000))
        params = self._common_params(mystic_time)

        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{self.base_url}/teacherp/chat/common/questions/list", params=params) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise Exception(f"API 请求失败 ({resp.status}): {error_text[:200]}")
                raw = await resp.json()

        data = raw.get("data", [])
        if not isinstance(data, list):
            raise Exception("API 返回数据格式异常")

        lines = []
        for stage_entry in data:
            stage = stage_entry.get("stage", "")
            if self.education_stage != "全部" and stage != self.education_stage:
                continue

            classifiers = stage_entry.get("classifier", [])
            for classifier in classifiers:
                key = classifier.get("key", "")
                if self.category_type != "全部" and key != self.category_type:
                    continue

                lines.append(f"【{stage} - {key}】")
                questions = classifier.get("value", [])
                for q in questions:
                    show = q.get("show", "")
                    send = q.get("send", "")
                    if show and send:
                        lines.append(f"  Q: {show}")
                    elif show:
                        lines.append(f"  Q: {show}")

        if not lines:
            stage_text = self.education_stage
            cat_text = self.category_type
            lines.append(f"当前筛选条件（{stage_text} / {cat_text}）下没有找到常见问题")

        return "\n".join(lines)

    async def _synthesize(self, text: str, voice: str) -> str:
        chunks = self._split_text(text, self.max_length)
        if not chunks:
            raise ValueError("文本为空")

        if len(chunks) == 1:
            return await self._request_tts(chunks[0], voice)

        tmp_dir = tempfile.mkdtemp(prefix="youdao_tts_")
        part_files = []
        for idx, chunk in enumerate(chunks):
            logger.info(f"合成第 {idx + 1}/{len(chunks)} 段")
            part_path = await self._request_tts(chunk, voice)
            part_files.append(part_path)
            await asyncio.sleep(0.5)

        merged_path = Path(tmp_dir) / "merged.mp3"
        with open(merged_path, "wb") as outfile:
            for pf in part_files:
                with open(pf, "rb") as infile:
                    outfile.write(infile.read())
                Path(pf).unlink()
        return str(merged_path)

    async def _request_tts(self, text: str, voice: str) -> str:
        mystic_time = str(int(time.time() * 1000))
        data = self._common_params(mystic_time)
        data["q"] = text
        data["voiceName"] = voice
        data["format"] = "mp3"
        data["volume"] = "1"

        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(f"{self.base_url}/zhiyun/tts", data=data) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise Exception(f"API 请求失败 ({resp.status}): {error_text[:200]}")
                tmp_fd, tmp_path = tempfile.mkstemp(suffix=".mp3", prefix="youdao_")
                with open(tmp_fd, "wb") as f:
                    f.write(await resp.read())
                return tmp_path

    def _split_text(self, text: str, max_len: int) -> list:
        if len(text) <= max_len:
            return [text]

        sentences = re.split(r'([。！？；，,])', text)
        chunks = []
        current = ""

        for part in sentences:
            if not part:
                continue
            if len(current) + len(part) <= max_len:
                current += part
            else:
                if current:
                    chunks.append(current)
                current = part

        if current:
            chunks.append(current)

        final = []
        for chunk in chunks:
            if len(chunk) <= max_len:
                final.append(chunk)
            else:
                for i in range(0, len(chunk), max_len):
                    final.append(chunk[i:i + max_len])
        return final

    async def _delayed_delete(self, path: str, delay: int = 10):
        await asyncio.sleep(delay)
        try:
            Path(path).unlink(missing_ok=True)
            parent = Path(path).parent
            if parent.name.startswith("youdao_tts_") and not any(parent.iterdir()):
                parent.rmdir()
        except Exception as e:
            logger.debug(f"删除临时文件失败: {e}")

    @filter.command_group("yd")
    def yd(self):
        pass

    @yd.command("chat")
    async def yd_chat(self, event: AstrMessageEvent):
        '''有道小P AI 对话答疑'''
        if not self._check_config():
            yield event.plain_result("插件配置不完整，请先在 WebUI 中配置 device_sn, key_id, fixed_key, base_url")
            return

        raw = event.message_str.strip()
        if raw.startswith("/"):
            raw = raw[1:]
        for prefix in ["yd chat ", "yd chat"]:
            if raw.startswith(prefix):
                raw = raw[len(prefix):].strip()
                break

        if not raw:
            yield event.plain_result("请输入问题。用法: yd chat <问题>")
            return

        try:
            answer = await self._chat_sse(raw)
            yield event.plain_result(answer)
        except Exception as e:
            logger.error(f"AI 对话失败: {e}")
            yield event.plain_result(f"AI 对话失败: {e}")

    @yd.command("tts")
    async def yd_tts(self, event: AstrMessageEvent):
        '''有道小P 文字转语音'''
        if not self._check_config():
            yield event.plain_result("插件配置不完整，请先在 WebUI 中配置 device_sn, key_id, fixed_key, base_url")
            return

        raw = event.message_str.strip()
        if raw.startswith("/"):
            raw = raw[1:]
        for prefix in ["yd tts ", "yd tts"]:
            if raw.startswith(prefix):
                raw = raw[len(prefix):].strip()
                break

        voice = self.default_voice
        content = raw

        m = re.match(r'^(youxiaoshi|youxiaojin)(?:\s+(.*))?$', raw, re.DOTALL)
        if m:
            voice = m.group(1)
            content = (m.group(2) or "").strip()
            if not content:
                yield event.plain_result(f"音色 {voice} 后没有提供文本内容。")
                return

        if not content:
            yield event.plain_result("请提供要合成的文本。用法: yd tts <文本>")
            return

        logger.info(f"音色: {voice}, 文本: {content}")

        try:
            audio_path = await self._synthesize(content, voice)
            if self.send_mode == "voice":
                yield event.chain_result([Record(file=audio_path)])
            else:
                yield event.chain_result([File(file=audio_path, name="tts.mp3")])
            asyncio.create_task(self._delayed_delete(audio_path))
        except Exception as e:
            logger.error(f"语音合成失败: {e}")
            yield event.plain_result(f"语音合成失败: {e}")

    @yd.command("常见问法")
    async def yd_faq(self, event: AstrMessageEvent):
        '''查看有道小P 常用问题'''
        if not self._check_config():
            yield event.plain_result("插件配置不完整，请先在 WebUI 中配置 device_sn, key_id, fixed_key, base_url")
            return

        try:
            faq_text = await self._fetch_faq()
            yield event.plain_result(faq_text)
        except Exception as e:
            logger.error(f"获取常见问题失败: {e}")
            yield event.plain_result(f"获取常见问题失败: {e}")

    async def terminate(self):
        pass
