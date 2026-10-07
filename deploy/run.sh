#!/bin/sh
# Pull, collect, commit and push if prices changed. Expects the repo clone mounted at /repo.
set -eu
cd /repo
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0=/repo
export GIT_AUTHOR_NAME="${GIT_AUTHOR_NAME:-pricerAI collector}" GIT_AUTHOR_EMAIL="${GIT_AUTHOR_EMAIL:-collector@invalid}"
export GIT_COMMITTER_NAME="$GIT_AUTHOR_NAME" GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL"
if [ -f /key ]; then
  export GIT_SSH_COMMAND="ssh -i /key -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/tmp/known_hosts"
fi

git pull --ff-only
status=0
python3 -m collector.run || status=$?
git add data
if ! git diff --cached --quiet; then
  git commit -q -m "Update prices $(date -u +%F)"
  git push -q
fi
exit "$status"
