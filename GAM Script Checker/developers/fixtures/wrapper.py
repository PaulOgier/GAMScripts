# expect: DESTRUCTIVE
import subprocess
GAM = "/usr/local/bin/gam"

def gam(*args):
    return subprocess.run([GAM, *args], check=True, capture_output=True, text=True)

gam("print", "users")
for email in ["dan@example.com"]:
    gam("user", email, "delete", "messages", "query", "in:anywhere", "doit")
