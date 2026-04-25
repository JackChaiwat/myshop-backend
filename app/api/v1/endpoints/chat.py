"""
backend/app/api/v1/endpoints/chat.py
"""
from __future__ import annotations
import json
from datetime import datetime
from typing import Dict, List
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException
from jose import JWTError, jwt
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.auth import get_current_user, require_admin
from app.core.config import settings
from app.db.session import get_db
from app.db.crud.user import get_user_by_id
from app.models.models import ChatRoom, ChatMessage, User

router = APIRouter(prefix="/chat", tags=["chat"])

class ConnectionManager:
    def __init__(self):
        self.rooms: Dict[str, List[WebSocket]] = {}
        self.admins: List[WebSocket] = []

    async def connect_room(self, room_id: str, ws: WebSocket):
        await ws.accept()
        self.rooms.setdefault(room_id, []).append(ws)

    def disconnect_room(self, room_id: str, ws: WebSocket):
        try:
            self.rooms.get(room_id, []).remove(ws)
        except ValueError:
            pass

    async def connect_admin(self, ws: WebSocket):
        await ws.accept()
        self.admins.append(ws)

    def disconnect_admin(self, ws: WebSocket):
        try:
            self.admins.remove(ws)
        except ValueError:
            pass

    async def broadcast_room(self, room_id: str, data: dict):
        for ws in list(self.rooms.get(room_id, [])):
            try:
                await ws.send_json(data)
            except Exception:
                self.disconnect_room(room_id, ws)

    async def broadcast_admins(self, data: dict):
        for ws in list(self.admins):
            try:
                await ws.send_json(data)
            except Exception:
                self.disconnect_admin(ws)

manager = ConnectionManager()

async def _get_or_create_room(db: AsyncSession, user_id: str) -> ChatRoom:
    result = await db.execute(select(ChatRoom).where(ChatRoom.user_id == user_id).options(selectinload(ChatRoom.user)))
    room = result.scalar_one_or_none()
    if not room:
        room = ChatRoom(user_id=user_id)
        db.add(room)
        await db.commit()
        result = await db.execute(select(ChatRoom).where(ChatRoom.user_id == user_id).options(selectinload(ChatRoom.user)))
        room = result.scalar_one()
    return room

async def _verify_ws_token(token: str, db: AsyncSession):
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "access":
            return None
        return await get_user_by_id(db, payload.get("sub"))
    except JWTError:
        return None

def _msg_dict(msg: ChatMessage) -> dict:
    return {"id": msg.id, "room_id": msg.room_id, "sender_id": msg.sender_id,
            "sender_role": msg.sender_role, "message": msg.message,
            "is_read": msg.is_read, "created_at": msg.created_at.isoformat()}

@router.websocket("/ws/user")
async def ws_user(websocket: WebSocket, db: AsyncSession = Depends(get_db)):
    await websocket.accept()
    try:
        raw = await websocket.receive_text()
        first = json.loads(raw)
    except Exception:
        await websocket.close(code=4001); return
    if first.get("type") != "auth":
        await websocket.close(code=4001); return
    user = await _verify_ws_token(first.get("token", ""), db)
    if not user:
        await websocket.close(code=4001); return
    room = await _get_or_create_room(db, user.id)
    await manager.connect_room(room.id, websocket)
    await db.execute(update(ChatMessage).where(ChatMessage.room_id == room.id, ChatMessage.sender_role == "admin", ChatMessage.is_read == False).values(is_read=True))
    await db.execute(update(ChatRoom).where(ChatRoom.id == room.id).values(unread_user=0))
    await db.commit()
    try:
        while True:
            data = await websocket.receive_text()
            text = json.loads(data).get("message", "").strip()
            if not text: continue
            msg = ChatMessage(room_id=room.id, sender_id=user.id, sender_role="customer", message=text)
            db.add(msg)
            await db.execute(update(ChatRoom).where(ChatRoom.id == room.id).values(last_message=text, last_message_at=datetime.utcnow(), unread_admin=ChatRoom.unread_admin + 1))
            await db.commit()
            await db.refresh(msg)
            await manager.broadcast_room(room.id, {"type": "message", **_msg_dict(msg)})
            await manager.broadcast_admins({"type": "new_message", "room_id": room.id, "user_name": user.full_name or user.email, **_msg_dict(msg)})
    except WebSocketDisconnect:
        manager.disconnect_room(room.id, websocket)

@router.websocket("/ws/admin/room/{room_id}")
async def ws_admin_room(room_id: str, websocket: WebSocket, db: AsyncSession = Depends(get_db)):
    await websocket.accept()
    try:
        raw = await websocket.receive_text()
        first = json.loads(raw)
    except Exception:
        await websocket.close(code=4001); return
    if first.get("type") != "auth":
        await websocket.close(code=4001); return
    user = await _verify_ws_token(first.get("token", ""), db)
    if not user or user.role != "admin":
        await websocket.close(code=4001); return
    await manager.connect_room(room_id, websocket)
    await db.execute(update(ChatMessage).where(ChatMessage.room_id == room_id, ChatMessage.sender_role == "customer", ChatMessage.is_read == False).values(is_read=True))
    await db.execute(update(ChatRoom).where(ChatRoom.id == room_id).values(unread_admin=0))
    await db.commit()
    try:
        while True:
            data = await websocket.receive_text()
            text = json.loads(data).get("message", "").strip()
            if not text: continue
            msg = ChatMessage(room_id=room_id, sender_id=user.id, sender_role="admin", message=text)
            db.add(msg)
            await db.execute(update(ChatRoom).where(ChatRoom.id == room_id).values(last_message=text, last_message_at=datetime.utcnow(), unread_user=ChatRoom.unread_user + 1))
            await db.commit()
            await db.refresh(msg)
            await manager.broadcast_room(room_id, {"type": "message", **_msg_dict(msg)})
    except WebSocketDisconnect:
        manager.disconnect_room(room_id, websocket)

