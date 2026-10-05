#!/usr/bin/env python3
"""Build an offline Synology runtime archive.

NAS packaging deliberately keeps only deps referenced by VOD-facing products.
The repository manifest is a historical ledger and is NOT a packaging root.
"""
from pathlib import Path
import re, shutil, tarfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"nas"/"runtime"
ARCHIVE=ROOT/"nas"/"runtime.tar.gz"
CODE_DIRS=("scripts","config","drpy-sandbox","state/vocab")
PRODUCTS=("tvbox.json","vod.json","short.json","tvbox_recommended.json")
ROOT_FILES=("list.json","status.json","checks.json")
SEED_STATE=("adult_leak_whitelist.txt","blacklist_auto.txt","blacklist_manual.txt",
            "category_overrides.json","fetch_headers.json","sites_state.json",
            "upstream_baseline.json","upstream_failures.json","upstream_latency.json",
            "upstream_retry.json","upstreams_state.json","validated.json","whitelist_manual.txt")
SEED_PROBE=("drpy_probe.json","sites_probe.json")
SEED_RADAR=("discovered.json",)
DEP_RE=re.compile(r"(?:\./)?deps/[^\s\"'<>\\),;]+")

def dep_refs():
    refs=set()
    for name in PRODUCTS:
        p=ROOT/name
        if not p.is_file(): continue
        for m in DEP_RE.finditer(p.read_text(encoding="utf-8",errors="replace")):
            rel=m.group(0).lstrip("./")
            if (ROOT/rel).is_file(): refs.add(rel)
    return refs

if OUT.exists(): shutil.rmtree(OUT)
if ARCHIVE.exists(): ARCHIVE.unlink()
OUT.mkdir(parents=True)
for name in CODE_DIRS:
    src=ROOT/name
    if src.exists(): shutil.copytree(src,OUT/name,ignore=shutil.ignore_patterns("__pycache__","*.pyc",".DS_Store"))
(OUT/"deps").mkdir()
refs=dep_refs()
for rel in sorted(refs):
    dst=OUT/rel; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(ROOT/rel,dst)
for dirname,names in (("state",SEED_STATE),("probe",SEED_PROBE),("radar",SEED_RADAR)):
    dst=OUT/dirname; dst.mkdir()
    for name in names:
        src=ROOT/dirname/name
        if src.is_file(): shutil.copy2(src,dst/name)
(OUT/"nas").mkdir()
for name in ("app.py","index.html","media_quality.py"):
    shutil.copy2(ROOT/"nas"/name,OUT/"nas"/name)
for name in PRODUCTS+ROOT_FILES:
    src=ROOT/name
    if src.is_file(): shutil.copy2(src,OUT/name)
with tarfile.open(ARCHIVE,"w:gz",compresslevel=6) as tf:
    for p in OUT.rglob("*"): tf.add(p,arcname=p.relative_to(OUT))
shutil.rmtree(OUT)
print(f"runtime: {ARCHIVE}")
print(f"referenced deps: {len(refs)}")
print(f"archive MiB: {ARCHIVE.stat().st_size/1024/1024:.1f}")
