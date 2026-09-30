#!/bin/bash
# expect: READ-ONLY
gam print users fields primaryemail,suspended > users.csv
gam info domain
gam user alice@example.com show filelist
gam select dev redirect csv ./groups.csv multiprocess print groups
