#!/bin/bash
# =============================================================================
# Deploy na PythonAnywhere: git pull + Reload webu
# Spusťte TADY na PA v Bash:  bash deploy_on_pa.sh
# (Jednou nastavte deploy_on_pa.env – viz deploy_on_pa.env.example)
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT" || exit 1

# Načti env (PA_USERNAME, PA_API_TOKEN, PA_DOMAIN)
if [ -f "$SCRIPT_DIR/deploy_on_pa.env" ]; then
  set -a
  # shellcheck source=deploy_on_pa.env
  . "$SCRIPT_DIR/deploy_on_pa.env"
  set +a
fi

echo "[1] git pull v $REPO_ROOT"
git pull
GIT_RC=$?
if [ $GIT_RC -ne 0 ]; then
  echo "Chyba: git pull skoncil s kodem $GIT_RC"
  exit $GIT_RC
fi

if [ -z "$PA_USERNAME" ] || [ -z "$PA_API_TOKEN" ] || [ -z "$PA_DOMAIN" ]; then
  echo "[2] Reload preskocen – nastavte PA_USERNAME, PA_API_TOKEN, PA_DOMAIN v deploy_on_pa.env"
  echo "    (zkopirujte deploy_on_pa.env.example na deploy_on_pa.env a vyplnte)"
  exit 0
fi

echo "[2] Reload webu (PythonAnywhere API)"
URL="https://www.pythonanywhere.com/api/v0/user/${PA_USERNAME}/webapps/${PA_DOMAIN}/reload/"
HTTP=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$URL" -H "Authorization: Token $PA_API_TOKEN")
if [ "$HTTP" = "200" ]; then
  echo "    Reload OK (200)"
else
  echo "    Reload vratil HTTP $HTTP"
fi
echo "Hotovo."
