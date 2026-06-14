# skills

My preferred [agent skills](https://docs.claude.com/en/docs/claude-code/skills) — a personal,
curated, cross-agent collection. `SKILL.md` is an open standard, so these work in **Claude Code,
Codex CLI, and Cursor** from the same folder. Some are original; many draw on prior art from the
community, credited in [`CREDITS.md`](CREDITS.md).

## Organization

Skills are grouped by **domain**; `workflows/` holds *playbooks* that compose atomic skills into an
end-to-end process; `meta/` holds domain-agnostic skills. The **top-level domain is the install
unit** — [`install.sh`](install.sh) installs only the domains listed in [`install.conf`](install.conf)
(so a non-coding domain never leaks into a coding agent). Within a domain, skills can nest at any
depth — that deeper grouping is for humans — but **leaf** folder names must stay unique across the repo.

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

Each area documents its own skills — browse:

- [`software-development/`](software-development/README.md) — design, planning, review, engineering
- [`workflows/`](workflows/README.md) — multi-skill playbooks
- [`meta/`](meta/README.md) — domain-agnostic skills

Each skill's own `SKILL.md` is the single source of truth for what it does. This README stays
deliberately thin so it doesn't rot as the collection grows.

## Install

```bash
./install.sh            # link skills from the configured domains into every supported agent
```

`SKILL.md` is a cross-agent standard, but each agent reads a *different* user-level directory. The
union of two dirs covers all three (paths verified 2026-05-30 against the Claude Code, Codex, and
Cursor docs — recheck if those tools move):

| Target dir | Read by | Notes |
|------------|---------|-------|
| `~/.claude/skills/` | **Claude Code** | Claude Code reads *only* this. |
| `~/.agents/skills/` | **Codex CLI**, **Cursor** | The shared cross-agent path. Codex reads *only* this; Cursor reads both dirs. |

The installer links into **both** by default — every target dir is read by at least one agent, with
no dead links. Edit a skill in this repo and every agent sees the change. Once linked, each skill
triggers automatically by its `description:`, or is invocable as `/<name>`.

```bash
./install.sh --claude     # only ~/.claude/skills  (Claude Code)
./install.sh --codex      # only ~/.agents/skills  (Codex CLI)
./install.sh --cursor     # only ~/.agents/skills  (Cursor reads it)
./install.sh --copy       # copy instead of symlink (changes won't sync back)
./install.sh --force      # overwrite an existing foreign skill of the same name
./install.sh --uninstall  # remove only the links pointing back into this repo
./install.sh --dry-run    # preview, change nothing
```

**What installs:** only the top-level domains listed in [`install.conf`](install.conf) (default-deny),
so a new non-coding domain won't leak into your coding agents until you opt it in. Within each, every
leaf folder with a `SKILL.md` is linked and the leaf name becomes the skill's command name, so leaf
names must be unique repo-wide (the installer aborts on a collision). The installer **refuses to
overwrite a same-named skill it didn't create** — pass `--force` to override.

(If an agent doesn't pick up a symlinked skill, re-run with `--copy`.) To publish the whole set as one
installable Claude Code plugin later, add a `.claude-plugin/plugin.json` + marketplace entry; the
folders are already shaped for it.

## Adding a skill

1. Copy [`docs/skill-template.md`](docs/skill-template.md) into a kebab-case folder in the right
   place — an atomic skill under a domain (`<domain>/<group>/<name>/`), a playbook under
   `workflows/<name>/`, a domain-agnostic one under `meta/<name>/`. Or run the `skill-creator`
   skill (`/skill-creator`) for a guided flow.
2. Add a one-line entry to that area's `README.md`.

## License

Original skills are MIT ([`LICENSE`](LICENSE)). Sources for adapted skills are in [`CREDITS.md`](CREDITS.md).
