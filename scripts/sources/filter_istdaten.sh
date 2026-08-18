#!/bin/bash
# Filters istdaten CSV files keeping rows matching:
#   - BETREIBER_ABK == VMCV
#   - BETREIBER_ABK == MVR-cev
#   - BPUIC == 8501200
# Output: one CSV per month in $DST, with header preserved.
# Idempotent: skips months whose output file already exists in $DST.

# Chemins paramétrables (aucun chemin absolu local codé en dur).
#   SRC : répertoire des archives mensuelles ISTDATEN téléchargées depuis
#         opentransportdata.swiss (volume externe ou disque local).
#   DST : répertoire de destination dans le dépôt.
# Exemple : SRC=/media/disque/istdaten_raw ./scripts/sources/filter_istdaten.sh
SRC="${ISTDATEN_SRC:?definir ISTDATEN_SRC : repertoire des archives mensuelles ISTDATEN}"
DST="${ISTDATEN_DST:-$(cd "$(dirname "$0")/../.." && pwd)/data/external/istdaten}"
LOG="$DST/filter_log.txt"

mkdir -p "$DST"
echo "Started: $(date)" | tee "$LOG"

total_months=0
total_rows=0

# Process one source directory into a single monthly CSV.
# Args: $1 = source dir, $2 = output month (YYYY-MM)
process_month() {
    local month_dir="$1"
    local month="$2"
    local output_file="$DST/istdaten_${month}.csv"

    if [ -f "$output_file" ]; then
        echo "Skipping $month (already exists)" | tee -a "$LOG"
        return
    fi

    if [ ! -d "$month_dir" ]; then
        echo "ERROR: source directory not found: $month_dir" | tee -a "$LOG"
        return
    fi

    echo "Processing $month..." | tee -a "$LOG"

    local first_file=true
    for csv_file in $(ls "$month_dir"/*.csv 2>/dev/null | sort); do
        [ -f "$csv_file" ] || continue
        if [ "$first_file" = true ]; then
            awk -F';' 'NR==1 || ($4=="VMCV" || $4=="MVR-cev" || $13=="8501200")' "$csv_file" > "$output_file"
            first_file=false
        else
            awk -F';' 'NR>1 && ($4=="VMCV" || $4=="MVR-cev" || $13=="8501200")' "$csv_file" >> "$output_file"
        fi
    done

    if [ -f "$output_file" ]; then
        rows=$(awk 'NR>1' "$output_file" | wc -l | tr -d ' ')
        size=$(du -sh "$output_file" | cut -f1)
        echo "  -> $rows rows, $size : $output_file" | tee -a "$LOG"
        total_rows=$((total_rows + rows))
        total_months=$((total_months + 1))
    fi
}

# ---------------------------------------------------------------------------
# 2018 — deux conventions : noms textuels (jan–mai, jul, aug) et NN_MM
# ---------------------------------------------------------------------------
process_month "$SRC/jan18"  "2018-01"
process_month "$SRC/feb18"  "2018-02"
process_month "$SRC/mrz18"  "2018-03"
process_month "$SRC/apr18"  "2018-04"
process_month "$SRC/mai18"  "2018-05"
process_month "$SRC/18_06"  "2018-06"
process_month "$SRC/jul18"  "2018-07"
process_month "$SRC/aug18"  "2018-08"
process_month "$SRC/18_09"  "2018-09"
process_month "$SRC/18_10"  "2018-10"
process_month "$SRC/18_11"  "2018-11"
process_month "$SRC/18_12"  "2018-12"

# ---------------------------------------------------------------------------
# 2019 — jan–jul en chiffre simple (19_1…19_7), aoû–déc en NN_MM
# ---------------------------------------------------------------------------
process_month "$SRC/19_1"   "2019-01"
process_month "$SRC/19_2"   "2019-02"
process_month "$SRC/19_3"   "2019-03"
process_month "$SRC/19_4"   "2019-04"
process_month "$SRC/19_5"   "2019-05"
process_month "$SRC/19_6"   "2019-06"
process_month "$SRC/19_7"   "2019-07"
process_month "$SRC/19_08"  "2019-08"
process_month "$SRC/19_09"  "2019-09"
process_month "$SRC/19_10"  "2019-10"
process_month "$SRC/19_11"  "2019-11"
process_month "$SRC/19_12"  "2019-12"

# ---------------------------------------------------------------------------
# 2020 — tous en NN_MM
# ---------------------------------------------------------------------------
for mm in 01 02 03 04 05 06 07 08 09 10 11 12; do
    process_month "$SRC/20_${mm}" "2020-${mm}"
done

# ---------------------------------------------------------------------------
# 2021 jan–mai — en NN_MM
# ---------------------------------------------------------------------------
for mm in 01 02 03 04 05; do
    process_month "$SRC/21_${mm}" "2021-${mm}"
done

# ---------------------------------------------------------------------------
# 2021 juin–déc + années futures — format ist-daten-YYYY-MM
# ---------------------------------------------------------------------------
for month_dir in "$SRC"/ist-daten-*/; do
    [ -d "$month_dir" ] || continue
    month=$(basename "$month_dir" | sed 's/ist-daten-//')
    process_month "$month_dir" "$month"
done

echo "" | tee -a "$LOG"
echo "Finished: $(date)" | tee -a "$LOG"
echo "Total months processed this run: $total_months" | tee -a "$LOG"
echo "Total rows this run: $total_rows" | tee -a "$LOG"
