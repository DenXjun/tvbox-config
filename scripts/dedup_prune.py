#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dedup_prune.py — deps 重复副本回收（默认 dry-run，移动不删除）。

为什么单独一个脚本
----------------
2026-10-05 全仓体检：`state/dep_audit.json` 报 `unreferenced_bytes 701MB / 8696 文件`，
`duplicate_savable_bytes 423MB / 1583 组`。这两个数字连续 8 天原地不动——因为
`dep_audit.py` 设计上「只报告不删除」，`dep_gc.py` 的 `gc_candidate` 又因为
按 mtime 算 age、而 daily 每天重写 deps 导致 age 永远停在 6.0 天，任何阈值都触发不了。
审计没有闭环，等于没审计。

已有清理工具的覆盖缺口
----------------------
`cleanup_deps.py`（P1-8）的安全模型是对的（双轮观察 + trash 回滚 + 体积分档），
但只扫 `deps/localized/` 与 `deps/external/` 两个无主目录（合计 113MB）；
真正的体积大头在 `deps/auto`(338M) / `deps/jar`(243M) / `deps/feishu-sync`(98M)，
`deps/<origin>/` 被安全边界排除，于是 679MB 一个都清不掉。

安全模型（比 cleanup_deps 更严，宁可不清不可误删）
--------------------------------------------------
  1. **必须未被任何引用**：口径 = `dep_refs.collect_all_refs`（产物 ∪ manifest 账本
     ∪ 消费者，见 scripts/dep_refs.py，PR#41 抽出的唯一权威），与 dep_audit /
     dep_gc / cleanup_deps 完全一致。
  2. **必须内容有替身**：目标文件的 md5 在同组内另有副本留存，且该副本是被引用的
     或按规则保留的。⇒ 全程不丢任何一份内容，即使运行时拼接路径真的命中被删副本，
     内容仍在仓库内（且 .trash 保留 30 天可秒级回滚）。
  3. **双轮观察**：首次发现只记 `state/dedup_unused.json` 的 `unused_since`，
     下一轮再扫仍未被引用、且替身仍在，才允许回收。防的是"引用口径某天失效"。
  4. **每组至少留一份**：被引用的副本全部保留；一组都没被引用时，按"偏好非 auto
     目录、路径短者优先"留 1 份，避免把 canary 收编的原件全删光。
  5. **移动而非删除**：移入 `deps/.trash/<日期>/<原相对路径>`，保留原目录结构
     —— 沿用 basename 会让 `deps/a/drpy2.min.js` 与 `deps/b/drpy2.min.js` 撞车
     互相覆盖（cleanup_deps.py 现存缺陷，本脚本不复制该行为）。
  6. **小于 100KB 不动**：省不下体积，反而增加误判面。
  7. **近 2 天被改写过的文件不动**（2026-10-05 推远端时补的护栏）：daily 会每日
     重写部分 deps 文件，「有内容替身」只对**改写前**的内容成立。真实踩坑——
     `deps/feishu-sync/live.txt` 判为「未引用 + 有替身」被回收，但 10-04 CI 刚把它
     从 1143 行刷成 57 行，新内容在仓内并无替身；把删除推上远端会用删除覆盖掉
     刚拉到的有效直播源，且触发 delete/modify 冲突。故用 mtime 近 N 天作护栏。

用法
----
    python scripts/dedup_prune.py                # dry-run：只写 state/dedup_unused.json + 报告
    python scripts/dedup_prune.py --execute      # 真回收（移入 deps/.trash/<日期>/）
    python scripts/dedup_prune.py --min-bytes 200000   # 抬高体积门槛（更保守）
    python scripts/dedup_prune.py --trash-keep-days 30
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

MIN_BYTES_DEFAULT = 100 * 1024      # <100KB 不动
TRASH_KEEP_DAYS_DEFAULT = 30
ROUND2_DAYS_DEFAULT = 1             # 第 2 轮起算的最小闲置天数

# 近 N 天内被改写过的文件一律不回收（2026-10-05 推远端时踩到的真实坑）。
# 起因：deps/feishu-sync/live.txt 被判为「未引用 + 有内容替身」而回收，但它同时
# 被 daily 每日重写——「有替身」只对**旧内容**成立，10-04 CI 把它从 1143 行刷成
# 57 行后，新内容在仓内并无替身。此时若把删除推上远端，就会用「删除」覆盖掉
# CI 刚拉到的有效直播源，且 delete/modify 冲突无法自动合并。
# 判据：文件 mtime 距今不足 N 天 ⇒ 内容仍在流动，回收不成立。
RECENT_SKIP_DAYS = 2.0


def md5_of(path, chunk=1 << 20):
    h = hashlib.md5()
    try:
        with open(path, "rb") as f:
            while True:
                b = f.read(chunk)
                if not b:
                    break
                h.update(b)
    except OSError:
        return None
    return h.hexdigest()


