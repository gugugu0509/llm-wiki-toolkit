#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
append_only_guard.py —— 「纯追加编辑」的机器护栏

用途
----
当你要做的改动本应是**只加不删**（追加注记、回注、互指、标注、补字段……）时，
提交前跑一次本脚本，用 `git diff --numstat` 证明所有改动文件的**删除列都为 0**。

为什么需要它
------------
结构自检（标题层级、断链、index 覆盖之类）**查不出**「以为在追加、实际在替换」的事故：
比如把某一行当作替换锚点，结果连带删掉了那一行——结构仍然完整，只有逐字回读才能发现。
本护栏机器可验、成本近零，能挡住这**整类**事故。

用法
----
    python append_only_guard.py                  # 检查工作区未暂存改动
    python append_only_guard.py --cached         # 检查已暂存的改动
    python append_only_guard.py --ref HEAD~1     # 与指定提交/分支比较
    python append_only_guard.py --allow CHANGELOG.md
                                                 # 允许某些文件存在删除（可重复）
    python append_only_guard.py --quiet          # 仅在失败时输出

退出码
------
    0 = 所有改动文件都是纯追加（或已 --allow 豁免）
    1 = 存在删除行（会列出文件名与 +/- 行数）
    2 = git 调用失败（不在仓库里 / ref 不存在等）

注意
----
- **二进制文件**在 numstat 里以 `-` 表示行数，本脚本会跳过它们并在报告中提示。
- 新增文件天然没有删除行；`numstat` 也不会列出未跟踪文件。
"""
from __future__ import annotations

import argparse
import subprocess
import sys


def run_git(args: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        ["git", "-c", "core.quotePath=false", *args],
        capture_output=True,
    )
    out = proc.stdout.decode("utf-8", "replace") + proc.stderr.decode("utf-8", "replace")
    return proc.returncode, out


def collect(numstat_args: list[str]) -> tuple[list[tuple[str, str, str]], list[str]]:
    """返回 (违规项, 跳过的二进制文件)。违规项 = (文件, 新增行, 删除行)。"""
    code, out = run_git(["diff", "--numstat", *numstat_args])
    if code != 0:
        print(out.strip(), file=sys.stderr)
        sys.exit(2)

    offenders: list[tuple[str, str, str]] = []
    binaries: list[str] = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        added, deleted, path = parts[0], parts[1], parts[2]
        if not deleted.isdigit():          # 二进制文件：numstat 用 '-' 占位
            binaries.append(path)
            continue
        if int(deleted) > 0:
            offenders.append((path, added, deleted))
    return offenders, binaries


def main() -> int:
    ap = argparse.ArgumentParser(
        description="纯追加护栏：验证 git 改动的「删除列」是否全为 0",
    )
    ap.add_argument("--cached", action="store_true", help="检查已暂存的改动（git diff --cached）")
    ap.add_argument("--ref", metavar="REV", help="与指定提交/分支比较（git diff REV）")
    ap.add_argument("--allow", action="append", default=[], metavar="PATH",
                    help="允许存在删除的文件（可重复；支持前缀匹配）")
    ap.add_argument("--quiet", action="store_true", help="仅在失败时输出")
    a = ap.parse_args()

    numstat_args: list[str] = []
    if a.cached:
        numstat_args.append("--cached")
    if a.ref:
        numstat_args.append(a.ref)

    offenders, binaries = collect(numstat_args)

    if a.allow:
        def allowed(path: str) -> bool:
            return any(path == pat or path.startswith(pat) for pat in a.allow)
        exempt = [o for o in offenders if allowed(o[0])]
        offenders = [o for o in offenders if not allowed(o[0])]
    else:
        exempt = []

    if not a.quiet:
        if exempt:
            print("已豁免（--allow）:")
            for path, added, deleted in exempt:
                print("  · %s  (+%s/−%s)" % (path, added, deleted))
        if binaries:
            print("跳过二进制文件 %d 个（numstat 无行数）: %s"
                  % (len(binaries), ", ".join(binaries[:5])))

    if offenders:
        print("❌ 纯追加检查未通过：%d 个文件存在删除行" % len(offenders))
        for path, added, deleted in offenders:
            print("  · %s  (+%s/−%s)" % (path, added, deleted))
        print("\n如果这些删除是有意的，请逐字说明删了什么、为什么；"
              "确认无误后可用 --allow <路径> 豁免。")
        return 1

    if not a.quiet:
        print("✅ 纯追加检查通过：所有改动文件的「删除列」均为 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
