# Deploy บน Render

## ขั้นตอนทั้งหมด

---

### 1. เตรียม Git Repos

แนะนำแยก repo backend กับ frontend:
```
github.com/you/myshop-backend   ← โฟลเดอร์ backend/
github.com/you/myshop-frontend  ← โฟลเดอร์ frontend-fixed/
```

> ⚠️ ตรวจสอบว่า `.env` อยู่ใน `.gitignore` ก่อน push ทุกครั้ง

---

### 2. Deploy Backend (ทำก่อน — frontend ต้องการ URL ของ backend)

**a) สร้าง service ใหม่บน Render**
1. ไปที่ https://dashboard.render.com → New → **Blueprint**
2. เลือก repo `myshop-backend`
3. Render จะอ่าน `render.yaml` แล้วสร้าง service + database ให้อัตโนมัติ

**b) กรอก Environment Variables ที่ยังขาด**

ไปที่ service → Environment tab กรอกค่าเหล่านี้:

| Key | ค่า |
|-----|-----|
| `ALLOWED_ORIGINS` | `["https://myshop-frontend.onrender.com"]` |
| `ALLOWED_HOSTS` | `["myshop-backend.onrender.com"]` |
| `FRONTEND_URL` | `https://myshop-frontend.onrender.com` |
| `SMTP_USER` | อีเมล Gmail ของคุณ |
| `SMTP_PASSWORD` | App Password (ไม่ใช่รหัส Gmail ปกติ) |
| `EMAIL_FROM` | อีเมลเดียวกับ SMTP_USER |
| `R2_ACCOUNT_ID` | จาก Cloudflare dashboard |
| `R2_ACCESS_KEY_ID` | จาก Cloudflare R2 → Manage API tokens |
| `R2_SECRET_ACCESS_KEY` | จาก Cloudflare R2 → Manage API tokens |
| `R2_PUBLIC_URL` | `https://pub-xxx.r2.dev` |
| `OMISE_PUBLIC_KEY` | จาก Omise dashboard |
| `OMISE_SECRET_KEY` | จาก Omise dashboard |
| `OMISE_WEBHOOK_SECRET` | ตั้งเองแล้วใส่ใน Omise webhook config ด้วย |

**c) Run Database Migration**

หลัง deploy สำเร็จ ไปที่ service → Shell:
```bash
alembic upgrade head
```

**d) สร้าง Admin User**
```bash
python create_admin.py
```

**e) จด URL ของ backend**
```
https://myshop-backend.onrender.com
```

---

### 3. Deploy Frontend

**a) สร้าง service ใหม่บน Render**
1. New → **Blueprint**
2. เลือก repo `myshop-frontend`
3. Render จะอ่าน `render.yaml` อัตโนมัติ

**b) กรอก Environment Variables**

| Key | ค่า |
|-----|-----|
| `VITE_API_URL` | `https://myshop-backend.onrender.com/api/v1` |
| `VITE_WS_URL` | `wss://myshop-backend.onrender.com/api/v1` |
| `VITE_STATIC_URL` | `https://myshop-backend.onrender.com` |

**c) Redeploy Backend ให้รู้จัก frontend URL**

กลับไปที่ backend service → Environment → แก้ `ALLOWED_ORIGINS` และ `FRONTEND_URL` ให้ตรงกับ URL จริงของ frontend แล้วกด **Save Changes** (จะ redeploy อัตโนมัติ)

---

### 4. ตั้ง Omise Webhook

ใน Omise dashboard → Webhooks → เพิ่ม URL:
```
https://myshop-backend.onrender.com/api/v1/orders/webhook/omise
```

---

### 5. ตรวจสอบ

```bash
# Health check
curl https://myshop-backend.onrender.com/health
# → {"status": "ok"}
```

เปิด `https://myshop-frontend.onrender.com` แล้วทดสอบ:
- [ ] สมัครสมาชิก / เข้าสู่ระบบ
- [ ] เพิ่มสินค้าใส่ตะกร้า
- [ ] Checkout + ชำระเงิน
- [ ] แชท

---

### หมายเหตุ Render Free Plan

- Service จะ **sleep หลัง 15 นาที** ที่ไม่มีการใช้งาน — request แรกจะช้า ~30 วินาที
- Database ฟรี: 1GB storage, หมดอายุหลัง 90 วัน
- ถ้าต้องการ production จริงแนะนำ upgrade เป็น Starter plan ($7/เดือน)
