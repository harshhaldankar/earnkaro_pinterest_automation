
import sys

with open(".github/workflows/deals_automation.yml", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace("cron: '0 */5 * * *' # Run every 5 hours", "cron: '0 */3 * * *' # Run every 3 hours")

with open(".github/workflows/deals_automation.yml", "w", encoding="utf-8") as f:
    f.write(content)

print("Cron updated successfully!")

