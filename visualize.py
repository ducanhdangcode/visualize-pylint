import sys
import json
import subprocess
import html
import os
import re
import glob
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

SCORE_WEIGHTS = {'fatal': 50, 'error': 25, 'warning': 5, 'refactor': 2, 'convention': 1}
SEVERITY_ORDER = {'fatal': 0, 'error': 1, 'warning': 2, 'refactor': 3, 'convention': 4}
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
        if not os.path.exists(file_path):
            return "File not found (path issue)"
        
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            if 1 <= line_no <= len(lines):
                return lines[line_no - 1].strip()
    except Exception:
        return "Could not read source code."
    return ""

def get_python_files(target_path):
    """Get all Python files from target path."""
    if os.path.isfile(target_path):
        return [target_path]
    
    python_files = []
    for root, dirs, files in os.walk(target_path):
        dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git', 'venv', 'env', '.venv']]
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    
    return python_files

def run_pylint_on_file(file_path):
    """Run pylint on a single file and return results."""
    try:
        result_json = subprocess.run(
            ["pylint", file_path, "--output-format=json"],
            capture_output=True, text=True
        )
        result_text = subprocess.run(
            ["pylint", file_path],
            capture_output=True, text=True
        )
        
        output_data = result_json.stdout.strip()
        issues = []
        
        if output_data:
            try:
                issues = json.loads(output_data)
            except json.JSONDecodeError:
                pass
        
        score = 10.0
        score_match = re.search(r'rated at ([\d.]+)/10', result_text.stdout)
        if score_match:
            score = float(score_match.group(1))
        elif not issues:
            score = 10.0
            
        return issues, score
    except FileNotFoundError:
        return [], 0.0
    except Exception as e:
        return [], 0.0

def calculate_priority_score(row):
    """Calculate priority score for sorting (lower is higher priority)."""
    severity_score = SEVERITY_ORDER.get(row['type'], 999)
    weight = SCORE_WEIGHTS.get(row['type'], 0)
    return (severity_score, -weight, row['path'], row['line'])

