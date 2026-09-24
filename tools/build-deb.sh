#!/bin/sh
set -eu
PROJECT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
VERSION=$(cat "$PROJECT/VERSION")
STAGE="$PROJECT/.build/deb-root"
OUTDIR="$PROJECT/dist"
rm -rf "$STAGE"
mkdir -p "$STAGE/opt/deft-pro/deft_pro" "$OUTDIR"
cp -a "$PROJECT/packaging/deb/." "$STAGE/"
cp -a "$PROJECT/src/deft_pro/." "$STAGE/opt/deft-pro/deft_pro/"
find "$STAGE" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$STAGE" -type f -name "*.pyc" -delete
chmod 0755 "$STAGE/DEBIAN"
chmod g-s "$STAGE/DEBIAN"
chmod 0755 "$STAGE/usr/bin"
sed "s/^Version:.*/Version: $VERSION/" "$PROJECT/packaging/deb/DEBIAN/control" > "$STAGE/DEBIAN/control"
dpkg-deb --build --root-owner-group "$STAGE" "$OUTDIR/deft-pro-configurator_${VERSION}_all.deb"
echo "$OUTDIR/deft-pro-configurator_${VERSION}_all.deb"
