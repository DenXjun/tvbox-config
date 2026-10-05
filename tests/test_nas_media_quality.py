import importlib.util, tempfile, os
from pathlib import Path

def load(tmp):
    os.environ["TVBOX_DATA"]=str(tmp)
    spec=importlib.util.spec_from_file_location("mq","nas/media_quality.py")
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def test_empty_history(tmp_path):
    m=load(tmp_path); assert m.score("missing") is None
    s=m.stats("missing"); assert s["d7"]["samples"]==0

def test_score_formula(tmp_path):
    m=load(tmp_path)
    import sqlite3
    from datetime import datetime, timezone
    with sqlite3.connect(m.DB) as c:
        m.init(c)
        now=datetime.now(timezone.utc).isoformat()
        for _ in range(3):
            c.execute("insert into media_checks(site_key,url,checked,ok,first_byte_ms,bytes,kbps,error) values(?,?,?,?,?,?,?,?)",("a","u",now,1,500,1000,4096,""))
        c.commit()
    assert m.score("a") >= 95
