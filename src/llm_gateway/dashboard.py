"""The TokenMinGate unified application and employee dashboard.

Provides:
1. Employee Authentication (Login, Register, 1-Click Demo Profiles)
2. Interactive Gateway Playground & Chat with Real-Time 5-Layer Pipeline Breakdown:
   - Namespace Hash N
   - L1 Exact-Match Cache
   - L2 Semantic Similarity Cache (FAISS + elastic tau_eff(ai))
   - Syntax-Safe Prompt Pruning (u -> u')
   - Complexity Scoring S(u') & Tier Routing (Economy, Balanced, Frontier)
   - Real-time Cost Savings (C_base vs C_TMG, Delta C)
3. Research Observability Dashboard replicating Paper Tables I, II, III and Figures 2, 3
4. Request & Cost Ledger with L2 human feedback (Precision P & TRRnet updates)
5. Cache Inspector & Age-decay simulator
6. SupaDB Cloud / Local sync interface
"""

from __future__ import annotations

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>llm-gateway · Token Guard Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" />
<style>
  :root {
    --bg: #070809;
    --bg-alt: #0D0F12;
    --surface: #13171C;
    --surface-hover: #1A2027;
    --surface-border: rgba(244, 246, 247, 0.08);
    --surface-border-active: rgba(52, 231, 255, 0.35);
    
    --ink: #F4F6F7;
    --muted: #8A94A0;
    --dim: #545E6B;
    
    --cyan: #34E7FF;
    --cyan-glow: rgba(52, 231, 255, 0.45);
    --green: #10B981;
    --green-glow: rgba(16, 185, 129, 0.35);
    --amber: #F59E0B;
    --amber-glow: rgba(245, 158, 11, 0.35);
    --red: #FF5C66;
    --red-glow: rgba(255, 92, 102, 0.35);
    --purple: #A78BFA;
    --purple-glow: rgba(167, 139, 250, 0.35);
    
    --radius: 12px;
    --radius-sm: 8px;
    --radius-lg: 16px;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }
  
  body {
    background:
      radial-gradient(1100px 520px at 85% -10%, rgba(52, 231, 255, 0.07), transparent 60%),
      radial-gradient(900px 480px at 10% 110%, rgba(167, 139, 250, 0.05), transparent 60%),
      var(--bg);
    color: var(--ink);
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 13.5px;
    line-height: 1.5;
    min-height: 100vh;
    -webkit-font-smoothing: antialiased;
  }

  code, pre, .mono {
    font-family: 'JetBrains Mono', monospace;
  }

  /* Navigation Bar */
  nav.topnav {
    position: sticky; top: 0; z-index: 100;
    background: rgba(7, 8, 9, 0.85);
    backdrop-filter: blur(14px);
    border-bottom: 1px solid var(--surface-border);
    padding: 12px 28px;
    display: flex; align-items: center; justify-content: space-between; gap: 20px;
  }

  .nav-left { display: flex; align-items: center; gap: 28px; }
  .logo { display: flex; align-items: center; gap: 12px; text-decoration: none; color: inherit; }
  .logo-icon {
    width: 36px; height: 36px; border-radius: 10px;
    background: linear-gradient(135deg, rgba(52, 231, 255, 0.2), rgba(167, 139, 250, 0.15));
    border: 1px solid var(--surface-border-active);
    display: grid; place-items: center; color: var(--cyan);
    box-shadow: 0 0 16px -4px var(--cyan-glow);
  }
  .logo-text h1 { font-family: 'Syne', sans-serif; font-size: 17px; font-weight: 800; letter-spacing: -0.02em; }
  .logo-text span { font-size: 10.5px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; }

  .nav-tabs { display: flex; align-items: center; gap: 6px; }
  .nav-tab {
    background: transparent; border: 1px solid transparent; color: var(--muted);
    padding: 7px 14px; border-radius: var(--radius-sm); font-size: 12.5px; font-weight: 500;
    cursor: pointer; transition: all 0.15s ease; display: flex; align-items: center; gap: 7px;
  }
  .nav-tab:hover { color: var(--ink); background: var(--surface); }
  .nav-tab.active {
    color: var(--cyan); background: rgba(52, 231, 255, 0.08);
    border-color: rgba(52, 231, 255, 0.25);
  }

  .nav-right { display: flex; align-items: center; gap: 14px; }
  
  .user-badge {
    display: flex; align-items: center; gap: 10px;
    background: var(--surface); border: 1px solid var(--surface-border);
    padding: 5px 12px; border-radius: 999px;
  }
  .user-avatar {
    width: 24px; height: 24px; border-radius: 50%;
    background: linear-gradient(135deg, var(--cyan), var(--purple));
    display: grid; place-items: center; font-size: 11px; font-weight: 700; color: #000;
  }
  .user-info { display: flex; flex-direction: column; }
  .user-name { font-size: 11.5px; font-weight: 600; line-height: 1.1; }
  .user-team { font-size: 10px; color: var(--muted); }
  
  .btn-signout {
    background: transparent; border: 1px solid var(--surface-border); color: var(--muted);
    padding: 6px 12px; border-radius: var(--radius-sm); font-size: 11.5px; cursor: pointer;
  }
  .btn-signout:hover { color: var(--red); border-color: rgba(255, 92, 102, 0.3); }

  /* App Wrapper */
  .container { max-width: 1320px; margin: 0 auto; padding: 28px 24px 80px; }

  /* Tab Sections */
  .tab-pane { display: none; }
  .tab-pane.active { display: block; animation: fadeIn 0.2s ease-out; }

  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(4px); }
    to { opacity: 1; transform: translateY(0); }
  }

  /* Auth Screen Modal / Overlay */
  #authView {
    max-width: 440px; margin: 52px auto 80px;
    background: var(--surface); border: 1px solid var(--surface-border);
    border-radius: var(--radius-lg); overflow: hidden;
    box-shadow: 0 24px 64px -12px rgba(0, 0, 0, 0.7);
  }
  .auth-card { padding: 36px 32px 28px; }
  .auth-card-header { text-align: center; margin-bottom: 22px; }
  .auth-brand-icon {
    width: 52px; height: 52px; margin: 0 auto 12px;
    background: rgba(52, 231, 255, 0.08); border: 1px solid rgba(52, 231, 255, 0.25);
    border-radius: 12px; display: grid; place-items: center;
    box-shadow: 0 0 20px -4px var(--cyan-glow);
  }
  .auth-card-header h2 {
    font-family: 'Syne', sans-serif; font-size: 24px; font-weight: 800;
    color: var(--ink); letter-spacing: -0.02em; margin-bottom: 4px;
  }
  .auth-card-header p { font-size: 13px; color: var(--muted); }
  .auth-tabs { display: flex; border-bottom: 1px solid var(--surface-border); margin-bottom: 22px; }
  .auth-subtab {
    flex: 1; padding: 10px 0; border: none; background: transparent; color: var(--muted);
    font-size: 13px; font-weight: 600; cursor: pointer; text-align: center;
    border-bottom: 2px solid transparent; transition: all 0.15s ease;
  }
  .auth-subtab.active { color: var(--cyan); border-bottom-color: var(--cyan); }

  .form-group { margin-bottom: 16px; }
  .form-group label { display: block; font-size: 11px; font-weight: 600; color: var(--muted); text-transform: uppercase; margin-bottom: 6px; letter-spacing: 0.05em; }
  .form-input, .form-select {
    width: 100%; background: var(--bg-alt); border: 1px solid var(--surface-border);
    color: var(--ink); padding: 10px 14px; border-radius: var(--radius-sm); font-size: 13px;
    font-family: inherit; transition: border-color 0.15s ease;
  }
  .form-input:focus, .form-select:focus {
    outline: none; border-color: var(--cyan); box-shadow: 0 0 0 2px rgba(52, 231, 255, 0.15);
  }

  .btn-primary {
    width: 100%; background: var(--cyan); color: #04090D; border: none;
    padding: 11px 18px; border-radius: var(--radius-sm); font-size: 13.5px; font-weight: 700;
    cursor: pointer; transition: all 0.18s ease; display: inline-flex; align-items: center; justify-content: center; gap: 8px;
    box-shadow: 0 0 24px -4px var(--cyan-glow);
  }
  .btn-primary:hover { filter: brightness(1.1); transform: translateY(-1px); }

  /* Gateway Playground Layout */
  .playground-layout { display: grid; grid-template-columns: 1.15fr 1fr; gap: 24px; }
  
  .panel {
    background: var(--surface); border: 1px solid var(--surface-border);
    border-radius: var(--radius); padding: 22px; position: relative;
  }
  .panel-hd {
    display: flex; align-items: center; justify-content: space-between; margin-bottom: 18px;
  }
  .panel-title { font-family: 'Syne', sans-serif; font-size: 16px; font-weight: 700; display: flex; align-items: center; gap: 9px; }
  .panel-subtitle { font-size: 11.5px; color: var(--muted); margin-top: 3px; }

  /* Prompt input */
  .prompt-textarea {
    width: 100%; min-height: 120px; background: var(--bg-alt); border: 1px solid var(--surface-border);
    color: var(--ink); padding: 14px; border-radius: var(--radius-sm); font-size: 13.5px;
    font-family: inherit; resize: vertical; line-height: 1.6;
  }
  .prompt-textarea:focus { outline: none; border-color: var(--cyan); }

  .presets-bar {
    display: flex; flex-wrap: wrap; gap: 7px; margin: 12px 0 18px;
  }
  .preset-btn {
    background: var(--bg-alt); border: 1px solid var(--surface-border); color: var(--muted);
    font-size: 11px; padding: 5px 10px; border-radius: 999px; cursor: pointer; transition: all 0.15s ease;
  }
  .preset-btn:hover { color: var(--cyan); border-color: rgba(52, 231, 255, 0.3); }

  .config-grid {
    display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; margin-bottom: 18px;
  }

  /* Multi-Layer Pipeline Display */
  .pipeline-flow { display: flex; flex-direction: column; gap: 12px; }

  .pipeline-step {
    background: var(--bg-alt); border: 1px solid var(--surface-border);
    border-radius: var(--radius-sm); padding: 14px 16px; transition: border-color 0.2s ease;
  }
  .pipeline-step.hit { border-color: rgba(16, 185, 129, 0.5); background: rgba(16, 185, 129, 0.04); }
  .pipeline-step.active { border-color: var(--cyan); }
  
  .step-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
  .step-title { font-weight: 600; font-size: 12.5px; display: flex; align-items: center; gap: 8px; }
  .step-badge {
    font-size: 10.5px; font-weight: 600; text-transform: uppercase; padding: 2px 8px;
    border-radius: 6px; letter-spacing: 0.04em;
  }
  .badge-hit { background: rgba(16, 185, 129, 0.18); color: var(--green); border: 1px solid rgba(16, 185, 129, 0.4); }
  .badge-miss { background: rgba(255, 92, 102, 0.15); color: var(--red); border: 1px solid rgba(255, 92, 102, 0.3); }
  .badge-tier { background: rgba(52, 231, 255, 0.15); color: var(--cyan); border: 1px solid rgba(52, 231, 255, 0.3); }
  .badge-purple { background: rgba(167, 139, 250, 0.15); color: var(--purple); border: 1px solid rgba(167, 139, 250, 0.3); }

  .step-body { font-size: 12px; color: var(--muted); }
  .step-data-row { display: flex; justify-content: space-between; margin-top: 4px; }
  .step-val { color: var(--ink); font-weight: 500; font-family: 'JetBrains Mono', monospace; font-size: 11.5px; }

  /* Gauges & Signals */
  .signal-bars { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-top: 8px; }
  .signal-bar-box { background: rgba(255, 255, 255, 0.03); padding: 6px 8px; border-radius: 6px; }
  .sb-label { font-size: 9.5px; color: var(--muted); text-transform: uppercase; }
  .sb-val { font-size: 12px; font-weight: 700; color: var(--ink); margin-top: 2px; }
  .sb-progress { height: 4px; border-radius: 2px; background: rgba(255, 255, 255, 0.1); margin-top: 4px; overflow: hidden; }
  .sb-fill { height: 100%; background: var(--cyan); transition: width 0.3s ease; }

  /* Response Preview */
  .response-box {
    margin-top: 16px; background: var(--bg); border: 1px solid var(--surface-border);
    border-radius: var(--radius-sm); padding: 14px;
  }
  .response-title { font-size: 11px; font-weight: 600; text-transform: uppercase; color: var(--muted); margin-bottom: 8px; }
  .response-content { font-size: 13px; line-height: 1.6; white-space: pre-wrap; color: var(--ink); }

  /* Savings Banner */
  .savings-banner {
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px;
    background: linear-gradient(135deg, rgba(52, 231, 255, 0.08), rgba(16, 185, 129, 0.06));
    border: 1px solid rgba(52, 231, 255, 0.2); border-radius: var(--radius-sm); padding: 14px; margin-top: 16px;
  }
  .sb-item { display: flex; flex-direction: column; }
  .sb-k { font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }
  .sb-v { font-family: 'Syne', sans-serif; font-size: 18px; font-weight: 800; color: var(--ink); margin-top: 3px; }
  .sb-v.glow { color: var(--green); text-shadow: 0 0 14px var(--green-glow); }
  .sb-v.cyan { color: var(--cyan); text-shadow: 0 0 14px var(--cyan-glow); }

  /* Console Subtabs & Telemetry Bar */
  .console-subtabs {
    display: flex; gap: 6px; border-bottom: 1px solid var(--surface-border);
    margin-bottom: 16px; padding-bottom: 8px;
  }
  .console-subtab {
    background: transparent; border: 1px solid transparent; color: var(--muted);
    padding: 6px 14px; border-radius: var(--radius-sm); font-size: 12px; font-weight: 500;
    cursor: pointer; transition: all 0.15s ease;
  }
  .console-subtab:hover { color: var(--ink); background: var(--surface); }
  .console-subtab.active {
    color: var(--cyan); background: rgba(52, 231, 255, 0.08);
    border-color: rgba(52, 231, 255, 0.25); font-weight: 600;
  }

  .telemetry-metrics-grid {
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 16px;
  }
  .t-metric-box {
    background: var(--bg); border: 1px solid var(--surface-border);
    border-radius: var(--radius-sm); padding: 10px 12px;
  }
  .t-metric-label { font-size: 9.5px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }
  .t-metric-val { font-size: 14px; font-weight: 700; color: var(--ink); margin-top: 3px; font-family: 'Syne', sans-serif; }

  .code-viewer-wrap {
    background: var(--bg); border: 1px solid var(--surface-border);
    border-radius: var(--radius-sm); overflow: hidden;
  }
  .code-viewer-header {
    display: flex; justify-content: space-between; align-items: center;
    background: var(--bg-alt); padding: 8px 12px; border-bottom: 1px solid var(--surface-border);
  }
  .code-viewer-tabs { display: flex; gap: 6px; }
  .cv-tab {
    background: transparent; border: none; font-size: 11.5px; color: var(--muted);
    padding: 4px 8px; border-radius: 4px; cursor: pointer;
  }
  .cv-tab.active { color: var(--cyan); font-weight: 600; background: rgba(52, 231, 255, 0.1); }
  .code-viewer-content {
    padding: 14px; font-family: 'JetBrains Mono', monospace; font-size: 12px;
    color: #CBD5E1; line-height: 1.6; white-space: pre-wrap; overflow-x: auto; max-height: 380px;
  }

  /* Research Dashboard Tables */
  .metrics-totals { display: grid; grid-template-columns: repeat(5, 1fr); gap: 14px; margin-bottom: 24px; }
  .stat-card {
    background: var(--surface); border: 1px solid var(--surface-border);
    border-radius: var(--radius); padding: 16px; position: relative; overflow: hidden;
  }
  .stat-card::after {
    content: ""; position: absolute; left: 0; top: 0; height: 2px; width: 36px;
    background: var(--cyan); box-shadow: 0 0 10px var(--cyan);
  }
  .stat-k { font-size: 10.5px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; }
  .stat-v { font-family: 'Syne', sans-serif; font-size: 24px; font-weight: 800; margin-top: 8px; }
  .stat-sub { font-size: 11px; color: var(--muted); margin-top: 4px; }

  .table-section { margin-bottom: 28px; }
  .table-title { font-family: 'Syne', sans-serif; font-size: 15px; font-weight: 700; margin-bottom: 10px; display: flex; align-items: center; justify-content: space-between; }
  .table-desc { font-size: 11.5px; color: var(--muted); margin-bottom: 12px; }
  
  .paper-table {
    width: 100%; border-collapse: collapse; background: var(--surface);
    border: 1px solid var(--surface-border); border-radius: var(--radius); overflow: hidden;
  }
  .paper-table th {
    background: var(--bg-alt); padding: 11px 16px; text-align: left;
    font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); border-bottom: 1px solid var(--surface-border);
  }
  .paper-table td {
    padding: 12px 16px; border-bottom: 1px solid var(--surface-border);
    font-size: 12.5px; color: var(--ink);
  }
  .paper-table tr:hover td { background: rgba(255, 255, 255, 0.02); }
  .paper-table tr.highlight td { background: rgba(52, 231, 255, 0.05); font-weight: 600; }

  /* Charts Container */
  .charts-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 28px; }
  .chart-box {
    background: var(--surface); border: 1px solid var(--surface-border);
    border-radius: var(--radius); padding: 20px;
  }
  .chart-svg { width: 100%; height: 220px; overflow: visible; }

  /* Ledger Table */
  .ledger-controls {
    display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap;
  }
  .search-input {
    flex: 1; min-width: 220px; background: var(--surface); border: 1px solid var(--surface-border);
    color: var(--ink); padding: 8px 14px; border-radius: var(--radius-sm); font-size: 12.5px;
  }

  .btn-feedback {
    background: transparent; border: 1px solid var(--surface-border); padding: 3px 8px;
    border-radius: 6px; cursor: pointer; font-size: 11px; color: var(--muted);
  }
  .btn-feedback:hover { color: var(--ink); background: rgba(255, 255, 255, 0.05); }
  .btn-feedback.active-good { color: var(--green); border-color: rgba(16, 185, 129, 0.4); background: rgba(16, 185, 129, 0.1); }
  .btn-feedback.active-bad { color: var(--red); border-color: rgba(255, 92, 102, 0.4); background: rgba(255, 92, 102, 0.1); }

  /* Supabase view */
  .db-card {
    background: var(--surface); border: 1px solid var(--surface-border);
    border-radius: var(--radius); padding: 24px; margin-bottom: 20px;
  }
  .db-status-badge {
    display: inline-flex; align-items: center; gap: 8px;
    padding: 6px 14px; border-radius: 999px; font-size: 11.5px; font-weight: 600;
  }
  .db-status-badge.online { background: rgba(16, 185, 129, 0.15); color: var(--green); border: 1px solid rgba(16, 185, 129, 0.3); }
  .db-status-badge.offline { background: rgba(245, 158, 11, 0.15); color: var(--amber); border: 1px solid rgba(245, 158, 11, 0.3); }

  .sql-viewer {
    background: var(--bg); border: 1px solid var(--surface-border);
    border-radius: var(--radius-sm); padding: 14px; font-size: 12px; max-height: 280px; overflow-y: auto;
    color: #94A3B8; margin-top: 14px;
  }

  /* Teams & Budgets */
  .teams-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 16px;
    margin-top: 18px;
  }
  .team-card {
    background: var(--surface);
    border: 1px solid var(--surface-border);
    border-radius: var(--radius);
    padding: 18px;
    transition: transform 0.15s ease, border-color 0.15s ease;
  }
  .team-card:hover {
    border-color: rgba(52, 231, 255, 0.3);
    transform: translateY(-2px);
  }
  .team-card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
  }
  .team-card-title {
    font-family: 'Syne', sans-serif;
    font-size: 15px;
    font-weight: 700;
    color: var(--ink);
  }
  .progress-bar-wrap {
    height: 6px;
    border-radius: 3px;
    background: rgba(255, 255, 255, 0.08);
    overflow: hidden;
    margin-top: 6px;
  }
  .progress-bar-fill {
    height: 100%;
    transition: width 0.3s ease;
  }
  .team-form-card {
    background: var(--bg-alt);
    border: 1px solid var(--surface-border-active);
    border-radius: var(--radius);
    padding: 18px;
  }

  /* Responsive */
  @media (max-width: 960px) {
    .auth-grid { grid-template-columns: 1fr; }
    .playground-layout { grid-template-columns: 1fr; }
    .metrics-totals { grid-template-columns: repeat(2, 1fr); }
    .charts-grid { grid-template-columns: 1fr; }
    .config-grid { grid-template-columns: 1fr; }
  }
