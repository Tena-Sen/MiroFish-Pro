"""
LLM 配置 API。
"""

import os
from pathlib import Path

from flask import jsonify, request
from openai import OpenAI

from . import llm_bp
from ..config import Config, project_root_env


_CONFIG_KEYS = (
    "LLM_API_KEY",
    "LLM_BASE_URL",
    "LLM_MODEL_NAME",
    "GRAPH_BACKEND",
    "ZEP_API_KEY",
)


def _mask_api_key(value: str | None) -> str:
    if not value:
        return ""
    return "***" + value[-4:] if len(value) > 4 else "***"


def _current_config() -> dict:
    return {
        "api_key_configured": bool(Config.LLM_API_KEY),
        "api_key_masked": _mask_api_key(Config.LLM_API_KEY),
        "base_url": Config.LLM_BASE_URL or "",
        "model_name": Config.LLM_MODEL_NAME or "",
        "graph_backend": Config.GRAPH_BACKEND or "local",
        "zep_api_key_configured": bool(Config.ZEP_API_KEY),
        "zep_api_key_masked": _mask_api_key(Config.ZEP_API_KEY),
    }


def _update_env_file(values: dict) -> None:
    env_path = Path(project_root_env)
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    replaced = set()
    output = []

    for line in lines:
        stripped = line.strip()
        key = stripped.split("=", 1)[0] if "=" in stripped and not stripped.startswith("#") else ""
        if key in _CONFIG_KEYS:
            output.append(f"{key}={values[key]}")
            replaced.add(key)
        else:
            output.append(line)

    for key in _CONFIG_KEYS:
        if key not in replaced:
            output.append(f"{key}={values[key]}")

    env_path.write_text("\n".join(output) + "\n", encoding="utf-8")


def _read_payload(payload: dict, keep_current_key: bool = True) -> dict:
    api_key = payload.get("api_key")
    if api_key is None or (keep_current_key and not str(api_key).strip()):
        api_key = Config.LLM_API_KEY or ""
    else:
        api_key = str(api_key).strip()

    base_url = str(payload.get("base_url") or "").strip()
    model_name = str(payload.get("model_name") or "").strip()

    missing = []
    if not api_key:
        missing.append("API Key")
    if not base_url:
        missing.append("Base URL")
    if not model_name:
        missing.append("Model")
    if missing:
        raise ValueError("请填写：" + "、".join(missing))

    zep_api_key = payload.get("zep_api_key")
    if zep_api_key is None or (keep_current_key and not str(zep_api_key).strip()):
        zep_api_key = Config.ZEP_API_KEY or ""
    else:
        zep_api_key = str(zep_api_key).strip()

    graph_backend = str(payload.get("graph_backend") or Config.GRAPH_BACKEND or "local").strip().lower()
    if graph_backend not in ("local", "zep"):
        raise ValueError("图谱后端只能选择 local 或 zep")
    if graph_backend == "zep" and not zep_api_key:
        raise ValueError("选择 Zep Cloud 后必须填写 Zep API Key")

    return {
        "api_key": api_key,
        "base_url": base_url,
        "model_name": model_name,
        "graph_backend": graph_backend,
        "zep_api_key": zep_api_key,
    }


@llm_bp.get("/config")
def get_llm_config():
    return jsonify({"success": True, "data": _current_config()})


@llm_bp.post("/config")
def save_llm_config():
    try:
        values = _read_payload(request.get_json(silent=True) or {})
        _update_env_file({
            "LLM_API_KEY": values["api_key"],
            "LLM_BASE_URL": values["base_url"],
            "LLM_MODEL_NAME": values["model_name"],
            "GRAPH_BACKEND": values["graph_backend"],
            "ZEP_API_KEY": values["zep_api_key"],
        })

        os.environ.update({
            "LLM_API_KEY": values["api_key"],
            "LLM_BASE_URL": values["base_url"],
            "LLM_MODEL_NAME": values["model_name"],
            "GRAPH_BACKEND": values["graph_backend"],
            "ZEP_API_KEY": values["zep_api_key"],
        })
        Config.LLM_API_KEY = values["api_key"]
        Config.LLM_BASE_URL = values["base_url"]
        Config.LLM_MODEL_NAME = values["model_name"]
        Config.GRAPH_BACKEND = values["graph_backend"]
        Config.ZEP_API_KEY = values["zep_api_key"]

        return jsonify({"success": True, "data": _current_config()})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@llm_bp.post("/test")
def test_llm_connection():
    try:
        values = _read_payload(request.get_json(silent=True) or {}, keep_current_key=True)
        client = OpenAI(
            api_key=values["api_key"],
            base_url=values["base_url"],
            timeout=20,
        )
        response = client.chat.completions.create(
            model=values["model_name"],
            messages=[
                {"role": "system", "content": "只回复 OK。"},
                {"role": "user", "content": "连接测试"},
            ],
            temperature=0,
            max_tokens=8,
        )
        content = response.choices[0].message.content or ""
        return jsonify({
            "success": True,
            "message": "LLM 连接成功",
            "data": {"preview": content[:20]},
        })
    except Exception as exc:
        error_text = str(exc)
        if "Arrearage" in error_text or "overdue-payment" in error_text:
            error_text = "LLM 服务商账户欠费或账户状态异常，请充值、解除欠费后重试。"
        return jsonify({"success": False, "error": f"LLM 连接失败：{error_text}"}), 400