def scan_deps(repo, deps_dir):
    """扫 deps/ 下所有文件，返回 [(abs, rel_posix, size, md5), ...]。跳过 .trash。"""
    out = []
    root_all = os.path.join(repo, deps_dir)
    if not os.path.isdir(root_all):
        return out
    for base, dirs, names in os.walk(root_all):
        rel_base = os.path.relpath(base, repo).replace("\\", "/")
        if rel_base == f"{deps_dir}/.trash" or rel_base.startswith(f"{deps_dir}/.trash/"):
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if not (rel_base == deps_dir and d == ".trash")]
        for n in names:
            ap = os.path.join(base, n)
            if not os.path.isfile(ap):
                continue
            try:
                size = os.path.getsize(ap)
                mtime = os.path.getmtime(ap)
            except OSError:
                continue
            rel = os.path.relpath(ap, repo).replace("\\", "/")
            m = md5_of(ap)
            if not m:
                continue
            out.append((ap, rel, size, m, mtime))
    return out


def age_days_of(mtime, now=None):
    now = now if now is not None else time.time()
    return (now - mtime) / 86400.0


def keep_preference(rel):
    """同组都没被引用时，选谁当"留下的那一份"。

    排序键：偏好非 auto/ 目录（auto 是 canary 收编副本，原生目录更权威）、
    路径短者优先、字典序兜底。返回排序后的 key，min() 即最佳保留者。
    """
    return (1 if rel.startswith("deps/auto/") else 0, len(rel), rel)


def plan_prune(files, refs, min_bytes, skip_recent_days=RECENT_SKIP_DAYS):
    """算出删除计划。返回 (plan, stats)。plan 项含 keep_within_group 便于人工核对。

    额外护栏：近 `skip_recent_days` 天内被改写过的文件一律不回收（见 RECENT_SKIP_DAYS）。
    """
    now = time.time()
    by_md5 = defaultdict(list)
    for ap, rel, size, m, mtime in files:
        by_md5[m].append((ap, rel, size, mtime))

    plan, stats = [], {
        "dup_groups": 0, "dup_total_files": 0,
        "kept_for_content": 0, "kept_referenced": 0,
        "too_small": 0, "no_duplicate": 0, "recently_rewritten": 0,
        "candidates": 0, "candidate_bytes": 0,
    }
    for m, group in by_md5.items():
        if len(group) < 2:
            stats["no_duplicate"] += len(group)
            continue
        stats["dup_groups"] += 1
        stats["dup_total_files"] += len(group)
        # 被引用的副本：一个都不动
        referenced = [g for g in group if g[1] in refs]
        unreferenced = [g for g in group if g[1] not in refs]
        stats["kept_referenced"] += len(referenced)
        if not unreferenced:
            continue
        # 留一份：优先留被引用的（最稳）；一组都没被引用则按 keep_preference 留 1 份
        if referenced:
            keeper = min(referenced, key=lambda g: keep_preference(g[1]))
        else:
            keeper = min(unreferenced, key=lambda g: keep_preference(g[1]))
        stats["kept_for_content"] += 1
        for ap, rel, size, mtime in unreferenced:
            if rel == keeper[1]:
                continue
            if size < min_bytes:
                stats["too_small"] += 1
                continue
            # 内容仍在流动 ⇒ "有替身"只对旧内容成立，不回收
            if skip_recent_days and age_days_of(mtime, now) < skip_recent_days:
                stats["recently_rewritten"] += 1
                continue
            plan.append({
                "path": rel, "bytes": size, "md5": m,
                "keep_within_group": keeper[1],
            })
            stats["candidates"] += 1
            stats["candidate_bytes"] += size
    plan.sort(key=lambda x: -x["bytes"])
    return plan, stats


def load_state(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(path, doc):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)


def prune_trash(trash_root, keep_days):
    """清理 .trash 里超期文件（真删）。返回删除数与释放字节。"""
    n, freed = 0, 0
    if not os.path.isdir(trash_root):
        return n, freed
    cutoff = time.time() - keep_days * 86400
    for base, _dirs, names in os.walk(trash_root):
        for name in names:
            fp = os.path.join(base, name)
            try:
                if os.path.getmtime(fp) < cutoff:
                    freed += os.path.getsize(fp)
                    os.remove(fp)
                    n += 1
            except OSError:
                pass
    return n, freed


