#!/bin/bash
# КирпичИнвест: отправить актуальные URL через IndexNow.
# Файл можно запускать двойным кликом из Finder или из Терминала.
set -o errexit
set -o nounset
set -o pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPORT_DIR="$ROOT/_project/seo"
REPORT="$REPORT_DIR/SEO011_INDEXNOW_LAST.json"
mkdir -p "$REPORT_DIR"

if command -v python3 >/dev/null 2>&1; then
  PYTHON="$(command -v python3)"
elif [ -x /usr/bin/python3 ]; then
  PYTHON=/usr/bin/python3
else
  echo "Не найден Python 3. Установите Python 3 и запустите файл ещё раз." >&2
  exit 1
fi

echo "IndexNow: проверяю sitemap и ключ, затем отправляю URL..."
"$PYTHON" "$ROOT/_src/indexnow.py" --sitemap --submit | tee "$REPORT"
echo
echo "Готово. Отчёт сохранён: $REPORT"
