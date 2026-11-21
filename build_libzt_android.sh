#!/bin/bash
# Builds libzt (the embeddable ZeroTier node) for Android and puts the AAR
# where the game's Gradle export picks it up:
#   project/android/build/libs/zerotier/libzt-release.aar
#
# Needs: JDK 17, Android SDK with the NDK and CMake packages below, and the
# libzt source with its submodules (git clone --recursive
# https://github.com/zerotier/libzt). Run once; rerun only to update libzt.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
LIBZT_SRC="${LIBZT_SRC:-$HERE/../third_party/libzt}"
# Build outside the source drive: exFAT/FAT volumes break Gradle and CMake.
WORK="${LIBZT_WORK:-$HOME/Library/Caches/pokewilds-libzt}"
OUT="$HERE/project/android/build/libs/zerotier"
NDK_VERSION="${NDK_VERSION:-29.0.14206865}"   # same NDK the Godot export uses
CMAKE_VERSION="${CMAKE_VERSION:-3.22.1}"

: "${ANDROID_HOME:?Set ANDROID_HOME to your Android SDK folder}"
[ -f "$LIBZT_SRC/ext/ZeroTierOne/node/Node.cpp" ] || {
    echo "libzt submodules are missing in $LIBZT_SRC (git submodule update --init)"; exit 1; }
[ -d "$ANDROID_HOME/ndk/$NDK_VERSION" ] || {
    echo "Install NDK $NDK_VERSION: sdkmanager \"ndk;$NDK_VERSION\" \"cmake;$CMAKE_VERSION\""; exit 1; }

mkdir -p "$WORK" "$OUT"
rsync -a --delete --exclude '.git' --exclude '._*' --exclude 'cache' --exclude 'dist' "$LIBZT_SRC/" "$WORK/"

python3 "$HERE/libzt_patches.py" "$WORK"

GRADLE="$WORK/pkg/android/app/build.gradle"
# Only the two ABIs the game exports, built with the game's NDK.
sed -i.bak \
    -e 's/abiFilters .*/abiFilters "armeabi-v7a", "arm64-v8a"/' \
    -e "s/ndkVersion '.*'/ndkVersion '$NDK_VERSION'/" \
    -e "s/version '3\\.22\\.1'/version '$CMAKE_VERSION'/" \
    "$GRADLE"

# Maven Central (repo.maven.apache.org) was unreachable from CI: AGP's
# transitive deps (asm, fastutil, ...) all failed there while Google's
# mirror worked. Add Google's Maven Central mirror ahead of mavenCentral()
# in the root build.gradle so the build never depends on that host alone.
ROOT_GRADLE="$WORK/pkg/android/build.gradle"
python3 - "$ROOT_GRADLE" <<'PYEOF'
import sys
p = sys.argv[1]
s = open(p).read()
mirror = "        maven { url 'https://maven-central.storage-download.googleapis.com/maven2' }"
n = s.count("        mavenCentral()")
if n == 0:
    print("mirror patch: mavenCentral() not found in " + p, file=sys.stderr)
    sys.exit(1)
s = s.replace("        mavenCentral()", mirror + "\n        mavenCentral()")
open(p, "w").write(s)
PYEOF

cd "$WORK/pkg/android"
chmod +x gradlew
attempt=1
until ./gradlew --no-daemon assembleRelease; do
  if [ "$attempt" -ge 3 ]; then echo "libzt Gradle build failed after 3 attempts"; exit 1; fi
  echo "libzt Gradle build attempt $attempt failed; retrying in 30s..."
  sleep 30
  attempt=$((attempt + 1))
done
cp app/build/outputs/aar/libzt-release.aar "$OUT/libzt-release.aar"
echo "Built $OUT/libzt-release.aar"
