# skills

My personal, curated collection of [agent skills](https://docs.claude.com/en/docs/claude-code/skills).
`SKILL.md` is an open standard, so the same folder works in **Claude Code, Codex CLI, Cursor, and Hermes Agent**.
Some are original; many build on community prior art, credited in [`CREDITS.md`](CREDITS.md).

## Layout

Skills are grouped by **domain**. `workflows/` holds playbooks that compose atomic skills into an
end-to-end process; `meta/` holds domain-agnostic skills. The **domain is the install unit** —
[`install.sh`](install.sh) installs only the domains opted into [`install.conf`](install.conf), so a
non-coding domain never leaks into a coding agent. Skills can nest at any depth inside a domain (just
for humans); only **leaf folder names** must be unique across the repo.

```
.
├── install.sh
├── <domain>/                 # atomic skills (e.g. software-development/)
│   └── <group>/<skill>/SKILL.md
├── workflows/                # playbooks that compose atomic skills
│   └── <workflow>/SKILL.md
└── meta/                     # domain-agnostic skills
    └── <skill>/SKILL.md
```

Each area has its own index:

- [`software-development/`](software-development/README.md) — design, planning, review, engineering
- [`workflows/`](workflows/README.md) — multi-skill playbooks
- [`meta/`](meta/README.md) — domain-agnostic skills

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

```bash
./install.sh --claude     # only ~/.claude/skills  (Claude Code)
./install.sh --codex      # only ~/.agents/skills  (Codex CLI)
./install.sh --cursor     # only ~/.agents/skills  (Cursor)
./install.sh --hermes     # only configure Hermes (when installed)
./install.sh --copy       # copy instead of symlink — use if an agent ignores symlinks (won't sync back)
./install.sh --force      # overwrite a foreign skill of the same name
./install.sh --uninstall  # remove only the links into this repo
./install.sh --prune-only # remove only stale links to skills removed from this repo; link nothing
./install.sh --dry-run    # preview, change nothing
```

`--uninstall` removes this repository's links and, when Hermes is installed, removes only this
repository's external-directory registration and staging directory. It leaves unrelated Hermes
skills and configuration entries untouched. If a same-named skill already exists in Hermes's
primary `~/.hermes/skills/` directory, Hermes's local skill takes precedence over the external
copy; the installer does not overwrite that skill. Every install also removes any link it
previously created for a skill that no longer exists in the repo; `--prune-only` does just that
without linking anything. A link to the repo's *previous* path after a move isn't recognized as
ours — run `--force` to relink under the new path, then remove the leftover old link by hand.

Installation is **default-deny** — only the domains in [`install.conf`](install.conf) link, so a new
domain stays out of your agents until you opt it in. Each leaf `SKILL.md` becomes a `/command` named for its
folder, so leaf names are unique repo-wide and the installer aborts on a collision. It won't overwrite
a same-named skill it didn't create — pass `--force` for that.

## Adding a skill

Copy [`docs/skill-template.md`](docs/skill-template.md) into a kebab-case folder, add a one-line row to
the area's README, and run `./scripts/validate-skills.sh` until it's clean. In Claude Code,
[`/add-skill`](.claude/skills/add-skill/SKILL.md) does all of that for you.

## Companion: agents

The companion [`agents`](https://github.com/blutarche/agents) repo's subagent definitions reference
skills from here by name (`scrutinize`, `brainstorming`, `writing-plans`). Install skills first so those agents get the
methodology they expect.

## License

Original skills are MIT ([`LICENSE`](LICENSE)); adapted ones are credited in
[`CREDITS.md`](CREDITS.md).
