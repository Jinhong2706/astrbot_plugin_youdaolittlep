import json
import aiohttp
from astrbot.api import logger


async def chat_sse(base_url: str, params: dict, question: str):
    escaped = question.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    message_contents = json.dumps([{"text": {"content": escaped}, "type": "text"}], ensure_ascii=False)
    message_info = json.dumps({"subscribe": "strategy", "sensitiveScope": "message", "responseStyle": "offical"}, ensure_ascii=False)

    data = dict(params)
    data["messageContents"] = message_contents
    data["messageInfo"] = message_info
    data["messageScene"] = "dayiPracticeAsk"
    data["messageSource"] = "yd_gpt_dictpen"

    timeout = aiohttp.ClientTimeout(total=60)
    full_answer = []
    chat_id = None

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(f"{base_url}/teacherp/chat/ask/sse", data=data) as resp:
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
                                event_data = json.loads(data_str)
                                lists = event_data.get("data", {}).get("list", [])
                                for item in lists:
                                    item_type = item.get("type", "")
                                    if item_type == "chat":
                                        chat_obj = item.get("chat", {})
                                        if not chat_id:
                                            chat_id = chat_obj.get("chatId", "")
                                    elif item_type == "text":
                                        content = item.get("text", {}).get("content", "")
                                        full_answer.append(content)
                            except (json.JSONDecodeError, KeyError, TypeError):
                                continue

    result = "".join(full_answer).strip()
    if not result:
        raise Exception("AI 未返回有效回答")
    return chat_id, result


async def delete_chat(base_url: str, params: dict, chat_id: str):
    chat_ids = json.dumps([chat_id], ensure_ascii=False)
    data = dict(params)
    data["chatIds"] = chat_ids

    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(f"{base_url}/teacherp/chat/history/batch/delete", data=data) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                raise Exception(f"删除对话失败 ({resp.status}): {error_text[:200]}")
            raw = await resp.json()
            if raw.get("code") != 0:
                raise Exception(f"删除对话失败: {raw.get('msg', '未知错误')}")
            logger.info(f"对话 {chat_id} 已删除")
