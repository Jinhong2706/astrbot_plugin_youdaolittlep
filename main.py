import asyncio
import re

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import File, Record
from astrbot.api.star import Context, Star
from astrbot.core.utils.session_waiter import session_waiter, SessionController
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


from core.retry import retry
from core.sign import common_params
from services.chat import chat_sse, delete_chat
from services.faq import fetch_faq
from services.tts import delayed_delete, synthesize


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

    def _get_params(self):
        return common_params(self.device_sn, self.key_id, self.fixed_key)

    async def _safe_delete(self, chat_id: str):
        try:
            params = self._get_params()
            await retry(delete_chat, self.base_url, params, chat_id)
        except Exception as e:
            logger.warning(f"删除对话失败（已忽略）: {e}")

    @filter.command_group("yd")
    def yd(self):
        pass

    @yd.command("chat")
    async def yd_chat(self, event: AstrMessageEvent):
        if not self._check_config():
            yield event.plain_result("插件配置不完整，请先在 WebUI 中配置 device_sn, key_id, fixed_key, base_url")
            event.stop_event()
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
            event.stop_event()
            return

        try:
            params = self._get_params()
            chat_id, answer = await retry(chat_sse, self.base_url, params, raw)
            yield event.plain_result(answer)
            if chat_id:
                asyncio.create_task(self._safe_delete(chat_id))
        except Exception as e:
            logger.error(f"AI 对话失败: {e}")
            yield event.plain_result(f"AI 对话失败: {e}")
            event.stop_event()

    @yd.command("tts")
    async def yd_tts(self, event: AstrMessageEvent):
        if not self._check_config():
            yield event.plain_result("插件配置不完整，请先在 WebUI 中配置 device_sn, key_id, fixed_key, base_url")
            event.stop_event()
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
                event.stop_event()
                return

        if not content:
            yield event.plain_result("请提供要合成的文本。用法: yd tts <文本>")
            event.stop_event()
            return

        logger.info(f"音色: {voice}, 文本: {content}")

        try:
            params = self._get_params()
            audio_path = await retry(synthesize, self.base_url, params, content, voice, self.max_length)
            if self.send_mode == "voice":
                yield event.chain_result([Record(file=audio_path)])
            else:
                yield event.chain_result([File(file=audio_path, name="tts.mp3")])
            asyncio.create_task(delayed_delete(audio_path))
        except Exception as e:
            logger.error(f"语音合成失败: {e}")
            yield event.plain_result(f"语音合成失败: {e}")
            event.stop_event()

    @yd.command("常见问法")
    async def yd_faq(self, event: AstrMessageEvent):
        if not self._check_config():
            yield event.plain_result("插件配置不完整，请先在 WebUI 中配置 device_sn, key_id, fixed_key, base_url")
            event.stop_event()
            return

        raw = event.message_str.strip()
        if raw.startswith("/"):
            raw = raw[1:]
        for prefix in ["yd 常见问法 ", "yd 常见问法"]:
            if raw.startswith(prefix):
                extra = raw[len(prefix):].strip()
                if extra:
                    yield event.plain_result("用法错误。请输入 'yd 常见问法' 查看问题列表，然后单独输入序号选择问题。")
                    event.stop_event()
                    return
                break

        try:
            params = self._get_params()
            faq_items = await retry(fetch_faq, self.base_url, params, self.education_stage, self.category_type)
        except Exception as e:
            logger.error(f"获取常见问题失败: {e}")
            yield event.plain_result(f"获取常见问题失败: {e}")
            event.stop_event()
            return

        if not faq_items:
            stage_text = self.education_stage
            cat_text = self.category_type
            yield event.plain_result(f"当前筛选条件（{stage_text} / {cat_text}）下没有找到常见问题")
            event.stop_event()
            return

        lines = []
        current_header = None
        index = 0
        for item in faq_items:
            header = f"【{item['stage']} - {item['category']}】"
            if header != current_header:
                current_header = header
                lines.append(header)
            index += 1
            lines.append(f"  {index}. {item['show']}")

        lines.append("")
        lines.append("请直接回复序号选择问题（如: 1）")
        yield event.plain_result("\n".join(lines))

        try:

            @session_waiter(timeout=120)
            async def faq_waiter(controller: SessionController, waiter_event: AstrMessageEvent):
                msg = waiter_event.message_str.strip()
                if msg.startswith("/"):
                    msg = msg[1:]

                if re.match(r'^yd\s+常见问法\s+\d+', msg):
                    await waiter_event.send(waiter_event.plain_result("用法错误。请直接输入序号，无需重复 'yd 常见问法'。"))
                    controller.stop()
                    return

                try:
                    choice = int(msg)
                except ValueError:
                    await waiter_event.send(waiter_event.plain_result("请输入有效数字序号"))
                    controller.stop()
                    return

                if choice < 1 or choice > len(faq_items):
                    await waiter_event.send(waiter_event.plain_result(f"序号超出范围，请输入 1-{len(faq_items)}"))
                    controller.stop()
                    return

                send_text = faq_items[choice - 1]["send"]
                if not send_text:
                    await waiter_event.send(waiter_event.plain_result("该问题无效，请选择其他序号"))
                    controller.stop()
                    return

                try:
                    params = self._get_params()
                    chat_id, answer = await retry(chat_sse, self.base_url, params, send_text)
                    await waiter_event.send(waiter_event.plain_result(answer))
                    if chat_id:
                        asyncio.create_task(self._safe_delete(chat_id))
                except Exception as e:
                    logger.error(f"AI 对话失败: {e}")
                    await waiter_event.send(waiter_event.plain_result(f"AI 对话失败: {e}"))

                controller.stop()

            await faq_waiter(event)
        except TimeoutError:
            yield event.plain_result("常见问法选择已超时，请重新输入 'yd 常见问法'")
        finally:
            event.stop_event()

    async def terminate(self):
        pass