@router.websocket("/ws/admin")
async def ws_admin_global(websocket: WebSocket, db: AsyncSession = Depends(get_db)):
    await websocket.accept()
    try:
        raw = await websocket.receive_text()
        first = json.loads(raw)
    except Exception:
        await websocket.close(code=4001); return
    if first.get("type") != "auth":
        await websocket.close(code=4001); return
    user = await _verify_ws_token(first.get("token", ""), db)
    if not user or user.role != "admin":
        await websocket.close(code=4001); return
    await manager.connect_admin(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect_admin(websocket)

@router.get("/room")
async def get_my_room(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    room = await _get_or_create_room(db, current_user.id)
    return {"room_id": room.id, "status": room.status, "unread_user": room.unread_user}

@router.get("/room/messages")
async def get_my_messages(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    room = await _get_or_create_room(db, current_user.id)
    result = await db.execute(select(ChatMessage).where(ChatMessage.room_id == room.id).order_by(ChatMessage.created_at.asc()))
    msgs = result.scalars().all()
    await db.execute(update(ChatMessage).where(ChatMessage.room_id == room.id, ChatMessage.sender_role == "admin", ChatMessage.is_read == False).values(is_read=True))
    await db.execute(update(ChatRoom).where(ChatRoom.id == room.id).values(unread_user=0))
    await db.commit()
    return [_msg_dict(m) for m in msgs]

@router.post("/room/messages")
async def send_message_rest(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """REST fallback สำหรับส่งข้อความ (กรณี WebSocket ยังไม่พร้อม)"""
    room = await _get_or_create_room(db, current_user.id)
    text = body.get("message", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Message is empty")
    msg = ChatMessage(
        room_id=room.id,
        sender_id=current_user.id,
        sender_role="customer",
        message=text,
    )
    db.add(msg)
    await db.execute(
        update(ChatRoom).where(ChatRoom.id == room.id).values(
            last_message=text,
            last_message_at=datetime.utcnow(),
            unread_admin=ChatRoom.unread_admin + 1,
        )
    )
    await db.commit()
    await db.refresh(msg)
    await manager.broadcast_admins({"type": "new_message", "room_id": room.id,
        "user_name": current_user.full_name or current_user.email, **_msg_dict(msg)})
    return _msg_dict(msg)

@router.get("/admin/rooms")
async def admin_list_rooms(db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    result = await db.execute(select(ChatRoom).options(selectinload(ChatRoom.user)).order_by(ChatRoom.last_message_at.desc().nullslast()))
    rooms = result.scalars().all()
    return [{"room_id": r.id, "status": r.status, "unread_admin": r.unread_admin, "last_message": r.last_message, "last_message_at": r.last_message_at.isoformat() if r.last_message_at else None, "user": {"id": r.user.id, "name": r.user.full_name or r.user.email, "email": r.user.email}} for r in rooms]

@router.get("/admin/rooms/{room_id}/messages")
async def admin_get_messages(room_id: str, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    result = await db.execute(select(ChatMessage).where(ChatMessage.room_id == room_id).order_by(ChatMessage.created_at.asc()))
    msgs = result.scalars().all()
    await db.execute(update(ChatMessage).where(ChatMessage.room_id == room_id, ChatMessage.sender_role == "customer", ChatMessage.is_read == False).values(is_read=True))
    await db.execute(update(ChatRoom).where(ChatRoom.id == room_id).values(unread_admin=0))
    await db.commit()
    return [_msg_dict(m) for m in msgs]

# ── 2 endpoint ใหม่ ───────────────────────────────────────────────────────────

@router.post("/admin/rooms/{room_id}/read")
async def admin_mark_as_read(
    room_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    """Mark ข้อความของ customer ใน room นี้ว่าอ่านแล้ว"""
    await db.execute(
        update(ChatMessage).where(
            ChatMessage.room_id == room_id,
            ChatMessage.sender_role == "customer",
            ChatMessage.is_read == False,
        ).values(is_read=True)
    )
    await db.execute(
        update(ChatRoom).where(ChatRoom.id == room_id).values(unread_admin=0)
    )
    await db.commit()
    return {"ok": True}

@router.post("/admin/rooms/{room_id}/messages")
async def admin_send_message_rest(
    room_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    """REST fallback สำหรับ admin ส่งข้อความ (กรณี WebSocket ยังไม่พร้อม)"""
    text = body.get("message", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Message is empty")
    msg = ChatMessage(
        room_id=room_id,
        sender_id=current_user.id,
        sender_role="admin",
        message=text,
    )
    db.add(msg)
    await db.execute(
        update(ChatRoom).where(ChatRoom.id == room_id).values(
            last_message=text,
            last_message_at=datetime.utcnow(),
            unread_user=ChatRoom.unread_user + 1,
        )
    )
    await db.commit()
    await db.refresh(msg)
    await manager.broadcast_room(room_id, {"type": "message", **_msg_dict(msg)})
    return _msg_dict(msg)