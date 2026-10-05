#!/usr/bin/env python3
import json, mimetypes, os, shutil, sqlite3, subprocess, sys, threading, time
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote, urlparse, urlsplit

ROOT=Path(__file__).resolve().parents[1]
DATA=Path(os.getenv("TVBOX_DATA","/data"))
OUTPUT=Path(os.getenv("TVBOX_OUTPUT","/output"))
CONFIG=Path(os.getenv("TVBOX_CONFIG","/config"))
LOGS=Path(os.getenv("TVBOX_LOGS","/logs"))
PORT=int(os.getenv("TVBOX_PORT","8080"))
INTERVAL=int(os.getenv("TVBOX_INTERVAL_HOURS","12"))*3600
FIRST_RUN_DELAY=max(5,int(os.getenv("TVBOX_FIRST_RUN_DELAY","30")))
AUTO_RUN=os.getenv("TVBOX_AUTO_RUN","1").lower() not in ("0","false","no")
DB=DATA/"nas.db"
UPSTREAM_CFG=CONFIG/"upstreams.json"
RUN_LOCK=threading.Lock()
CURRENT={"step":"","log":"","next_auto_at":None}

for p in (DATA,OUTPUT,CONFIG,LOGS): p.mkdir(parents=True,exist_ok=True)

def _persist_dir(name):
    """Merge shipped files into /data without overwriting runtime history, then symlink."""
    target=DATA/name; target.mkdir(parents=True,exist_ok=True)
    src_root=ROOT/name
    if src_root.is_symlink():
        return
    if src_root.exists():
        for src in src_root.rglob("*"):
            rel=src.relative_to(src_root); dst=target/rel
            if src.is_dir():
                dst.mkdir(parents=True,exist_ok=True)
            elif src.is_file() and not dst.exists():
                dst.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(src,dst)
        shutil.rmtree(src_root)
    src_root.symlink_to(target,target_is_directory=True)

# State contains history/static vocab. Deps contains localized jars/js/json used by
# generated subscriptions. Both must survive image rebuilds and upgrades.
_persist_dir("state")
_persist_dir("deps")

def db():
    c=sqlite3.connect(DB)
    c.execute("""create table if not exists runs(id integer primary key, started text, finished text, ok integer, message text)""")
    c.execute("""create table if not exists upstreams(id integer primary key, url text unique, name text, enabled integer default 1, source text default 'manual', created text)""")
    c.commit(); return c

def valid_url(v):
    try:
        u=urlparse(v); return u.scheme in ("http","https") and bool(u.netloc)
    except Exception: return False

def _upstream_doc():
    try:
        d=json.loads(UPSTREAM_CFG.read_text(encoding="utf-8"))
        if isinstance(d,dict) and isinstance(d.get("upstreams"),list): return d
    except (OSError,ValueError): pass
    seed=ROOT/"config"/"upstreams.json"
    try:
        d=json.loads(seed.read_text(encoding="utf-8"))
        if isinstance(d,dict) and isinstance(d.get("upstreams"),list): return d
    except (OSError,ValueError): pass
    return {"version":1,"upstreams":[]}

def _save_upstream_doc(d):
    tmp=UPSTREAM_CFG.with_suffix(".tmp")
    tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf-8"); tmp.replace(UPSTREAM_CFG)

def add_upstream(url,name="",source="manual"):
    if not valid_url(url): raise ValueError("invalid http/https URL")
    d=_upstream_doc()
    if any(x.get("url")==url for x in d["upstreams"]): return
    stamp=datetime.now(timezone.utc).date().isoformat()
    d["upstreams"].append({"name":name or ("nas-"+str(len(d["upstreams"])+1)),"url":url,"type":"vod","priority":50,"enabled":True,"added_at":stamp,"source":source,"format":"json"})
    _save_upstream_doc(d)

def upstreams():
    return [{"id":i+1,"url":x.get("url"),"name":x.get("name"),"enabled":x.get("enabled",True),"source":x.get("source","seed")}
            for i,x in enumerate(_upstream_doc().get("upstreams",[])) if x.get("url")]

