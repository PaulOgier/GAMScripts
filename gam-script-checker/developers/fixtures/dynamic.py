# expect: CANNOT TELL
import subprocess
cmd = input("gam command to run: ")
subprocess.run(cmd, shell=True)
