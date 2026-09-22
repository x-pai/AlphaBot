"""在可重启子进程内运行原生 SDK，隔离 chdir、原生阻塞及配置文件。"""
from __future__ import annotations

import asyncio
import configparser
import contextlib
import io
import importlib
import importlib.util
import multiprocessing as mp
import os
import re
from pathlib import Path
import shutil
import sys
import tempfile
import time
from typing import Any

from app.core.config import settings


class TdxAiDataUnavailable(RuntimeError):
    """TDX 未返回有效数据；不能作为空行情缓存。"""


class TdxAiDataAuthenticationError(TdxAiDataUnavailable):
    """额度或 Key 错误，不重试、不按证券展开请求。"""


def _worker(connection, lib_dir: str, token: str, runtime_dir: str) -> None:
    try:
        if lib_dir:
            origin = Path(lib_dir).expanduser().resolve()
        elif os.environ.get("TDX_AI_DATA_LIB"):
            origin = Path(os.environ["TDX_AI_DATA_LIB"]).expanduser().resolve().parent
        else:
            spec = importlib.util.find_spec("tdxaidata")
            if spec is None or spec.origin is None:
                raise RuntimeError("install requirements.txt")
            origin = Path(spec.origin).parent / "lib"
        target = Path(runtime_dir)
        shutil.copytree(origin, target, dirs_exist_ok=True)
        ini = target / "TdxAiData.ini"
        if token:
            config = configparser.ConfigParser()
            config.optionxform = str
            config.read(ini, encoding="utf-8-sig")
            if not config.has_section("Token"):
                config.add_section("Token")
            config.set("Token", "token", token)
            with ini.open("w", encoding="utf-8") as f:
                config.write(f)
        if ini.exists():
            ini.chmod(0o600)
        library = "TdxAiData.dll" if os.name == "nt" else "libTdxAiData.dylib" if sys.platform == "darwin" else "libTdxAiData.so"
        os.environ["TDX_AI_DATA_LIB"] = str(target / library)
        sdk = importlib.import_module("tdxaidata").tqs
        while True:
            request = connection.recv()
            if request is None:
                break
            method, args, kwargs = request
            try:
                sdk_output = io.StringIO()
                with contextlib.redirect_stdout(sdk_output):
                    result = getattr(sdk, method)(*args, **kwargs)
                if '[错误]' in sdk_output.getvalue():
                    messages = [line for line in sdk_output.getvalue().splitlines() if '[错误]' in line]
                    safe_message = re.sub(r'TDX-[A-Za-z0-9_-]+', '[redacted]', '; '.join(messages))[:200]
                    raise TdxAiDataUnavailable(f'{method}: {safe_message}')
                if result is None:
                    raise TdxAiDataUnavailable(f"{method}: no data; check connectivity and data permissions")
                connection.send((True, result))
            except Exception as exc:
                # 不传回 SDK 的原始异常文本，避免其中携带认证配置。
                connection.send((False, str(exc) if isinstance(exc, TdxAiDataUnavailable) else f"{method}: {type(exc).__name__}; check SDK connectivity, parameters and permissions"))
    except EOFError:
        pass
    except Exception as exc:
        try:
            connection.send((False, f"SDK initialization failed: {type(exc).__name__}"))
        except (BrokenPipeError, EOFError):
            pass
    finally:
        connection.close()


class TdxAiDataClient:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._pending = 0
        self._process = None
        self._connection = None
        self._runtime = None
        self._closed = False
        self._auth_error_until = 0.0
        self._auth_error = ""

    def _start(self) -> None:
        self._runtime = tempfile.TemporaryDirectory(prefix="alphabot-tdxaidata-")
        context = mp.get_context("spawn")
        parent, child = context.Pipe()
        self._connection = parent
        self._process = context.Process(target=_worker, args=(
            child, settings.TDXAIDATA_LIB_DIR, settings.TDXAIDATA_TOKEN.get_secret_value(), self._runtime.name,
        ), daemon=True)
        self._process.start()
        child.close()

    def _stop(self) -> None:
        if self._process is not None:
            if self._process.is_alive():
                self._process.terminate()
            self._process.join(timeout=1)
            if self._process.is_alive():
                self._process.kill()
                self._process.join(timeout=1)
            self._process.close()
        if self._connection is not None:
            self._connection.close()
        if self._runtime is not None:
            self._runtime.cleanup()
        self._process = self._connection = self._runtime = None

    def _exchange_once(self, request, timeout: float):
        if self._process is None or not self._process.is_alive():
            self._stop()
            self._start()
        try:
            self._connection.send(request)
            if not self._connection.poll(timeout):
                raise TimeoutError("tdxaidata native call timed out; worker restarted on next request")
            ok, value = self._connection.recv()
            if not ok:
                if "TokenKey" in str(value):
                    raise TdxAiDataAuthenticationError(value)
                raise TdxAiDataUnavailable(value)
            return value
        except (TimeoutError, EOFError, BrokenPipeError, OSError) as exc:
            self._stop()
            raise TdxAiDataUnavailable(str(exc)) from exc

    def _exchange(self, request, timeout: float):
        if time.monotonic() < self._auth_error_until:
            raise TdxAiDataAuthenticationError(self._auth_error)
        deadline = time.monotonic() + timeout
        for attempt in range(3):
            try:
                return self._exchange_once(request, max(0.01, deadline-time.monotonic()))
            except TdxAiDataAuthenticationError as exc:
                self._auth_error_until = time.monotonic() + 60
                self._auth_error = str(exc)
                raise
            except TdxAiDataUnavailable:
                if attempt == 2 or time.monotonic() >= deadline:
                    raise
                self._stop()
                time.sleep(min(0.25 * (attempt+1), max(0, deadline-time.monotonic())))

    async def call(self, method_name: str, *args: Any, timeout_seconds: float | None = None, **kwargs: Any) -> Any:
        if self._closed:
            raise RuntimeError("tdxaidata client is closed")
        if self._pending >= max(1, settings.TDXAIDATA_MAX_PENDING):
            raise TdxAiDataUnavailable("tdxaidata request queue is full")
        self._pending += 1
        timeout = max(0.05, timeout_seconds or settings.TDXAIDATA_TIMEOUT)
        try:
            async with self._lock:
                if self._closed:
                    raise RuntimeError("tdxaidata client is closed")
                task = asyncio.create_task(asyncio.to_thread(self._exchange, (method_name, args, kwargs), timeout))
                try:
                    return await asyncio.shield(task)
                except asyncio.CancelledError:
                    # 不让另一请求在当前原生调用结束前复用同一连接。
                    await task
                    raise
        finally:
            self._pending -= 1

    async def aclose(self) -> None:
        self._closed = True
        async with self._lock:
            await asyncio.to_thread(self._stop)
