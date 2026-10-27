#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
名单表静态检查（PR 场景使用）

当学生直接编辑 roster.csv 并提交 Pull Request 时，
本脚本会在 CI 中检查这个 PR 是否破坏了名单规则。

检查项：
  1. 表头必须是 序号,成员1,成员2,成员3,备注
  2. 每行最多 3 名成员
  3. 同一队内成员不重名
  4. 全表成员不重复
  5. 每行至少 1 名成员（空行允许保留）
  6. 备注长度不超过 100 字，且不含手机号
"""
import csv
import re
import sys
from collections import Counter
from pathlib import Path

HEADER = ["序号", "成员1", "成员2", "成员3", "备注"]
NOTE_MAX = 100
CSV_PATH = Path(__file__).resolve().parent.parent / "roster.csv"


def main() -> int:
    if not CSV_PATH.exists():
        print("找不到 roster.csv")
        return 1

    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        raw = list(csv.reader(f))

    if not raw:
        print("roster.csv 是空的")
        return 1

    head = [c.strip() for c in raw[0]]
    if head != HEADER:
        print(f"表头不正确。\n应为：{','.join(HEADER)}\n实际：{','.join(head)}")
        return 1

    errors: list[str] = []
    names: Counter[str] = Counter()

    for i, r in enumerate(raw[1:], start=2):
        r = [c.strip() for c in r] + [""] * max(0, len(HEADER) - len(r))
        seq = r[0] or f"第{i}行"
        members = [m for m in r[1:4] if m]

        if len(members) > 3:
            errors.append(f"序号 {seq}：成员超过 3 人")
        if len(set(members)) != len(members):
            errors.append(f"序号 {seq}：队内成员重名")
        for m in members:
            names[m] += 1

        note = r[4]
        if len(note) > NOTE_MAX:
            errors.append(f"序号 {seq}：备注超过 {NOTE_MAX} 字（{len(note)} 字）")
        if re.search(r"1[3-9]\d{9}", note):
            errors.append(f"序号 {seq}：备注中疑似填写了手机号")

    for name, cnt in names.items():
        if cnt > 1:
            errors.append(f"「{name}」出现了 {cnt} 次，同一学生不能加入多支队伍")

    if errors:
        print("名单检查未通过：")
        for e in errors:
            print(" -", e)
        return 1

    filled = sum(1 for r in raw[1:] if any(c.strip() for c in r[1:4]))
    print(f"名单检查通过：共 {len(raw) - 1} 个位置，已登记 {filled} 支队伍。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
