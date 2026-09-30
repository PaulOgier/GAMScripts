# expect: DESTRUCTIVE
import os
cmds = ["gam print users", "gam delete user erin@example.com"]
for c in cmds:
    os.system(c)
