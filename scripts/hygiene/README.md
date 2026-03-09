# Hygiene Checks (Scratchpad + Promotion Approval)

Instalacao local dos hooks:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/hygiene/install_git_hooks.ps1 -Force
```

Uso direto:

```powershell
python scripts/hygiene/git_hook.py pre-commit
python scripts/hygiene/git_hook.py ci --base origin/main
```

Objetivo:
- bloquear artefatos transitorios antes de commit
- manter `scratchpad.sql` sob controle
- exigir aprovacao explicita ao promover SQL estavel em `queries/`

