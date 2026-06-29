"""
原子文件 I/O 工具

修复并发场景下的「读到半截写入文件」问题：
- 监控线程每 5 秒写一次 run_state.json
- 前端每 2-3 秒轮询读取 run_state.json
- 在 Windows 上，写入中途如果被读取，读到的是截断 JSON

解决方案：写入临时文件 + os.replace() 原子重命名（同目录下 Windows/Linux 都是原子的）。

用法：
    from app.utils.atomic_io import atomic_write_json, atomic_write_text

    atomic_write_json('/path/to/run_state.json', data)
    atomic_write_text('/path/to/log.txt', 'content')

不改变预测准确度——纯文件系统语义，与 LLM 无关。
"""

import json
import os
import tempfile
import threading
import time
from typing import Any, Union


# 线程级唯一标识用于临时文件名，避免同一进程多线程冲突
_local = threading.local()


def _temp_suffix() -> str:
    """生成线程级唯一临时后缀，避免多线程写入同一目录冲突"""
    pid = os.getpid()
    tid = getattr(_local, 'thread_id', None)
    if tid is None:
        tid = threading.get_ident()
        _local.thread_id = tid
    return f".tmp.{pid}.{tid}"


def atomic_write_text(path: str, content: str, encoding: str = 'utf-8') -> None:
    """
    原子写入文本文件：写入临时文件 → os.replace 覆盖。

    Args:
        path: 目标文件路径
        content: 要写入的文本
        encoding: 文件编码，默认 utf-8

    Raises:
        OSError: 写入失败时抛出（最终重试后仍失败）
    """
    dir_name = os.path.dirname(path) or None
    # 修复（必修 4）：Windows 上 os.replace 经常被 [WinError 5] 拒绝访问打断
    # 根因：Windows Defender 扫描 / OneDrive 同步 / AV 软件短暂持有目标文件句柄
    # 解决：os.replace 失败时重试（短退避），而不是直接抛错
    # 关键：tmp 文件已落盘且已关闭 → 重试只需重做 os.replace，不需要重写 tmp
    last_exc: Exception = None
    backoff_ms = [0, 50, 150, 400, 800]  # 5 次尝试，0/50/150/400/800ms 退避
    tmp_path = None
    try:
        # 第一次写 tmp
        fd, tmp_path = tempfile.mkstemp(
            prefix=os.path.basename(path) + '.',
            suffix=_temp_suffix(),
            dir=dir_name,
        )
        with os.fdopen(fd, 'w', encoding=encoding) as f:
            f.write(content)
    except Exception as e:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise OSError(f"原子写入失败（写 tmp 阶段）: {path}: {e}") from e

    # os.replace 重试阶段
    for attempt, sleep_ms in enumerate(backoff_ms):
        try:
            if sleep_ms > 0:
                time.sleep(sleep_ms / 1000.0)
            os.replace(tmp_path, path)
            return  # 成功
        except OSError as e:
            last_exc = e
            # WinError 5 (ERROR_ACCESS_DENIED) / 32 (sharing violation) / 33 (lock violation) → 重试
            # 其他 OSError（如磁盘满、路径不存在）→ 立即失败
            winerror = getattr(e, 'winerror', None)
            errno = getattr(e, 'errno', None)
            if winerror not in (5, 32, 33) and errno not in (13, 11):  # EACCES=13, EAGAIN=11
                # 不可重试的错误
                break
            if attempt == len(backoff_ms) - 1:
                break  # 最后一次也失败
            # 否则继续重试
        except Exception as e:
            last_exc = e
            break  # 未知异常，不重试

    # 所有重试用尽，清理 tmp 并抛出
    try:
        os.remove(tmp_path)
    except OSError:
        pass
    raise OSError(f"原子写入失败（os.replace 重试 {len(backoff_ms)} 次后仍失败）: {path}: {last_exc}") from last_exc


def atomic_write_json(
    path: str,
    data: Any,
    encoding: str = 'utf-8',
    indent: int = 2,
    ensure_ascii: bool = False,
) -> None:
    """
    原子写入 JSON 文件。

    Args:
        path: 目标文件路径
        data: 可被 json.dumps 序列化的对象
        encoding: 文件编码，默认 utf-8
        indent: 缩进空格数，默认 2
        ensure_ascii: 是否转义非 ASCII 字符，默认 False（保留中文）

    Raises:
        OSError: 写入失败时抛出
    """
    content = json.dumps(data, ensure_ascii=ensure_ascii, indent=indent)
    atomic_write_text(path, content, encoding=encoding)
