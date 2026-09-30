#!/bin/bash
# expect: DESTRUCTIVE
gam print users > /tmp/u.csv
rm -rf "$HOME/Documents"
