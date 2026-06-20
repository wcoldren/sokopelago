#!/usr/bin/env bash
# Pop up the Sokopelago client locally in solo free-play (no Archipelago server).
#
# Starts the Vite dev server and opens your browser straight to the game. All Microban
# levels are unlocked; Hint and Undo work for free in solo mode. For AP-connected play
# (items, world keys, tokens from a multiworld), use ./playtest.sh instead.
#
#   ./dev.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT/client"

[[ -d node_modules ]] || npm install
exec npm run dev -- --open
