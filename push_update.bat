@echo off
echo ========================================================
echo Pushing GetYourDeal Updates to GitHub
echo ========================================================
echo.

echo Syncing with remote repository...
git pull --rebase origin master

echo.
echo Pushing to GitHub...
git push origin master

echo.
echo ========================================================
echo Done! If git push succeeded, all updates are LIVE!
echo ========================================================
pause
