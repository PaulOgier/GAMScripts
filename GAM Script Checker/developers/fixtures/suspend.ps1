# expect: CHANGES
$gam = "C:\GAM7\gam.exe"
& $gam print users
foreach ($u in $users) { & $gam user $u suspend users }
