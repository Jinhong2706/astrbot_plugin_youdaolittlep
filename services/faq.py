import aiohttp


async def fetch_faq(base_url: str, params: dict, education_stage: str, category_type: str) -> list:
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(f"{base_url}/teacherp/chat/common/questions/list", params=params) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                raise Exception(f"API 请求失败 ({resp.status}): {error_text[:200]}")
            raw = await resp.json()

    data = raw.get("data", [])
    if not isinstance(data, list):
        raise Exception("API 返回数据格式异常")

    faq_items = []
    for stage_entry in data:
        stage = stage_entry.get("stage", "")
        if education_stage != "全部" and stage != education_stage:
            continue

        classifiers = stage_entry.get("classifier", [])
        for classifier in classifiers:
            key = classifier.get("key", "")
            if category_type != "全部" and key != category_type:
                continue

            questions = classifier.get("value", [])
            for q in questions:
                show = q.get("show", "")
                send = q.get("send", "")
                faq_items.append({"stage": stage, "category": key, "show": show, "send": send})

    return faq_items
