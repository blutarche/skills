# Technical sources — where the authoritative answer actually lives

When the question is about software (libraries, APIs, versions, repos, vulnerabilities, language/runtime behaviour), the credibility ladder is concrete. Go to the primary source first; everything else is a lead.

## Where to look, by question type

| Question | Primary source (go here first) | Notes |
|----------|--------------------------------|-------|
| Current version of a package | The registry: [npm](https://www.npmjs.com), [PyPI](https://pypi.org), [crates.io](https://crates.io), [pkg.go.dev](https://pkg.go.dev), Maven Central | Registry shows the actual latest published version + release date. Don't trust a tutorial's version. |
| What changed / when a feature landed | The repo's `CHANGELOG`/releases page, or the release notes | GitHub Releases and `git tag` history are authoritative. "Introduced in vX" claims must come from here. |
| How an API works / signatures | Official docs for that exact version, or the source code | Match the docs version to the version in question — APIs drift. When docs are thin, read the source. |
| Behaviour of a specific repo | The repo itself; for a fast orientation, DeepWiki (`ask_question` / `read_wiki_contents`) | DeepWiki is AI-generated over the real repo — good for navigation, but confirm load-bearing claims against the actual code/docs. |
| Is X deprecated / EOL | Official deprecation notice, release notes, or the project's support policy page | "Someone on a forum said it's dead" is not a citation. |
| Security / CVE | [NVD](https://nvd.nist.gov), the [GitHub Advisory Database](https://github.com/advisories), the vendor's security advisory | Get the CVE ID, affected version range, and fixed version from the advisory itself. |
| Standard / spec behaviour | The spec (RFC, WHATWG, ECMA, W3C, language reference) | The spec is the ground truth; MDN etc. are excellent secondary but verify edge cases against the spec. |
| Pricing / limits / quotas | The vendor's own pricing/limits page, dated | Pricing changes constantly and is the classic stale-memory trap. Always fetch. |

## Pin the version

Most technical wrongness comes from version drift. A true answer for v2 is a false answer for v4.

- Establish *which version* the question is about before answering. If the user didn't say, find the version in their lockfile / `package.json` / `go.mod` / `Cargo.toml` / `requirements.txt`, or ask.
- Quote docs and changelogs *for that version*, not "latest" docs, unless the user wants latest.
- When you state "X works like this," scope it: "as of vN (released YYYY-MM-DD)…".

## Reading the repo directly

When docs are missing, outdated, or contradicted by behaviour, the source code wins. Read the actual implementation, the tests (they document intended behaviour), and the issues/PRs for the *why*. A claim grounded in a quoted line of source at a specific commit/tag is the strongest technical citation there is.

## Cross-check the local codebase

If the question touches code in the current repo, the installed/declared version here is part of the answer — a globally-true fact can still be wrong *for this project*. Reconcile what the upstream source says with what this repo actually uses.
