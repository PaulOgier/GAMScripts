#!/bin/bash
# expect: DESTRUCTIVE
gam cros_ou /Kiosks issuecommand command reboot
gam cros_ou /Loaners issuecommand command wipe_users doit
