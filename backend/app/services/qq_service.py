"""Official QQ gateway; one receiver per shared lock volume, REST for delivery."""
import asyncio
import contextlib
import json
import random
import re
import time
from urllib.parse import quote
import httpx
from app.core.config import settings
from app.db.session import SessionLocal
from app.services.channel_service import channel_status, ensure_available, claim_event

_token = ""
_expires = 0.0
_token_lock = asyncio.Lock()
_status = "未启动"

def connection_status():
    return _status

ERROR_FIELDS = ("error", "code", "http_status", "provider_message", "trace_id", "stage")


class QQAPIError(ValueError):
    def __init__(self, result):
        self.result = result
        super().__init__(result["error"])


def _safe_detail(value):
    text = str(value or "")
    for secret in (_token, settings.QQ_BOT_APP_SECRET.get_secret_value()):
        if secret:
            text = text.replace(secret, "[redacted]")
    return text[:1000]


def _response_data(response):
    try:
        data = response.json()
        return data if isinstance(data, dict) else {}
    except ValueError:
        return {}


def _api_error(response, data, stage):
    code = data.get("err_code", data.get("code"))
    message = _safe_detail(data.get("message") or data.get("msg") or data.get("error_description"))
    trace = _safe_detail(data.get("trace_id") or response.headers.get("X-Tps-trace-ID"))
    detail = [f"QQ {stage}失败", f"HTTP {response.status_code}"]
    if code is not None:
        detail.append(f"错误码 {code}")
    detail.append(message or "平台未返回具体错误说明")
    if trace:
        detail.append(f"Trace ID: {trace}")
    result = {"success": False, "error": "；".join(detail), "code": code,
              "http_status": response.status_code, "provider_message": message,
              "trace_id": trace, "stage": stage}
    from app.middleware.logging import logger
    logger.warning("%s", result["error"])
    return result


async def access_token():
    global _token, _expires
    async with _token_lock:
        if _token and time.monotonic() < _expires:
            return _token
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post("https://api.bot.qq.com/app/getAppAccessToken", json={"appId": settings.QQ_BOT_APP_ID, "clientSecret": settings.QQ_BOT_APP_SECRET.get_secret_value()})
        data = _response_data(response)
        if response.is_error or data.get("err_code", data.get("code")) not in (None, 0) or not data.get("access_token"):
            raise QQAPIError(_api_error(response, data, "获取访问凭证"))
        _token = data["access_token"]
        _expires = time.monotonic() + max(1, int(data.get("expires_in", 7200)) - 60)
        return _token

async def api_request(method, path, payload=None):
    global _expires
    ensure_available("qq")
    for attempt in range(3):
        token = await access_token()
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.request(method, "https://api.bot.qq.com" + path,
                headers={"Authorization": f"QQBot {token}", "X-Union-Appid": settings.QQ_BOT_APP_ID}, json=payload)
        data = _response_data(response)
        if response.status_code == 401 and attempt == 0:
            _expires = 0
            continue
        if response.status_code == 429 and attempt < 2:
            try:
                delay = float(response.headers.get("Retry-After", 2))
            except ValueError:
                delay = 2
            await asyncio.sleep(min(10, max(1, delay)))
            continue
        error_code = data.get("err_code", data.get("code"))
        if response.is_error or error_code not in (None, 0) or not data:
            return _api_error(response, data, "发送消息" if method == "POST" else "获取网关")
        return {"success": True, **data}
    return {"success": False, "error": "QQ 请求重试失败"}

async def send_qq_message(address, text, msg_id=None):
    kind, sep, external_id = str(address).partition(":")
    if not sep or kind not in ("private", "group") or not external_id:
        return {"success": False, "error": "QQ 接收目标无效"}
    path = f"/v2/{'users' if kind == 'private' else 'groups'}/{quote(external_id, safe='')}/messages"
    # One bounded text message; reports are delivered as summaries + links.
    payload = {"msg_type": 0, "content": text[:3500] + ("\n（内容较长，已截取）" if len(text) > 3500 else "")}
    if msg_id:
        payload.update(msg_id=msg_id, msg_seq=1)
    try:
        result = await api_request("POST", path, payload)
        return {"success": result.get("success", False), **({"message_id": result["id"]} if result.get("id") else {}), **{k: result[k] for k in ERROR_FIELDS if k in result}}
    except QQAPIError as exc:
        return exc.result
    except httpx.HTTPError as exc:
        # Network failures have no provider response; never retry an unknown POST outcome.
        return {"success": False, "error": f"QQ 网络请求失败（{type(exc).__name__}），发送结果可能不确定，请检查网络后再操作", "stage": "网络请求"}
    except ValueError as exc:
        return {"success": False, "error": f"QQ 请求配置或响应无效：{_safe_detail(exc)}", "stage": "请求校验"}

