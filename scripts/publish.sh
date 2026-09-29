#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if [ "$#" -ne 1 ]; then
  echo '用法：sh scripts/publish.sh "发布说明"' >&2
  exit 1
fi
if [ "$(git branch --show-current)" != "master" ]; then
  echo '请在 master 分支发布。' >&2
  exit 1
fi
git fetch origin master
if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/master)" ]; then
  echo '本地与远端存在差异，请先检查并同步后再发布。' >&2
  exit 1
fi
python3 scripts/build.py
python3 scripts/check.py
git add -A
git diff --cached --check
if git diff --cached --quiet; then
  echo '没有需要发布的变更。'
  exit 0
fi
git diff --cached --stat
git commit -m "$1"
git push origin master