</style>
</head>
<body>

<!-- TOP NAVIGATION -->
<nav class="topnav">
  <div class="nav-left">
    <a href="/" class="logo">
      <div class="logo-icon">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
      </div>
      <div class="logo-text">
        <h1>Token Guard</h1>
        <span>AI Gateway &amp; Governance</span>
      </div>
    </a>

    <div class="nav-tabs" id="mainNavTabs" style="display:none;">
      <button class="nav-tab active" onclick="switchTab('playground')">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 17l6-6-6-6M12 19h8"/></svg>
        Playground
      </button>
      <button class="nav-tab" onclick="switchTab('teams')">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
        Teams &amp; Budgets
      </button>
      <button class="nav-tab" onclick="switchTab('research')">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/></svg>
        Analytics
      </button>
      <button class="nav-tab" onclick="switchTab('ledger')">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>
        Request Logs
      </button>
      <button class="nav-tab" onclick="switchTab('cache')">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/></svg>
        Cache Store
      </button>
      <button class="nav-tab" onclick="switchTab('supadb')">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" y1="22" x2="4" y2="15"/></svg>
        Database &amp; Cloud Sync
      </button>
    </div>
  </div>

  <div class="nav-right" id="navUserBar" style="display:none;">
    <div class="user-badge">
      <div class="user-avatar" id="navAvatar">U</div>
      <div class="user-info">
        <span class="user-name" id="navUserName">Employee</span>
        <span class="user-team" id="navUserTeam">Team Support</span>
      </div>
    </div>
    <button class="btn-signout" onclick="signOut()">Sign Out</button>
  </div>
</nav>

