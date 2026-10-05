#!/usr/bin/env python3
"""Build one compact Synology runtime archive: nas/runtime.tar.gz."""
from pathlib import Path
import shutil, tarfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"nas"/"runtime"
ARCHIVE=ROOT/"nas"/"runtime.tar.gz"
KEEP_DIRS=("scripts","config","deps","drpy-sandbox")
SEED_STATE=("adult_leak_whitelist.txt","blacklist_auto.txt","blacklist_manual.txt",
            "category_overrides.json","fetch_headers.json","sites_state.json",
            "upstream_baseline.json","upstream_changelog.jsonl","upstream_failures.json",
            "upstream_latency.json","upstream_retry.json","upstreams_state.json",
            "validated.json","whitelist_manual.txt")
SEED_PROBE=("drpy_probe.json","sites_probe.json")
ROOT_FILES=("tvbox.json","tvbox_recommended.json","vod.json","short.json","list.json","status.json","checks.json")

if OUT.exists(): shutil.rmtree(OUT)
if ARCHIVE.exists(): ARCHIVE.unlink()
OUT.mkdir(parents=True)
for name in KEEP_DIRS:
    src=ROOT/name
    if src.exists():
        shutil.copytree(src,OUT/name,ignore=shutil.ignore_patterns("__pycache__","*.pyc",".DS_Store"))
for dirname,names in (("state",SEED_STATE),("probe",SEED_PROBE)):
    dst=OUT/dirname; dst.mkdir()
    for name in names:
        src=ROOT/dirname/name
        if src.is_file(): shutil.copy2(src,dst/name)
(OUT/"nas").mkdir()
for name in ("app.py","index.html","media_quality.py"):
    shutil.copy2(ROOT/"nas"/name,OUT/"nas"/name)
for name in ROOT_FILES:
    src=ROOT/name
    if src.is_file(): shutil.copy2(src,OUT/name)
with tarfile.open(ARCHIVE,"w:gz",compresslevel=6) as tf:
    for p in OUT.rglob("*"):
        tf.add(p,arcname=p.relative_to(OUT))
shutil.rmtree(OUT)
print(f"ready: {ARCHIVE} ({ARCHIVE.stat().st_size/1024/1024:.1f} MiB)")
