# skills

My personal, curated collection of [agent skills](https://docs.claude.com/en/docs/claude-code/skills).
`SKILL.md` is an open standard, so the same folder works in **Claude Code, Codex CLI, and Cursor**.
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
./install.sh            # link every configured domain into all supported agents
```

The standard is shared, but each agent reads a different directory — two cover all three (paths
verified 2026-05-30 against the Claude Code, Codex, and Cursor docs; recheck if those tools move):

| Directory | Read by |
|-----------|---------|
| `~/.claude/skills/` | **Claude Code** (only this) |
| `~/.agents/skills/` | **Codex CLI** (only this), **Cursor** (this + the Claude dir) |

By default, `install.sh` links into both. Edit a skill here and every agent sees the change; once
linked, each one triggers on its `description:` or runs as `/<name>`.

```bash
./install.sh --claude     # only ~/.claude/skills  (Claude Code)
./install.sh --codex      # only ~/.agents/skills  (Codex CLI)
./install.sh --cursor     # only ~/.agents/skills  (Cursor)
./install.sh --copy       # copy instead of symlink — use if an agent ignores symlinks (won't sync back)
./install.sh --force      # overwrite a foreign skill of the same name
./install.sh --uninstall  # remove only the links into this repo
./install.sh --dry-run    # preview, change nothing
```

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
skills from here by name (`scrutinize`, `karpathy-guidelines`, `brainstorming`, `writing-plans`,
`verification-before-completion`, `de-flaking-tests`). Install skills first so those agents get the
methodology they expect.

## License

Original skills are MIT ([`LICENSE`](LICENSE)); adapted ones are credited in
[`CREDITS.md`](CREDITS.md).
