#!/usr/bin/env bash
set -euo pipefail
SRC="${1:?папка с PDF}"
DST="${2:?папка для текста}"
TMP="$(mktemp -d)"
mkdir -p "$DST"

declare -A MAP=(
  ["ALFA-Macro_Insights-Policy_Rate_11Sep"]=R_RATE
  ["Inflation_tracker_02"]=R_INFL
  ["ALFA-7M26"]=R_7M26
  ["ALFA-consumption"]=R_CONS
  ["ALFA-macro_stat1H26"]=R_1H26
  ["Gold_digest_August26"]=R_GOLD
  ["FI_Strategy_3Q26_22072026"]=R_STRAT
)

for pdf in "$SRC"/*.pdf; do
  base="$(basename "$pdf" .pdf)"
  id="${MAP[$base]:-}"
  if [[ -z "$id" ]]; then
    case "$base" in
      *Steels*) id=R_STEEL ;;
      *14092026*) id=R_BOND ;;
      *) echo "skip: $base"; continue ;;
    esac
  fi
  pdftoppm -r 200 -gray -png "$pdf" "$TMP/$id"
  : > "$TMP/$id.txt"
  for img in $(ls "$TMP/$id"-*.png | sort -V); do
    page="$(basename "$img" .png | sed 's/.*-//')"
    echo "=== page $((10#$page)) ===" >> "$TMP/$id.txt"
    tesseract "$img" - -l rus+eng --psm 3 2>/dev/null >> "$TMP/$id.txt"
  done
  python3 -I "$(dirname "$0")/clean_report_text.py" "$TMP/$id.txt" "$DST/$id.txt"
  echo "ok: $id"
done
rm -rf "$TMP"
