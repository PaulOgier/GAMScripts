# expect: CHANGES
import subprocess
def offboard(email):
    subprocess.run(f"gam update user {email} suspended on", shell=True)
    subprocess.run(["gam", "user", email, "show", "delegates"])
