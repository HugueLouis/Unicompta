#!/bin/bash
# usage: setup_git.sh "Full Name" "token"
git config --global user.name "$1"
git config --global user.email "unicompta@users.noreply.github.com"
git config --global credential.helper store
printf 'https://unicompta:%s@github.com\n' "$2" > ~/.git-credentials
chmod 600 ~/.git-credentials
cd "$(head -1 /Unicompta/config)" && git ls-remote origin >/dev/null 2>&1 \
  && echo "OK: GitHub connection successful" || echo "FAILED: check the token and its permissions on the repository"