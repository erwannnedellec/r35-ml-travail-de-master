#!/usr/bin/env bash
# check_sources.sh - verifie presence et empreintes des entrees figees et sources requises.
# Cible : `make check-sources`. Prealable bloquant a `make clean-all && make` (ADR-075).
set -u
fail=0
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 2

# Entree figee : verifie presence + empreinte SHA256 (contractuelle).
check_sha() {
  local path="$1" expected="$2"
  if [ ! -f "$path" ]; then
    echo "  MANQUANT (fige)   : $path"; fail=1; return
  fi
  local got; got="$(shasum -a 256 "$path" | cut -d' ' -f1)"
  if [ "$got" != "$expected" ]; then
    echo "  EMPREINTE FAUSSE  : $path"
    echo "      obtenu  : $got"
    echo "      attendu : $expected"
    fail=1
  else
    echo "  OK (fige)         : $path"
  fi
}

# Source requise : verifie presence d'au moins un fichier (empreinte non suivie).
check_present() {
  local pattern="$1" label="$2"
  local n; n="$(ls $pattern 2>/dev/null | wc -l | tr -d ' ')"
  if [ "$n" = "0" ]; then
    echo "  MANQUANT (source) : $label"; fail=1
  else
    echo "  OK ($n)             : $label"
  fi
}

echo "check-sources : entrees figees (SHA256) et sources requises (ADR-075)"
echo "-- entrees figees (empreinte contractuelle) --"
# statpop_clean_causal N'EST PLUS une entree figee (ADR-076) : refabriquee depuis les
# bruts par build_fact_statpop_gare.py (forward-fill causal). Sa reproductibilite se
# verifie par le run vierge (double make), pas par un SHA epingle. Restent figees les
# entrees NON refabricables par indisponibilite de source : statent, dim_rotations.
check_sha "data/processed/sources/statent_clean_causal.parquet" "cede91b9e9dd69329a5b081ae7dd7591700ddb7b95889595b19269d2c2155efe"
# dim_rotations_r35 : entree figee documentee (addendum ADR-075). Hors chaine ml_dataset
# (ne participe pas a ba493568) mais source de verite de la baseline humaine (couche 2) ;
# regeneration desactivee dans le Makefile, empreinte verifiee ici (blocage si derive).
check_sha "data/dimension/dim_rotations_r35.parquet" "688e943b5ea99404cfa3a210d6848cfc4b5688c31ca6e8a370318b944810277c"
check_sha "data/external/vacances_scolaires/Vacances_scolaires_vaudoises.pdf" "8a3494690a08d744cd857d23d8fadc9b4982bd933e4f70a8024dad1c94cd313f"
check_sha "data/external/vacances_scolaires/def_calendrier_vacances_scolaires_2023_2031.pdf" "ba8fed55ae2237e6fc5fc909843029238c36b9ec38e5cd5e8a191c25413e5a73"
echo "-- sources requises (presence) --"
check_present "data/raw/*.csv" "data/raw/*.csv (APC)"
check_present "data/external/meteosuisse/*.csv" "data/external/meteosuisse/*.csv"
check_present "data/external/statpop/*.csv" "data/external/statpop/*.csv"
check_present "data/external/horaires_r35/*.pdf" "data/external/horaires_r35/*.pdf"
check_present "data/external/ski/ski_*.pdf" "data/external/ski/ski_*.pdf"
check_present "data/external/simba/*.csv" "data/external/simba/*.csv"
check_present "data/external/reservations/*.xlsx" "data/external/reservations/*.xlsx"
check_present "data/external/rotations/rotations_23_25.csv" "data/external/rotations/rotations_23_25.csv"
check_present "data/external/istdaten/istdaten_*.csv" "data/external/istdaten/istdaten_*.csv"
check_present "data/external/statent/*STATENT*" "data/external/statent/ (STATENT)"

if [ "$fail" != "0" ]; then
  echo ""
  echo "check-sources : ECHEC. Provisionner les entrees manquantes ou non conformes."
  echo "  Voir data/README.md (fetch des sources publiques, entrees figees rematerialisees)."
  exit 1
fi
echo ""
echo "check-sources : OK, toutes les entrees requises sont presentes et conformes."
