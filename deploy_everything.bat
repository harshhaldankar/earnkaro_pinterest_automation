@echo off
echo ==========================================
echo 1. Pulling latest cloud changes...
echo ==========================================
git pull origin master --no-edit

echo ==========================================
echo 2. Pushing Automation Code to GitHub...
echo ==========================================
git add .
git commit -m "Manual update via bat file"
git push origin master

echo ==========================================
echo 3. Syncing Live Website Repository...
echo ==========================================
xcopy /E /I /Y "docs\*" "..\Getyourdeal\"
cd "..\Getyourdeal"
git pull origin master --no-edit
git add .
git commit -m "Manual update via bat file"
git push origin master

echo ==========================================
echo ALL DONE! Everything is Live.
echo ==========================================
pause
