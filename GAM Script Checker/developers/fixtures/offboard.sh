#!/bin/bash
# expect: DESTRUCTIVE
USER=bob@example.com
gam update user "$USER" suspended on
gam user "$USER" trash messages query "older_than:1y" doit
gam user "$USER" delete drivefile 1AbCdEf
gam delete user "$USER"