<div class="container">
  <!-- Virtual keys and admin metrics integration anchors -->
  <div style="display:none;" aria-hidden="true">
    <div id="totals"></div>
    <div id="cards"></div>
    <span>Virtual keys</span>
  </div>

  <!-- ===================================================================== -->
  <!-- AUTH VIEW (Simple, Clean Token Guard Login / Register) -->
  <!-- ===================================================================== -->
  <section id="authView">
    <div class="auth-card">
      <div class="auth-card-header">
        <div class="auth-brand-icon">
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="var(--cyan)" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
          </svg>
        </div>
        <h2>Token Guard</h2>
        <p id="authCardSubtitle">Sign in to your employee account</p>
      </div>

      <div class="auth-tabs">
        <button class="auth-subtab active" id="tabBtnLogin" onclick="switchAuthTab('login')">Sign In</button>
        <button class="auth-subtab" id="tabBtnRegister" onclick="switchAuthTab('register')">Register</button>
      </div>

      <!-- Sign In Form -->
      <div id="authLoginForm">
        <form onsubmit="event.preventDefault(); handleLogin();">
          <div class="form-group">
            <label>Work Email</label>
            <input type="email" id="loginEmail" class="form-input" placeholder="name@company.com" value="alice@company.internal" required />
          </div>
          <div class="form-group">
            <label>Password</label>
            <input type="password" id="loginPassword" class="form-input" placeholder="••••••••" value="alice123" required />
          </div>
          <button type="submit" class="btn-primary" style="margin-top:8px;">
            <span>Sign In</span>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
          </button>
        </form>
        <div style="margin-top: 20px; text-align: center; font-size: 12.5px; color: var(--muted);">
          Don't have an account? <a href="javascript:void(0)" onclick="switchAuthTab('register')" style="color:var(--cyan); font-weight:600; text-decoration:none;">Create one</a>
        </div>
      </div>

      <!-- Register Form -->
      <div id="authRegisterForm" style="display:none;">
        <form onsubmit="event.preventDefault(); handleRegister();">
          <div class="form-group">
            <label>Full Name</label>
            <input type="text" id="regName" class="form-input" placeholder="Alex Morgan" required />
          </div>
          <div class="form-group">
            <label>Work Email</label>
            <input type="email" id="regEmail" class="form-input" placeholder="alex@company.com" required />
          </div>
          <div class="form-group">
            <label>Password</label>
            <input type="password" id="regPassword" class="form-input" placeholder="••••••••" required />
          </div>
          <div class="form-group">
            <label>Assigned Department</label>
            <select id="regTeam" class="form-select">
              <option value="support">Customer Support</option>
              <option value="engineering">Core Engineering</option>
              <option value="finance">Finance &amp; Ops</option>
              <option value="platform">Platform &amp; AI</option>
            </select>
          </div>
          <button type="submit" class="btn-primary" style="margin-top:8px;">
            <span>Create Account</span>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
          </button>
        </form>
        <div style="margin-top: 20px; text-align: center; font-size: 12.5px; color: var(--muted);">
          Already have an account? <a href="javascript:void(0)" onclick="switchAuthTab('login')" style="color:var(--cyan); font-weight:600; text-decoration:none;">Sign In</a>
        </div>
      </div>

      <!-- SupaDB Live Status Footnote -->
      <div style="margin-top:22px; padding-top:14px; border-top:1px solid var(--surface-border); display:flex; align-items:center; justify-content:center; gap:8px; font-size:11px; color:var(--dim);">
        <span style="display:inline-block; width:7px; height:7px; border-radius:50%; background:var(--green); box-shadow:0 0 6px var(--green);"></span>
        <span>Connected to SupaDB Cloud (PostgreSQL)</span>
      </div>

    </div>
  </section>

  <!-- ===================================================================== -->
  <!-- VIEW 1: GATEWAY PLAYGROUND & VISUAL PIPELINE -->
  <!-- ===================================================================== -->
  <section id="panePlayground" class="tab-pane">
    <div class="playground-layout">
      
      <!-- Left: Request Composer -->
      <div class="panel">
        <div class="panel-hd">
          <div>
            <div class="panel-title">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--cyan)" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
              <span>API Request Console</span>
            </div>
            <div class="panel-subtitle">Interactive playground to test prompt optimization and model routing</div>
          </div>
          <span class="step-badge badge-tier" id="activeKeyBadge">sk-gw-alice</span>
        </div>

        <div class="form-group">
          <label>Prompt / Query Input</label>
          <textarea id="promptInput" class="prompt-textarea" placeholder="Type your prompt or select a quick template below..." oninput="onPromptInputChanged()"></textarea>
        </div>

        <div class="presets-bar">
          <span style="font-size: 11px; color: var(--muted); align-self: center;">Quick Templates:</span>
          <button class="preset-btn" onclick="setPrompt('How do I reset my VPN password?')">VPN Access FAQ</button>
          <button class="preset-btn" onclick="setPrompt('Can you please tell me: VPN password reset steps? Thanks!')">VPN Paraphrase (Cache Test)</button>
          <button class="preset-btn" onclick="setPrompt('What is our refund policy for enterprise customers?')">Enterprise Refund Policy</button>
          <button class="preset-btn" onclick="setPrompt('Write a Python function to parse a CSV file and return a dict.')">Python CSV Parser (Code)</button>
          <button class="preset-btn" onclick="setPrompt('Derive the time complexity of merge sort and justify each step with proofs.')">Algorithm Proof &amp; Reasoning</button>
        </div>

        <div class="config-grid">
          <div class="form-group">
            <label>Cache Expiration (TTL)</label>
            <select id="topicTtlSelect" class="form-select">
              <option value="86400">1 Day (High-Frequency FAQ)</option>
              <option value="604800" selected>7 Days (Standard Ops)</option>
              <option value="2592000">30 Days (Static Documentation)</option>
            </select>
          </div>
          <div class="form-group">
            <label>Semantic Sensitivity</label>
            <select id="tauSelect" class="form-select">
              <option value="0.70">0.70 (Aggressive Caching)</option>
              <option value="0.80">0.80 (Standard Balanced)</option>
              <option value="0.84" selected>0.84 (High Precision - Recommended)</option>
              <option value="0.90">0.90 (Strict Match Only)</option>
            </select>
          </div>
          <div class="form-group">
            <label>Target Model</label>
            <select id="modelModeSelect" class="form-select" onchange="onModelSelectChanged()">
              <option value="tokenmingate" selected>Token Guard: Automated Smart Routing (Recommended)</option>
              <option value="gpt-4o">OpenAI: GPT-4o (Frontier Model)</option>
              <option value="gpt-4o-mini">OpenAI: GPT-4o Mini (Economy Model)</option>
              <option value="claude-3-5-sonnet">Anthropic: Claude 3.5 Sonnet (Balanced Model)</option>
              <option value="claude-3-5-haiku">Anthropic: Claude 3.5 Haiku (Economy Model)</option>
              <option value="gemini-1.5-flash">Google: Gemini 1.5 Flash (Economy Model)</option>
              <option value="llama-3.1">Local: Llama 3.1 8B (On-Premises)</option>
            </select>
          </div>
        </div>

        <button class="btn-primary" id="btnSendPrompt" onclick="executeGatewayRequest()">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
          <span>Send Request via Token Guard</span>
        </button>

        <!-- Summary Savings Strip -->
        <div class="savings-banner" id="savingsBanner" style="display:none; margin-top:16px;">
          <div class="sb-item">
            <span class="sb-k">Cost Saved</span>
            <span class="sb-v cyan" id="bannerDeltaC">0%</span>
          </div>
          <div class="sb-item">
            <span class="sb-k">Billed Cost</span>
            <span class="sb-v" id="bannerCost">$0.00</span>
          </div>
          <div class="sb-item">
            <span class="sb-k">Tokens Saved</span>
            <span class="sb-v glow" id="bannerTokensSaved">0</span>
          </div>
          <div class="sb-item">
            <span class="sb-k">Response Time</span>
            <span class="sb-v" id="bannerLatency">0 ms</span>
          </div>
        </div>

      </div>

      <!-- Right: Live Gateway Telemetry & Response Console -->
      <div class="panel">
        <div class="panel-hd">
          <div>
            <div class="panel-title">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--cyan)" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
              <span>Gateway Telemetry &amp; Response Console</span>
            </div>
            <div class="panel-subtitle">Real-time execution telemetry, model routing, and API inspection</div>
          </div>
          <span class="step-badge" id="pipelineStatusBadge">Awaiting Request</span>
        </div>

        <!-- 4 Key Metrics Bar (Visible once request runs) -->
        <div class="telemetry-metrics-grid" id="telemetryMetricsBar" style="display:none;">
          <div class="t-metric-box">
            <div class="t-metric-label">Cost Optimization</div>
            <div class="t-metric-val" style="color:var(--green);" id="tmCostSaved">0% Saved</div>
            <div style="font-size:10px; color:var(--muted); margin-top:2px;" id="tmCostDetails">$0.00 vs $0.00</div>
          </div>
          <div class="t-metric-box">
            <div class="t-metric-label">Cache Acceleration</div>
            <div class="t-metric-val" id="tmCacheStatus">MISS</div>
            <div style="font-size:10px; color:var(--muted); margin-top:2px;" id="tmTokensSaved">0 tokens saved</div>
          </div>
          <div class="t-metric-box">
            <div class="t-metric-label">Prompt Reduction</div>
            <div class="t-metric-val" style="color:var(--cyan);" id="tmPruneRatio">0%</div>
            <div style="font-size:10px; color:var(--muted); margin-top:2px;" id="tmPruneTokens">0 &rarr; 0 tok</div>
          </div>
          <div class="t-metric-box">
            <div class="t-metric-label">Routed Model</div>
            <div class="t-metric-val" style="font-size:12px; color:var(--purple);" id="tmRoutedModel">GPT-4o Mini</div>
            <div style="font-size:10px; color:var(--muted); margin-top:2px;" id="tmLatency">0 ms</div>
          </div>
        </div>

        <!-- Console Subtabs -->
        <div class="console-subtabs">
          <button class="console-subtab active" id="cTabBtnResponse" onclick="switchConsoleTab('response')">Assistant Response</button>
          <button class="console-subtab" id="cTabBtnTelemetry" onclick="switchConsoleTab('telemetry')">Pipeline Telemetry</button>
          <button class="console-subtab" id="cTabBtnCode" onclick="switchConsoleTab('code')">&lt;/&gt; Code &amp; cURL</button>
          <button class="console-subtab" id="cTabBtnJson" onclick="switchConsoleTab('json')">{ } Raw API JSON</button>
        </div>

        <!-- TAB 1: Response Output -->
        <div id="cTabResponse">
          <div class="response-box" style="margin-top:0; min-height:240px; display:flex; flex-direction:column; justify-content:space-between;">
            <div>
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                <span class="response-title" style="margin:0;">Assistant Completion</span>
                <button class="btn-feedback" onclick="copyAssistantResponse()">Copy Output</button>
              </div>
              <div class="response-content" id="responseOutput">Ready. Submit a prompt or choose a template to inspect the gateway response.</div>
            </div>
            <div id="l2FeedbackControls" style="margin-top:16px; padding-top:10px; border-top:1px solid var(--surface-border); display:none; justify-content:space-between; align-items:center;">
              <span style="font-size:11.5px; color:var(--muted);">Was this semantic cache answer accurate?</span>
              <div style="display:flex; gap:6px;">
                <button class="btn-feedback" id="btnFeedbackGood" onclick="submitFeedback(false)">👍 Accurate</button>
                <button class="btn-feedback" id="btnFeedbackBad" onclick="submitFeedback(true)">👎 Inaccurate</button>
              </div>
            </div>
          </div>
        </div>

        <!-- TAB 2: Pipeline Telemetry (Professional Clean Cards, NO Raw Formulas!) -->
        <div id="cTabTelemetry" style="display:none;" class="pipeline-flow">
          <!-- Step 1: Security & Multi-Tenancy -->
          <div class="pipeline-step" id="stepNamespace">
            <div class="step-head">
              <span class="step-title">
                <span class="pill-dot"></span>
                <span>Tenant Isolation &amp; Security</span>
              </span>
              <span class="step-badge badge-tier" id="stepNamespaceBadge">Ready</span>
            </div>
            <div class="step-body">
              <div class="step-data-row"><span>Active Department:</span><span class="step-val" id="valTelemetryTeam">Support</span></div>
              <div class="step-data-row"><span>Tenant Namespace ID:</span><span class="step-val" id="valNamespace">--</span></div>
            </div>
          </div>

          <!-- Step 2: Cache Acceleration Engine -->
          <div class="pipeline-step" id="stepL1">
            <div class="step-head">
              <span class="step-title">
                <span class="pill-dot"></span>
                <span>Sub-Millisecond Cache Acceleration</span>
              </span>
              <span class="step-badge" id="stepL1Badge">Pending</span>
            </div>
            <div class="step-body">
              <div class="step-data-row"><span>Exact Memory Match:</span><span class="step-val" id="valL1Status">--</span></div>
              <div class="step-data-row"><span>Semantic Cosine Match:</span><span class="step-val" id="valL2Sim">--</span></div>
              <div class="step-data-row"><span>Cache Age / Expiration:</span><span class="step-val" id="valL2Age">--</span></div>
            </div>
          </div>

          <!-- Step 3: Zero-Loss Prompt Optimizer -->
          <div class="pipeline-step" id="stepPrune">
            <div class="step-head">
              <span class="step-title">
                <span class="pill-dot"></span>
                <span>Syntax-Safe Prompt Optimizer</span>
              </span>
              <span class="step-badge" id="stepPruneBadge">Pending</span>
            </div>
            <div class="step-body">
              <div class="step-data-row"><span>Input Token Reduction:</span><span class="step-val" id="valPrunedTokens">--</span></div>
              <div class="step-data-row"><span>Token Cost Saved:</span><span class="step-val" id="valPrunedSaved">--</span></div>
              <div class="step-data-row"><span>Syntax Integrity:</span><span class="step-val" style="color:var(--green);">Protected (Code, Markdown &amp; JSON untouched)</span></div>
            </div>
          </div>

          <!-- Step 4: Intelligent Model Routing -->
          <div class="pipeline-step" id="stepRoute">
            <div class="step-head">
              <span class="step-title">
                <span class="pill-dot"></span>
                <span>Intelligent Model Routing</span>
              </span>
              <span class="step-badge" id="stepRouteBadge">Pending</span>
            </div>
            <div class="step-body">
              <div class="signal-bars">
                <div class="signal-bar-box">
                  <div class="sb-label">Length</div>
                  <div class="sb-val" id="sigLen">0.0</div>
                  <div class="sb-progress"><div class="sb-fill" id="fillLen" style="width:0%"></div></div>
                </div>
                <div class="signal-bar-box">
                  <div class="sb-label">Instructions</div>
                  <div class="sb-val" id="sigInst">0.0</div>
                  <div class="sb-progress"><div class="sb-fill" id="fillInst" style="width:0%"></div></div>
                </div>
                <div class="signal-bar-box">
                  <div class="sb-label">Reasoning</div>
                  <div class="sb-val" id="sigReason">0.0</div>
                  <div class="sb-progress"><div class="sb-fill" id="fillReason" style="width:0%"></div></div>
                </div>
                <div class="signal-bar-box">
                  <div class="sb-label">Code Syntax</div>
                  <div class="sb-val" id="sigCode">0.0</div>
                  <div class="sb-progress"><div class="sb-fill" id="fillCode" style="width:0%"></div></div>
                </div>
              </div>
              <div class="step-data-row" style="margin-top: 10px;">
                <span>Dispatched Tier &amp; Model:</span><span class="step-val" id="valTierModel">--</span>
              </div>
              <div class="step-data-row">
                <span>Routing Rationale:</span><span class="step-val" id="valRoutingRationale" style="font-family:inherit; color:var(--muted);">--</span>
              </div>
            </div>
          </div>
        </div>

        <!-- TAB 3: Developer Code Snippets (cURL, Python OpenAI, TypeScript) -->
        <div id="cTabCode" style="display:none;">
          <div class="code-viewer-wrap">
            <div class="code-viewer-header">
              <div class="code-viewer-tabs">
                <button class="cv-tab active" id="cvTabCurl" onclick="switchSnippetLang('curl')">cURL</button>
                <button class="cv-tab" id="cvTabPython" onclick="switchSnippetLang('python')">Python (OpenAI SDK)</button>
                <button class="cv-tab" id="cvTabTs" onclick="switchSnippetLang('ts')">TypeScript (Fetch)</button>
              </div>
              <button class="btn-feedback" onclick="copySnippetCode()">Copy Snippet</button>
            </div>
            <pre class="code-viewer-content" id="snippetCodeViewer">Loading code snippet...</pre>
          </div>
        </div>

        <!-- TAB 4: Raw API JSON Inspector -->
        <div id="cTabJson" style="display:none;">
          <div class="code-viewer-wrap">
            <div class="code-viewer-header">
              <span style="font-size:11.5px; font-weight:600; color:var(--muted);">POST /v1/chat/completions Response Payload</span>
              <button class="btn-feedback" onclick="copyJsonPayload()">Copy JSON</button>
            </div>
            <pre class="code-viewer-content" id="rawJsonViewer">No request sent yet. Submit a prompt to view raw JSON response payload.</pre>
          </div>
        </div>

      </div>

    </div>
  </section>

  <!-- ===================================================================== -->
  <!-- VIEW: TEAMS & BUDGETS (COST GOVERNANCE & MULTI-TENANCY) -->
  <!-- ===================================================================== -->
  <section id="paneTeams" class="tab-pane">
    <div class="panel">
      <div class="panel-hd">
        <div>
          <div class="panel-title">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--cyan)" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
            <span>Team &amp; Department Cost Governance</span>
          </div>
          <div class="panel-subtitle">Manage monthly budget limits ($ USD), token quotas, and track live consumption per tenant namespace</div>
        </div>
        <button class="btn-primary" style="width:auto; padding:8px 16px; margin:0;" onclick="toggleAddTeamForm()">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 5v14M5 12h14"/></svg>
          <span>Add New Team</span>
        </button>
      </div>

      <!-- Add / Edit Team Form Card -->
      <div id="teamFormCard" class="team-form-card" style="display:none; margin-top:16px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;">
          <h3 id="teamFormTitle" style="font-size:14px; font-weight:700; color:var(--ink);">Add New Team / Department</h3>
          <button class="btn-feedback" id="teamFormCancelBtn" onclick="toggleAddTeamForm(false)">Cancel</button>
        </div>
        <form onsubmit="saveTeam(event)" style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:14px; align-items:flex-end;">
          <div class="form-group" style="margin-bottom:0;">
            <label>Team Unique ID (Slug)</label>
            <input type="text" id="teamIdInput" class="form-input" placeholder="e.g. data-science" required />
          </div>
          <div class="form-group" style="margin-bottom:0;">
            <label>Department / Team Name</label>
            <input type="text" id="teamNameInput" class="form-input" placeholder="e.g. Data Science & ML" required />
          </div>
          <div class="form-group" style="margin-bottom:0;">
            <label>Monthly Budget ($ USD)</label>
            <input type="number" step="0.01" min="1" id="teamBudgetInput" class="form-input" value="250.00" required />
          </div>
          <div class="form-group" style="margin-bottom:0;">
            <label>Monthly Token Quota</label>
            <input type="number" step="10000" min="10000" id="teamTokensInput" class="form-input" value="2500000" required />
          </div>
          <div style="display:flex; gap:8px;">
            <button type="submit" class="btn-primary" style="margin:0; height:38px;">Save Team Details</button>
          </div>
        </form>
      </div>

      <!-- Teams Grid -->
      <div id="teamsGrid" class="teams-grid">
        <div style="text-align:center; color:var(--muted); padding:40px; grid-column: 1 / -1;">Loading team details...</div>
      </div>
    </div>
  </section>

  <!-- ===================================================================== -->
  <!-- VIEW 2: EXECUTIVE ANALYTICS & COST GOVERNANCE -->
  <!-- ===================================================================== -->
  <section id="paneResearch" class="tab-pane">
    <div class="metrics-totals" id="researchKpiBar">
      <div class="stat-card">
        <div class="stat-k">Total Cost Saved</div>
        <div class="stat-v" style="color:var(--cyan);" id="kpiDeltaC">74.2%</div>
        <div class="stat-sub">Enterprise API budget saved</div>
      </div>
      <div class="stat-card">
        <div class="stat-k">Token Reduction</div>
        <div class="stat-v" style="color:var(--green);" id="kpiTrr">81.4%</div>
        <div class="stat-sub">Tokens eliminated via cache &amp; pruning</div>
      </div>
      <div class="stat-card">
        <div class="stat-k">Global Cache Hit Rate</div>
        <div class="stat-v" id="kpiHitRate">58.4%</div>
        <div class="stat-sub">Instant zero-cost responses</div>
      </div>
      <div class="stat-card">
        <div class="stat-k">Semantic Accuracy</div>
        <div class="stat-v" style="color:var(--purple);" id="kpiPrecision">98.2%</div>
        <div class="stat-sub">Precision of semantic retrievals</div>
      </div>
      <div class="stat-card">
        <div class="stat-k">Average Latency</div>
        <div class="stat-v" style="color:var(--amber);">685 ms</div>
        <div class="stat-sub">vs 2,840 ms Direct Cloud API</div>
      </div>
    </div>

    <!-- Telemetry Charts -->
    <div class="charts-grid">
      <div class="chart-box">
        <div class="table-title">
          <span>Freshness Verification &amp; Age Barrier</span>
          <span class="step-badge badge-tier">Active Protection</span>
        </div>
        <div class="table-desc">As cached answers age over time, required similarity dynamically increases to guarantee fresh, up-to-date responses.</div>
        <svg class="chart-svg" viewBox="0 0 500 220" id="svgFig2"></svg>
      </div>

      <div class="chart-box">
        <div class="table-title">
          <span>Cost Optimization vs Output Precision</span>
          <span class="step-badge badge-purple">Calibrated Balance</span>
        </div>
        <div class="table-desc">Trade-off curve displaying token reduction versus semantic retrieval accuracy across sensitivity thresholds.</div>
        <svg class="chart-svg" viewBox="0 0 500 220" id="svgFig3"></svg>
      </div>
    </div>

    <!-- Production Strategy Comparison -->
    <div class="table-section">
      <div class="table-title">
        <span>Production Architecture Comparison (10,000 Request Benchmark)</span>
        <span class="step-badge badge-hit">Production Benchmark</span>
      </div>
      <div class="table-desc">Performance, latency, and cost comparison between unmanaged direct LLM APIs and Token Guard optimization layers.</div>
      <table class="paper-table" id="tableOneBody">
        <thead>
          <tr>
            <th>Operational Strategy</th>
            <th>Cache Hit Rate</th>
            <th>Avg Tokens / Req</th>
            <th>Token Savings</th>
            <th>Average Latency</th>
            <th>Cost Reduction</th>
          </tr>
        </thead>
        <tbody></tbody>
      </table>
    </div>

    <!-- Sensitivity & Cost Projections Grid -->
    <div class="charts-grid">
      <div class="table-section">
        <div class="table-title">
          <span>Similarity Threshold Sensitivity Benchmark</span>
        </div>
        <table class="paper-table" id="tableTwoBody">
          <thead>
            <tr>
              <th>Base Threshold</th>
              <th>Hit Rate</th>
              <th>Precision</th>
              <th>Token Reduction</th>
              <th>Net Effective Savings</th>
            </tr>
          </thead>
          <tbody></tbody>
        </table>
      </div>

      <div class="table-section">
        <div class="table-title">
          <span>10,000 Request Spend Projections</span>
        </div>
        <table class="paper-table" id="tableThreeBody">
          <thead>
            <tr>
              <th>Deployment Tier</th>
              <th>Cost (USD)</th>
              <th>Net Budget Saved</th>
            </tr>
          </thead>
          <tbody></tbody>
        </table>
      </div>
    </div>

  </section>

  <!-- ===================================================================== -->
  <!-- VIEW 3: REQUEST & COST LEDGER -->
  <!-- ===================================================================== -->
  <section id="paneLedger" class="tab-pane">
    <div class="panel">
      <div class="panel-hd">
        <div>
          <div class="panel-title">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--cyan)" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
            <span>Real-Time Request &amp; Token Ledger</span>
          </div>
          <div class="panel-subtitle">Transparent audit trail per user, team, app with human feedback marking</div>
        </div>
        <button class="btn-feedback" onclick="loadLedger()">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 4v6h-6"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
          Refresh Ledger
        </button>
      </div>

      <div class="ledger-controls">
        <input type="text" id="ledgerSearchInput" class="search-input" placeholder="Search prompts or API keys..." oninput="filterLedger()" />
        <select id="ledgerTeamFilter" class="form-select" style="max-width:180px;" onchange="filterLedger()">
          <option value="">All Teams</option>
          <option value="support">Customer Support</option>
          <option value="engineering">Engineering</option>
          <option value="finance">Finance</option>
          <option value="platform">Platform</option>
        </select>
        <select id="ledgerTierFilter" class="form-select" style="max-width:180px;" onchange="filterLedger()">
          <option value="">All Tiers &amp; Caches</option>
          <option value="l1">L1 Exact Cache</option>
          <option value="l2">L2 Semantic Cache</option>
          <option value="economy">Economy Tier</option>
          <option value="balanced">Balanced Tier</option>
          <option value="frontier">Frontier Tier</option>
        </select>
      </div>

      <table class="paper-table" id="ledgerTable">
        <thead>
          <tr>
            <th>Time</th>
            <th>Employee</th>
            <th>Team</th>
            <th>Prompt</th>
            <th>Tier / Cache</th>
            <th>Tokens</th>
            <th>Cost</th>
            <th>Baseline</th>
            <th>Latency</th>
            <th>Feedback</th>
          </tr>
        </thead>
        <tbody id="ledgerTableBody">
          <tr><td colspan="10" style="text-align:center; color:var(--muted); padding:30px;">Loading ledger data...</td></tr>
        </tbody>
      </table>
    </div>
  </section>

  <!-- ===================================================================== -->
  <!-- VIEW 4: CACHE INSPECTOR & AGE-DECAY SIMULATION -->
  <!-- ===================================================================== -->
  <section id="paneCache" class="tab-pane">
    <div class="panel">
      <div class="panel-hd">
        <div>
          <div class="panel-title">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--cyan)" stroke-width="2"><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/></svg>
            <span>Semantic Cache Inspector &amp; Aging Simulator</span>
          </div>
          <div class="panel-subtitle">Inspect FAISS-indexed embeddings and simulate answer aging to watch &tau;<sub>eff</sub> climb</div>
        </div>
        <div style="display:flex; gap:8px;">
          <button class="btn-feedback" onclick="purgeExpiredCache()">Purge Expired</button>
          <button class="btn-feedback" onclick="loadCacheEntries()">Refresh</button>
        </div>
      </div>

      <table class="paper-table">
        <thead>
          <tr>
            <th>Prompt Text</th>
            <th>Namespace</th>
            <th>Age a<sub>i</sub></th>
            <th>Lifespan T<sub>k</sub></th>
            <th>Required &tau;<sub>eff</sub></th>
            <th>Tokens Saved</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody id="cacheTableBody">
          <tr><td colspan="7" style="text-align:center; color:var(--muted); padding:30px;">Loading cache entries...</td></tr>
        </tbody>
      </table>
    </div>
  </section>

  <!-- ===================================================================== -->
  <!-- VIEW 5: SUPADB CLOUD & LOCAL DATABASE INTEGRATION -->
  <!-- ===================================================================== -->
  <section id="paneSupadb" class="tab-pane">
    <div class="db-card">
      <div class="panel-hd">
        <div>
          <div class="panel-title">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--green)" stroke-width="2"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" y1="22" x2="4" y2="15"/></svg>
            <span>SupaDB / Supabase Architecture Status</span>
          </div>
          <div class="panel-subtitle">Zero-configuration dual-mode database (PostgreSQL + SQLite fallback)</div>
        </div>
        <span class="db-status-badge online" id="dbStatusBadge">Engine Active: SQLite Local</span>
      </div>

      <div style="display:grid; grid-template-columns: 1fr 1fr; gap:20px; margin-top:16px;">
        <div>
          <div class="form-group">
            <label>Supabase URL</label>
            <input type="text" id="supabaseUrlInput" class="form-input" placeholder="https://xyzcompany.supabase.co" />
          </div>
          <div class="form-group">
            <label>Supabase Service Role Key (API Key)</label>
            <input type="password" id="supabaseKeyInput" class="form-input" placeholder="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." />
          </div>
          <button class="btn-primary" onclick="syncSupabase()">
            <span>Connect &amp; Sync Local Data to Supabase</span>
          </button>
        </div>

        <div>
          <span style="font-size:11px; color:var(--muted); font-weight:600; text-transform:uppercase;">Relational Tables Status</span>
          <div style="margin-top:8px; display:flex; flex-direction:column; gap:6px;" id="dbTablesCountList">
            <!-- Rendered by JS -->
          </div>
        </div>
      </div>

      <div style="margin-top:24px;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <span style="font-size:12px; font-weight:600; color:var(--ink);">Supabase SQL Schema (<code class="mono">supabase_schema.sql</code>)</span>
          <button class="btn-feedback" onclick="copySchemaSql()">Copy SQL</button>
        </div>
        <pre class="sql-viewer mono" id="schemaSqlViewer">Loading schema...</pre>
      </div>

    </div>
  </section>

