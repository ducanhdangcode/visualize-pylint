import sys
import json
import subprocess
import html
import os
import re  # ADD THIS - needed for regex score extraction
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

SCORE_WEIGHTS = {'fatal': 50, 'error': 25, 'warning': 5, 'refactor': 2, 'convention': 1}
COLORS = {
    'background': '#f4f6f8',
    'card_bg': '#ffffff',
    'text': '#2c3e50',
    'convention': '#3498db',
    'refactor': '#2ecc71',
    'warning': '#f1c40f',
    'error': '#e74c3c',
    'fatal': '#8e44ad'
}

def get_line_of_code(file_path, line_no):
    try:
        # line_no is 1-based, list index is 0-based
        if not os.path.exists(file_path):
            return "File not found (path issue)"
        
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            if 1 <= line_no <= len(lines):
                return lines[line_no - 1].strip()
    except Exception:
        return "Could not read source code."
    return ""

def generate_html_report(df, score, plotly_div, target_path):
    if score >= 8:
        score_color = '#2ecc71'
    elif score >= 5:
        score_color = '#f1c40f'
    else:
        score_color = '#e74c3c' 
    
    table_rows = ""
    for _, row in df.iterrows():
        severity_color = COLORS.get(row['type'], '#95a5a6')
        code_snippet = get_line_of_code(row['path'], row['line'])
        
        row_html = f"""
        <tr>
            <td style="border-left: 5px solid {severity_color};">
                <span class="badge" style="background-color: {severity_color}">{row['type'].upper()}</span>
            </td>
            <td><strong>{row['symbol']}</strong></td>
            <td>{row['message']}</td>
            <td>
                <div class="file-loc">{row['path']}:{row['line']}</div>
                <code class="code-snippet">{html.escape(code_snippet)}</code>
            </td>
        </tr>
        """
        table_rows += row_html

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Code Quality Report</title>
        <style>
            body {{ font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: {COLORS['background']}; color: {COLORS['text']}; margin: 0; padding: 20px; }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .meta {{ color: #7f8c8d; font-size: 14px; }}
            .card {{ background: {COLORS['card_bg']}; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); padding: 20px; margin-bottom: 20px; }}
            .charts-row {{ display: flex; gap: 20px; flex-wrap: wrap; }}
            .chart-box {{ flex: 1; min-width: 300px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            th {{ text-align: left; padding: 12px; background-color: #ecf0f1; border-bottom: 2px solid #bdc3c7; color: #7f8c8d; font-size: 12px; text-transform: uppercase; }}
            td {{ padding: 12px; border-bottom: 1px solid #ecf0f1; vertical-align: top; }}
            tr:hover {{ background-color: #f9f9f9; }}
            .badge {{ color: white; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }}
            .file-loc {{ font-family: monospace; color: #7f8c8d; font-size: 12px; margin-bottom: 4px; }}
            .code-snippet {{ display: block; background: #f4f6f8; padding: 8px; border-radius: 4px; font-family: 'Consolas', monospace; color: #d63031; border-left: 3px solid #fab1a0; font-size: 13px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div>
                    <h1>Pylint Analysis Report</h1>
                    <div class="meta">Target: {target_path}</div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 32px; font-weight: bold; color: {score_color}">{score:.2f}/10</div>
                    <div class="meta">Code Health Score</div>
                </div>
            </div>

            <div class="card">
                {plotly_div}
            </div>

            <div class="card">
                <h3>Issue Log</h3>
                <table>
                    <thead>
                        <tr>
                            <th style="width: 100px;">Type</th>
                            <th style="width: 150px;">Code</th>
                            <th>Message</th>
                            <th>Location & Context</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_rows if table_rows else "<tr><td colspan='4' style='text-align:center'>No issues found. Great job!</td></tr>"}
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    """
    return html_content

def run_dashboard(target_path):
    try:
        result_json = subprocess.run(
            ["pylint", target_path, "--output-format=json"],
            capture_output=True, text=True
        )
        result_text = subprocess.run(
            ["pylint", target_path],
            capture_output=True, text=True
        )
    except FileNotFoundError:
        print("Error: Pylint is not installed.")
        return

    output_data = result_json.stdout.strip()
    
    if not output_data:
        df = pd.DataFrame()
        issues = []
    else:
        try:
            issues = json.loads(output_data)
            df = pd.DataFrame(issues)
        except json.JSONDecodeError:
            print("❌ Failed to decode JSON.")
            return

    score = 10.0
    text_output = result_text.stdout

    score_match = re.search(r'rated at ([\d.]+)/10', text_output)
    if score_match:
        score = float(score_match.group(1))
    elif df.empty:
        score = 10.0

    fig = make_subplots(
        rows=1, cols=2,
        column_widths=[0.3, 0.7],
        specs=[[{"type": "indicator"}, {"type": "sunburst"}]],
    )

    fig.add_trace(go.Indicator(
        mode="gauge+number", value=score,
        gauge={'axis': {'range': [0, 10]}, 'bar': {'color': "#2c3e50"},
               'steps': [{'range': [0, 5], 'color': "#e74c3c"}, {'range': [5, 8], 'color': "#f1c40f"}, {'range': [8, 10], 'color': "#2ecc71"}]},
    ), row=1, col=1)

    if not df.empty:
        df_sunburst = df.copy()
        df_sunburst['type'] = df_sunburst['type'].str.capitalize()
        sunburst = px.sunburst(
            df_sunburst, path=['type', 'symbol', 'path'], values=[1]*len(df),
            color='type', color_discrete_map={k.capitalize(): v for k, v in COLORS.items() if k not in ['background', 'text', 'card_bg']}
        )
        fig.add_trace(sunburst.data[0], row=1, col=2)

    fig.update_layout(margin=dict(t=0, l=0, r=0, b=0), height=400, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    
    plotly_html = fig.to_html(full_html=False, include_plotlyjs='cdn')

    full_html = generate_html_report(df, score, plotly_html, target_path)

    with open("pylint_pro_report.html", "w", encoding="utf-8") as f:
        f.write(full_html)

    try:
        if sys.platform == 'win32': os.startfile("pylint_pro_report.html")
        elif sys.platform == 'darwin': subprocess.call(['open', "pylint_pro_report.html"])
        else: subprocess.call(['xdg-open', "pylint_pro_report.html"])
    except:
        pass

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "."
    run_dashboard(path)