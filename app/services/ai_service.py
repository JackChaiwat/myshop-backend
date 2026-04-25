"""ai_service.py — Gemini API for product descriptions"""
import asyncio
import google.generativeai as genai
from app.core.config import settings

if settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")
else:
    model = None


async def generate_product_description(name: str, attributes: dict) -> str:
    if not model:
        return ""
    attr_str = ", ".join([f"{k}: {v}" for k, v in attributes.items()])
    prompt = f"""เขียนคำอธิบายสินค้าภาษาไทยสำหรับ:
ชื่อสินค้า: {name}
คุณสมบัติ: {attr_str}

คำอธิบายควรน่าสนใจ ดึงดูดลูกค้า ความยาว 2-3 ประโยค"""
    response = await asyncio.to_thread(model.generate_content, prompt)
    return response.text


async def suggest_related_products(product_name: str, all_products: list) -> list:
    """Use Gemini to suggest related product IDs"""
    if not model or not all_products:
        return []
    product_list = "\n".join([f"- {p['id']}: {p['name']}" for p in all_products[:50]])
    prompt = f"""จากรายการสินค้าต่อไปนี้:
{product_list}

แนะนำ 4 สินค้าที่เกี่ยวข้องกับ "{product_name}" โดยตอบเป็น JSON array ของ id เท่านั้น เช่น ["id1","id2","id3","id4"]"""
    response = await asyncio.to_thread(model.generate_content, prompt)
    import json, re
    match = re.search(r'\[.*?\]', response.text, re.DOTALL)
    if match:
        return json.loads(match.group())
    return []
