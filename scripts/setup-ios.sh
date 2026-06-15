#!/usr/bin/env bash
# Build, sign, and install ForgeLab on a tethered iPhone — to be run on a Mac
# with Xcode 15+ and a configured Apple Developer team.
#
# Prerequisites the script will check:
#   - Xcode + xcodebuild + xcrun devicectl
#   - xcodegen (brew install xcodegen)
#   - FORGE_APPLE_TEAM_ID exported (the 10-char team identifier from
#     developer.apple.com/account)
#   - The iPhone connected via USB and trusted ("Trust this Mac" prompt accepted)
#
# Usage:
#   FORGE_APPLE_TEAM_ID=ABC1234567 ./scripts/setup-ios.sh           # build + install
#   FORGE_APPLE_TEAM_ID=ABC1234567 ./scripts/setup-ios.sh --build-only

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/apps/ios"
SCHEME="ForgeLab"
CONFIGURATION="Debug"
BUILD_DIR="$PROJECT_DIR/.build"
ARCHIVE_PATH="$BUILD_DIR/ForgeLab.xcarchive"

BUILD_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --build-only) BUILD_ONLY=1 ;;
    -h|--help)
      sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
  esac
done

err() { echo "Erreur: $*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || err "'$1' introuvable dans PATH. $2"; }

echo "==> Vérification de l'environnement"
need xcodebuild "Installe Xcode depuis le Mac App Store."
need xcrun "Installe les Xcode Command Line Tools (xcode-select --install)."
need xcodegen "Installe XcodeGen: brew install xcodegen"

if ! xcrun devicectl --help >/dev/null 2>&1; then
  err "xcrun devicectl indisponible. Mets Xcode à jour (Xcode 15+)."
fi

if [[ -z "${FORGE_APPLE_TEAM_ID:-}" ]]; then
  err "Export FORGE_APPLE_TEAM_ID avant de lancer (l'ID à 10 caractères du compte développeur)."
fi

echo "==> Génération du projet Xcode (XcodeGen)"
cd "$PROJECT_DIR"
xcodegen --quiet

if [[ "$BUILD_ONLY" -eq 1 ]]; then
  echo "==> Compilation (sans archive)"
  xcodebuild \
    -project ForgeLab.xcodeproj \
    -scheme "$SCHEME" \
    -configuration "$CONFIGURATION" \
    -destination 'generic/platform=iOS' \
    -derivedDataPath "$BUILD_DIR/DerivedData" \
    -allowProvisioningUpdates \
    build \
    DEVELOPMENT_TEAM="$FORGE_APPLE_TEAM_ID"
  echo "Build OK. Pour installer sur ton iPhone, relance sans --build-only."
  exit 0
fi

echo "==> Découverte de l'iPhone connecté"
RAW_DEVICES="$(xcrun devicectl list devices 2>/dev/null || true)"
DEVICE_LINE="$(echo "$RAW_DEVICES" | grep -i 'iPhone' | grep -i 'available\|connected' | head -1 || true)"
if [[ -z "$DEVICE_LINE" ]]; then
  echo "Aucun iPhone connecté détecté."
  echo "Branche-le en USB, déverrouille-le, et accepte le prompt 'Trust this Mac'."
  err "Pas d'appareil iOS disponible."
fi
# Extract the device UUID from the Identifier column. `awk '{print $NF}'` is
# wrong: the last field is the Model (e.g. "(iPhone18,4)"), not the UUID.
DEVICE_ID="$(echo "$DEVICE_LINE" | grep -oE '[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}' | head -1 || true)"
[[ -z "$DEVICE_ID" ]] && err "Impossible d'extraire l'identifiant de l'iPhone:\n$DEVICE_LINE"
echo "    Appareil cible: $DEVICE_LINE"

echo "==> Archive (xcodebuild archive)"
mkdir -p "$BUILD_DIR"
xcodebuild \
  -project ForgeLab.xcodeproj \
  -scheme "$SCHEME" \
  -configuration "$CONFIGURATION" \
  -destination "generic/platform=iOS" \
  -archivePath "$ARCHIVE_PATH" \
  -derivedDataPath "$BUILD_DIR/DerivedData" \
  -allowProvisioningUpdates \
  archive \
  DEVELOPMENT_TEAM="$FORGE_APPLE_TEAM_ID"

APP_BUNDLE="$ARCHIVE_PATH/Products/Applications/ForgeLab.app"
[[ -d "$APP_BUNDLE" ]] || err "Bundle introuvable: $APP_BUNDLE"

echo "==> Installation sur l'iPhone via devicectl"
xcrun devicectl device install app --device "$DEVICE_ID" "$APP_BUNDLE"

echo ""
echo "Installation terminée."
echo ""
echo "Étapes restantes sur l'iPhone:"
echo "  1. Réglages → Général → VPN et gestion de l'appareil → faire confiance au profil"
echo "     développeur (uniquement la 1ère fois sur un nouveau profil)."
echo "  2. Ouvre 'FORGE LAB' sur le téléphone."
echo "  3. Renseigne l'IP locale du PC (ex: 192.168.1.50) et la clé API:"
echo "       sur ton PC: python -m forge_engine.scripts.seed_api_key create 'iPhone Air'"
echo "  4. Active FORGE_BIND_LAN=1 et FORGE_REQUIRE_AUTH=1 dans apps/forge-engine/.env"
echo "     puis relance le moteur (pnpm dev)."
echo ""
