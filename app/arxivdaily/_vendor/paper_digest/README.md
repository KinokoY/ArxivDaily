# Pinned Paper Digest source

The upstream Python files and LICENSE are copied as raw committed blob bytes from
[`X-PG13/paper-digest`](https://github.com/X-PG13/paper-digest) commit
`8906f9a12309956913eab29dade75c01cb7d0771` (MIT). The original
[`LICENSE`](LICENSE) is preserved byte-for-byte. Only the configuration,
arXiv metadata and shared network modules needed to load the metadata types
are included. No upstream Git metadata or GitHub workflows are included.
SHA-256 hashes for every copied file are in [`ORIGIN.json`](ORIGIN.json). They
were checked against `git show <commit>:<path>` output, bypassing local Git
checkout line-ending conversion.

`arxivdaily.upstream` loads this package under a private module name and uses
its `Paper` normalization, base-ID and duplicate-merge behavior. ArxivDaily
uses `arxiv` 4.x for collection and its own rules, full-text quality gate,
two-tier rendering, DeepSeek roles, durable state and Server酱 delivery.
