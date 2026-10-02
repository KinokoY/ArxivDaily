# Pinned upstream and integration boundary

ArxivDaily incorporates a small, unmodified subset of
[`X-PG13/paper-digest`](https://github.com/X-PG13/paper-digest) at commit
`8906f9a12309956913eab29dade75c01cb7d0771`. It is stored in
[`arxivdaily/_vendor/paper_digest`](arxivdaily/_vendor/paper_digest/README.md)
with the upstream MIT [`LICENSE`](arxivdaily/_vendor/paper_digest/LICENSE).
The license and all five copied Python files were written from the raw Git
blobs at that commit and compared byte-for-byte with `git show` output. This
avoids Windows checkout line-ending conversion. SHA-256 hashes are in
[`ORIGIN.json`](arxivdaily/_vendor/paper_digest/ORIGIN.json). No upstream `.git`
directory or GitHub workflows were imported.

The checkout was fetched into `../tmp/upstream-staging` and its HEAD matched
the pinned SHA. Before integration, the upstream `unittest` baselines passed
under conda `ml` Python 3.12.9 with `TEMP`/`TMP` inside the workspace:

| Upstream suite | Result |
| --- | --- |
| `test_arxiv_client.py` | 15 passed |
| `test_config.py` | 26 passed |
| `test_digest.py` | 26 passed |

These are targeted upstream baseline tests, not a claim that its entire test
suite passed. ArxivDaily's adapter tests are in `tests/test_upstream.py`.

`arxivdaily.upstream` loads the pinned package under a private module name.
It uses upstream `Paper.canonical_id`, ordered author/category normalization,
and `Paper.merge_duplicate` for metadata deduplication. ArxivDaily validates
the incoming versioned ID first, retains its version and timestamps, and uses
the newer version's title and abstract when cross-listings are merged. This
keeps old-style arXiv IDs and cross-categories while preventing upstream's
broader ID parser from relaxing ArxivDaily's ID contract.

The upstream API/RSS fetcher has a latest-results limit and differs from the
required arxiv.py 4 paginated collector, so it is not called. Its rendering
inserts unescaped titles and combines abstract analysis with digest content;
that path cannot represent the full-text evidence gate and light-only tier.
Its CLI, notifications, state and GitHub workflows similarly do not implement
the required two-stage DeepSeek, Server酱 free-account and checkpoint rules.
ArxivDaily supplies these parts independently. Source attribution therefore
describes the actual reused metadata functions rather than claiming the whole
upstream application is active.

Root planning documents and skills have been preserved.
