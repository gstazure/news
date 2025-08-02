# cleanup.ps1
# Purpose: Clean the repo after orphan reset by ignoring and untracking build artifacts, envs, nested repos, and secrets,
#          then commit and force-push main. PowerShell-safe; no command chaining.
# Usage:   From repository root in PowerShell:
#          powershell -NoProfile -ExecutionPolicy Bypass -File .\cleanup.ps1
# Notes:
#  - Keeps files on disk (rm --cached), only removes from Git index.
#  - If a path doesn't exist, we ignore the error and continue.
#  - Requires you are on the 'main' branch with the fresh root commit already created.

$ErrorActionPreference = 'Continue'
Set-StrictMode -Version Latest

Write-Host "Step 1/4: Writing .gitignore with robust rules..." -ForegroundColor Cyan

$gitignoreContent = @"
# Python
__pycache__/
*.py[cod]
*.pyo
*.so

# Environments
venv/
.env
.env.*
**/.env
**/.env.*

# Artifacts and logs
outputs/
logs/
*.log
forum_bot.db

# Nested repos
news.git/
"@

Out-File -FilePath ".gitignore" -InputObject $gitignoreContent -Encoding UTF8 -Force

Write-Host "Step 2/4: Removing large/binary and secret paths from Git index (kept on disk)..." -ForegroundColor Cyan

function Untrack-Path {
    param(
        [Parameter(Mandatory=$true)][string]$PathArg
    )
    if (Test-Path -LiteralPath $PathArg -PathType Any) {
        Write-Host "  - Untracking $PathArg" -ForegroundColor Yellow
        git rm -r --cached -- "$PathArg" | Out-Null
    } else {
        Write-Host "  - Skip (not found): $PathArg" -ForegroundColor DarkGray
    }
}

# Paths to untrack
$paths = @(
    "venv",
    "news.git",
    "__pycache__",
    "outputs",
    "logs",
    "forum_bot.db",
    ".env"
)

foreach ($p in $paths) {
    Untrack-Path -PathArg $p
}

# Handle .env.* wildcard: enumerate matches safely (if any)
$envDotStar = Get-ChildItem -LiteralPath . -Filter ".env.*" -File -ErrorAction SilentlyContinue
if ($envDotStar) {
    foreach ($f in $envDotStar) {
        Untrack-Path -PathArg $f.FullName
    }
} else {
    Write-Host "  - Skip (no matches): .env.*" -ForegroundColor DarkGray
}

Write-Host "Step 3/4: Committing cleanup..." -ForegroundColor Cyan

# Stage .gitignore explicitly (and any index removals)
git add .gitignore | Out-Null

# Only commit if there are staged changes
$changes = git diff --cached --name-only
if ([string]::IsNullOrWhiteSpace($changes)) {
    Write-Host "  - No staged changes to commit." -ForegroundColor DarkGray
} else
{
    git commit -m "cleanup: stop tracking env, nested repo, caches, outputs, logs, db, and .env" | Out-Null
    Write-Host "  - Commit created." -ForegroundColor Green
}

Write-Host "Step 4/4: Force-pushing to origin/main..." -ForegroundColor Cyan
# Validate current branch is 'main'
$currentBranch = (git rev-parse --abbrev-ref HEAD).Trim()
if ($currentBranch -ne "main") {
    Write-Host "  - Current branch is '$currentBranch', renaming to 'main'..." -ForegroundColor Yellow
    git branch -M main | Out-Null
}

git push -f origin main

Write-Host "Done. The repository now excludes venv, news.git, __pycache__, outputs, logs, forum_bot.db, and .env from tracking." -ForegroundColor Green
Write-Host "Collaborators must re-clone or hard reset: git fetch origin; git reset --hard origin/main" -ForegroundColor Green