def latest_log_tail(lines=120):
    logs=sorted(LOGS.glob("run_*.log"),reverse=True)
    if not logs: return ""
    try:
        return "\n".join(logs[0].read_text(encoding="utf-8",errors="replace").splitlines()[-lines:])
    except OSError: return ""

def _atomic_write(path,payload):
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_bytes(payload); tmp.replace(path)

def _validated_healthy(path):
    try:
        doc=json.loads(path.read_text(encoding="utf-8"))
    except (OSError,ValueError) as e:
        raise RuntimeError(f"healthy export invalid: {e}") from e
    sites=doc.get("sites") if isinstance(doc,dict) else None
    if not isinstance(sites,list) or not sites:
        raise RuntimeError("healthy export has no validated sites")
    if doc.get("lives"):
        raise RuntimeError("NAS healthy export unexpectedly contains live sources")
    return json.dumps(doc,ensure_ascii=False,indent=1).encode("utf-8")

def run_pipeline():
    if not RUN_LOCK.acquire(blocking=False): return False,"already running"
    started=datetime.now(timezone.utc).isoformat(); ok=False; msg=""
    try:
        env=os.environ.copy()
        env["TVBOX_NAS_MODE"]="1"
        env["LIVE_SPEEDTEST"]="0"
        env["UPSTREAM_CONFIG"]=str(UPSTREAM_CFG)
        d=_upstream_doc(); _save_upstream_doc(d)

        # Discovery is opportunistic. From fetch/verification onward every stage is
        # release-critical: a failed probe/store/export must never publish stale output.
        stages=[
          ([sys.executable,"scripts/mirror_probe.py"],False),
          ([sys.executable,"scripts/discover_upstreams.py","--pages","1"],False),
          ([sys.executable,"scripts/evaluate_candidates.py","--min-unique","3","--write-canary"],False),
          ([sys.executable,"scripts/fetch_merge.py"],True),
          ([sys.executable,"scripts/probe_sites.py","--only","http","--concurrency","16"],True),
          ([sys.executable,"nas/media_quality.py","--batch","probe/sites_probe.json"],True),
          ([sys.executable,"scripts/dedup_mirrors.py"],True),
          ([sys.executable,"scripts/drpy_probe.py","--workers","3"],True),
          ([sys.executable,"scripts/store.py","--ingest-sites","tvbox.json","--ingest-probes","probe/sites_probe.json","probe/drpy_probe.json","--prune","--stats"],True),
          ([sys.executable,"scripts/export_healthy.py"],True),
        ]
        healthy=ROOT/"exports"/"healthy.json"
        try: healthy.unlink()
        except FileNotFoundError: pass

        log=LOGS/("run_"+datetime.now().strftime("%Y%m%d_%H%M%S")+".log")
        CURRENT["log"]=log.name
        with log.open("w",encoding="utf-8") as f:
            for cmd,required in stages:
                CURRENT["step"]=" ".join(cmd[1:3])
                f.write("\n===== "+CURRENT["step"]+" =====\n"); f.flush()
                p=subprocess.run(cmd,cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=3600)
                if p.returncode:
                    if not required:
                        f.write(f"\n[nas] optional stage failed (exit {p.returncode}), continuing\n"); f.flush()
                        continue
                    f.flush()
                    tail=latest_log_tail(30).replace("\n"," | ")
                    raise RuntimeError(f"{Path(cmd[1]).name} failed (exit {p.returncode}): {tail[-1800:]}")

        if not healthy.exists():
            raise RuntimeError("healthy export missing")
        payload=_validated_healthy(healthy)

        # Last-known-good publication: only a fully successful run replaces public files.
        _atomic_write(OUTPUT/"tvbox.json",payload)
        _atomic_write(OUTPUT/"healthy.json",payload)
        raw=ROOT/"tvbox.json"
        if raw.exists(): _atomic_write(OUTPUT/"tvbox_all.json",raw.read_bytes())
        ok=True; msg="completed"
    except Exception as e:
        msg=str(e)
    finally:
        finished=datetime.now(timezone.utc).isoformat()
        with db() as c:
            c.execute("insert into runs(started,finished,ok,message) values(?,?,?,?)",(started,finished,int(ok),msg))
        CURRENT["step"]=""
        RUN_LOCK.release()
    return ok,msg

