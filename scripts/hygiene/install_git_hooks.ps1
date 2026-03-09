param(
  [switch]$Force
)

$ErrorActionPreference = "Stop"

function Get-RepoRoot {
  $root = (git rev-parse --show-toplevel) 2>$null
  if (-not $root) { throw "Not a git repo (cannot find repo root)." }
  return $root.Trim()
}

$repoRoot = Get-RepoRoot
$hooksDir = Join-Path $repoRoot ".git/hooks"

if (-not (Test-Path $hooksDir)) {
  throw "Hooks dir not found: $hooksDir"
}

$preCommitPath = Join-Path $hooksDir "pre-commit"
$commitMsgPath = Join-Path $hooksDir "commit-msg"

$preCommit = @"
#!/bin/sh
set -e

REPO_ROOT=\$(git rev-parse --show-toplevel)
SCRIPT=\"\$REPO_ROOT/scripts/hygiene/git_hook.py\"

if command -v python >/dev/null 2>&1; then
  python \"\$SCRIPT\" pre-commit
elif command -v py >/dev/null 2>&1; then
  py -3 \"\$SCRIPT\" pre-commit
else
  echo \"[ERROR] Python not found. Install Python or add it to PATH.\"
  exit 1
fi
"@

$commitMsg = @"
#!/bin/sh
set -e

REPO_ROOT=\$(git rev-parse --show-toplevel)
SCRIPT=\"\$REPO_ROOT/scripts/hygiene/git_hook.py\"
MSG_FILE=\"\$1\"

if [ -z \"\$MSG_FILE\" ]; then
  echo \"[ERROR] commit-msg hook missing message file path\"
  exit 1
fi

if command -v python >/dev/null 2>&1; then
  python \"\$SCRIPT\" commit-msg \"\$MSG_FILE\"
elif command -v py >/dev/null 2>&1; then
  py -3 \"\$SCRIPT\" commit-msg \"\$MSG_FILE\"
else
  echo \"[ERROR] Python not found. Install Python or add it to PATH.\"
  exit 1
fi
"@

if ((Test-Path $preCommitPath) -and (-not $Force)) {
  Write-Host "pre-commit hook already exists. Re-run with -Force to overwrite."
} else {
  Set-Content -Path $preCommitPath -Value $preCommit -NoNewline
  Write-Host "Installed: $preCommitPath"
}

if ((Test-Path $commitMsgPath) -and (-not $Force)) {
  Write-Host "commit-msg hook already exists. Re-run with -Force to overwrite."
} else {
  Set-Content -Path $commitMsgPath -Value $commitMsg -NoNewline
  Write-Host "Installed: $commitMsgPath"
}

Write-Host ""
Write-Host "Done. Hooks are local to this repo (.git/hooks) and are not committed to git."
Write-Host "Test:"
Write-Host "  git commit -m \"test\"  # should fail if scratch artifacts are staged"
Write-Host ""

