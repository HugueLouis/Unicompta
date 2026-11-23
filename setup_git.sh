#!/bin/bash
# usage: setup_git.sh "Full Name" "token"
git config --global user.name "$1"
git config --global user.email "unicompta@users.noreply.github.com"
git config --global credential.helper store
printf 'https://unicompta:%s@github.com\n' "$2" > ~/.git-credentials
chmod 600 ~/.git-credentials

# The repo folder is now chosen inside the app, so the config file may not exist yet.
CONFIG=/Unicompta/config
if [ -f "$CONFIG" ]; then
  cd "$(head -1 "$CONFIG")" && git ls-remote origin >/dev/null 2>&1 \
    && echo "OK: GitHub connection successful" || echo "FAILED: check the token and its permissions on the repository"
else
  echo "Token saved. Launch Unicompta, pick the repository folder, then press Push to test the connection."
fi