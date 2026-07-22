import json
import os
from datetime import datetime

ANALYTICS_FILE = 'analytics.json'
DASHBOARD_FILE = os.path.join('docs', 'dashboard.html')

def log_deal(title, status, reason=""):
    """
    Log a deal attempt to analytics.json.
    status: 'POSTED' or 'SKIPPED'
    reason: Context on why it was skipped.
    """
    try:
        data = []
        if os.path.exists(ANALYTICS_FILE):
            with open(ANALYTICS_FILE, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                except:
                    data = []
                    
        # Keep only last 1000 logs
        data.insert(0, {
            "title": title[:100],
            "status": status,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat()
        })
        data = data[:1000]
        
        with open(ANALYTICS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"  [ANALYTICS] Failed to log deal: {e}")

def generate_dashboard():
    """Reads analytics.json and generates a static HTML dashboard."""
    try:
        if not os.path.exists(ANALYTICS_FILE):
            return
            
        with open(ANALYTICS_FILE, 'r', encoding='utf-8') as f:
            logs = json.load(f)
            
        # Calculate stats
        total = len(logs)
        posted = sum(1 for log in logs if log['status'] == 'POSTED_ALL')
        web_only = sum(1 for log in logs if log['status'] == 'WEBSITE_ONLY')
        skipped = sum(1 for log in logs if log['status'] == 'SKIPPED')
        
        reason_counts = {}
        for log in logs:
            if log['status'] in ('SKIPPED', 'WEBSITE_ONLY'):
                reason_counts[log['reason']] = reason_counts.get(log['reason'], 0) + 1
                
        reasons_labels = list(reason_counts.keys())
        reasons_data = list(reason_counts.values())

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pipeline Analytics Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 20px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ text-align: center; margin-bottom: 40px; padding: 20px; background: #1e293b; border-radius: 12px; border: 1px solid #334155; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 40px; }}
        .stat-card {{ background: #1e293b; padding: 24px; border-radius: 12px; text-align: center; border: 1px solid #334155; }}
        .stat-card h3 {{ margin: 0; color: #94a3b8; font-size: 1rem; text-transform: uppercase; letter-spacing: 1px; }}
        .stat-card .value {{ font-size: 2.5rem; font-weight: bold; margin: 10px 0 0; color: #38bdf8; }}
        .charts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 40px; }}
        .chart-container {{ background: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #334155; height: 400px; }}
        .log-table {{ width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 12px; overflow: hidden; border: 1px solid #334155; }}
        .log-table th, .log-table td {{ padding: 12px 16px; text-align: left; border-bottom: 1px solid #334155; }}
        .log-table th {{ background: #0f172a; color: #94a3b8; font-weight: 600; }}
        .badge {{ padding: 4px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: bold; }}
        .badge-POSTED_ALL {{ background: rgba(34, 197, 94, 0.2); color: #4ade80; border: 1px solid #4ade80; }}
        .badge-WEBSITE_ONLY {{ background: rgba(234, 179, 8, 0.2); color: #facc15; border: 1px solid #facc15; }}
        .badge-SKIPPED {{ background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid #f87171; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Pinterest Pipeline Analytics</h1>
            <p>Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <h3>Total Processed</h3>
                <div class="value">{total}</div>
            </div>
            <div class="stat-card">
                <h3>Fully Posted (Web+Pin)</h3>
                <div class="value" style="color: #4ade80;">{posted}</div>
            </div>
            <div class="stat-card">
                <h3>Website Only (No Pin)</h3>
                <div class="value" style="color: #facc15;">{web_only}</div>
            </div>
            <div class="stat-card">
                <h3>Fully Skipped</h3>
                <div class="value" style="color: #f87171;">{skipped}</div>
            </div>
        </div>

        <div class="charts">
            <div class="chart-container">
                <canvas id="funnelChart"></canvas>
            </div>
            <div class="chart-container">
                <canvas id="reasonsChart"></canvas>
            </div>
        </div>

        <h2>Recent Deal Logs</h2>
        <table class="log-table">
            <thead>
                <tr>
                    <th>Time (UTC)</th>
                    <th>Status</th>
                    <th>Reason</th>
                    <th>Title</th>
                </tr>
            </thead>
            <tbody>
"""
        for log in logs[:100]:  # Show last 100
            html += f"""
                <tr>
                    <td>{log['timestamp'].replace('T', ' ')[:16]}</td>
                    <td><span class="badge badge-{log['status']}">{log['status']}</span></td>
                    <td>{log['reason'] or '-'}</td>
                    <td>{log['title']}</td>
                </tr>
"""
        
        html += f"""
            </tbody>
        </table>
    </div>

    <script>
        // Funnel Chart
        new Chart(document.getElementById('funnelChart'), {{
            type: 'doughnut',
            data: {{
                labels: ['Fully Posted', 'Website Only', 'Skipped'],
                datasets: [{{
                    data: [{posted}, {web_only}, {skipped}],
                    backgroundColor: ['#4ade80', '#facc15', '#f87171'],
                    borderColor: '#1e293b',
                    borderWidth: 2
                }}]
            }},
            options: {{ responsive: true, maintainAspectRatio: false, plugins: {{ title: {{ display: true, text: 'Pipeline Funnel', color: '#f8fafc' }}, legend: {{ labels: {{ color: '#f8fafc' }} }} }} }}
        }});

        // Reasons Chart
        new Chart(document.getElementById('reasonsChart'), {{
            type: 'bar',
            data: {{
                labels: {json.dumps(reasons_labels)},
                datasets: [{{
                    label: 'Drop-off Reasons',
                    data: {json.dumps(reasons_data)},
                    backgroundColor: '#38bdf8',
                    borderRadius: 4
                }}]
            }},
            options: {{ 
                responsive: true, maintainAspectRatio: false, 
                plugins: {{ legend: {{ display: false }}, title: {{ display: true, text: 'Rejection/Fallback Reasons', color: '#f8fafc' }} }},
                scales: {{ y: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: '#334155' }} }}, x: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ display: false }} }} }}
            }}
        }});
    </script>
</body>
</html>"""
        
        os.makedirs('docs', exist_ok=True)
        with open(DASHBOARD_FILE, 'w', encoding='utf-8') as f:
            f.write(html)
            
    except Exception as e:
        print(f"  [ANALYTICS] Failed to generate dashboard: {e}")
