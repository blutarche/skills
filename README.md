# skills

My personal, curated collection of [agent skills](https://docs.claude.com/en/docs/claude-code/skills).
`SKILL.md` is an open standard, so the same folder works in **Claude Code, Codex CLI, Cursor, and Hermes Agent**.
Some are original; many build on community prior art, credited in [`CREDITS.md`](CREDITS.md).

## Layout

Skills are grouped by **domain**. `workflows/` holds playbooks that compose atomic skills into an
end-to-end process; `meta/` holds domain-agnostic skills; `in-progress/` holds experiments not yet
graduated to a domain. The **domain is the install unit** (see [Install](#install)). Skills can nest at
any depth inside a domain (just for humans); only **leaf folder names** must be unique across the repo.

```
.
├── install.sh
├── <domain>/                 # atomic skills (e.g. software-development/)
│   └── <group>/<skill>/SKILL.md
├── workflows/                # playbooks that compose atomic skills
│   └── <workflow>/SKILL.md
├── meta/                     # domain-agnostic skills
│   └── <skill>/SKILL.md
└── in-progress/              # experiments, not yet graduated
    └── <skill>/SKILL.md
```

Each area has its own index:

- [`software-development/`](software-development/README.md) — design, planning, review, engineering
- [`workflows/`](workflows/README.md) — multi-skill playbooks
- [`meta/`](meta/README.md) — domain-agnostic skills
- [`in-progress/`](in-progress/README.md) — experimental skills, installed but not yet graduated

A skill's `SKILL.md` is the source of truth.

## Install

```bash
./install.sh            # link every configured domain into all detected agents
```

The standard is shared, but each agent reads a different directory. The installer links the
configured domains into Claude Code and Codex/Cursor, and—when `hermes` is installed—registers a
repo-owned staging directory with Hermes through its `skills.external_dirs` setting:

| Directory | Read by |
|-----------|---------|
| `~/.claude/skills/` | **Claude Code** (only this) |
| `~/.agents/skills/` | **Codex CLI** (only this), **Cursor** (this + the Claude dir) |
| `~/.hermes/external-skills/<repo-dir-name>/` | **Hermes Agent** (via `skills.external_dirs`) |

By default, `install.sh` links into the first two targets and adds the Hermes target when Hermes is
available. The Hermes staging directory contains symlinks back to this repository, so edits here
remain the source of truth. Hermes exposes external skills in its index, `skill_view`, and slash
commands; the symlinked staging directory is not a write-protection boundary, so an agent-directed
edit to one of these skills can modify the repository. If Hermes is absent, the installer skips it
without failing.

Run `./install.sh --help` for all options.

`--uninstall` removes this repository's links and, when Hermes is installed, removes only this
repository's external-directory registration and staging directory. It leaves unrelated Hermes
skills and configuration entries untouched. If a same-named skill already exists in Hermes's
primary `~/.hermes/skills/` directory, Hermes's local skill takes precedence over the external
copy; the installer does not overwrite that skill. Every install also removes any link it
previously created for a skill that no longer exists in the repo; `--prune-only` does just that
without linking anything. A link to the repo's *previous* path after a move isn't recognized as
ours — run `--force` to relink under the new path, then remove the leftover old link by hand.

Installation is **default-deny** — only the top-level domains in [`install.conf`](install.conf) link, so
a new domain (e.g. a non-coding one) stays out of your agents until you opt it in. Each leaf `SKILL.md`
becomes a `/command` named for its folder, so leaf names are unique repo-wide and the installer aborts
on a collision. It won't overwrite a same-named skill it didn't create — pass `--force` for that.

## Adding a skill

See [`AGENTS.md`](AGENTS.md) for placement, rules, and the validation gate, and
[`docs/skill-template.md`](docs/skill-template.md) for the `SKILL.md` template.

## Companion: agents

The companion [`agents`](https://github.com/blutarche/agents) repo's subagent definitions reference
the `scrutinize` skill from here by name. Install skills first so those agents get the
methodology they expect.

## License

Original skills are MIT ([`LICENSE`](LICENSE)); adapted ones are credited in
[`CREDITS.md`](CREDITS.md).
