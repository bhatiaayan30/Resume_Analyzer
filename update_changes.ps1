# update_changes.ps1

# ------------------------------------------------------------
# Script: update_changes.ps1
# Purpose: Generate a changelog of all commits made in the last
#          few hours, add the changelog to the repo, commit any
#          pending changes, and push to the remote GitHub.
# ------------------------------------------------------------

# 1. Retrieve recent commits (last 2 hours) and write to CHANGELOG.md
# Adjust the time window if needed.
$since = (Get-Date).AddHours(-2)
$sinceStr = $since.ToString("yyyy-MM-dd HH:mm:ss")

git log --since="$sinceStr" --pretty=format:"%h %ad %s" --date=short > CHANGELOG.md

# 2. Stage all changes (including the newly generated CHANGELOG.md)
git add .

# 3. Commit with a descriptive message. If there are no changes, skip commit.
$hasChanges = git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    git commit -m "Update: recent changes (generated on $(Get-Date -Format "yyyy-MM-dd HH:mm:ss"))"
    Write-Host "Committed changes."
} else {
    Write-Host "No changes to commit."
}

# 4. Push to the remote (default branch assumed to be 'main')
# You may need to set up authentication (SSH key or PAT) beforehand.
git push

Write-Host "Done. Recent changes are documented in CHANGELOG.md and pushed to GitHub."
