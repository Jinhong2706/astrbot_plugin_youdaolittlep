import asyncio
import hashlib
import tempfile
import re
from pathlib import Path
from typing import List
import aiohttp
from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.message_components import Record, File
from astrbot.api.star import Context, Star
from astrbot.api import AstrBotConfig


class YoudaoXiaoPPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.device_sn = config.get("device_sn", "")
        self.key_id = config.get("key_id", "")
        self.fixed_key = config.get("fixed_key", "")
        self.base_url = config.get("base_url", "")
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

    @filter.command("tts")
    async def tts_command(self, event: AstrMessageEvent):
        if not self.device_sn or not self.key_id or not self.fixed_key or not self.base_url:
            yield event.plain_result("插件配置不完整，请先在 WebUI 中配置 device_sn, key_id, fixed_key, base_url")
            return

        raw = event.message_str.strip()
        # 兼容某些平台残留的指令名 'tts'
        if raw.startswith('tts'):
            raw = raw[3:].strip()

        if not raw:
            yield event.plain_result("请提供要合成的文本。示例：tts 你好世界")
            return

        voice = self.default_voice
        content = raw

        # 匹配音色（支持后面跟空格或者直接跟文本）
        m = re.match(r'^(youxiaoshi|youxiaojin)(?:\s+(.*))?$', raw, re.DOTALL)
        if m:
            voice = m.group(1)
            content = (m.group(2) or "").strip()
            if not content:
                yield event.plain_result(f"音色 {voice} 后没有提供文本内容。")
                return

        if not content:
            yield event.plain_result("文本内容不能为空。")
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

    async def _synthesize(self, text: str, voice: str) -> str:
        chunks = self._split_text(text, self.max_length)
        if not chunks:
            raise ValueError("文本为空")

        if len(chunks) == 1:
            return await self._request_tts(chunks[0], voice)

        tmp_dir = tempfile.mkdtemp(prefix="youdao_tts_")
        part_files = []
        for idx, chunk in enumerate(chunks):
            logger.info(f"合成第 {idx+1}/{len(chunks)} 段")
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
        mystic_time = str(int(asyncio.get_event_loop().time() * 1000))
        sign_raw = f"deviceSn={self.device_sn}&keyid={self.key_id}&mysticTime={mystic_time}&key={self.fixed_key}"
        sign = hashlib.md5(sign_raw.encode()).hexdigest()

        data = {
            "deviceSn": self.device_sn,
            "keyid": self.key_id,
            "mysticTime": mystic_time,
            "sign": sign,
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
            "q": text,
            "voiceName": voice,
            "format": "mp3",
            "volume": "1",
        }

        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(self.base_url + "/zhiyun/tts", data=data) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise Exception(f"API 请求失败 ({resp.status}): {error_text[:200]}")
                tmp_fd, tmp_path = tempfile.mkstemp(suffix=".mp3", prefix="youdao_")
                with open(tmp_fd, "wb") as f:
                    f.write(await resp.read())
                return tmp_path

    def _split_text(self, text: str, max_len: int) -> List[str]:
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
                    final.append(chunk[i:i+max_len])
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

    async def terminate(self):
        pass