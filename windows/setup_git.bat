@echo off
set /p NAME=Full name: 
echo.
echo A GitHub page will open so you can create a token:
echo   - Repository access: Only select repositories, then pick the data repository
echo   - Permissions: Contents = Read and write
echo   - Expiration: 1 year
echo Click Generate token, copy it, then come back here.
start https://github.com/settings/personal-access-tokens/new
set /p TOKEN=Paste the token here: 
wsl -d Unicompta -- bash /Unicompta/setup_git.sh "%NAME%" "%TOKEN%"
pause