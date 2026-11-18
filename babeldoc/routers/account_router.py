"""账户管理模块 - FastAPI Router

数据保存在 users.json 中，格式为用户信息数组：
[
    {"id": "...", "username": "admin", "password": "...",
     "realname": "管理员", "email": "...", "role": "admin", "created_at": "..."}
]

接口一览：
  GET    /api/captcha           获取登录验证码
  POST   /api/register          注册用户
  POST   /api/login             用户登录（需验证码），返回 token
  POST   /api/logout            用户登出
  GET    /api/users             查询用户列表（支持 ?keyword= 模糊搜索）
  GET    /api/users/{user_id}   查询单个用户
  POST   /api/users             新增用户
  PUT    /api/users/{user_id}   修改用户
  DELETE /api/users/{user_id}   删除用户（admin 角色）
"""
import base64
import json
import os
import random
import re
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Header, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

router = APIRouter()

# ---------- 路径 & 存储 ----------
BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "users.json"
DATA_LOCK = threading.Lock()

# 内存存储：重启后失效
TOKENS: dict[str, dict] = {}  # {token: {"username": ..., "role": ...}}

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,32}$")

# 验证码：一次性使用，5 分钟过期
CAPTCHA_TTL = 300
CAPTCHA_CHARS = "abcdefghjkmnpqrstuvwxyz23456789"
CAPTCHA_STORE: dict[str, tuple[str, float]] = {}

# ---------- Pydantic Schemas ----------
class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=6)
    realname: str = ""
    email: str = ""
    role: str = "user"

class UserLoginRequest(BaseModel):
    username: str
    password: str
    captcha_id: str
    captcha: str

class UserUpdateRequest(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    realname: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None

class UserCreateRequest(UserRegisterRequest):
    pass

# ---------- 验证码 ----------
def cleanup_captcha():
    now = time.time()
    for key in [k for k, (_, ts) in CAPTCHA_STORE.items() if now - ts > CAPTCHA_TTL]:
        CAPTCHA_STORE.pop(key, None)

def gen_captcha() -> tuple[str, str]:
    """生成 4 位验证码，返回 (captcha_id, base64 svg data URI)"""
    cleanup_captcha()
    code = "".join(random.choices(CAPTCHA_CHARS, k=4))
    captcha_id = uuid.uuid4().hex
    CAPTCHA_STORE[captcha_id] = (code, time.time())

    width, height = 140, 48
    colors = ["#2563eb", "#059669", "#d97706", "#7c3aed", "#be185d"]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"'
        f' viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="#f1f5f9" rx="6"/>',
    ]
    for _ in range(4):
        x1, y1 = random.randint(0, width), random.randint(0, height)
        x2, y2 = random.randint(0, width), random.randint(0, height)
        c = random.choice(colors)
        parts.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"'
            f' stroke="{c}" stroke-width="1" opacity="0.4"/>'
        )
    for i, ch in enumerate(code):
        x = 24 + i * 26 + random.randint(-3, 3)
        y = 33 + random.randint(-4, 4)
        rot = random.randint(-25, 25)
        c = random.choice(colors)
        size = random.randint(24, 30)
        parts.append(
            f'<text x="{x}" y="{y}" font-size="{size}" font-family="Arial"'
            f' font-weight="bold" fill="{c}" text-anchor="middle"'
            f' transform="rotate({rot} {x} {y})">{ch}</text>'
        )
    parts.append("</svg>")
    svg = "".join(parts)
    image = "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return captcha_id, image

# ---------- 数据读写 ----------
def load_users() -> list[dict]:
    if not DATA_FILE.exists():
        return []
    try:
        content = DATA_FILE.read_text(encoding="utf-8").strip()
        return json.loads(content) if content else []
    except (json.JSONDecodeError, IOError):
        return []

def save_users(users: list[dict]):
    tmp = str(DATA_FILE) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_FILE)

# ---------- 工具 ----------
def public_user(user: dict) -> dict:
    return {k: v for k, v in user.items() if k != "password"}

def find_user(users: list[dict], **kw) -> Optional[dict]:
    for u in users:
        if all(u.get(k) == v for k, v in kw.items()):
            return u
    return None

def get_token_user(authorization: Optional[str]) -> Optional[dict]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[len("Bearer "):]
    return TOKENS.get(token)

def require_login(authorization: Optional[str]) -> dict:
    user = get_token_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="未登录或 token 无效")
    return user

def validate_username(username: str) -> Optional[str]:
    if not USERNAME_RE.match(username):
        return "username 必须为 3-32 位字母、数字或下划线"
    return None

def validate_password(password: str) -> Optional[str]:
    if len(password) < 6:
        return "password 至少 6 位"
    return None

def validate_email(email: Optional[str]) -> Optional[str]:
    if email and email != "" and "@" not in email:
        return "email 格式不正确"
    return None

# ---------- 接口 ----------
@router.get("/api/captcha")
def captcha():
    cid, image = gen_captcha()
    return {"code": 0, "msg": "success", "data": {"captcha_id": cid, "image": image}}

