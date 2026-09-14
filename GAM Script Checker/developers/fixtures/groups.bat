@echo off
REM expect: DESTRUCTIVE
set GAM=C:\GAM7\gam.exe
%GAM% print groups
%GAM% delete group old-team@example.com