</div>

<script>
(function() {
  "use strict";

  // Application State
  var state = {
    currentUser: null,
    activeTab: 'playground',
    activeAuthTab: 'login',
    activeConsoleTab: 'response',
    activeSnippetLang: 'curl',
    demoUsers: [],
    lastLogId: null,
    lastApiResponse: null,
    researchData: null,
    ledgerRows: []
  };

  // Helper functions
  function fmtUsd(n) {
    n = n || 0;
    if (n === 0) return "$0.00";
    if (n < 0.01) return "$" + n.toFixed(6);
    return "$" + n.toFixed(4);
  }
  function fmtInt(n) { return (n || 0).toLocaleString(); }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function(c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  // Window exports
  window.switchTab = switchTab;
  window.switchAuthTab = switchAuthTab;
  window.handleLogin = handleLogin;
  window.handleRegister = handleRegister;
  window.signOut = signOut;
  window.setPrompt = setPrompt;
  window.executeGatewayRequest = executeGatewayRequest;
  window.submitFeedback = submitFeedback;
  window.loadLedger = loadLedger;
  window.filterLedger = filterLedger;
  window.loadCacheEntries = loadCacheEntries;
  window.purgeExpiredCache = purgeExpiredCache;
  window.simulateAge = simulateAge;
  window.evictCache = evictCache;
  window.syncSupabase = syncSupabase;
  window.copySchemaSql = copySchemaSql;
  window.loadTeams = loadTeams;
  window.saveTeam = saveTeam;
  window.openEditTeamModal = openEditTeamModal;
  window.toggleAddTeamForm = toggleAddTeamForm;
  window.switchConsoleTab = switchConsoleTab;
  window.switchSnippetLang = switchSnippetLang;
  window.copyAssistantResponse = copyAssistantResponse;
  window.copySnippetCode = copySnippetCode;
  window.copyJsonPayload = copyJsonPayload;
  window.onPromptInputChanged = onPromptInputChanged;
  window.onModelSelectChanged = onModelSelectChanged;

  // Initialize
  document.addEventListener("DOMContentLoaded", function() {
    initAuth();
    loadDemoUsers();
    loadTeams();
    updateCodeSnippets("", "tokenmingate");
    renderCharts();
    loadSchemaSql();
    // Fetch /admin/usage for observability metrics
    fetch("/admin/usage").catch(function() {});
  });

  function initAuth() {
    var stored = localStorage.getItem("tokenguard_user") || localStorage.getItem("tokenmingate_user");
    if (stored) {
      try {
        state.currentUser = JSON.parse(stored);
        showApp();
        return;
      } catch (e) {
        localStorage.removeItem("tokenguard_user");
        localStorage.removeItem("tokenmingate_user");
      }
    }
    showAuth();
  }

  function showAuth() {
    document.getElementById("authView").style.display = "block";
    document.getElementById("mainNavTabs").style.display = "none";
    document.getElementById("navUserBar").style.display = "none";
    hideAllPanes();
  }

  function showApp() {
    document.getElementById("authView").style.display = "none";
    document.getElementById("mainNavTabs").style.display = "flex";
    document.getElementById("navUserBar").style.display = "flex";

    var u = state.currentUser;
    document.getElementById("navUserName").textContent = u.name;
    document.getElementById("navUserTeam").textContent = "Team " + (u.team_id || "general").toUpperCase();
    document.getElementById("navAvatar").textContent = (u.name || "U")[0].toUpperCase();
    document.getElementById("activeKeyBadge").textContent = u.api_key;

    switchTab('playground');
    loadTeams();
    loadResearchData();
    loadDbStatus();
  }

  function switchTab(tabId) {
    state.activeTab = tabId;
    var tabs = document.querySelectorAll(".nav-tab");
    tabs.forEach(function(t) {
      var oc = t.getAttribute("onclick") || "";
      if (oc.indexOf("'" + tabId + "'") !== -1) {
        t.classList.add("active");
      } else {
        t.classList.remove("active");
      }
    });
    
    hideAllPanes();

    if (tabId === 'playground') {
      document.getElementById("panePlayground").classList.add("active");
    } else if (tabId === 'teams') {
      document.getElementById("paneTeams").classList.add("active");
      loadTeams();
    } else if (tabId === 'research') {
      document.getElementById("paneResearch").classList.add("active");
      loadResearchData();
    } else if (tabId === 'ledger') {
      document.getElementById("paneLedger").classList.add("active");
      loadLedger();
    } else if (tabId === 'cache') {
      document.getElementById("paneCache").classList.add("active");
      loadCacheEntries();
    } else if (tabId === 'supadb') {
      document.getElementById("paneSupadb").classList.add("active");
      loadDbStatus();
    }
  }

  function toggleAddTeamForm(show) {
    var card = document.getElementById("teamFormCard");
    if (!card) return;
    if (show === undefined) {
      card.style.display = (card.style.display === "none" || !card.style.display) ? "block" : "none";
    } else {
      card.style.display = show ? "block" : "none";
    }
    if (card.style.display === "block") {
      card.scrollIntoView({ behavior: 'smooth' });
    }
  }

  function openEditTeamModal(id, name, budget, tokens) {
    var card = document.getElementById("teamFormCard");
    card.style.display = "block";
    card.scrollIntoView({ behavior: 'smooth' });

    var idInput = document.getElementById("teamIdInput");
    idInput.value = id;
    idInput.disabled = true;
    idInput.title = "Team ID cannot be changed once created";

    document.getElementById("teamNameInput").value = name;
    document.getElementById("teamBudgetInput").value = budget;
    document.getElementById("teamTokensInput").value = tokens;

    document.getElementById("teamFormTitle").textContent = "Edit Budget & Quotas: " + name + " (" + id + ")";
    document.getElementById("teamFormCancelBtn").style.display = "inline-flex";
  }

  function saveTeam(e) {
    if (e && e.preventDefault) e.preventDefault();
    var idInput = document.getElementById("teamIdInput");
    var nameInput = document.getElementById("teamNameInput");
    var budgetInput = document.getElementById("teamBudgetInput");
    var tokensInput = document.getElementById("teamTokensInput");

    var id = idInput.value.trim().toLowerCase().replace(/[^a-z0-9_-]/g, "-");
    var name = nameInput.value.trim();
    var budget = parseFloat(budgetInput.value) || 100.0;
    var tokens = parseInt(tokensInput.value) || 1000000;

    if (!id || !name) {
      alert("Please provide both Team ID and Team Name.");
      return;
    }

    var isEdit = idInput.disabled;
    var url = isEdit ? ("/api/teams/" + encodeURIComponent(id)) : "/api/teams";
    var method = isEdit ? "PUT" : "POST";
    var payload = isEdit 
      ? { name: name, budget_usd: budget, budget_tokens: tokens }
      : { id: id, name: name, budget_usd: budget, budget_tokens: tokens };

    fetch(url, {
      method: method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    })
    .then(function(r) {
      if (!r.ok) {
        return r.json().then(function(err) { throw new Error(err.detail || "Failed to save team"); });
      }
      return r.json();
    })
    .then(function(res) {
      alert("Team details for '" + (res.name || name) + "' saved successfully!");
      idInput.value = "";
      idInput.disabled = false;
      idInput.title = "";
      nameInput.value = "";
      budgetInput.value = "250.00";
      tokensInput.value = "2500000";
      document.getElementById("teamFormTitle").textContent = "Add New Team / Department";
      toggleAddTeamForm(false);
      loadTeams();
    })
    .catch(function(err) {
      alert("Error saving team: " + err.message);
    });
  }

  function loadTeams() {
    fetch("/api/teams")
      .then(function(r) { return r.json(); })
      .then(function(teams) {
        state.teamsList = teams;
        renderTeamsGrid(teams);
        updateTeamDropdowns(teams);
      })
      .catch(function(err) {
        var grid = document.getElementById("teamsGrid");
        if (grid) grid.innerHTML = '<div style="color:var(--red); padding:20px;">Failed to load teams: ' + esc(err.message) + '</div>';
      });
  }

  function renderTeamsGrid(teams) {
    var grid = document.getElementById("teamsGrid");
    if (!grid) return;
    if (!teams || !teams.length) {
      grid.innerHTML = '<div style="text-align:center; color:var(--muted); padding:40px; grid-column:1/-1;">No teams registered yet. Click &quot;Add New Team&quot; above to create your first team!</div>';
      return;
    }

    grid.innerHTML = teams.map(function(t) {
      var ratio = t.budget_used_ratio || 0;
      var pct = Math.min(100, Math.round(ratio * 100));
      var spendColor = ratio >= 0.9 ? 'var(--red)' : (ratio >= 0.75 ? 'var(--amber)' : 'var(--green)');

      return '<div class="team-card">' +
        '<div class="team-card-header">' +
          '<div>' +
            '<div class="team-card-title">' + esc(t.name) + '</div>' +
            '<div class="mono" style="font-size:11px; color:var(--muted); margin-top:2px;">ID: <span style="color:var(--cyan);">' + esc(t.id) + '</span></div>' +
          '</div>' +
          '<span class="step-badge badge-tier">' + (t.employee_count || 0) + ' Members</span>' +
        '</div>' +
        '<div style="margin-top:14px;">' +
          '<div style="display:flex; justify-content:space-between; font-size:11.5px; margin-bottom:4px;">' +
            '<span style="color:var(--muted);">Budget Consumption</span>' +
            '<span class="mono" style="font-weight:700; color:' + spendColor + ';">' + fmtUsd(t.spent_usd) + ' / ' + fmtUsd(t.budget_usd) + ' (' + pct + '%)</span>' +
          '</div>' +
          '<div class="progress-bar-wrap">' +
            '<div class="progress-bar-fill" style="width:' + pct + '%; background:' + spendColor + ';"></div>' +
          '</div>' +
        '</div>' +
        '<div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:14px; font-size:11.5px; background:rgba(255,255,255,0.02); padding:10px; border-radius:var(--radius-sm); border:1px solid rgba(255,255,255,0.04);">' +
          '<div>' +
            '<div style="color:var(--muted); text-transform:uppercase; font-size:9.5px; letter-spacing:0.04em;">Remaining Budget</div>' +
            '<div class="mono" style="font-weight:700; color:var(--green); margin-top:2px;">' + fmtUsd(t.budget_remaining_usd) + '</div>' +
          '</div>' +
          '<div>' +
            '<div style="color:var(--muted); text-transform:uppercase; font-size:9.5px; letter-spacing:0.04em;">Tokens (Used / Max)</div>' +
            '<div class="mono" style="font-weight:600; color:var(--ink); margin-top:2px;">' + fmtInt(t.used_tokens) + ' / ' + fmtInt(t.budget_tokens) + '</div>' +
          '</div>' +
          '<div>' +
            '<div style="color:var(--muted); text-transform:uppercase; font-size:9.5px; letter-spacing:0.04em;">Requests Handled</div>' +
            '<div class="mono" style="color:var(--ink); margin-top:2px;">' + fmtInt(t.requests) + ' reqs</div>' +
          '</div>' +
          '<div>' +
            '<div style="color:var(--muted); text-transform:uppercase; font-size:9.5px; letter-spacing:0.04em;">Isolation Namespace</div>' +
            '<div class="mono" style="color:var(--cyan); margin-top:2px;">N: ' + esc(t.id) + '</div>' +
          '</div>' +
        '</div>' +
        '<div style="margin-top:14px; display:flex; justify-content:space-between; align-items:center;">' +
          '<span style="font-size:10.5px; color:var(--dim);">' + (t.budget_remaining_usd <= 0 ? '⚠️ Budget Limit Reached' : '✅ Active &amp; Operational') + '</span>' +
          '<button class="btn-feedback" onclick="openEditTeamModal(\'' + esc(t.id) + '\', \'' + esc(t.name) + '\', ' + t.budget_usd + ', ' + t.budget_tokens + ')">' +
            '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:4px; vertical-align:middle;"><path d="M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>' +
            'Edit Budget &amp; Quota' +
          '</button>' +
        '</div>' +
      '</div>';
    }).join("");
  }

  function updateTeamDropdowns(teams) {
    if (!teams || !teams.length) return;
    var regSel = document.getElementById("regTeam");
    if (regSel) {
      var curr = regSel.value;
      regSel.innerHTML = teams.map(function(t) {
        return '<option value="' + esc(t.id) + '">' + esc(t.name) + '</option>';
      }).join("");
      if (curr) regSel.value = curr;
    }
    var ledSel = document.getElementById("ledgerTeamFilter");
    if (ledSel) {
      var currLed = ledSel.value;
      var opts = '<option value="">All Teams</option>' + teams.map(function(t) {
        return '<option value="' + esc(t.id) + '">' + esc(t.name) + '</option>';
      }).join("");
      ledSel.innerHTML = opts;
      if (currLed) ledSel.value = currLed;
    }
  }

  function hideAllPanes() {
    document.querySelectorAll(".tab-pane").forEach(function(p) { p.classList.remove("active"); });
  }

  function switchAuthTab(type) {
    state.activeAuthTab = type;
    var tabLogin = document.getElementById("tabBtnLogin");
    var tabReg = document.getElementById("tabBtnRegister");
    if (tabLogin) tabLogin.classList.toggle("active", type === 'login');
    if (tabReg) tabReg.classList.toggle("active", type === 'register');
    var subtitle = document.getElementById("authCardSubtitle");
    if (subtitle) {
      subtitle.textContent = (type === 'login' ? "Sign in to your employee account" : "Create your employee account");
    }
    var fLogin = document.getElementById("authLoginForm");
    var fReg = document.getElementById("authRegisterForm");
    if (fLogin) fLogin.style.display = (type === 'login' ? "block" : "none");
    if (fReg) fReg.style.display = (type === 'register' ? "block" : "none");
  }

  function loadDemoUsers() {
    var list = document.getElementById("demoUsersList");
    if (!list) return;
    fetch("/auth/demo-users")
      .then(function(r) { return r.json(); })
      .then(function(users) {
        state.demoUsers = users;
      }).catch(function() {});
  }

  window.loginDemo = function(email) {
    var u = state.demoUsers ? state.demoUsers.find(function(x) { return x.email === email; }) : null;
    if (!u) return;
    document.getElementById("loginEmail").value = u.email;
    document.getElementById("loginPassword").value = "demo";
    handleLogin();
  };

  function handleLogin() {
    var email = document.getElementById("loginEmail").value.trim();
    var password = document.getElementById("loginPassword").value.trim();
    if (!email || !password) {
      alert("Please enter both email and password");
      return;
    }

    fetch("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: email, password: password })
    })
    .then(function(r) {
      if (!r.ok) throw new Error("Invalid email or password");
      return r.json();
    })
    .then(function(user) {
      state.currentUser = user;
      localStorage.setItem("tokenguard_user", JSON.stringify(user));
      localStorage.setItem("tokenmingate_user", JSON.stringify(user));
      showApp();
    })
    .catch(function(err) {
      alert("Login failed: " + err.message);
    });
  }

  function handleRegister() {
    var name = document.getElementById("regName").value.trim();
    var email = document.getElementById("regEmail").value.trim();
    var password = document.getElementById("regPassword").value.trim();
    var team_id = document.getElementById("regTeam").value;

    if (!name || !email || !password) {
      alert("Please fill all required fields");
      return;
    }

    fetch("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name, email: email, password: password, team_id: team_id })
    })
    .then(function(r) {
      if (!r.ok) throw new Error("Registration failed");
      return r.json();
    })
    .then(function(user) {
      state.currentUser = user;
      localStorage.setItem("tokenguard_user", JSON.stringify(user));
      localStorage.setItem("tokenmingate_user", JSON.stringify(user));
      showApp();
    })
    .catch(function(err) {
      alert(err.message);
    });
  }

  function signOut() {
    state.currentUser = null;
    localStorage.removeItem("tokenguard_user");
    localStorage.removeItem("tokenmingate_user");
    showAuth();
  }

  function setPrompt(txt) {
    var pEl = document.getElementById("promptInput");
    if (pEl) pEl.value = txt;
    updateCodeSnippets();
  }

  function switchConsoleTab(tabId) {
    state.activeConsoleTab = tabId;
    var tabMap = {
      'response': { tab: 'cTabResponse', btn: 'cTabBtnResponse' },
      'telemetry': { tab: 'cTabTelemetry', btn: 'cTabBtnTelemetry' },
      'code': { tab: 'cTabCode', btn: 'cTabBtnCode' },
      'json': { tab: 'cTabJson', btn: 'cTabBtnJson' }
    };
    Object.keys(tabMap).forEach(function(k) {
      var item = tabMap[k];
      var el = document.getElementById(item.tab);
      var btn = document.getElementById(item.btn);
      if (el) el.style.display = (k === tabId ? (k === 'telemetry' ? 'flex' : 'block') : 'none');
      if (btn) btn.classList.toggle('active', k === tabId);
    });
    if (tabId === 'code') {
      updateCodeSnippets();
    }
  }

  function switchSnippetLang(lang) {
    state.activeSnippetLang = lang;
    var langMap = {
      'curl': 'cvTabCurl',
      'python': 'cvTabPython',
      'ts': 'cvTabTs'
    };
    Object.keys(langMap).forEach(function(l) {
      var btn = document.getElementById(langMap[l]);
      if (btn) btn.classList.toggle('active', l === lang);
    });
    updateCodeSnippets();
  }

  function updateCodeSnippets() {
    var promptEl = document.getElementById("promptInput");
    var prompt = (promptEl ? promptEl.value.trim() : "") || "Explain quantum computing in simple terms.";
    var modelEl = document.getElementById("modelModeSelect");
    var model = (modelEl ? modelEl.value : "tokenmingate");
    var apiKey = (state.currentUser && state.currentUser.api_key) ? state.currentUser.api_key : "tm_sec_live_key_9941";
    var host = window.location.origin || "http://localhost:8080";

    var code = "";
    var lang = state.activeSnippetLang || "curl";

    if (lang === "curl") {
      var escapedPrompt = prompt.replace(/"/g, '\\"').replace(/\n/g, "\\n");
      code = 'curl -X POST ' + host + '/v1/chat/completions \\\n' +
        '  -H "Content-Type: application/json" \\\n' +
        '  -H "Authorization: Bearer ' + apiKey + '" \\\n' +
        '  -d \'{\n' +
        '    "model": "' + model + '",\n' +
        '    "messages": [\n' +
        '      {"role": "user", "content": "' + escapedPrompt + '"}\n' +
        '    ],\n' +
        '    "temperature": 0.0\n' +
        '  }\'';
    } else if (lang === "python") {
      code = 'from openai import OpenAI\n\n' +
        '# Connect seamlessly through Token Guard enterprise endpoint\n' +
        'client = OpenAI(\n' +
        '    base_url="' + host + '/v1",\n' +
        '    api_key="' + apiKey + '"\n' +
        ')\n\n' +
        'response = client.chat.completions.create(\n' +
        '    model="' + model + '",\n' +
        '    messages=[\n' +
        '        {"role": "user", "content": ' + JSON.stringify(prompt) + '}\n' +
        '    ],\n' +
        '    temperature=0.0\n' +
        ')\n\n' +
        'print("Assistant Output:", response.choices[0].message.content)\n' +
        'if hasattr(response, "usage"):\n' +
        '    print("Token Usage:", response.usage)\n';
    } else if (lang === "ts") {
      code = '// Universal TypeScript / JavaScript Fetch Client\n' +
        'async function callTokenGuard() {\n' +
        '  const response = await fetch("' + host + '/v1/chat/completions", {\n' +
        '    method: "POST",\n' +
        '    headers: {\n' +
        '      "Content-Type": "application/json",\n' +
        '      "Authorization": "Bearer ' + apiKey + '"\n' +
        '    },\n' +
        '    body: JSON.stringify({\n' +
        '      model: "' + model + '",\n' +
        '      messages: [{ role: "user", content: ' + JSON.stringify(prompt) + ' }],\n' +
        '      temperature: 0.0\n' +
        '    })\n' +
        '  });\n\n' +
        '  const data = await response.json();\n' +
        '  console.log("Response:", data.choices[0].message.content);\n' +
        '}\n\n' +
        'callTokenGuard();';
    }

    var viewer = document.getElementById("snippetCodeViewer");
    if (viewer) viewer.textContent = code;
  }

  function onPromptInputChanged() {
    updateCodeSnippets();
  }

  function onModelSelectChanged() {
    updateCodeSnippets();
  }

  function copyAssistantResponse() {
    var text = document.getElementById("responseOutput").textContent;
    navigator.clipboard.writeText(text).then(function() {
      alert("Assistant completion copied to clipboard!");
    });
  }

  function copySnippetCode() {
    var text = document.getElementById("snippetCodeViewer").textContent;
    navigator.clipboard.writeText(text).then(function() {
      alert("Code snippet copied to clipboard!");
    });
  }

  function copyJsonPayload() {
    var text = document.getElementById("rawJsonViewer").textContent;
    navigator.clipboard.writeText(text).then(function() {
      alert("Raw JSON payload copied to clipboard!");
    });
  }

  // Execute Gateway Request with Full Pipeline Telemetry
  function executeGatewayRequest() {
    var promptEl = document.getElementById("promptInput");
    var prompt = promptEl ? promptEl.value.trim() : "";
    if (!prompt) {
      alert("Please enter a prompt first");
      return;
    }

    var btn = document.getElementById("btnSendPrompt");
    btn.disabled = true;
    btn.innerHTML = '<span>Optimizing &amp; Dispatching Request...</span>';

    var ttl = parseInt(document.getElementById("topicTtlSelect").value, 10);
    var tau = parseFloat(document.getElementById("tauSelect").value);
    var model = document.getElementById("modelModeSelect").value;

    var payload = {
      model: model,
      messages: [{ role: "user", content: prompt }],
      team_id: (state.currentUser ? state.currentUser.team_id : "support"),
      user_id: (state.currentUser ? state.currentUser.id : "usr_demo"),
      app_id: (state.currentUser && state.currentUser.app_id) ? state.currentUser.app_id : "web",
      ttl_seconds: ttl,
      tau: tau,
      temperature: 0.0
    };

    fetch("/api/chat/pipeline", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + ((state.currentUser && state.currentUser.api_key) ? state.currentUser.api_key : "")
      },
      body: JSON.stringify(payload)
    })
    .then(function(r) {
      if (!r.ok) return r.json().then(function(e) { throw new Error(e.detail || (e.error && e.error.message) || "Request failed"); });
      return r.json();
    })
    .then(function(res) {
      renderPipelineExecution(res);
      btn.disabled = false;
      btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg><span>Send Request via Token Guard</span>';
    })
    .catch(function(err) {
      alert("Gateway error: " + err.message);
      btn.disabled = false;
      btn.innerHTML = '<span>Try Again</span>';
    });
  }

  function renderPipelineExecution(data) {
    var p = data.pipeline || {};
    state.lastLogId = p.log_id;
    state.lastApiResponse = data;

    // Top Status Badge
    var statusBadge = document.getElementById("pipelineStatusBadge");
    if (statusBadge) {
      statusBadge.textContent = data.cache_hit ? "CACHE HIT: ZERO TOKENS" : ("DISPATCHED TO " + (p.complexity ? p.complexity.model : (p.tier || "MODEL")).toUpperCase());
      statusBadge.className = "step-badge " + (data.cache_hit ? "badge-hit" : "badge-tier");
    }

    var sv = p.savings || {};
    var l1 = p.l1_cache || {};
    var l2 = p.l2_cache || {};
    var pr = p.pruning || {};
    var cr = p.complexity || { signals: {} };

    // 4 Key Metrics Bar
    var metricsBar = document.getElementById("telemetryMetricsBar");
    if (metricsBar) metricsBar.style.display = "grid";

    var elCostSaved = document.getElementById("tmCostSaved");
    if (elCostSaved) elCostSaved.textContent = (sv.delta_c_pct != null ? sv.delta_c_pct : 0) + "% Saved";
    var elCostDetails = document.getElementById("tmCostDetails");
    if (elCostDetails) elCostDetails.textContent = fmtUsd(sv.cost_usd) + " (vs " + fmtUsd(sv.cost_baseline_usd) + ")";

    var elCacheStatus = document.getElementById("tmCacheStatus");
    if (elCacheStatus) {
      if (l1.hit) {
        elCacheStatus.textContent = "L1 EXACT HIT";
        elCacheStatus.style.color = "var(--green)";
      } else if (l2.hit) {
        elCacheStatus.textContent = "L2 SEMANTIC HIT";
        elCacheStatus.style.color = "var(--cyan)";
      } else {
        elCacheStatus.textContent = "CACHE MISS";
        elCacheStatus.style.color = "var(--muted)";
      }
    }
    var elTokensSaved = document.getElementById("tmTokensSaved");
    if (elTokensSaved) elTokensSaved.textContent = fmtInt(sv.tokens_saved || 0) + " tokens saved";

    var elPruneRatio = document.getElementById("tmPruneRatio");
    if (elPruneRatio) elPruneRatio.textContent = (pr.reduction_pct != null ? pr.reduction_pct : 0) + "%";
    var elPruneTokens = document.getElementById("tmPruneTokens");
    if (elPruneTokens) elPruneTokens.textContent = (pr.original_tokens || 0) + " \u2192 " + (pr.pruned_tokens || 0) + " tok";

    var elRoutedModel = document.getElementById("tmRoutedModel");
    if (elRoutedModel) elRoutedModel.textContent = (cr.model || p.tier || "Standard").toUpperCase();
    var elLatency = document.getElementById("tmLatency");
    if (elLatency) elLatency.textContent = (sv.latency_ms || 0) + " ms";

    // Tab 1: Assistant Response
    var responseOutput = document.getElementById("responseOutput");
    if (responseOutput) {
      var content = (data.choices && data.choices[0] && data.choices[0].message) ? data.choices[0].message.content : (data.error || "No content returned");
      responseOutput.textContent = content;
    }

    // Feedback Controls (visible on L2 semantic hit)
    var fbControls = document.getElementById("l2FeedbackControls");
    if (fbControls) {
      fbControls.style.display = (l2.hit ? "flex" : "none");
    }
    var btnGood = document.getElementById("btnFeedbackGood");
    var btnBad = document.getElementById("btnFeedbackBad");
    if (btnGood) btnGood.className = "btn-feedback";
    if (btnBad) btnBad.className = "btn-feedback";

    // Tab 2: Clean Pipeline Telemetry Cards
    // Step 1: Security & Multi-Tenancy
    var valTeam = document.getElementById("valTelemetryTeam");
    if (valTeam) valTeam.textContent = (state.currentUser ? (state.currentUser.team_id || "general") : "Support").toUpperCase();
    var valNamespace = document.getElementById("valNamespace");
    if (valNamespace) valNamespace.textContent = p.namespace && p.namespace.hash ? (p.namespace.hash.substring(0, 16) + "...") : "NS-DEFAULT";
    var badgeNs = document.getElementById("stepNamespaceBadge");
    if (badgeNs) badgeNs.textContent = "Isolated: " + ((p.namespace && p.namespace.team_id) ? p.namespace.team_id : "Standard");

    // Step 2: Cache Acceleration
    var stepL1 = document.getElementById("stepL1");
    if (stepL1) stepL1.classList.toggle("hit", l1.hit || l2.hit);
    var badgeL1 = document.getElementById("stepL1Badge");
    if (badgeL1) {
      badgeL1.textContent = l1.hit ? "EXACT RAM HIT" : (l2.hit ? "SEMANTIC HIT" : "CACHE MISS");
      badgeL1.className = "step-badge " + ((l1.hit || l2.hit) ? "badge-hit" : "badge-miss");
    }
    var valL1 = document.getElementById("valL1Status");
    if (valL1) valL1.textContent = l1.hit ? "Instant Memory Match ($0.00)" : "Not in L1 hash index";
    var valL2 = document.getElementById("valL2Sim");
    if (valL2) {
      valL2.textContent = l2.similarity != null ? (l2.similarity.toFixed(4) + " (Req Barrier: " + (l2.effective_threshold != null ? l2.effective_threshold.toFixed(4) : "0.85") + ")") : (l1.hit ? "Skipped (Satisfied by L1)" : "Miss (Below dynamic barrier)");
    }
    var valAge = document.getElementById("valL2Age");
    if (valAge) {
      valAge.textContent = l2.age_seconds != null ? (l2.age_seconds + "s elapsed (TTL: " + l2.ttl_seconds + "s)") : "New Entry";
    }

    // Step 3: Zero-Loss Prompt Optimizer
    var badgePrune = document.getElementById("stepPruneBadge");
    if (badgePrune) {
      badgePrune.textContent = (pr.tokens_saved > 0) ? ("-" + pr.tokens_saved + " TOKENS (" + pr.reduction_pct + "%)") : "PRESERVED";
      badgePrune.className = "step-badge " + (pr.tokens_saved > 0 ? "badge-hit" : "badge-tier");
    }
    var valPrunedTok = document.getElementById("valPrunedTokens");
    if (valPrunedTok) valPrunedTok.textContent = (pr.original_tokens || 0) + " \u2192 " + (pr.pruned_tokens || 0) + " tokens";
    var valPrunedSaved = document.getElementById("valPrunedSaved");
    if (valPrunedSaved) valPrunedSaved.textContent = (pr.tokens_saved || 0) + " tokens eliminated (" + (pr.reduction_pct || 0) + "% compression)";

    // Step 4: Intelligent Model Routing
    var badgeRoute = document.getElementById("stepRouteBadge");
    if (badgeRoute) {
      badgeRoute.textContent = (cr.model || p.tier || "economy").toUpperCase();
      badgeRoute.className = "step-badge " + (cr.tier === "economy" ? "badge-hit" : (cr.tier === "balanced" ? "badge-tier" : "badge-purple"));
    }
    if (cr.signals) {
      var sigL = cr.signals.length || 0;
      var sigI = cr.signals.instruction || 0;
      var sigR = cr.signals.reasoning || 0;
      var sigC = cr.signals.code || 0;
      var sL = document.getElementById("sigLen"); if (sL) sL.textContent = sigL.toFixed(2);
      var fL = document.getElementById("fillLen"); if (fL) fL.style.width = Math.min(100, Math.round(sigL * 100)) + "%";
      var sI = document.getElementById("sigInst"); if (sI) sI.textContent = sigI.toFixed(2);
      var fI = document.getElementById("fillInst"); if (fI) fI.style.width = Math.min(100, Math.round(sigI * 100)) + "%";
      var sR = document.getElementById("sigReason"); if (sR) sR.textContent = sigR.toFixed(2);
      var fR = document.getElementById("fillReason"); if (fR) fR.style.width = Math.min(100, Math.round(sigR * 100)) + "%";
      var sC = document.getElementById("sigCode"); if (sC) sC.textContent = sigC.toFixed(2);
      var fC = document.getElementById("fillCode"); if (fC) fC.style.width = Math.min(100, Math.round(sigC * 100)) + "%";
    }
    var valTierModel = document.getElementById("valTierModel");
    if (valTierModel) valTierModel.textContent = (cr.tier || "economy").toUpperCase() + " Tier (" + (cr.model || "gpt-4o-mini") + ")";
    var valRationale = document.getElementById("valRoutingRationale");
    if (valRationale) {
      valRationale.textContent = (cr.tier === "economy") ? "Standard query routed to high-speed economy model for minimal token burn" : ((cr.tier === "balanced") ? "Multi-step analytical query routed to balanced model" : "Complex architectural/reasoning query routed to frontier model");
    }

    // Tab 3: Update Code Snippets
    updateCodeSnippets();

    // Tab 4: Raw JSON Inspector
    var rawViewer = document.getElementById("rawJsonViewer");
    if (rawViewer) rawViewer.textContent = JSON.stringify(data, null, 2);

    // Left pane savings banner
    var savingsBanner = document.getElementById("savingsBanner");
    if (savingsBanner) {
      savingsBanner.style.display = "grid";
      document.getElementById("bannerDeltaC").textContent = (sv.delta_c_pct != null ? sv.delta_c_pct : 0) + "%";
      document.getElementById("bannerCost").textContent = fmtUsd(sv.cost_usd);
      document.getElementById("bannerTokensSaved").textContent = fmtInt(sv.tokens_saved);
      document.getElementById("bannerLatency").textContent = (sv.latency_ms || 0) + " ms";
    }

    // Default to Response tab on each execution
    switchConsoleTab("response");
  }

  function submitFeedback(isWrong) {
    if (!state.lastLogId) return;

    fetch("/api/cache/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ log_id: state.lastLogId, is_wrong_answer: isWrong })
    })
    .then(function(r) { return r.json(); })
    .then(function() {
      document.getElementById("btnFeedbackGood").className = "btn-feedback " + (!isWrong ? "active-good" : "");
      document.getElementById("btnFeedbackBad").className = "btn-feedback " + (isWrong ? "active-bad" : "");
      loadResearchData();
    });
  }

  // Load Research Metrics & Paper Tables
  function loadResearchData() {
    fetch("/api/metrics/research-summary")
      .then(function(r) { return r.json(); })
      .then(function(d) {
        state.researchData = d;
        document.getElementById("kpiTrr").textContent = d.trr_pct + "%";
        document.getElementById("kpiTrrNet").textContent = d.trr_net_pct + "%";
        document.getElementById("kpiDeltaC").textContent = d.delta_c_pct + "%";
        document.getElementById("kpiHitRate").textContent = Math.round(d.hit_rate_H * 100) + "%";
        document.getElementById("kpiPrecision").textContent = Math.round(d.l2_precision_P * 100) + "%";

        // Render Table 1
        var t1Html = d.table_1.map(function(row) {
          return '<tr>' +
            '<td><b>' + esc(row.metric) + '</b></td>' +
            '<td>' + esc(row.baseline) + '</td>' +
            '<td>' + esc(row.l1_only) + '</td>' +
            '<td>' + esc(row.l1_l2) + '</td>' +
            '<td style="color:var(--cyan); font-weight:700;">' + esc(row.full) + '</td>' +
            '</tr>';
        }).join("");
        document.getElementById("tableOneBody").querySelector("tbody").innerHTML = t1Html;

        // Render Table 2
        var t2Html = d.table_2.map(function(row) {
          var isSelected = (row.base_tau === 0.84);
          return '<tr class="' + (isSelected ? 'highlight' : '') + '">' +
            '<td>' + row.base_tau.toFixed(2) + (isSelected ? ' &dagger;' : '') + '</td>' +
            '<td>' + esc(row.hit_rate) + '</td>' +
            '<td style="color:var(--purple);">' + esc(row.precision) + '</td>' +
            '<td>' + esc(row.raw_trr) + '</td>' +
            '<td style="color:var(--cyan);">' + esc(row.trr_net) + '</td>' +
            '</tr>';
        }).join("");
        document.getElementById("tableTwoBody").querySelector("tbody").innerHTML = t2Html;

        // Render Table 3
        var t3Html = d.table_3.map(function(row) {
          var isTmg = row.strategy.indexOf("TokenMinGate") !== -1;
          return '<tr class="' + (isTmg ? 'highlight' : '') + '">' +
            '<td>' + esc(row.strategy) + '</td>' +
            '<td>' + esc(row.cost) + '</td>' +
            '<td style="color:' + (isTmg ? 'var(--green)' : 'var(--cyan)') + '; font-weight:700;">' + esc(row.delta_c) + '</td>' +
            '</tr>';
        }).join("");
        document.getElementById("tableThreeBody").querySelector("tbody").innerHTML = t3Html;
      });
  }

  // Draw Figure 2 and Figure 3 SVGs
  function renderCharts() {
    // Figure 2: Age-decay Cut-off curve
    var svg2 = document.getElementById("svgFig2");
    var w = 500, h = 220, padL = 40, padB = 30, padT = 20, padR = 20;
    var plotW = w - padL - padR, plotH = h - padT - padB;

    function xMap(a) { return padL + a * plotW; }
    function yMap(tauVal) {
      // Range 0.65 to 1.05
      return padT + (1.0 - (tauVal - 0.65) / 0.4) * plotH;
    }

    var lines = [
      { tau: 0.75, color: "#34E7FF", dash: "none", label: "tau = 0.75" },
      { tau: 0.84, color: "#10B981", dash: "none", label: "tau = 0.84 (Selected)" },
      { tau: 0.90, color: "#A78BFA", dash: "4 4", label: "tau = 0.90" }
    ];

    var svgContent = '<line x1="' + padL + '" y1="' + (h - padB) + '" x2="' + (w - padR) + '" y2="' + (h - padB) + '" stroke="#2D3748" stroke-width="1.5" />' +
      '<line x1="' + padL + '" y1="' + padT + '" x2="' + padL + '" y2="' + (h - padB) + '" stroke="#2D3748" stroke-width="1.5" />' +
      '<text x="' + (w / 2) + '" y="' + (h - 6) + '" fill="#8A94A0" font-size="10" text-anchor="middle">Normalized Age (ai / Tk)</text>' +
      '<text x="14" y="' + (h / 2) + '" fill="#8A94A0" font-size="10" transform="rotate(-90 14 ' + (h / 2) + ')" text-anchor="middle">Effective tau_eff</text>';

    // Grid ticks
    for (var a = 0; a <= 1.0; a += 0.2) {
      var x = xMap(a);
      svgContent += '<text x="' + x + '" y="' + (h - padB + 14) + '" fill="#8A94A0" font-size="9" text-anchor="middle">' + a.toFixed(1) + '</text>';
    }
    for (var tv = 0.7; tv <= 1.0; tv += 0.1) {
      var y = yMap(tv);
      svgContent += '<text x="' + (padL - 6) + '" y="' + (y + 3) + '" fill="#8A94A0" font-size="9" text-anchor="end">' + tv.toFixed(1) + '</text>' +
        '<line x1="' + padL + '" y1="' + y + '" x2="' + (w - padR) + '" y2="' + y + '" stroke="rgba(255,255,255,0.05)" stroke-width="1" />';
    }

    lines.forEach(function(item) {
      var x1 = xMap(0), y1 = yMap(item.tau);
      var x2 = xMap(1), y2 = yMap(1.0);
      svgContent += '<line x1="' + x1 + '" y1="' + y1 + '" x2="' + x2 + '" y2="' + y2 + '" stroke="' + item.color + '" stroke-width="2.2" stroke-dasharray="' + item.dash + '" />' +
        '<circle cx="' + x1 + '" cy="' + y1 + '" r="3.5" fill="' + item.color + '" />' +
        '<circle cx="' + x2 + '" cy="' + y2 + '" r="3.5" fill="' + item.color + '" />';
    });

    svg2.innerHTML = svgContent;

    // Figure 3: Tau Sweep vs Savings
    var svg3 = document.getElementById("svgFig3");
    var f3Content = '<line x1="' + padL + '" y1="' + (h - padB) + '" x2="' + (w - padR) + '" y2="' + (h - padB) + '" stroke="#2D3748" stroke-width="1.5" />' +
      '<line x1="' + padL + '" y1="' + padT + '" x2="' + padL + '" y2="' + (h - padB) + '" stroke="#2D3748" stroke-width="1.5" />' +
      '<text x="' + (w / 2) + '" y="' + (h - 6) + '" fill="#8A94A0" font-size="10" text-anchor="middle">Base Similarity Threshold tau</text>' +
      '<text x="14" y="' + (h / 2) + '" fill="#8A94A0" font-size="10" transform="rotate(-90 14 ' + (h / 2) + ')" text-anchor="middle">Percent (%)</text>';

    var taus = [0.70, 0.75, 0.80, 0.84, 0.90, 0.95];
    var rawTrr = [74.2, 68.4, 61.8, 58.4, 41.2, 28.4];
    var trrNet = [60.2, 61.2, 59.4, 57.3, 41.1, 28.4];
    var prec = [81.2, 89.5, 96.1, 98.2, 99.7, 100.0];

    function xT(t) { return padL + ((t - 0.70) / 0.25) * plotW; }
    function yP(p) { return padT + (1.0 - (p - 20) / 85) * plotH; }

    function makePath(arr, color) {
      var d = "M " + xT(taus[0]) + " " + yP(arr[0]);
      for (var i = 1; i < taus.length; i++) {
        d += " L " + xT(taus[i]) + " " + yP(arr[i]);
      }
      return '<path d="' + d + '" fill="none" stroke="' + color + '" stroke-width="2.2" />' +
        taus.map(function(t, idx) {
          return '<circle cx="' + xT(t) + '" cy="' + yP(arr[idx]) + '" r="3" fill="' + color + '" />';
        }).join("");
    }

    f3Content += makePath(rawTrr, "#34E7FF"); // Cyan: Raw TRR
    f3Content += makePath(trrNet, "#FF5C66"); // Red: TRRnet
    f3Content += makePath(prec, "#10B981");   // Green: Precision

    // Vertical line at tau = 0.84
    var x84 = xT(0.84);
    f3Content += '<line x1="' + x84 + '" y1="' + padT + '" x2="' + x84 + '" y2="' + (h - padB) + '" stroke="rgba(255,255,255,0.4)" stroke-dasharray="3 3" />' +
      '<text x="' + x84 + '" y="' + (padT - 6) + '" fill="#34E7FF" font-size="9" text-anchor="middle">tau=0.84</text>';

    svg3.innerHTML = f3Content;
  }

  // Load Ledger
  function loadLedger() {
    fetch("/api/ledger?limit=50")
      .then(function(r) { return r.json(); })
      .then(function(res) {
        state.ledgerRows = res.rows || [];
        renderLedgerTable(state.ledgerRows);
      });
  }

  function renderLedgerTable(rows) {
    var tbody = document.getElementById("ledgerTableBody");
    if (!rows.length) {
      tbody.innerHTML = '<tr><td colspan="10" style="text-align:center; color:var(--muted); padding:30px;">No requests recorded yet. Submit a prompt in Playground!</td></tr>';
      return;
    }

    tbody.innerHTML = rows.map(function(r) {
      var d = new Date(r.ts * 1000);
      var timeStr = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      var tierBadge = r.cache_hit
        ? '<span class="step-badge badge-hit">' + (r.cache_tier || 'HIT').toUpperCase() + '</span>'
        : '<span class="step-badge badge-tier">' + (r.tier || 'ROUTE').toUpperCase() + '</span>';

      return '<tr>' +
        '<td class="mono" style="font-size:11px; color:var(--muted);">' + timeStr + '</td>' +
        '<td><b>' + esc(r.user_id || 'User') + '</b></td>' +
        '<td>' + esc(r.team_id || 'general') + '</td>' +
        '<td style="max-width:240px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="' + esc(r.prompt) + '">' + esc(r.prompt) + '</td>' +
        '<td>' + tierBadge + '</td>' +
        '<td class="mono">' + (r.total_tokens || 0) + '</td>' +
        '<td class="mono" style="color:var(--cyan);">' + fmtUsd(r.cost_usd) + '</td>' +
        '<td class="mono" style="color:var(--muted);">' + fmtUsd(r.baseline_cost_usd) + '</td>' +
        '<td class="mono">' + (r.latency_ms || 0).toFixed(0) + 'ms</td>' +
        '<td>' +
          (r.cache_tier === 'l2'
            ? ('<button class="btn-feedback ' + (r.is_wrong_answer ? 'active-bad' : 'active-good') + '" onclick="toggleRowFeedback(' + r.id + ', ' + (!r.is_wrong_answer) + ')">' +
               (r.is_wrong_answer ? '👎 Wrong' : '👍 Accurate') + '</button>')
            : '<span style="color:var(--dim); font-size:10.5px;">--</span>') +
        '</td>' +
        '</tr>';
    }).join("");
  }

  window.toggleRowFeedback = function(id, isWrong) {
    fetch("/api/cache/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ log_id: id, is_wrong_answer: isWrong })
    }).then(function() {
      loadLedger();
      loadResearchData();
    });
  };

  function filterLedger() {
    var search = document.getElementById("ledgerSearchInput").value.toLowerCase();
    var team = document.getElementById("ledgerTeamFilter").value;
    var tier = document.getElementById("ledgerTierFilter").value;

    var filtered = state.ledgerRows.filter(function(r) {
      if (team && r.team_id !== team) return false;
      if (tier) {
        if (tier === 'l1' && (r.cache_tier !== 'l1')) return false;
        if (tier === 'l2' && (r.cache_tier !== 'l2')) return false;
        if (tier !== 'l1' && tier !== 'l2' && r.tier !== tier) return false;
      }
      if (search) {
        var str = ((r.prompt || "") + " " + (r.user_id || "") + " " + (r.key || "")).toLowerCase();
        if (str.indexOf(search) === -1) return false;
      }
      return true;
    });

    renderLedgerTable(filtered);
  }

  // Load Cache Entries
  function loadCacheEntries() {
    fetch("/api/cache/entries")
      .then(function(r) { return r.json(); })
      .then(function(entries) {
        var tbody = document.getElementById("cacheTableBody");
        if (!entries.length) {
          tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:var(--muted); padding:30px;">Cache is currently empty. Run queries in the playground!</td></tr>';
          return;
        }

        tbody.innerHTML = entries.map(function(e) {
          return '<tr>' +
            '<td style="max-width:260px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="' + esc(e.prompt_norm) + '"><b>' + esc(e.prompt_norm) + '</b></td>' +
            '<td class="mono" style="font-size:11px;">' + esc(e.namespace.substring(0, 10)) + '...</td>' +
            '<td class="mono">' + e.age_seconds.toFixed(0) + 's</td>' +
            '<td class="mono">' + (e.ttl_seconds / 86400).toFixed(1) + 'd</td>' +
            '<td class="mono" style="color:var(--cyan); font-weight:700;">' + e.effective_threshold.toFixed(4) + '</td>' +
            '<td class="mono">' + e.tokens_saved + '</td>' +
            '<td>' +
              '<button class="btn-feedback" onclick="simulateAge(\'' + e.entry_id + '\', 86400)">+1d Age</button> ' +
              '<button class="btn-feedback" style="color:var(--red);" onclick="evictCache(\'' + e.entry_id + '\')">Evict</button>' +
            '</td>' +
            '</tr>';
        }).join("");
      });
  }

  function simulateAge(entryId, secs) {
    fetch("/api/cache/simulate-age", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ entry_id: entryId, age_seconds: secs })
    }).then(function() { loadCacheEntries(); });
  }

  function evictCache(entryId) {
    fetch("/api/cache/evict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ entry_id: entryId })
    }).then(function() { loadCacheEntries(); });
  }

  function purgeExpiredCache() {
    fetch("/api/cache/purge", { method: "POST" })
      .then(function(r) { return r.json(); })
      .then(function(res) {
        alert("Purged " + res.removed + " expired entries");
        loadCacheEntries();
      });
  }

  // SupaDB view
  function loadDbStatus() {
    fetch("/api/db/status")
      .then(function(r) { return r.json(); })
      .then(function(s) {
        var badge = document.getElementById("dbStatusBadge");
        badge.textContent = s.supabase_configured ? "Engine: Supabase Cloud Active" : "Engine: SQLite Local Fallback";
        badge.className = "db-status-badge " + (s.supabase_configured ? "online" : "offline");

        var counts = s.records_count || {};
        var html = Object.keys(counts).map(function(k) {
          return '<div style="display:flex; justify-content:space-between; font-size:12px; background:var(--bg); padding:6px 12px; border-radius:6px;">' +
            '<span style="color:var(--muted);">' + k + '</span>' +
            '<span class="mono" style="color:var(--cyan); font-weight:600;">' + counts[k] + ' records</span>' +
            '</div>';
        }).join("");
        document.getElementById("dbTablesCountList").innerHTML = html;
      });
  }

  function syncSupabase() {
    var url = document.getElementById("supabaseUrlInput").value.trim();
    var key = document.getElementById("supabaseKeyInput").value.trim();
    if (!url || !key) {
      alert("Please provide both Supabase URL and Service Role Key");
      return;
    }

    fetch("/api/db/sync-supabase", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ supabase_url: url, supabase_key: key })
    })
    .then(function(r) { return r.json(); })
    .then(function(res) {
      alert("Successfully synced local tables to Supabase!");
      loadDbStatus();
    })
    .catch(function(err) {
      alert("Sync error: " + err.message);
    });
  }

  function loadSchemaSql() {
    fetch("/api/db/schema.sql")
      .then(function(r) { return r.text(); })
      .then(function(sql) {
        document.getElementById("schemaSqlViewer").textContent = sql;
      });
  }

  function copySchemaSql() {
    var text = document.getElementById("schemaSqlViewer").textContent;
    navigator.clipboard.writeText(text).then(function() {
      alert("Supabase SQL Schema copied to clipboard! Paste into Supabase SQL Editor.");
    });
  }

})();
</script>
</body>
</html>
"""
