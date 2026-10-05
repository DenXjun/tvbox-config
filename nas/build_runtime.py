#!/usr/bin/env python3
"""Create a compact Synology build context under nas/runtime."""
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"nas"/"runtime"
KEEP_DIRS=("scripts","config","deps","drpy-sandbox","probe","state")
KEEP_FILES=("tvbox.json","tvbox_recommended.json","vod.json","live.json","short.json","adult.json","list.json","status.json","checks.json")

if OUT.exists(): shutil.rmtree(OUT)
OUT.mkdir(parents=True)
for name in KEEP_DIRS:
    src=ROOT/name
    if src.exists(): shutil.copytree(src,OUT/name,ignore=shutil.ignore_patterns("__pycache__","*.pyc",".gitkeep"))
(OUT/"nas").mkdir()
for name in ("app.py","index.html","media_quality.py"):
    shutil.copy2(ROOT/"nas"/name,OUT/"nas"/name)
for name in KEEP_FILES:
    src=ROOT/name
    if src.exists(): shutil.copy2(src,OUT/name)
print(f"runtime ready: {OUT}")
