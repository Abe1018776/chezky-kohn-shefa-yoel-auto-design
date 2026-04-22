# Environment

Environment variables, external dependencies, and setup notes.

**What belongs here:** external dependency quirks, platform-specific notes, tool paths, and credentials (references only, never the values themselves).

**What does NOT belong here:** service ports/commands (see `.factory/services.yaml`), architectural or invariant information (see `architecture.md`).

---

## Build sandbox: `sefer-design`

- Linux container, preprovisioned with:
  - `~/.local/bin/typst` — Typst 0.14.2 (b33de9de)
  - `python3` — 3.x with standard library
  - `pypdf` (user-site; auto-installed by `.factory/init.sh` if missing)
  - `Pillow (PIL)` (user-site; auto-installed by `.factory/init.sh` if missing)
- Repo path: `/home/factory-user/chezky-kohn-shefa-yoel-auto-design`
- No `sudo` available. No `pdftotext`, no `poppler-utils`, no `mutool`.
- Fonts: `typst/fonts/` contains `PFT_Frank.ttf` + `PFT_Vilna.ttf` + `shefa.ttf` + `Drogolin*.ttf`. `Noto Serif Hebrew` is referenced in the current template but NOT installed — this produces a warning workers must resolve by committing a fallback font-family list in `template.typ`.

## Windows host (orchestrator)

- Path: `E:\chezky-kohn-shefa-yoel-auto-design\`
- SSH client: OpenSSH (via Git for Windows / built-in). Workers invoke `ssh.exe` directly with a ProxyCommand pointing at the Factory Droid CLI for authentication.
- No Typst, no audit tools locally — all heavy work happens on the sandbox.

## SSH identity + ProxyCommand

- Private key: `C:\Users\Main\.factory\.ssh\id_ed25519`
- ProxyCommand: `C:\Users\Main\bin\droid.exe computer ssh %h --proxy`
- User: `factory-user`
- Host: `sefer-design`

Workers invoke commands like:

```
ssh.exe -o "ProxyCommand=C:\\Users\\Main\\bin\\droid.exe computer ssh %h --proxy" \
        -o "StrictHostKeyChecking=no" \
        -o "UserKnownHostsFile=NUL" \
        -o "IdentityFile=C:\\Users\\Main\\.factory\\.ssh\\id_ed25519" \
        -o "IdentitiesOnly=yes" \
        -o "User=factory-user" \
        sefer-design "cd ~/chezky-kohn-shefa-yoel-auto-design && <command>"
```

## Git conventions

- Feature commits stay local until mission close. Do NOT `git push` as part of a feature.
- Between local (Windows) and sandbox, the two trees are kept in sync by pushing to a shared bare repo OR by pushing to origin on a feature branch and pulling on the sandbox. Workers may choose either; the orchestrator does NOT push to main.
- `build/*.pdf`, `build/*.png`, `build/*.typ`, `build/audit_report.md` are gitignored but the `build/` directory itself is not. `git check-ignore build/book.pdf` should exit 0.
- `.factory/` directory is committed (never gitignored).

## External services

NONE. No APIs, no databases, no auth providers. Pure file-based pipeline.

## Credentials

NONE required.