@router.post("/api/register")
def register(req: UserRegisterRequest):
    err = validate_username(req.username) or validate_password(req.password) or validate_email(req.email)
    if err:
        raise HTTPException(status_code=400, detail=err)
    with DATA_LOCK:
        users = load_users()
        if find_user(users, username=req.username):
            raise HTTPException(status_code=409, detail="用户名已存在")
        user = {
            "id": uuid.uuid4().hex,
            "username": req.username,
            "password": str(req.password),
            "email": req.email,
            "realname": req.realname,
            "role": req.role or "user",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        users.append(user)
        save_users(users)
    return {"code": 0, "msg": "注册成功", "data": public_user(user)}

@router.post("/api/login")
def login(req: UserLoginRequest):
    cleanup_captcha()
    entry = CAPTCHA_STORE.pop(req.captcha_id, None)
    if not entry or entry[0] != req.captcha.strip().lower():
        raise HTTPException(status_code=401, detail="验证码错误或已过期")
    with DATA_LOCK:
        users = load_users()
        user = find_user(users, username=req.username)
    if not user or user["password"] != req.password:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = uuid.uuid4().hex
    TOKENS[token] = {"username": user["username"], "role": user.get("role", "user")}
    return {"code": 0, "msg": "登录成功", "data": {"token": token, "user": public_user(user)}}

@router.post("/api/logout")
def logout(authorization: Optional[str] = Header(None)):
    user = get_token_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="未登录或 token 无效")
    token = authorization[len("Bearer "):] # type: ignore
    TOKENS.pop(token, None)
    return {"code": 0, "msg": "登出成功"}

@router.get("/api/users")
def list_users(
    keyword: str = Query(""),
    authorization: Optional[str] = Header(None),
):
    require_login(authorization)
    with DATA_LOCK:
        users = load_users()
    keyword_lower = keyword.lower()
    result = [
        public_user(u) for u in users
        if not keyword_lower
        or keyword_lower in u.get("username", "").lower()
        or keyword_lower in u.get("email", "").lower()
        or keyword_lower in u.get("realname", "").lower()
    ]
    return {"code": 0, "msg": "success", "data": {"total": len(result), "list": result}}

@router.get("/api/users/{user_id}")
def get_user(user_id: str, authorization: Optional[str] = Header(None)):
    require_login(authorization)
    with DATA_LOCK:
        users = load_users()
    user = find_user(users, id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"code": 0, "msg": "success", "data": public_user(user)}

@router.post("/api/users")
def create_user(req: UserCreateRequest, authorization: Optional[str] = Header(None)):
    require_login(authorization)
    err = validate_username(req.username) or validate_password(req.password) or validate_email(req.email)
    if err:
        raise HTTPException(status_code=400, detail=err)
    with DATA_LOCK:
        users = load_users()
        if find_user(users, username=req.username):
            raise HTTPException(status_code=409, detail="用户名已存在")
        user = {
            "id": uuid.uuid4().hex,
            "username": req.username,
            "password": str(req.password),
            "email": req.email,
            "realname": req.realname,
            "role": req.role or "user",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        users.append(user)
        save_users(users)
    return JSONResponse(
        status_code=201,
        content={"code": 0, "msg": "创建成功", "data": public_user(user)},
    )

@router.put("/api/users/{user_id}")
def update_user(
    user_id: str,
    req: UserUpdateRequest,
    authorization: Optional[str] = Header(None),
):
    require_login(authorization)
    # 校验传入的字段
    if req.username is not None:
        err = validate_username(req.username)
        if err:
            raise HTTPException(status_code=400, detail=err)
    if req.password is not None:
        err = validate_password(req.password)
        if err:
            raise HTTPException(status_code=400, detail=err)
    if req.email is not None:
        err = validate_email(req.email)
        if err:
            raise HTTPException(status_code=400, detail=err)

    with DATA_LOCK:
        users = load_users()
        user = find_user(users, id=user_id)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        if req.username and req.username != user["username"]:
            if find_user(users, username=req.username):
                raise HTTPException(status_code=409, detail="用户名已存在")
        for key in ("username", "password", "email", "realname", "role"):
            val = getattr(req, key, None)
            if val is not None:
                user[key] = str(val) if key == "password" else val
        save_users(users)
    return {"code": 0, "msg": "更新成功", "data": public_user(user)}

@router.delete("/api/users/{user_id}")
def delete_user(user_id: str, authorization: Optional[str] = Header(None)):
    current = require_login(authorization)
    with DATA_LOCK:
        users = load_users()
        user = find_user(users, id=user_id)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        if current.get("role") != "admin":
            raise HTTPException(status_code=403, detail="需要 admin 权限")
        if user["username"] == current["username"]:
            raise HTTPException(status_code=400, detail="不能删除当前登录账号")
        users.remove(user)
        save_users(users)
    return {"code": 0, "msg": "删除成功"}

# ---------- 初始化（首次运行创建 admin）----------
def _ensure_default_admin():
    if not DATA_FILE.exists() or not load_users():
        with DATA_LOCK:
            save_users([{
                "id": uuid.uuid4().hex,
                "username": "admin",
                "realname": "管理员",
                "password": "vNYkjJtIv3JvL4XLOtFbyshVcNnc8naicf8g4fv5VN8=",
                "email": "admin@example.com",
                "role": "admin",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }])
        print("[account_router] 已初始化默认管理员账号")

_ensure_default_admin()
