# Local implementation contracts

Current phase (2026-10-03): root Git initialized; pinned upstream metadata utilities imported and reused; root Actions workflow prepared. Small real DeepSeek checks are authorized; notification and real GitHub deployment are not yet verified. All generated files stay in the workspace. Root owns shared models/state/pipeline/CLI/fixtures/packaging and integration; module ownership below records the initial implementation split. Upstream provenance and the unmodified MIT notice are in arxivdaily/_vendor/paper_digest/.

Shared types are in arxivdaily/models.py. Use these types; communicate proposed changes before editing models.py. Config is a nested dict loaded by config.load_config(path); missing config values should use documented defaults. Public serialization must never include credentials, raw provider responses/reasoning, local fulltext or image paths.

## Collector owner

Files: arxivdaily/config.py, rules.py, collection.py, config.example.toml, tests/test_collection.py, tests/test_rules.py.

APIs: load_config(path)->dict; match_rules(paper, config)->list[str]; plan_window(now, state, manual_start=None, manual_end=None)->dict with start/end ISO UTC, initial_floor, uncovered list; Collector(config, client=None).collect(window)->CollectionResult with papers:list[Paper], complete:bool, shards:list[dict], errors:list[str]. Collector.by_ids(ids)->list[Paper]. The client is single arxiv.Client results(search), max_results=None, >=3 seconds, cross classifications, finite shards/splits and no silent truncation. Root handles state persistence.

Config sections: collection(page_size=100, delay_seconds=3, initial_days=7, lookback_days=14, shard_limit=10000, max_candidates=2000); rules(categories=[cs.CV,cs.LG,cs.AI,eess.IV], title_enabled=false, exclude=[], groups=dict, routes=dict); limits(full_daily_limit=5, review_daily_limit=2, stage_attempts=3, recovery_days=14, run_seconds=2400); llm.filter / llm.summary(base_url,model,api_key_env,effort,max_tokens,timeout,attempts,image_capable,input_chars); llm.pricing(cache_hit_per_million,cache_miss_per_million,output_per_million,currency); llm.max_run_cost optional; fulltext(timeout,attempts,min_chars,chunk_chars,max_download_bytes); delivery(sendkey_env,daily_limit=5,chain_attempts=3,poll_limit=3,body_bytes=30000,quota_timezone=Asia/Shanghai,query_counts_quota=false); archive(public_base_url,state_branch=arxivdaily-state). Use env names, never secret values in config.

## Analysis owner

Files: arxivdaily/fulltext.py, llm.py, tests/test_fulltext.py, tests/test_llm.py. Use httpx, bs4, pypdf (BSD), pypdfium2 (PDFium BSD). Root installs dependencies under app/.runtime using conda ml Python.

APIs: FulltextReader(config, work_dir, client=None).read(paper)->Body, .parse_html(html,paper)->Body, .parse_pdf(path,paper)->Body; AnalysisClient(config, client=None).select(paper,hits)->Decision, .review(paper,body,decision)->Decision, .summarize(paper,body)->Summary; validate_summary(summary,body) raises ProcessingError for bad evidence/digits/unqualified body; .usage_records list[dict] safe model/fingerprint/usage/cost only. Need entire sections including appendix through evidence extraction/aggregation, not prefix truncation. No hidden reasoning recorded. Image function only required figures/key pages; uncertain image/table must not manufacture numbers. API config high/max thinking enabled, stop status & strict schema, finite retries. Read SPEC fully, use PDF skill for real visual inspection. Root owns real representative fixture download, you may test synthetic inputs.

## Delivery owner

Files: arxivdaily/delivery.py, render.py, scripts/publish_state.py, ../.github/workflows/daily-digest.yml, docs/DEPLOYMENT.md, tests/test_delivery.py, tests/test_render.py. The publisher has been exercised with a local bare Git remote; actual GitHub execution remains a deployment check. Use subprocess command vectors and never log credential-bearing Git stderr.

APIs: render_archive(date,items,notes=None)->str; render_notification(date,items,archive_url,max_bytes=30000)->tuple[str,dict[str,str]] (base id -> rendered_inline_full/archive_link_only/light_title_link/light_archive_only), .server_title(date)->str. ServerChan(config,client=None).send(title,body)->DeliveryResult; polling inside .send bounded, readkey only in local memory. Root reserves persisted quota/attempt_started before send and links immutable recovery snapshots. Agent adapter MUST NOT retry POST after ambiguous timeout. Known wxstatus mappings corroborate official docs; unrecognized -> unknown. MockDelivery(status='confirmed').send(...) same result API.

State publisher script arguments --state-dir --branch --repository --message: invoked as pre-side-effect checkpoint by pipeline callback in workflow, merges latest branch safely under workflow concurrency and verifies remote reachable archive snapshot. Local execution has no callback and no Git use. Root will implement --checkpoint-command support. Write deploy instructions recognizing absent upstream source; no license claims before imported originals.
