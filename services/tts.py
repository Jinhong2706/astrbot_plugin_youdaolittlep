import asyncio
import re
import tempfile
from pathlib import Path

import aiohttp
from astrbot.api import logger


def split_text(text: str, max_len: int) -> list:
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


async def request_tts(base_url: str, params: dict, text: str, voice: str) -> str:
    data = dict(params)
    data["q"] = text
    data["voiceName"] = voice
    data["format"] = "mp3"
    data["volume"] = "1"

    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(f"{base_url}/zhiyun/tts", data=data) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                raise Exception(f"API 请求失败 ({resp.status}): {error_text[:200]}")
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".mp3", prefix="youdao_")
            with open(tmp_fd, "wb") as f:
                f.write(await resp.read())
            return tmp_path


async def synthesize(base_url: str, params: dict, text: str, voice: str, max_length: int) -> str:
    chunks = split_text(text, max_length)
    if not chunks:
        raise ValueError("文本为空")

    if len(chunks) == 1:
        return await request_tts(base_url, params, chunks[0], voice)

    tmp_dir = tempfile.mkdtemp(prefix="youdao_tts_")
    part_files = []
    for idx, chunk in enumerate(chunks):
        logger.info(f"合成第 {idx + 1}/{len(chunks)} 段")
        part_path = await request_tts(base_url, params, chunk, voice)
        part_files.append(part_path)
        await asyncio.sleep(0.5)

    merged_path = Path(tmp_dir) / "merged.mp3"
    with open(merged_path, "wb") as outfile:
        for pf in part_files:
            with open(pf, "rb") as infile:
                outfile.write(infile.read())
            Path(pf).unlink()
    return str(merged_path)


async def delayed_delete(path: str, delay: int = 10):
    await asyncio.sleep(delay)
    try:
        Path(path).unlink(missing_ok=True)
        parent = Path(path).parent
        if parent.name.startswith("youdao_tts_") and not any(parent.iterdir()):
            parent.rmdir()
    except Exception as e:
        logger.debug(f"删除临时文件失败: {e}")
