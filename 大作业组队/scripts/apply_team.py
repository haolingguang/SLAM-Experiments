#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
组队报名自动登记脚本

由 GitHub Actions 在 Issue 被打开 / 编辑 / 重新校验时调用。

职责：
  1. 解析 Issue 表单内容（### 标题 + 正文 的 Markdown 结构）
  2. 校验：人数、重复姓名、重复队名、电话格式
  3. 通过 → 写入 roster.csv（占用第一个空位）、同步刷新 README.md 中的名单表格
  4. 回评论、打标签、关闭 Issue
  5. 失败 → 回评论列出具体原因，Issue 保持打开，等学生 Edit 后重跑

环境变量（由 workflow 注入）：
  ISSUE_BODY      Issue 正文
  ISSUE_NUMBER    Issue 编号
  ISSUE_AUTHOR    提交人 GitHub 用户名
  ISSUE_LABELS    逗号分隔的标签名
  ISSUE_TITLE     Issue 标题
  GH_TOKEN        GitHub token（gh cli 用）
  REPO            owner/repo
"""

import csv
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent      # .../大作业组队/
REPO_ROOT = ROOT.parent                            # 仓库根目录
CSV_PATH = ROOT / "roster.csv"
README_PATH = ROOT / "README.md"
STATE_PATH = REPO_ROOT / ".github" / "state.json"

HEADER = ["序号", "成员1", "成员2", "成员3", "联系电话"]
MAX_MEMBERS = 3
MIN_MEMBERS = 1
TEAM_NAME_MAX = 30

EMPTY_TOKENS = {"", "_no response_", "无", "没有", "-", "—", "空", "none"}
CANCEL_LABEL = "取消报名"


# --------------------------------------------------------------------------
# 通用 IO
# --------------------------------------------------------------------------
def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default) or default


def read_rows() -> list[list[str]]:
    """读取 roster.csv，统一补齐为 5 列。"""
    if not CSV_PATH.exists():
        return [HEADER[:] ] if False else []
    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    if not rows:
        return []
    # 第一行视为表头（可能是 序号,成员1,成员2,成员3,联系电话）
    data = rows[1:]
    fixed: list[list[str]] = []
    for r in data:
        r = [c.strip() for c in r]
        while len(r) < len(HEADER):
            r.append("")
        fixed.append(r[: len(HEADER)])
    return fixed


def write_rows(rows: list[list[str]]) -> None:
    """写回 roster.csv（utf-8-sig 便于 Excel 直接双击打开不乱码）。"""
    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        for r in rows:
            writer.writerow(r)


def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"issues": {}}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


# --------------------------------------------------------------------------
# 解析 Issue 表单
# --------------------------------------------------------------------------
def parse_form(body: str) -> dict[str, str]:
    """把 `### 标签\n内容` 结构解析成 {标签: 内容}。"""
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in (body or "").splitlines():
        m = re.match(r"^#{2,4}\s+(.+?)\s*$", line)
        if m:
            current = m.group(1).strip()
            sections.setdefault(current, [])
        elif current is not None:
            sections[current].append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items()}


def pick(sections: dict[str, str], keyword: str) -> str:
    """按标签关键词取内容，取第一个命中的。"""
    for k, v in sections.items():
        if keyword in k:
            return clean_value(v)
    return ""


def clean_value(v: str) -> str:
    """清理表单值：去掉复选框行、去除首尾空白、识别空值占位。"""
    if not v:
        return ""
    kept = []
    for line in v.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("- ["):  # 复选框
            continue
        kept.append(s)
    joined = " ".join(kept).strip()
    if joined.lower() in EMPTY_TOKENS:
        return ""
    return joined


# --------------------------------------------------------------------------
# 业务校验
# --------------------------------------------------------------------------
def collect_members(sections: dict[str, str]) -> list[str]:
    names = []
    for i in range(1, MAX_MEMBERS + 1):
        raw = pick(sections, f"成员{i}")
        raw = re.sub(r"（.*?）|\(.*?\)", "", raw).strip()  # 去掉「（队长）」之类后缀
        if raw:
            names.append(raw)
    return names


def validate(team: str, members: list[str], phone: str,
             rows: list[list[str]], state: dict, issue_number: str) -> list[str]:
    errors: list[str] = []

    if not team:
        errors.append("队伍名称不能为空。")
    elif len(team) > TEAM_NAME_MAX:
        errors.append(f"队伍名称过长（{len(team)} 字），请控制在 {TEAM_NAME_MAX} 字以内。")

    if len(members) < MIN_MEMBERS:
        errors.append("至少要填写 1 名成员（成员1 为必填）。")
    if len(members) > MAX_MEMBERS:
        errors.append(f"每队最多 {MAX_MEMBERS} 人，当前提交了 {len(members)} 人。")

    # 队内重复
    seen, dup = set(), []
    for n in members:
        if n in seen and n not in dup:
            dup.append(n)
        seen.add(n)
    if dup:
        errors.append("同一队伍中出现了重复姓名：" + "、".join(dup))

    # 队名重复
    my_prev_row = state["issues"].get(issue_number, {}).get("row")
    for onum, info in state["issues"].items():
        if onum == issue_number:
            continue
        if info.get("team") == team:
            errors.append(f"队伍名称「{team}」已被占用（Issue #{onum}），请换一个。")
            break

    # 成员已在别的队
    owner_of: dict[str, str] = {}
    for idx, r in enumerate(rows):
        if my_prev_row is not None and idx == my_prev_row:
            continue
        for name in r[1:4]:
            if name:
                owner_of[name] = r[0]
    clash = [n for n in members if n in owner_of]
    if clash:
        for n in clash:
            seq = owner_of[n]
            errors.append(f"「{n}」已登记在序号 {seq} 的队伍中，不能重复组队。")

    # 电话格式（宽松：数字/加号/横杠/空格，4~20 位）
    if phone and not re.fullmatch(r"[0-9+\-\s]{4,20}", phone):
        errors.append("联系电话格式不正确，请只填数字（可含 - 或空格），或留空。")

    return errors


# --------------------------------------------------------------------------
# 写入 / 回滚
# --------------------------------------------------------------------------
def upsert_row(members: list[str], phone: str, rows: list[list[str]],
               prev_row: int | None) -> tuple[int, list[list[str]]]:
    """写入或更新一行，返回 (行下标, 新 rows)。prev_row 为 None 表示新增。"""
    payload = members + [""] * (MAX_MEMBERS - len(members))
    record = [None, payload[0], payload[1], payload[2], phone]

    if prev_row is not None and 0 <= prev_row < len(rows):
        seq = rows[prev_row][0] or str(prev_row + 1)
        rows[prev_row] = [seq] + record[1:]
        return prev_row, rows

    # 找一个队名列为空的空位
    for i, r in enumerate(rows):
        if not any(r[1:4]):
            rows[i] = [r[0] or str(i + 1)] + record[1:]
            return i, rows

    # 没有空位就新增一行
    next_seq = str(len(rows) + 1)
    rows.append([next_seq] + record[1:])
    return len(rows) - 1, rows


def remove_row(prev_row: int, rows: list[list[str]]) -> list[list[str]]:
    if prev_row is not None and 0 <= prev_row < len(rows):
        rows[prev_row] = [rows[prev_row][0], "", "", "", ""]
    return rows


# --------------------------------------------------------------------------
# README 名单表格同步
# --------------------------------------------------------------------------
START_MARK = "<!-- ROSTER:START -->"
END_MARK = "<!-- ROSTER:END -->"


def mask_phone(p: str) -> str:
    if len(p) >= 7:
        return p[:3] + "****" + p[-4:] if len(p) >= 11 else p[:2] + "****"
    return p


def render_table(rows: list[list[str]]) -> str:
    lines = [
        START_MARK,
        "| 序号 | 成员1 | 成员2 | 成员3 | 联系电话 |",
        "| :--: | :-- | :-- | :-- | :-- |",
    ]
    for r in rows:
        cells = [r[0], r[1], r[2], r[3], mask_phone(r[4]) if r[4] else ""]
        cells = [c.replace("|", "\\|") for c in cells]
        lines.append("| " + " | ".join(cells) + " |")
    lines.append(END_MARK)
    return "\n".join(lines)


def sync_readme(rows: list[list[str]]) -> None:
    if not README_PATH.exists():
        return
    text = README_PATH.read_text(encoding="utf-8")
    table = render_table(rows)
    pattern = re.compile(re.escape(START_MARK) + r".*?" + re.escape(END_MARK), re.S)
    if pattern.search(text):
        text = pattern.sub(lambda _m: table, text)
    else:
        text = text.rstrip() + "\n\n" + table + "\n"
    README_PATH.write_text(text, encoding="utf-8")


# --------------------------------------------------------------------------
# GitHub 交互
# --------------------------------------------------------------------------
def gh(*args: str) -> subprocess.CompletedProcess:
    repo = env("REPO")
    cmd = ["gh", *args]
    if repo:
        cmd += ["--repo", repo]
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")


def comment(body: str) -> None:
    n = env("ISSUE_NUMBER")
    if not n:
        return
    r = gh("issue", "comment", n, "--body", body)
    if r.returncode != 0:
        print("comment failed:", r.stderr, file=sys.stderr)


def add_label(label: str) -> None:
    n = env("ISSUE_NUMBER")
    if n:
        gh("issue", "edit", n, "--add-label", label)


def remove_label(label: str) -> None:
    n = env("ISSUE_NUMBER")
    if n:
        gh("issue", "edit", n, "--remove-label", label)


def close_issue() -> None:
    n = env("ISSUE_NUMBER")
    if n:
        gh("issue", "close", n, "--reason", "completed")


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------
def main() -> int:
    issue_number = env("ISSUE_NUMBER")
    author = env("ISSUE_AUTHOR")
    labels = [s.strip() for s in env("ISSUE_LABELS").split(",") if s.strip()]
    sections = parse_form(env("ISSUE_BODY"))

    rows = read_rows()
    state = load_state()
    prev_row = state["issues"].get(issue_number, {}).get("row")

    # ---- 取消报名分支 ----
    if CANCEL_LABEL in labels:
        rows = remove_row(prev_row, rows)
        write_rows(rows)
        sync_readme(rows)
        state["issues"].pop(issue_number, None)
        save_state(state)
        comment("已收到取消报名，名单中的这一行已清空。如需重新组队，请新建一个「组队报名」Issue。")
        close_issue()
        return 0

    team = pick(sections, "队伍名称")
    members = collect_members(sections)
    phone = pick(sections, "联系电话")

    errors = validate(team, members, phone, rows, state, issue_number)

    if errors:
        body = "### ❌ 登记未通过，请修改后自动重试\n\n"
        body += "\n".join(f"- {e}" for e in errors)
        body += (
            "\n\n> 修改方式：点击本页右上角 **Edit**，改完直接保存即可，"
            "无需关闭本 Issue，机器人会自动重新校验。\n"
        )
        comment(body)
        add_label("需修改")
        print("validation failed:", errors)
        return 0

    # ---- 写入 ----
    idx, rows = upsert_row(members, phone, rows, prev_row)
    write_rows(rows)
    sync_readme(rows)

    state["issues"][issue_number] = {
        "row": idx,
        "team": team,
        "members": members,
        "author": author,
    }
    save_state(state)

    seq = rows[idx][0]
    body = "### ✅ 登记成功\n\n"
    body += f"- **队伍名称**：{team}\n"
    body += f"- **名单序号**：{seq}\n"
    body += f"- **成员**：{'、'.join(members)}（共 {len(members)} 人）\n"
    if phone:
        body += f"- **联系电话**：{phone}\n"
    body += (
        "\n名单已自动写入 `roster.csv`，并同步更新了仓库首页的表格。\n\n"
        "如果需要**修改成员**：直接 Edit 本 Issue 后保存，系统会自动覆盖原来那一行。\n\n"
        "如果需要**取消报名**：给本 Issue 加上 `取消报名` 标签即可。\n"
    )
    comment(body)
    remove_label("需修改")
    close_issue()
    print(f"registered: team={team} row={idx} seq={seq}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