async def handle_event(event):
    if event.get("t") not in ("C2C_MESSAGE_CREATE", "GROUP_AT_MESSAGE_CREATE"):
        return
    data = event.get("d") or {}
    author = data.get("author") or {}
    group = event["t"] == "GROUP_AT_MESSAGE_CREATE"
    sender = author.get("member_openid") if group else author.get("user_openid")
    target = data.get("group_openid") if group else sender
    text = re.sub(r"<@!?[^>]+>", "", data.get("content") or "").strip()
    if not sender or not target or not text or not data.get("id"):
        return
    db = SessionLocal()
    try:
        if not claim_event(db, "qq", data["id"]):
            return
        from app.services.channel_inbound import process_inbound
        kind = "group" if group else "private"
        reply = await process_inbound(db, "qq", sender, target, kind, text)
        if reply:
            await send_qq_message(f"{kind}:{target}", reply, data["id"])
    finally:
        db.close()

async def run_qq_gateway():
    global _status, _expires
    if not channel_status("qq")["available"]:
        _status = "已关闭" if not settings.QQ_BOT_ENABLED else "凭证未配置"
        return
    # File lock works across workers on one host/shared volume; multiple hosts
    # must use a single receiver deployment (see deployment documentation).
    import fcntl
    from websockets.asyncio.client import connect
    lock = open(settings.QQ_BOT_LOCK_PATH, "a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        _status = "由其他进程接收"
        lock.close()
        return
    queue = asyncio.Queue(maxsize=100)
    async def worker():
        while True:
            event = await queue.get()
            try:
                await handle_event(event)
            except Exception:
                from app.middleware.logging import logger
                logger.error("QQ 消息处理失败；请检查渠道和 Agent 配置")
            finally:
                queue.task_done()
    consumer = asyncio.create_task(worker())
    session_id = None
    sequence = None
    backoff = 1
    try:
        while True:
            try:
                _status = "连接中"
                gateway = await api_request("GET", "/gateway")
                if not gateway.get("url"):
                    raise ValueError("gateway unavailable")
                token = await access_token()
                async with connect(gateway["url"], ping_interval=None, max_size=2**20) as ws:
                    hello = json.loads(await asyncio.wait_for(ws.recv(), 20))
                    if hello.get("op") != 10:
                        raise ValueError("expected hello")
                    interval = max(1, hello["d"]["heartbeat_interval"] / 1000)
                    if session_id:
                        await ws.send(json.dumps({"op": 6, "d": {"token": f"QQBot {token}", "session_id": session_id, "seq": sequence}}))
                    else:
                        await ws.send(json.dumps({"op": 2, "d": {"token": f"QQBot {token}", "intents": 1 << 25, "shard": [0, 1]}}))
                    acknowledged = True
                    async def heartbeat():
                        nonlocal acknowledged
                        while True:
                            await asyncio.sleep(interval)
                            if not acknowledged:
                                await ws.close()
                                return
                            acknowledged = False
                            await ws.send(json.dumps({"op": 1, "d": sequence}))
                    heart = asyncio.create_task(heartbeat())
                    try:
                        while True:
                            event = json.loads(await asyncio.wait_for(ws.recv(), interval * 2 + 10))
                            previous_sequence = sequence
                            if event.get("s") is not None:
                                sequence = event["s"]
                            op = event.get("op")
                            if op == 11:
                                acknowledged = True
                            elif op == 1:
                                await ws.send(json.dumps({"op": 1, "d": sequence}))
                            elif op in (7, 9):
                                if op == 9:
                                    session_id = None
                                    sequence = None
                                    _expires = 0
                                break
                            elif op == 0:
                                if event.get("t") == "READY":
                                    session_id = event["d"]["session_id"]
                                if event.get("t") in ("READY", "RESUMED"):
                                    _status = "已连接"
                                    backoff = 1
                                elif event.get("t") in ("C2C_MESSAGE_CREATE", "GROUP_AT_MESSAGE_CREATE"):
                                    # Backpressure must not block heartbeat reception.
                                    try:
                                        queue.put_nowait(event)
                                    except asyncio.QueueFull:
                                        sequence = previous_sequence
                                        raise
                    finally:
                        heart.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await heart
            except asyncio.CancelledError:
                raise
            except Exception:
                _status = "连接中断，正在重连"
            await asyncio.sleep(backoff + random.random())
            backoff = min(backoff * 2, 60)
    finally:
        consumer.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await consumer
        _status = "已停止"
        lock.close()
