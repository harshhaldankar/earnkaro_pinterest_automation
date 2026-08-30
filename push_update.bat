@echo off
echo Resetting local history to match GitHub...
git reset --soft origin/master

echo Unstaging workflow folder changes to bypass PAT restriction...
git restore --staged .github/workflows/

echo Committing the new E-Commerce design and RSS pipeline...
git commit -m "feat: AAS E-commerce redesign and RSS pipeline"

echo Pushing to GitHub...
git push origin master

echo.
echo Done! If git push succeeded, you can now run Make.com.
pause
