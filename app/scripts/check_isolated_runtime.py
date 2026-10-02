"""Verify the workspace runtime with ml Python -I -S (no inherited site packages)."""
import importlib
import json
from pathlib import Path
import sys

APP = Path(__file__).resolve().parents[1]
RUNTIME = APP/".runtime"
if not sys.flags.isolated or not sys.flags.no_site:
    raise RuntimeError("run this check with Python -I -S")
sys.path[:0] = [str(RUNTIME),str(APP)]

modules = {}
for name in ("arxiv","httpx","bs4","pypdf","pypdfium2","PIL","tzdata","pytest","yaml"):
    module = importlib.import_module(name)
    path = Path(module.__file__).resolve()
    if not path.is_relative_to(RUNTIME):
        raise RuntimeError("dependency leaked from an inherited environment: "+name)
    modules[name] = str(path.relative_to(APP)).replace("\\","/")

from arxivdaily.config import load_config
from arxivdaily.delivery import MockDelivery
from arxivdaily.models import parse_time
from arxivdaily.pipeline import Pipeline
from arxivdaily.simulation import FixtureAnalysis,FixtureReader,load_fixture
from arxivdaily.state import StateStore
import uuid

fixture_path = APP/"fixtures/representative.json"
fixture,papers = load_fixture(fixture_path)
analysis = FixtureAnalysis(fixture)
store = StateStore(APP/"tmp/isolated-runs"/uuid.uuid4().hex)
reader = FixtureReader(load_config(APP/"config.example.toml"),fixture,fixture_path,APP/"tmp/isolated-visuals")
report = Pipeline(load_config(),store,None,analysis,reader,MockDelivery(),now=parse_time("2026-10-02T07:17:00+00:00")).run(papers)
result = {"isolated_no_site":True,"dependencies":modules,"full":report["full"],"light":report["light"],"errors":report["errors"],"external_llm_calls":False,"real_delivery":False}
(APP/"reports/isolated-runtime.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(result,ensure_ascii=False))
if report["errors"]:
    raise RuntimeError("isolated replay failed")
