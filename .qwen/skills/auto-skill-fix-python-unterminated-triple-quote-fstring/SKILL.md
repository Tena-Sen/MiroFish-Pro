---
name: fix-python-unterminated-triple-quote-fstring
description: Fix Python SyntaxError "unterminated triple-quoted string literal" caused by an unclosed f-string (prompt = f""") whose closing """ was missing before the next statement
source: auto-skill
extracted_at: '2026-06-14T08:49:00.000Z'
---

## Problem
Python reports `SyntaxError: unterminated triple-quoted string literal (detected at line N)` on a file that looks correct. The real cause is often that an f-string using triple quotes (`prompt = f"""...""") was missing its closing `"""` before the next line of code. Since everything after the unclosed `"""` is consumed as string content, the error surfaces at a later line (or even the end of file).

## Root Cause Pattern
```python
# ❌ BROKEN: f-string never closed
prompt = f"""
示例:
{{
    "reasoning": "针对该事件的时间配置说明"
}}

字段说明:
- reasoning (string): 简要说明为什么这样配置

        system_prompt = "..."  # ← This line is INSIDE the f-string!
```

The triple-quoted f-string starts on line N but the closing `"""` is never written. The next line (`system_prompt = ...`) is swallowed into the string literal. Python keeps reading until the end of the file and reports the error at the last line.

## Detection
1. Run `python -m py_compile file.py` — if it fails with "unterminated triple-quoted string literal", the error is in a triple-quoted string.
2. Search for all `f"""` or `"""` in the file — count opening vs closing triple quotes. They must pair up.
3. Look at the error line — if it's near EOF or looks like a normal code statement (e.g., `system_prompt = ...`), the real issue is earlier.

## Fix
Add the missing closing `"""` (and any needed escaping) before the next code statement:

```python
# ✅ FIXED
prompt = f"""
示例:
{{
    "reasoning": "针对该事件的时间配置说明"
}}

字段说明:
- reasoning (string): 简要说明为什么这样配置
}}"""

        system_prompt = "..."  # ← Now correctly outside the f-string
```

## When This Commonly Happens
1. **Building long prompt strings for LLM APIs** — Developers write multi-line f-strings with JSON examples containing nested braces (`{{...}}`), and the closing `"""` gets lost among the formatting.
2. **After a refactor** — Code is inserted between the f-string start and end, breaking the intended scope.
3. **Copy-paste from templates** — A prompt template block is copied but the trailing `"""` is omitted.
4. **Mixed indentation** — The closing `"""` ends up with wrong indentation (e.g., indented as part of the docstring content).

## Prevention Checklist
- After writing a multi-line f-string, immediately add the closing `"""` before writing the next statement.
- Use a linter (ruff, flake8) — `flake8` or `ruff` will flag unterminated strings.
- When editing large prompt f-strings, keep a mental count: each `"""` opens AND closes; they pair sequentially.
- For very long prompts, consider using a separate `.prompt` file loaded via `pathlib.read_text()` to avoid triple-quote nesting.

## Key Takeaway
> An unterminated triple-quoted string in Python doesn't error at the line where `"""` is opened — it errors at the **end of the file** (or at the next unmatched `"""`). When you see this error on a line that looks perfectly normal, the real bug is upstream in a triple-quoted string that was never closed.