def scheduler():
    if not AUTO_RUN: return
    CURRENT["next_auto_at"]=time.time()+FIRST_RUN_DELAY
    time.sleep(FIRST_RUN_DELAY)
    while True:
        CURRENT["next_auto_at"]=None
        run_pipeline()
        wait=max(INTERVAL,3600)
        CURRENT["next_auto_at"]=time.time()+wait
        time.sleep(wait)

def _next_auto_in():
    t=CURRENT.get("next_auto_at")
    return max(0,int(t-time.time())) if t else None

def _safe_static(path):
    raw=unquote(path.lstrip("/"))
    if ";md5;" in raw:
        raw=raw.split(";md5;",1)[0]
    for prefix in ("deps","stores","raw-vod","vod"):
        if raw==prefix or raw.startswith(prefix+"/"):
            base=(ROOT/prefix).resolve()
            p=(ROOT/raw).resolve()
            try: p.relative_to(base)
            except ValueError: return None
            return p if p.is_file() else None
    return None

class H(SimpleHTTPRequestHandler):
    def _json(self,obj,status=200):
        b=json.dumps(obj,ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b)
    def _file(self,p,ctype=None):
        b=p.read_bytes(); self.send_response(200)
        self.send_header("Content-Type",ctype or mimetypes.guess_type(str(p))[0] or "application/octet-stream")
        self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        path=urlsplit(self.path).path.rstrip("/") or "/"
        if path=="/api/status":
            with db() as c:
                r=c.execute("select started,finished,ok,message from runs order by id desc limit 1").fetchone()
            return self._json({
                "running":RUN_LOCK.locked(),"step":CURRENT["step"],"log":CURRENT["log"],
                "last_run":dict(zip(("started","finished","ok","message"),r)) if r else None,
                "upstreams":len(upstreams()),"auto_run":AUTO_RUN,"next_auto_in":_next_auto_in(),
                "subscription_ready":(OUTPUT/"tvbox.json").is_file()
            })
        if path=="/api/upstreams": return self._json(upstreams())
        if path=="/api/log": return self._json({"text":latest_log_tail()})
        if path in ("/","/index.html"): return self._file(ROOT/"nas"/"index.html","text/html; charset=utf-8")
        if path=="/favicon.ico":
            self.send_response(204); self.end_headers(); return
        name=path.lstrip("/")
        if name in ("tvbox.json","healthy.json","tvbox_all.json"):
            p=OUTPUT/name
            if p.exists(): return self._file(p,"application/json; charset=utf-8")
            if name in ("tvbox.json","healthy.json"):
                return self._json({"error":"subscription_not_ready","message":"首次自动维护成功后订阅可用"},503)
        p=_safe_static(path)
        if p: return self._file(p)
        self.send_error(404)
    def do_POST(self):
        path=urlsplit(self.path).path.rstrip("/") or "/"
        try:
            n=int(self.headers.get("Content-Length","0")); body=json.loads(self.rfile.read(n) or b"{}")
        except (ValueError,json.JSONDecodeError):
            return self._json({"ok":False,"error":"invalid JSON"},400)
        if path=="/api/upstreams":
            try: add_upstream(body.get("url",""),body.get("name","")); return self._json({"ok":True})
            except Exception as e: return self._json({"ok":False,"error":str(e)},400)
        if path=="/api/run":
            if RUN_LOCK.locked(): return self._json({"ok":False,"error":"already running"},409)
            threading.Thread(target=run_pipeline,daemon=True).start(); return self._json({"ok":True})
        self.send_error(404)
    def log_message(self,fmt,*args): print("[web]",fmt%args,flush=True)

if __name__=="__main__":
    db().close()
    threading.Thread(target=scheduler,daemon=True).start()
    print(f"TVBox NAS manager listening on :{PORT}; auto_run={AUTO_RUN}; first_run_delay={FIRST_RUN_DELAY}s",flush=True)
    ThreadingHTTPServer(("0.0.0.0",PORT),H).serve_forever()
