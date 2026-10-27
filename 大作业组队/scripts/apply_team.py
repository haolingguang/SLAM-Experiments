#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
组队报名自动登记脚本（两阶段执行）

    python3 apply_team.py plan      解析 + 校验 + 写文件（不评论）
    python3 apply_team.py notify    根据结果和 push 状态评论 / 打标签 / 关闭 Issue

为什么要拆两段：必须先确认 git push 成功，才能告诉学生"登记成功"。
早期版本在校验通过就回"✅ 成功"，push 被拒时学生会看到假成功。

环境变量（由 workflow 注入）：
    ISSUE_BODY / ISSUE_NUMBER / ISSUE_AUTHOR / ISSUE_LABELS
    GH_TOKEN / REPO
    PUSH_STATUS     notify 阶段使用：success | nochange | failed
"""

import csv
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent      # .../大作业组队/
REPO_ROOT = ROOT.parent                            # 仓库根目录
CSV_PATH = ROOT / "roster.csv"
README_PATH = ROOT / "README.md"
STATE_PATH = REPO_ROOT / ".github" / "state.json"
RESULT_PATH = Path(tempfile.gettempdir()) / "roster_result.json"

HEADER = ["序号", "成员1", "成员2", "成员3", "备注"]
MAX_MEMBERS = 3
MIN_MEMBERS = 1
TEAM_NAME_MAX = 30
NOTE_MAX = 100          # 备注长度上限（字）
NOTE_TABLE_MAX = 30     # README 表格内备注显示上限（字），超出用 … 截断

EMPTY_TOKENS = {"", "_no response_", "无", "没有", "-", "—", "空", "none"}
CANCEL_LABEL = "取消报名"
FIX_LABEL = "需修改"


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default) or default


# --------------------------------------------------------------------------
# IO
# --------------------------------------------------------------------------
def read_rows() -> list[list[str]]:
    if not CSV_PATH.exists():
        return []
    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    fixed = []
    for r in rows[1:]:
        r = [c.strip() for c in r]
        while len(r) < len(HEADER):
            r.append("")
        fixed.append(r[: len(HEADER)])
    return fixed


def write_rows(rows: list[list[str]]) -> None:
    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        for r in rows:
            w.writerow(r)


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
# 表单解析
# --------------------------------------------------------------------------
def parse_form(body: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current = None
    for line in (body or "").splitlines():
        m = re.match(r"^#{2,4}\s+(.+?)\s*$", line)
        if m:
            current = m.group(1).strip()
            sections.setdefault(current, [])
        elif current is not None:
            sections[current].append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items()}


def clean_value(v: str) -> str:
    if not v:
        return ""
    kept = []
    for line in v.splitlines():
        s = line.strip()
        if not s or s.startswith("- ["):
            continue
        kept.append(s)
    joined = " ".join(kept).strip()
    return "" if joined.lower() in EMPTY_TOKENS else joined


def pick(sections: dict[str, str], keyword: str) -> str:
    for k, v in sections.items():
        if keyword in k:
            return clean_value(v)
    return ""


def collect_members(sections: dict[str, str]) -> list[str]:
    names = []
    for i in range(1, MAX_MEMBERS + 1):
        raw = pick(sections, f"成员{i}")
        raw = re.sub(r"（.*?）|\(.*?\)", "", raw).strip()
        if raw:
            names.append(raw)
    return names


# --------------------------------------------------------------------------
# 校验
# --------------------------------------------------------------------------
def validate(team, members, note, rows, state, issue_number) -> list[str]:
    errors = []
    if not team:
        errors.append("队伍名称不能为空。")
    elif len(team) > TEAM_NAME_MAX:
        errors.append(f"队伍名称过长（{len(team)} 字），请控制在 {TEAM_NAME_MAX} 字以内。")

    if len(members) < MIN_MEMBERS:
        errors.append("至少要填写 1 名成员（成员1 为必填）。")
    if len(members) > MAX_MEMBERS:
        errors.append(f"每队最多 {MAX_MEMBERS} 人，当前提交了 {len(members)} 人。")

    seen, dup = set(), []
    for n in members:
        if n in seen and n not in dup:
            dup.append(n)
        seen.add(n)
    if dup:
        errors.append("同一队伍中出现了重复姓名：" + "、".join(dup))

    for onum, info in state["issues"].items():
        if onum == issue_number:
            continue
        if info.get("team") == team:
            errors.append(f"队伍名称「{team}」已被占用（Issue #{onum}），请换一个。")
            break

    my_prev_row = state["issues"].get(issue_number, {}).get("row")
    owner_of = {}
    for idx, r in enumerate(rows):
        if my_prev_row is not None and idx == my_prev_row:
            continue
        for name in r[1:4]:
            if name:
                owner_of[name] = r[0]
    for n in members:
        if n in owner_of:
            errors.append(f"「{n}」已登记在序号 {owner_of[n]} 的队伍中，不能重复组队。")

    if len(note) > NOTE_MAX:
        errors.append(f"备注过长（{len(note)} 字），请控制在 {NOTE_MAX} 字以内。")
    if re.search(r"1[3-9]\d{9}", note):
        errors.append("备注里请不要填写手机号，本名单是公开的。")

    return errors


# --------------------------------------------------------------------------
# 写入
# --------------------------------------------------------------------------
def upsert_row(members, note, rows, prev_row):
    payload = members + [""] * (MAX_MEMBERS - len(members))
    if prev_row is not None and 0 <= prev_row < len(rows):
        seq = rows[prev_row][0] or str(prev_row + 1)
        rows[prev_row] = [seq, payload[0], payload[1], payload[2], note]
        return prev_row, rows

    for i, r in enumerate(rows):
        if not any(r[1:4]):
            rows[i] = [r[0] or str(i + 1), payload[0], payload[1], payload[2], note]
            return i, rows

    rows.append([str(len(rows) + 1), payload[0], payload[1], payload[2], note])
    return len(rows) - 1, rows


def remove_row(prev_row, rows):
    if prev_row is not None and 0 <= prev_row < len(rows):
        rows[prev_row] = [rows[prev_row][0], "", "", "", ""]
    return rows


# --------------------------------------------------------------------------
# README 表格同步
# --------------------------------------------------------------------------
START_MARK = "<!-- ROSTER:START -->"
END_MARK = "<!-- ROSTER:END -->"


def clip(s: str, limit: int = NOTE_TABLE_MAX) -> str:
    s = s.replace("\r", " ").replace("\n", " ").strip()
    return s if len(s) <= limit else s[:limit] + "…"


def render_table(rows) -> str:
    lines = [
        START_MARK,
        "| 序号 | 成员1 | 成员2 | 成员3 | 备注 |",
        "| :--: | :-- | :-- | :-- | :-- |",
    ]
    for r in rows:
        cells = [r[0], r[1], r[2], r[3], clip(r[4]) if r[4] else ""]
        cells = [c.replace("|", "\\|") for c in cells]
        lines.append("| " + " | ".join(cells) + " |")
    lines.append(END_MARK)
    return "\n".join(lines)


def sync_readme(rows) -> None:
    if not README_PATH.exists():
        return
    text = README_PATH.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(START_MARK) + r".*?" + re.escape(END_MARK), re.S)
    table = render_table(rows)
    if pattern.search(text):
        text = pattern.sub(lambda _m: table, text)
    else:
        text = text.rstrip() + "\n\n" + table + "\n"
    README_PATH.write_text(text, encoding="utf-8")


# --------------------------------------------------------------------------
# GitHub 交互
# --------------------------------------------------------------------------
def gh(*args):
    repo = env("REPO")
    cmd = ["gh", *args]
    if repo:
        cmd += ["--repo", repo]
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")


def comment(body: str) -> None:
    n = env("ISSUE_NUMBER")
    if n:
        r = gh("issue", "comment", n, "--body", body)
        if r.returncode != 0:
            print("comment failed:", r.stderr, file=sys.stderr)


def set_label(label: str, on: bool) -> None:
    n = env("ISSUE_NUMBER")
    if not n:
        return
    gh("issue", "edit", n, "--add-label" if on else "--remove-label", label)


def close_issue() -> None:
    n = env("ISSUE_NUMBER")
    if n:
        gh("issue", "close", n, "--reason", "completed")


# --------------------------------------------------------------------------
# 阶段一：plan
# --------------------------------------------------------------------------
def do_plan() -> int:
    issue_number = env("ISSUE_NUMBER")
    author = env("ISSUE_AUTHOR")
    labels = [s.strip() for s in env("ISSUE_LABELS").split(",") if s.strip()]
    sections = parse_form(env("ISSUE_BODY"))

    rows = read_rows()
    state = load_state()
    prev_row = state["issues"].get(issue_number, {}).get("row")

    if CANCEL_LABEL in labels:
        rows = remove_row(prev_row, rows)
        write_rows(rows)
        sync_readme(rows)
        state["issues"].pop(issue_number, None)
        save_state(state)
        result = {"status": "ok", "cancelled": True}
        RESULT_PATH.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        print("cancelled")
        return 0

    team = pick(sections, "队伍名称")
    members = collect_members(sections)
    note = pick(sections, "备注")

    errors = validate(team, members, note, rows, state, issue_number)
    if errors:
        RESULT_PATH.write_text(
            json.dumps({"status": "error", "errors": errors}, ensure_ascii=False),
            encoding="utf-8",
        )
        print("validation failed:", errors)
        return 0

    idx, rows = upsert_row(members, note, rows, prev_row)
    write_rows(rows)
    sync_readme(rows)
    state["issues"][issue_number] = {
        "row": idx,
        "team": team,
        "members": members,
        "author": author,
    }
    save_state(state)

    result = {
        "status": "ok",
        "cancelled": False,
        "team": team,
        "seq": rows[idx][0],
        "members": members,
        "note": note,
    }
    RESULT_PATH.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    print(f"registered: team={team} row={idx} seq={rows[idx][0]}")
    return 0


# --------------------------------------------------------------------------
# 阶段二：notify
# --------------------------------------------------------------------------
def do_notify() -> int:
    push_status = env("PUSH_STATUS", "failed")

    if not RESULT_PATH.exists():
        comment("### ⚠️ 系统错误\n\n登记程序没有正常完成，请把这条回复截图发给老师。\n")
        return 0

    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    if result.get("status") == "error":
        body = "### ❌ 登记未通过，请修改后自动重试\n\n"
        body += "\n".join(f"- {e}" for e in result.get("errors", []))
        body += (
            "\n\n> 修改方式：点本页右上角 **Edit**，改完直接保存即可，"
            "无需关闭本 Issue，机器人会自动重新校验。\n"
        )
        comment(body)
        set_label(FIX_LABEL, True)
        return 0

    if push_status == "failed":
        comment(
            "### ⚠️ 校验通过，但写入仓库失败\n\n"
            "名单内容没问题，是系统这边提交时出了故障，**不需要你修改任何东西**。\n\n"
            "请把这条回复截图发给老师，老师会重新触发一次。\n"
        )
        return 0

    if push_status == "nochange":
        print("no file change, skip notification")
        return 0

    if result.get("cancelled"):
        comment(
            "已收到取消报名，名单中的这一行已清空。如需重新组队，请新建一个「组队报名」Issue。"
        )
        close_issue()
        return 0

    members = result.get("members", [])
    body = "### ✅ 登记成功\n\n"
    body += f"- **队伍名称**：{result.get('team')}\n"
    body += f"- **名单序号**：{result.get('seq')}\n"
    body += f"- **成员**：{'、'.join(members)}（共 {len(members)} 人）\n"
    if result.get("note"):
        body += f"- **备注**：{result['note']}\n"
    body += (
        "\n名单已写入 `roster.csv`，并同步更新了组队名单页面。\n\n"
        "需要**修改成员**：直接 Edit 本 Issue 后保存，系统会自动覆盖原来那一行。\n\n"
        "需要**取消报名**：给本 Issue 加上 `取消报名` 标签即可。\n"
    )
    comment(body)
    set_label(FIX_LABEL, False)
    close_issue()
    return 0


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "plan"
    if mode == "notify":
        sys.exit(do_notify())
    sys.exit(do_plan())
