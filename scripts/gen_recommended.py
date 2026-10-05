#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_recommended.py — 生成「精简推荐订阅」tvbox_recommended.json。

为什么需要这份产物（2026-10-05）
--------------------------------
`tvbox.json` 现状 4331 个 sites，但按 `exports/all.json` 的实测健康度拆开：

    healthy  167 (3.9%)   实测能搜/能播
    degraded 1541 (35.6%)  能连通
    dead     491 (11.3%)  实测失败
    unknown  2132 (49.2%)  从未被任何探针验证过

也就是说**主订阅里近一半是"不知道能不能用"**，另一半里还有 491 个已知是死的。
用户导入 `tvbox.json` 后的实际体感是"大半点不动"，而仓库里明明已经有一份
只装 1708 个能连通源的 `exports/usable.json`——只是它躺在 exports/ 里，
既没进 README 首屏推荐位，也没进 Release 附件，订阅者基本不会看到。

本脚本把 usable 那条线提升为**正式一级产物**，与 tvbox.json 并列发布：

    tvbox.json            全量 4331（保持既有语义，一字不改，零回归风险）
    tvbox_recommended.json  精简 1708（healthy + degraded，-60% 体积）

为什么不改 tvbox.json 本身
--------------------------
主产物的 sites 集合是订阅者的既有契约，直接删条目会让已导入的用户在下次同步时
「源凭空消失」，属于破坏性变更。改为新增并列产物 + README 引导，让用户自己切，
是可回退的增量方案。若日后 tvbox_recommended 连续多日稳定且订阅量迁移完成，
再考虑收敛主产物。

健康度取数
---------
优先读 `exports/all.json` 的 `_health` 标注（由 export_healthy.py 从
state/tvbox.db 生成）；该文件缺失时**不静默降级为全量**，而是直接报错退出——
宁可 CI 失败暴露问题，也不要悄悄产出一份"看起来正常其实没过滤"的文件。

用法
----
    python scripts/gen_recommended.py
    python scripts/gen_recommended.py --min-health degraded
    python scripts/gen_recommended.py --base tvbox.json --out tvbox_recommended.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime

HEALTH_ORDER = ("healthy", "degraded", "unknown", "dead")


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    ap = argparse.ArgumentParser(description="生成精简推荐订阅 tvbox_recommended.json")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--base", default="tvbox.json", help="以哪份产物为骨架（保留完整字段）")
    ap.add_argument("--all", dest="all_path", default="exports/all.json",
                    help="带 _health 标注的全量清单")
    ap.add_argument("--out", default="tvbox_recommended.json")
    ap.add_argument("--min-health", default="degraded",
                    choices=list(HEALTH_ORDER), help="收录此健康度及以上（默认 degraded）")
    ap.add_argument("--keep-lives", action="store_true", default=True,
                    help="保留 lives/parses/ad（默认保留）")
    args = ap.parse_args()

    repo = os.path.abspath(args.repo)
    base_path = os.path.join(repo, args.base)
    all_path = os.path.join(repo, args.all_path)
    out_path = os.path.join(repo, args.out)

    if not os.path.isfile(base_path):
        print(f"[gen_recommended] 找不到骨架 {args.base}", file=sys.stderr)
        return 1
    if not os.path.isfile(all_path):
        print(f"[gen_recommended] 找不到健康度清单 {args.all_path}\n"
              f"               拒绝在此情况下产出——否则会得到一份「看着正常、"
              f"其实没过滤」的推荐订阅。\n"
              f"               请先跑 export_healthy.py。", file=sys.stderr)
        return 1

    base = load_json(base_path)
    all_doc = load_json(all_path)
    sites_all = all_doc.get("sites", all_doc) if isinstance(all_doc, dict) else all_doc
    health_of = {}
    for s in sites_all:
        k = s.get("key")
        if k:
            health_of[k] = s.get("_health", "unknown")

    cutoff = HEALTH_ORDER.index(args.min_health)
    keep_levels = set(HEALTH_ORDER[:cutoff + 1])

    sites = base.get("sites", [])
    kept, dropped = [], Counter()
    for s in sites:
        h = health_of.get(s.get("key"), "unknown")
        if h in keep_levels:
            kept.append(s)
        else:
            dropped[h] += 1

    out = {}
    for k, v in base.items():
        if k == "sites":
            out[k] = kept
        else:
            out[k] = v
    out["recommended_meta"] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "base": args.base,
        "min_health": args.min_health,
        "sites_total": len(sites),
        "sites_kept": len(kept),
        "dropped": dict(dropped),
        "note": "healthy+degraded 子集。完整全量版见 tvbox.json。",
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

    def mb(p):
        return f"{os.path.getsize(p)/1024/1024:.2f} MB" if os.path.isfile(p) else "n/a"

    kept_dist = Counter(health_of.get(s.get("key"), "unknown") for s in kept)
    print(f"[gen_recommended] 骨架 {args.base}（{len(sites)} 站, {mb(base_path)}）")
    print(f"[gen_recommended] 收录 {len(kept)} 站 {args.min_health} 及以上"
          f"（{kept_dist.most_common()}）")
    if dropped:
        print(f"[gen_recommended] 剔除 {sum(dropped.values())} 站：{dict(dropped)}")
    print(f"[gen_recommended] 产出 {args.out}（{mb(out_path)}），"
          f"体积降 {(1 - os.path.getsize(out_path)/max(os.path.getsize(base_path),1))*100:.0f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