def main() -> int:
    ap = argparse.ArgumentParser(description="deps 重复副本回收（默认 dry-run）")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--deps", default="deps")
    ap.add_argument("--state", default="state/dedup_unused.json")
    ap.add_argument("--min-bytes", type=int, default=MIN_BYTES_DEFAULT,
                    help=f"小于此体积不动（默认 {MIN_BYTES_DEFAULT}）")
    ap.add_argument("--min-idle-days", type=int, default=ROUND2_DAYS_DEFAULT,
                    help="首次标记后再等几天才允许回收（默认 1）")
    ap.add_argument("--execute", action="store_true",
                    help="真回收（移入 deps/.trash/<日期>/）；缺省只报告")
    ap.add_argument("--trash-keep-days", type=int, default=TRASH_KEEP_DAYS_DEFAULT)
    ap.add_argument("--max-list", type=int, default=20)
    ap.add_argument("--skip-recent-days", type=float, default=RECENT_SKIP_DAYS,
                    help=f"近 N 天内被改写过的文件一律不回收（默认 {RECENT_SKIP_DAYS}）")
    args = ap.parse_args()

    repo = os.path.abspath(args.repo)
    if not os.path.isdir(os.path.join(repo, args.deps)):
        print(f"[dedup_prune] 无 {args.deps}/ 目录，跳过")
        return 0

    import dep_refs
    refs = dep_refs.collect_all_refs(repo, args.deps)
    files = scan_deps(repo, args.deps)
    total_bytes = sum(f[2] for f in files)
    print(f"[dedup_prune] deps/ {len(files)} 个文件 {total_bytes/1024/1024:.1f} MB；"
          f"权威引用口径 {len(refs)} 条")

    plan, stats = plan_prune(files, refs, args.min_bytes, args.skip_recent_days)
    print(f"[dedup_prune] 重复组 {stats['dup_groups']} 个涉及 {stats['dup_total_files']} 文件；"
          f"被引用保留 {stats['kept_referenced']}，为内容留存 {stats['kept_for_content']}，"
          f"<{args.min_bytes/1024:.0f}KB 跳过 {stats['too_small']}，"
          f"近期被改写跳过 {stats['recently_rewritten']}")
    print(f"[dedup_prune] 候选 {stats['candidates']} 个，"
          f"可回收 {stats['candidate_bytes']/1024/1024:.1f} MB")

    # 双轮观察：本轮只把新候选记进 state
    state_path = os.path.join(repo, args.state)
    ledger = load_state(state_path)
    today = datetime.now(timezone.utc).date().isoformat()
    plan_paths = {p["path"] for p in plan}
    new_marked, ready, aging = [], [], 0

    for item in plan:
        rec = ledger.get(item["path"])
        if rec is None:
            ledger[item["path"]] = {"bytes": item["bytes"], "unused_since": today,
                                    "md5": item["md5"],
                                    "keep_within_group": item["keep_within_group"]}
            new_marked.append(item)
            continue
        try:
            since = datetime.fromisoformat(rec["unused_since"]).date()
            age = (datetime.now(timezone.utc).date() - since).days
        except (KeyError, ValueError):
            ledger[item["path"]] = {"bytes": item["bytes"], "unused_since": today,
                                    "md5": item["md5"],
                                    "keep_within_group": item["keep_within_group"]}
            continue
        if age >= args.min_idle_days:
            item["idle_days"] = age
            ready.append(item)
        else:
            aging += 1

    # 已不满足候选条件的（重新被引用 / 替身没了 / 体积变小）从账本移除
    for rel in [r for r in ledger if r not in plan_paths]:
        ledger.pop(rel, None)

    trash_root = os.path.join(repo, args.deps, ".trash")
    trash_pruned, trash_freed = 0, 0
    if args.execute:
        trash_pruned, trash_freed = prune_trash(trash_root, args.trash_keep_days)

    moved, moved_bytes, failed = 0, 0, 0
    if ready:
        trash_dir = os.path.join(trash_root, today)
        for item in ready:
            src = os.path.join(repo, item["path"])
            # 保留原相对目录结构：basename 会让不同目录同名文件互相覆盖
            rel_in_trash = os.path.relpath(item["path"], args.deps)
            dst = os.path.join(trash_dir, rel_in_trash)
            if not args.execute:
                print(f"  - 待回收 {item['bytes']/1024:8.0f} KB  {item['path']}")
                moved += 1
                moved_bytes += item["bytes"]
                continue
            try:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.move(src, dst)
                ledger.pop(item["path"], None)
                moved += 1
                moved_bytes += item["bytes"]
            except OSError as e:
                failed += 1
                print(f"    !! 移动失败 {item['path']}: {e}", file=sys.stderr)

    save_state(state_path, ledger)

    mode = "EXECUTE" if args.execute else "DRY-RUN"
    print(f"\n[dedup_prune][{mode}] 新标记 {len(new_marked)}，继续观察 {aging}，"
          f"到期待回收 {len(ready)}（{moved_bytes/1024/1024:.1f} MB），失败 {failed}")
    if trash_pruned:
        print(f"[dedup_prune] 回收站清理 {trash_pruned} 个，释放 {trash_freed/1024/1024:.1f} MB")
    if new_marked:
        print("[dedup_prune] 本轮新标记（下一轮才会回收）：")
        for item in new_marked[:args.max_list]:
            print(f"   {item['bytes']/1024:8.0f} KB  {item['path']}")
    if not args.execute:
        print("[dedup_prune] dry-run：未移动任何文件。确认无误后加 --execute。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
