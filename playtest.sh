#!/usr/bin/env bash
# Pop up Sokopelago in AP-connected mode: generate a single-player seed, run a local
# Archipelago MultiServer, and open the client — so you can test received items, world
# keys, and escape valves (Hint/Skip/Undo tokens) end to end.
#
# Usage:
#   ./playtest.sh [path/to/seed.yaml]
#       Default YAML: examples/Sokopelago-Local.yaml
#
# Requires a local Archipelago 0.6.7 checkout. Configure via env:
#   AP_ROOT    Path to the Archipelago clone. Default: ../Archipelago relative to this
#              repo (the vendor/ sibling layout).
#   AP_PYTHON  Python command with Archipelago's deps. Default: "python".
#              e.g. AP_PYTHON="mamba run -n archipelago python" ./playtest.sh
#
# Safety: mirrors games/crystal/gen.sh — every existing Players/*.yaml is stashed aside
# (Generate.py scans Players/ with no .yaml filter, so any stray file becomes an extra
# slot → a silent multiworld) and restored on exit, and the spoiler is asserted to report
# exactly one player. The apworld is linked into worlds/ (NOT custom_worlds/: an unpacked
# source symlink under custom_worlds/ won't import on 0.6.7).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AP_ROOT="${AP_ROOT:-$(cd "$REPO_ROOT/.." && pwd)/Archipelago}"
AP_PYTHON="${AP_PYTHON:-python}"
YAML="${1:-$REPO_ROOT/examples/Sokopelago-Local.yaml}"

if [[ ! -d "$AP_ROOT" ]]; then
    echo "Error: Archipelago clone not found at AP_ROOT=$AP_ROOT" >&2
    echo "  Point AP_ROOT at an Archipelago 0.6.7 checkout. See apworld/README.md." >&2
    exit 1
fi
if [[ ! -f "$YAML" ]]; then
    echo "Error: YAML not found: $YAML" >&2
    exit 1
fi

PLAYERS_DIR="$AP_ROOT/Players"
OUTPUT_DIR="$AP_ROOT/output"
LINK="$AP_ROOT/worlds/sokopelago"
STASH_DIR="$PLAYERS_DIR/.playtest_stash"
YAML_BASE="$(basename "$YAML")"

# Ensure the apworld is visible to the runner.
if [[ ! -e "$LINK" ]]; then
    echo "==> Linking apworld -> $LINK"
    ln -s "$REPO_ROOT/apworld/sokopelago" "$LINK"
fi

# Stash any existing Players/*.yaml so they can't add slots (see header).
mkdir -p "$PLAYERS_DIR" "$STASH_DIR"
staged=()
shopt -s nullglob
for f in "$PLAYERS_DIR"/*.yaml; do
    mv "$f" "$STASH_DIR/"
    staged+=("$(basename "$f")")
done
shopt -u nullglob

SERVER_PID=""
cleanup() {
    [[ -n "$SERVER_PID" ]] && kill "$SERVER_PID" 2>/dev/null || true
    rm -f "$PLAYERS_DIR/$YAML_BASE"
    if [[ -d "$STASH_DIR" ]]; then
        for base in "${staged[@]:-}"; do
            [[ -n "$base" && -f "$STASH_DIR/$base" ]] && mv "$STASH_DIR/$base" "$PLAYERS_DIR/$base"
        done
        rmdir "$STASH_DIR" 2>/dev/null || true
    fi
}
trap cleanup EXIT

cp "$YAML" "$PLAYERS_DIR/$YAML_BASE"

echo "==> Generating a single-player seed from $YAML_BASE"
( cd "$AP_ROOT" && $AP_PYTHON Generate.py )

# Newest generated multiworld zip.
SEED_ZIP="$(ls -t "$OUTPUT_DIR"/AP_*.zip 2>/dev/null | head -1 || true)"
[[ -n "$SEED_ZIP" ]] || { echo "Error: no seed produced in $OUTPUT_DIR" >&2; exit 1; }

# Assert exactly one player (the spoiler header) — a stray Players/ file would add slots.
PLAYERS_LINE="$(unzip -p "$SEED_ZIP" '*_Spoiler.txt' 2>/dev/null | grep -m1 -i 'Players:' || true)"
echo "==> Spoiler: ${PLAYERS_LINE:-<no Players: line found>}"
if ! echo "$PLAYERS_LINE" | grep -qE 'Players:[[:space:]]*1([^0-9]|$)'; then
    echo "Error: expected exactly 1 player. A stray file in $PLAYERS_DIR may have added a slot." >&2
    exit 1
fi

SLOT="$(grep -E '^name:' "$YAML" | head -1 | sed -E 's/^name:[[:space:]]*//; s/[[:space:]]*$//')"

echo "==> Starting MultiServer on ws://localhost:38281  (seed: $(basename "$SEED_ZIP"))"
( cd "$AP_ROOT" && $AP_PYTHON MultiServer.py "$SEED_ZIP" ) &
SERVER_PID=$!

cat <<EOF

================================================================
 Local Archipelago server is up. Connect the client with:
     host:  localhost:38281
     slot:  ${SLOT:-<the name: in your YAML>}
================================================================

==> Launching the client (Ctrl-C here stops the server).
EOF

"$REPO_ROOT/dev.sh"
