# `_lib`

Reusable page-building machinery shared by skills that render a self-contained HTML page.
There is no `SKILL.md` here, so this directory is never installed as a skill and never
becomes a `/command`. A skill reaches it through its own `lib` symlink (e.g.
`software-development/review/walkthrough/lib -> ../../../_lib`), never by importing across
skill folders directly. `install.sh --copy` follows that symlink (`cp -RL`) so a copied skill
still gets a real, self-contained `lib/` directory.
