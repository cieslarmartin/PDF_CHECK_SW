#!/usr/bin/env python3
# deploy_to_pythonanywhere.py
# Automatické nasazení verze 41 na PythonAnywhere: Git push + (volitelně) SSH pull + reload web app
# Použití: z složky 41 spusťte  python deploy_to_pythonanywhere.py
# Nebo z nadřazené složky:  python 41/deploy_to_pythonanywhere.py

import os
import sys
import subprocess
import re

# Složka projektu (41)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)

def load_env(path="deploy_config.env"):
    """Načte deploy_config.env (klíč=hodnota)."""
    env = {}
    if not os.path.exists(path):
        return env
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r"(\w+)=(.*)", line)
            if m:
                key, val = m.group(1), m.group(2).strip()
                if val.startswith('"') and val.endswith('"'):
                    val = val[1:-1]
                env[key] = val
    return env

def run(cmd, check=True, shell=False):
    """Spustí příkaz, vrátí (success, output)."""
    try:
        r = subprocess.run(
            cmd if shell else cmd.split(),
            capture_output=True,
            text=True,
            shell=shell,
            cwd=SCRIPT_DIR,
        )
        out = (r.stdout or "") + (r.stderr or "")
        if check and r.returncode != 0:
            return False, out
        return True, out
    except Exception as e:
        return False, str(e)

def main():
    env = load_env()
    pa_user = env.get("PA_USERNAME", "").strip()
    pa_token = env.get("PA_API_TOKEN", "").strip()
    pa_domain = env.get("PA_DOMAIN", "").strip()
    pa_ssh = env.get("PA_SSH", "").strip()
    pa_app_path = env.get("PA_APP_PATH", "").strip()

    print("=" * 60)
    print("  Nasazeni na PythonAnywhere (v41)")
    print("=" * 60)

    # 1) Git: commit + push (pokud je to git repo)
    is_git = os.path.isdir(os.path.join(SCRIPT_DIR, ".git"))
    if is_git:
        ok, out = run("git status --short")
        if ok and out.strip():
            print("\n[1] Git: nalezeny zmeny, commit + push...")
            run("git add -A")
            run('git commit -m "Deploy v41 (automaticky)"')
            ok2, out2 = run("git push")
            if not ok2:
                print("    Varovani: git push selhal (mozna nejste na branch s remote).")
                print("    Vystup:", out2[:500])
            else:
                print("    git push OK.")
        else:
            print("\n[1] Git: zadne zmeny k commitnuti, push preskocen.")
    else:
        print("\n[1] Toto neni git repozitar. Preskakuji git.")
        print("    Tip: Pro automaticke nasazeni vytvorte repo a na PythonAnywhere klonujte z neho.")

    # 2) Volitelne: SSH + git pull na serveru
    if pa_ssh and pa_app_path:
        print("\n[2] SSH: git pull na serveru...")
        cmd = f'ssh {pa_ssh} "cd {pa_app_path} && git pull"'
        ok, out = run(cmd, check=False, shell=True)
        if ok:
            print("    git pull na PA OK.")
        else:
            print("    SSH/git pull selhal (zkontrolujte PA_SSH, PA_APP_PATH):", out[:300])
    else:
        print("\n[2] SSH nekonfigurovan – na PythonAnywhere v Bash konzoli spuste:")
        print("    cd /home/VASE_USERNAME/" + (pa_domain or "VASE_DOMENA").replace(".pythonanywhere.com", "") + " && git pull")

    # 3) Reload web app pres PythonAnywhere API
    if pa_user and pa_token and pa_domain:
        print("\n[3] PythonAnywhere API: reload web app...")
        try:
            import urllib.request
            url = f"https://www.pythonanywhere.com/api/v0/user/{pa_user}/webapps/{pa_domain}/reload/"
            req = urllib.request.Request(url, method="POST")
            req.add_header("Authorization", f"Token {pa_token}")
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status == 200:
                    print("    Reload OK.")
                else:
                    print("    Reload vratil status:", resp.status)
        except Exception as e:
            print("    Chyba reload:", e)
    else:
        print("\n[3] API nekonfigurovano – v deploy_config.env vyplnte PA_USERNAME, PA_API_TOKEN, PA_DOMAIN")
        print("    Token ziskate na: https://www.pythonanywhere.com/account/#api_token")
        print("    Na PythonAnywhere pak v zalozce Web kliknete na Reload.")

    print("\n" + "=" * 60)
    print("  Hotovo. Otestujte: https://" + (pa_domain or "vase-domena") + "/")
    print("=" * 60)

if __name__ == "__main__":
    main()
