import smtplib
import asyncio
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings

logger = logging.getLogger(__name__)


async def _send(to: str, subject: str, html: str):
    """ส่งอีเมลผ่าน Gmail SMTP ใน thread pool"""
    def _do_send():
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = settings.EMAIL_FROM
            msg["To"] = to
            msg.attach(MIMEText(html, "html", "utf-8"))

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.ehlo()
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.EMAIL_FROM, to, msg.as_string())
        except Exception as e:
            logger.warning(f"email send failed: {e}")

    await asyncio.to_thread(_do_send)


async def send_welcome_email(email: str, name: str):
    await _send(
        to=email,
        subject="ยินดีต้อนรับสู่ร้านของเรา!",
        html=f"<h1>สวัสดี {name}!</h1><p>ขอบคุณที่สมัครสมาชิกกับเรา</p>",
    )


async def send_order_confirmation(order):
    await _send(
        to=order.user.email,
        subject=f"ยืนยันคำสั่งซื้อ {order.order_number}",
        html=f"<h2>คำสั่งซื้อ {order.order_number} ยอดรวม ฿{order.total:,.2f}</h2>",
    )


async def send_order_status_update(order):
    status_map = {
        "processing": "กำลังดำเนินการ",
        "shipped": "จัดส่งแล้ว",
        "delivered": "ส่งถึงแล้ว",
        "cancelled": "ยกเลิกแล้ว",
    }
    label = status_map.get(order.status, order.status)
    await _send(
        to=order.user.email,
        subject=f"อัปเดตคำสั่งซื้อ {order.order_number}",
        html=f"<p>สถานะ: {label}</p>",
    )


async def send_otp_email(email: str, name: str, code: str):
    await _send(
        to=email,
        subject="รหัสยืนยัน OTP — MyShop",
        html=f"""
        <div style="font-family:sans-serif;max-width:480px;margin:auto;padding:32px;border:1px solid #eee;border-radius:12px">
          <h2 style="color:#111;margin-bottom:8px">รหัสยืนยัน OTP</h2>
          <p style="color:#555">สวัสดี {name},</p>
          <p style="color:#555">รหัสยืนยันของคุณคือ:</p>
          <div style="font-size:36px;font-weight:bold;letter-spacing:12px;color:#6366f1;text-align:center;padding:24px;background:#f5f5ff;border-radius:8px;margin:16px 0">
            {code}
          </div>
          <p style="color:#888;font-size:13px">รหัสนี้จะหมดอายุใน 10 นาที อย่าแชร์รหัสนี้กับผู้อื่น</p>
        </div>
        """,
    )