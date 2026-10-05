#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""type3 覆盖率观测 + 增量轮转补测窗口生成（T5）。

背景：type3 爬虫源（csp/drpy/js/py）必须运行时实测，纯 HTTP 测不了；
真机 csp 测试工程在 .workbuddy/csp-test/ 不进 CI（README 736），
所以 CI 只能只读复用 probe/*.json，覆盖率只能靠本地真机逐步补。

本脚本把「type3 覆盖率」从黑盒变成可观测 + 可增量推进：
  1. 读 state/last_tvbox.json（源全集）与各深探针产物
  2. 算 type3 各子类型覆盖率 + 未覆盖清单
  3. 生成「今日增量补测窗口」——按 key 字典序 + 按日轮转，
     复用 discover_upstreams.probe_window 的模式（同天可复现、跨天不饿死尾巴）
  4. 落 state/type3_coverage.json，并打印人读摘要

纯观测/计划，不修改任何产物；可接入 daily.yml 做趋势跟踪。
"""
from __future__ import annotations

import json
import os
import sys
import datetime
import hashlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def p(*a: str) -> str:
    return os.path.join(ROOT, *a)


def load_json(path: str):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# 深探针产物：能给出「能不能搜到片/出片」的结论，比 HTTP L 级 / 连通性更有价值
DEEP_PROBES = ["csp_probe", "drpy_probe", "js_probe", "py_probe", "spider_probe"]


def deep_probe_keys() -> set:
    keys: set = set()
    for fn in DEEP_PROBES:
        d = load_json(p("probe", f"{fn}.json"))
        if not d:
            continue
        arr = d.get("sites") or []
        for x in arr:
            if isinstance(x, dict) and x.get("key"):
                keys.add(x["key"])
    return keys


def load_type3() -> list:
    d = load_json(p("state", "last_tvbox.json"))
    if not d:
        return []
    return [s for s in d.get("sites", []) if str(s.get("type")) == "3"]


def classify(s: dict) -> str:
    g = str(s.get("group") or "")
    if "蜘蛛" in g:
        return "csp"
    if "本地JS" in g:
        return "js"
    if "网盘" in g:
        return "pan"
    if g == "短剧":
        return "short"
    if g == "成人":
        return "adult"
    if "采集站" in g or "直连" in g:
        return "std"
    return "other"


def probe_window(keys: list, date: datetime.date, window: int = 120) -> list:
    """按 key 字典序 + 按日轮转：每天取不同一段，循环覆盖不饿死尾巴。

    与 discover_upstreams.probe_window 同思路——确定性（同天可复现）、
    跨天推进（按日偏移，保证最终整池都能被轮到）。
    """
    if not keys:
        return []
    sk = sorted(keys)
    n = len(sk)
    seed = int(hashlib.md5(date.strftime("%Y-%m-%d").encode()).hexdigest(), 16)
    offset = seed % n
    return [sk[(offset + i) % n] for i in range(min(window, n))]


def main() -> int:
    sites = load_type3()
    if not sites:
        print("ERROR: 无法读取 state/last_tvbox.json 的 type3 源", file=sys.stderr)
        return 2

    deep = deep_probe_keys()
    t3_keys = set(s.get("key") for s in sites)
    covered = t3_keys & deep
    uncovered = t3_keys - deep

    by_kind: dict = {}
    for s in sites:
        by_kind.setdefault(classify(s), set()).add(s.get("key"))

    today = datetime.date.today()
    window_keys = probe_window(list(uncovered), today, window=120)

    report = {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "type3_total": len(t3_keys),
        "deep_covered_total": len(covered),
        "uncovered_total": len(uncovered),
        "coverage_pct": round(100.0 * len(covered) / len(t3_keys), 1) if t3_keys else 0,
        "by_kind": {},
        "today_window_date": today.isoformat(),
        "today_window_size": len(window_keys),
        "today_window_keys": window_keys,
        "uncovered_keys": sorted(uncovered),
    }
    for k, ks in by_kind.items():
        cov = ks & deep
        report["by_kind"][k] = {
            "total": len(ks),
            "covered": len(cov),
            "uncovered": len(ks - deep),
            "coverage_pct": round(100.0 * len(cov) / len(ks), 1) if ks else 0,
        }

    out = p("state", "type3_coverage.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"type3 源全集: {len(t3_keys)}")
    print(f"深探针覆盖:   {len(covered)} ({report['coverage_pct']}%)")
    print(f"未覆盖:       {len(uncovered)}")
    print("--- 按子类型 ---")
    for k in sorted(report["by_kind"]):
        b = report["by_kind"][k]
        print(
            f"  {k:6s} 全集{b['total']:5d} 覆盖{b['covered']:5d} "
            f"未覆盖{b['uncovered']:5d} ({b['coverage_pct']}%)"
        )
    print(f"--- 今日增量补测窗口: {len(window_keys)} 个 (date={today}) ---")
    print(f"报告已写: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
