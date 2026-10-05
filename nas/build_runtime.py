#!/usr/bin/env python3
"""Build an offline Synology runtime archive.

NAS packaging deliberately keeps only deps referenced by VOD-facing products.
The repository manifest is a historical ledger and is NOT a packaging root.
"""
from pathlib import Path
import json, re, shutil, tarfile

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

def mib(path):
    return path.stat().st_size/1024/1024 if path.is_file() else 0

if OUT.exists(): shutil.rmtree(OUT)
if ARCHIVE.exists(): ARCHIVE.unlink()
OUT.mkdir(parents=True)

for name in CODE_DIRS:
    src=ROOT/name
    if src.exists():
        shutil.copytree(src,OUT/name,ignore=shutil.ignore_patterns("__pycache__","*.pyc",".DS_Store"))

(OUT/"deps").mkdir(exist_ok=True)
refs=dep_refs()
for rel in sorted(refs):
    dst=OUT/rel; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(ROOT/rel,dst)

for dirname,names in (("state",SEED_STATE),("probe",SEED_PROBE),("radar",SEED_RADAR)):
    dst=OUT/dirname; dst.mkdir(parents=True,exist_ok=True)
    for name in names:
        src=ROOT/dirname/name
        if src.is_file(): shutil.copy2(src,dst/name)

# Candidate discovery is opportunistic. A missing seed must never make the
# offline runtime unusable; evaluate_candidates handles an empty candidate set.
radar=OUT/"radar"/"discovered.json"
if not radar.exists():
    radar.write_text(json.dumps({"generated_at":None,"candidates":[]},ensure_ascii=False),encoding="utf-8")

(OUT/"nas").mkdir(exist_ok=True)
for name in ("app.py","index.html","media_quality.py"):
    shutil.copy2(ROOT/"nas"/name,OUT/"nas"/name)
for name in PRODUCTS+ROOT_FILES:
    src=ROOT/name
    if src.is_file(): shutil.copy2(src,OUT/name)

# rglob already enumerates descendants. tarfile.add(recursive=True) here would
# re-add each subtree many times and unnecessarily inflate the archive.
with tarfile.open(ARCHIVE,"w:gz",compresslevel=6) as tf:
    for p in sorted(OUT.rglob("*")):
        tf.add(p,arcname=p.relative_to(OUT),recursive=False)

file_count=sum(1 for p in OUT.rglob("*") if p.is_file())
deps_bytes=sum(p.stat().st_size for p in (OUT/"deps").rglob("*") if p.is_file())
drpy_bytes=sum(p.stat().st_size for p in (OUT/"drpy-sandbox").rglob("*") if p.is_file()) if (OUT/"drpy-sandbox").exists() else 0
shutil.rmtree(OUT)
print(f"runtime: {ARCHIVE}")
print(f"files: {file_count}; referenced deps: {len(refs)}")
print(f"deps MiB: {deps_bytes/1024/1024:.1f}; drpy MiB: {drpy_bytes/1024/1024:.1f}")
print(f"archive MiB: {ARCHIVE.stat().st_size/1024/1024:.1f}")
