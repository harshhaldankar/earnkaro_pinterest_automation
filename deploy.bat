@echo off
echo ==========================================
echo Deploying Updates to GitHub...
echo ==========================================
git add .
git commit -m "Manual update via deploy.bat"
git push origin master
echo ==========================================
echo Done! Your cloud pipeline is now updated.
echo ==========================================
pause