def generate_html_report(df, score, plotly_div, target_path, file_summaries):
    if score >= 8:
        score_color = '#2ecc71'
    elif score >= 5:
        score_color = '#f1c40f'
    else:
        score_color = '#e74c3c'
    
    unique_files = sorted(df['path'].unique()) if not df.empty else []
    file_options = ''.join([f'<option value="{html.escape(f)}">{html.escape(f)}</option>' for f in unique_files])
    
    file_summary_html = ""
    if file_summaries:
        file_summary_html = """
        <div class="card">
            <h3>📊 Per-File Summary</h3>
            <table>
                <thead>
                    <tr>
                        <th>File</th>
                        <th style="width: 80px; text-align: center;">Score</th>
                        <th style="width: 80px; text-align: center;">Fatal</th>
                        <th style="width: 80px; text-align: center;">Error</th>
                        <th style="width: 80px; text-align: center;">Warning</th>
                        <th style="width: 80px; text-align: center;">Refactor</th>
                        <th style="width: 80px; text-align: center;">Convention</th>
                        <th style="width: 80px; text-align: center;">Total</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for summary in file_summaries:
            score_color_file = '#2ecc71' if summary['score'] >= 8 else '#f1c40f' if summary['score'] >= 5 else '#e74c3c'
            file_summary_html += f"""
                    <tr>
                        <td><div class="file-loc">{summary['file']}</div></td>
                        <td style="text-align: center; font-weight: bold; color: {score_color_file}">{summary['score']:.1f}</td>
                        <td style="text-align: center; background-color: {'#f8d7da' if summary['fatal'] > 0 else 'transparent'}">{summary['fatal'] if summary['fatal'] > 0 else '-'}</td>
                        <td style="text-align: center; background-color: {'#f8d7da' if summary['error'] > 0 else 'transparent'}">{summary['error'] if summary['error'] > 0 else '-'}</td>
                        <td style="text-align: center; background-color: {'#fff3cd' if summary['warning'] > 0 else 'transparent'}">{summary['warning'] if summary['warning'] > 0 else '-'}</td>
                        <td style="text-align: center; background-color: {'#d1ecf1' if summary['refactor'] > 0 else 'transparent'}">{summary['refactor'] if summary['refactor'] > 0 else '-'}</td>
                        <td style="text-align: center; background-color: {'#d1ecf1' if summary['convention'] > 0 else 'transparent'}">{summary['convention'] if summary['convention'] > 0 else '-'}</td>
                        <td style="text-align: center; font-weight: bold;">{summary['total']}</td>
                    </tr>
            """
        
        file_summary_html += """
                </tbody>
            </table>
        </div>
        """
    
    table_rows = ""
    for _, row in df.iterrows():
        severity_color = COLORS.get(row['type'], '#95a5a6')
        code_snippet = get_line_of_code(row['path'], row['line'])
        
        row_html = f"""
        <tr class="issue-row" data-file="{html.escape(row['path'])}" data-type="{row['type']}">
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
            .container {{ max-width: 1400px; margin: 0 auto; }}
            .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .meta {{ color: #7f8c8d; font-size: 14px; }}
            .card {{ background: {COLORS['card_bg']}; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); padding: 20px; margin-bottom: 20px; }}
            .charts-row {{ display: flex; gap: 20px; flex-wrap: wrap; }}
            .chart-box {{ flex: 1; min-width: 300px; }}
            .filter-bar {{ display: flex; gap: 15px; align-items: center; margin-bottom: 15px; flex-wrap: wrap; }}
            .filter-group {{ display: flex; align-items: center; gap: 8px; }}
            .filter-group label {{ font-weight: 600; font-size: 14px; color: #7f8c8d; }}
            .filter-select {{ padding: 8px 12px; border: 1px solid #bdc3c7; border-radius: 4px; background: white; font-size: 14px; cursor: pointer; }}
            .filter-select:focus {{ outline: none; border-color: #3498db; }}
            .filter-btn {{ padding: 8px 16px; border: none; border-radius: 4px; background: #3498db; color: white; font-size: 14px; cursor: pointer; font-weight: 600; }}
            .filter-btn:hover {{ background: #2980b9; }}
            .issue-count {{ font-size: 14px; color: #7f8c8d; padding: 8px 12px; background: #ecf0f1; border-radius: 4px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            th {{ text-align: left; padding: 12px; background-color: #ecf0f1; border-bottom: 2px solid #bdc3c7; color: #7f8c8d; font-size: 12px; text-transform: uppercase; }}
            td {{ padding: 12px; border-bottom: 1px solid #ecf0f1; vertical-align: top; }}
            tr:hover {{ background-color: #f9f9f9; }}
            .issue-row.hidden {{ display: none; }}
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
                    <div class="meta">Overall Code Health Score</div>
                </div>
            </div>

            <div class="card">
                {plotly_div}
            </div>

            {file_summary_html}

            <div class="card">
                <h3>🔍 Issue Log (Sorted by Priority)</h3>
                
                <div class="filter-bar">
                    <div class="filter-group">
                        <label for="fileFilter">📁 File:</label>
                        <select id="fileFilter" class="filter-select">
                            <option value="">All Files</option>
                            {file_options}
                        </select>
                    </div>
                    
                    <div class="filter-group">
                        <label for="typeFilter">⚠️ Type:</label>
                        <select id="typeFilter" class="filter-select">
                            <option value="">All Types</option>
                            <option value="fatal">Fatal</option>
                            <option value="error">Error</option>
                            <option value="warning">Warning</option>
                            <option value="refactor">Refactor</option>
                            <option value="convention">Convention</option>
                        </select>
                    </div>
                    
                    <button class="filter-btn" onclick="resetFilters()">Reset Filters</button>
                    
                    <div class="issue-count" id="issueCount">Showing: <strong>{len(df)}</strong> issues</div>
                </div>
                
                <table>
                    <thead>
                        <tr>
                            <th style="width: 100px;">Type</th>
                            <th style="width: 150px;">Code</th>
                            <th>Message</th>
                            <th>Location & Context</th>
                        </tr>
                    </thead>
                    <tbody id="issueTableBody">
                        {table_rows if table_rows else "<tr><td colspan='4' style='text-align:center'>✨ No issues found. Great job!</td></tr>"}
                    </tbody>
                </table>
            </div>
        </div>
        
        <script>
            const fileFilter = document.getElementById('fileFilter');
            const typeFilter = document.getElementById('typeFilter');
            const issueCount = document.getElementById('issueCount');
            
            function applyFilters() {{
                const selectedFile = fileFilter.value;
                const selectedType = typeFilter.value;
                const rows = document.querySelectorAll('.issue-row');
                let visibleCount = 0;
                
                rows.forEach(row => {{
                    const rowFile = row.getAttribute('data-file');
                    const rowType = row.getAttribute('data-type');
                    
                    const fileMatch = !selectedFile || rowFile === selectedFile;
                    const typeMatch = !selectedType || rowType === selectedType;
                    
                    if (fileMatch && typeMatch) {{
                        row.classList.remove('hidden');
                        visibleCount++;
                    }} else {{
                        row.classList.add('hidden');
                    }}
                }});
                
                issueCount.innerHTML = `Showing: <strong>${{visibleCount}}</strong> of <strong>${{rows.length}}</strong> issues`;
            }}
            
            function resetFilters() {{
                fileFilter.value = '';
                typeFilter.value = '';
                applyFilters();
            }}
            
            fileFilter.addEventListener('change', applyFilters);
            typeFilter.addEventListener('change', applyFilters);
        </script>
    </body>
    </html>
    """
    return html_content

def run_dashboard(target_path):
    
    python_files = get_python_files(target_path)
    
    if not python_files:
        return
    
    all_issues = []
    file_summaries = []
    overall_score = 10.0
    try:
        result_json = subprocess.run(
            ["pylint", target_path, "--output-format=json"],
            capture_output=True, text=True
        )
        result_text = subprocess.run(
            ["pylint", target_path],
            capture_output=True, text=True
        )
        score_match = re.search(r'rated at ([\d.]+)/10', result_text.stdout)
        if score_match:
            overall_score = float(score_match.group(1))
        output_data = result_json.stdout.strip()
        if output_data:
            try:
                all_issues = json.loads(output_data)
            except json.JSONDecodeError:
                pass
    except:
        pass
    for file_path in python_files:
        issues, score = run_pylint_on_file(file_path)
        issue_counts = {'fatal': 0, 'error': 0, 'warning': 0, 'refactor': 0, 'convention': 0}
        for issue in issues:
            issue_type = issue.get('type', '')
            if issue_type in issue_counts:
                issue_counts[issue_type] += 1
        
        file_summaries.append({
            'file': os.path.relpath(file_path, target_path) if os.path.isdir(target_path) else file_path,
            'score': score,
            'fatal': issue_counts['fatal'],
            'error': issue_counts['error'],
            'warning': issue_counts['warning'],
            'refactor': issue_counts['refactor'],
            'convention': issue_counts['convention'],
            'total': len(issues)
        })
    
    file_summaries.sort(key=lambda x: (x['score'], -x['total']))
    if all_issues:
        df = pd.DataFrame(all_issues)
        df['priority_score'] = df.apply(calculate_priority_score, axis=1)
        df = df.sort_values('priority_score')
        df = df.drop('priority_score', axis=1)
    else:
        df = pd.DataFrame()
    fig = make_subplots(
        rows=1, cols=2,
        column_widths=[0.3, 0.7],
        specs=[[{"type": "indicator"}, {"type": "sunburst"}]],
    )

    fig.add_trace(go.Indicator(
        mode="gauge+number", value=overall_score,
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

    full_html = generate_html_report(df, overall_score, plotly_html, target_path, file_summaries)

    with open("pylint_pro_report.html", "w", encoding="utf-8") as f:
        f.write(full_html)

    try:
        if sys.platform == 'win32': 
            os.startfile("pylint_pro_report.html")
        elif sys.platform == 'darwin': 
            subprocess.call(['open', "pylint_pro_report.html"])
        else: 
            subprocess.call(['xdg-open', "pylint_pro_report.html"])
    except:
        pass

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "."
    run_dashboard(path)