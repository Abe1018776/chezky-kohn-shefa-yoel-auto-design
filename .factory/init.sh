#!/usr/bin/env bash
# .factory/init.sh — environment setup for the Shefa Shlomo Phase-2 mission.
#
# This script is idempotent and safe to run at the start of every worker
# session. It:
#   1. Verifies the sandbox is reachable
#   2. Verifies the sandbox toolchain (typst, python3) is present
#   3. Ensures pypdf is available on the sandbox (used for PDF text extraction)
#   4. Verifies .gitignore includes build/ artefacts
#   5. Does NOT install anything on the Windows host (no deps there)
#
# Run from the repo root on the Windows host. Powershell-safe one-liners.

set -e

SANDBOX_USER="factory-user"
SANDBOX_HOST="sefer-design"
REMOTE_REPO="~/chezky-kohn-shefa-yoel-auto-design"
IDENTITY="C:\\Users\\Main\\.factory\\.ssh\\id_ed25519"
PROXY="C:\\Users\\Main\\bin\\droid.exe computer ssh %h --proxy"

SSH="ssh.exe -o ProxyCommand=\"${PROXY}\" -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -o IdentityFile=${IDENTITY} -o IdentitiesOnly=yes -o User=${SANDBOX_USER} ${SANDBOX_HOST}"

echo "[init] Checking sandbox reachability..."
eval $SSH "echo ok" >/dev/null 2>&1 || { echo "[init] ERROR: sandbox unreachable"; exit 1; }

echo "[init] Checking sandbox toolchain..."
eval $SSH "test -x ~/.local/bin/typst && ~/.local/bin/typst --version" || { echo "[init] ERROR: typst missing on sandbox"; exit 2; }
eval $SSH "python3 --version" || { echo "[init] ERROR: python3 missing on sandbox"; exit 3; }

echo "[init] Ensuring pypdf is installed on sandbox..."
eval $SSH "python3 -c 'import pypdf' 2>/dev/null || pip install --user --break-system-packages pypdf >/dev/null 2>&1" || { echo "[init] WARN: pypdf install failed; some validators may fallback"; }
eval $SSH "python3 -c 'import pypdf; print(\"pypdf ok\")'"

echo "[init] Ensuring PIL (Pillow) is installed on sandbox..."
eval $SSH "python3 -c 'from PIL import Image' 2>/dev/null || pip install --user --break-system-packages Pillow >/dev/null 2>&1" || { echo "[init] WARN: Pillow install failed; blob-scan assertions may fallback"; }
eval $SSH "python3 -c 'from PIL import Image; print(\"PIL ok\")'"

echo "[init] Checking repo state on sandbox matches local..."
LOCAL_HEAD=$(git -C C:/Users/Main/chezky-kohn-shefa-yoel-auto-design rev-parse HEAD 2>/dev/null || echo "unknown")
REMOTE_HEAD=$(eval $SSH "cd ${REMOTE_REPO} && git rev-parse HEAD" 2>/dev/null || echo "unknown")
echo "[init] local HEAD:  ${LOCAL_HEAD}"
echo "[init] remote HEAD: ${REMOTE_HEAD}"
if [ "${LOCAL_HEAD}" != "${REMOTE_HEAD}" ]; then
  echo "[init] WARN: local and sandbox HEADs differ. Worker should sync before building."
fi

echo "[init] Verifying .gitignore covers build/ artefacts..."
if ! grep -qE '^build/' C:/Users/Main/chezky-kohn-shefa-yoel-auto-design/.gitignore 2>/dev/null; then
  echo "[init] WARN: .gitignore does not exclude build/ — VAL-CROSS-005 may fail."
fi

echo "[init] done."
