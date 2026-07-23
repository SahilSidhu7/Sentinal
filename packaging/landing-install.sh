#!/usr/bin/env bash
# COPY THIS into the sentinal-landing repo as install.sh so it's served at
#   https://sahilsidhu7.github.io/sentinal-landing/install.sh
#
# It just forwards to the canonical installer in the main repo, so the landing
# page can never drift out of sync with the real install logic. All the
# env overrides (SENTINAL_VERSION, SENTINAL_INSTALL_METHOD, ...) pass straight
# through because they're already exported in the caller's environment.
set -euo pipefail
exec bash -c "curl -fsSL 'https://raw.githubusercontent.com/SahilSidhu7/Sentinal/main/scripts/install.sh' | bash"
