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
<title>llm-gateway · TokenMinGate Dashboard</title>
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
    max-width: 920px; margin: 40px auto;
    background: var(--surface); border: 1px solid var(--surface-border);
    border-radius: var(--radius-lg); overflow: hidden;
    box-shadow: 0 24px 64px -12px rgba(0, 0, 0, 0.7);
  }
  .auth-grid { display: grid; grid-template-columns: 1fr 1.15fr; }
  .auth-hero {
    background: linear-gradient(165deg, rgba(52, 231, 255, 0.12), rgba(167, 139, 250, 0.06), #0A0D11);
    padding: 44px 36px; border-right: 1px solid var(--surface-border);
    display: flex; flex-direction: column; justify-content: space-between;
  }
  .auth-hero h2 { font-family: 'Syne', sans-serif; font-size: 26px; font-weight: 800; line-height: 1.15; margin-bottom: 14px; }
  .auth-hero p { color: var(--muted); font-size: 13px; line-height: 1.6; }
  .feature-pills { margin-top: 24px; display: flex; flex-direction: column; gap: 10px; }
  .pill { display: flex; align-items: center; gap: 10px; font-size: 12px; color: var(--ink); }
  .pill-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--cyan); box-shadow: 0 0 8px var(--cyan); }

  .auth-form-wrap { padding: 40px 36px; }
  .auth-tabs { display: flex; border-bottom: 1px solid var(--surface-border); margin-bottom: 24px; }
  .auth-subtab {
    padding: 9px 18px; border: none; background: transparent; color: var(--muted);
    font-size: 13px; font-weight: 600; cursor: pointer; border-bottom: 2px solid transparent;
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

  .demo-users-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 14px; }
  .demo-user-card {
    background: var(--bg-alt); border: 1px solid var(--surface-border); border-radius: var(--radius-sm);
    padding: 10px 12px; cursor: pointer; text-align: left; transition: all 0.15s ease;
  }
  .demo-user-card:hover { border-color: var(--cyan); background: rgba(52, 231, 255, 0.04); transform: translateY(-1px); }
  .duc-name { font-weight: 600; font-size: 12px; color: var(--ink); }
  .duc-role { font-size: 10.5px; color: var(--cyan); margin-top: 2px; }
  .duc-team { font-size: 10px; color: var(--muted); }

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
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
      </div>
      <div class="logo-text">
        <h1>TokenMinGate</h1>
        <span>Cost-Cutting LLM Proxy</span>
      </div>
    </a>

    <div class="nav-tabs" id="mainNavTabs" style="display:none;">
      <button class="nav-tab active" onclick="switchTab('playground')">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 17l6-6-6-6M12 19h8"/></svg>
        Playground
      </button>
      <button class="nav-tab" onclick="switchTab('research')">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/></svg>
        Research &amp; Tables
      </button>
      <button class="nav-tab" onclick="switchTab('ledger')">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>
        Cost Ledger
      </button>
      <button class="nav-tab" onclick="switchTab('cache')">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/></svg>
        Cache Inspector
      </button>
      <button class="nav-tab" onclick="switchTab('supadb')">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" y1="22" x2="4" y2="15"/></svg>
        SupaDB Sync
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

  <!-- ===================================================================== -->
  <!-- AUTH VIEW (Sign In / Register / Quick Demo) -->
  <!-- ===================================================================== -->
  <section id="authView">
    <div class="auth-grid">
      <div class="auth-hero">
        <div>
          <h2>TokenMinGate</h2>
          <p>Cut your LLM API bill by up to 74% and token usage by 81% through multi-layer semantic caching, age-decay validation, and tiered model routing.</p>
          <div class="feature-pills">
            <div class="pill"><span class="pill-dot"></span><span><b>L1 + L2 Cache:</b> Exact + FAISS Cosine Similarity</span></div>
            <div class="pill"><span class="pill-dot"></span><span><b>Elastic &tau;<sub>eff</sub>:</b> Age-based similarity barrier</span></div>
            <div class="pill"><span class="pill-dot"></span><span><b>Syntax-Safe Pruning:</b> Zero-loss prompt compression</span></div>
            <div class="pill"><span class="pill-dot"></span><span><b>Complexity Routing:</b> Economy, Balanced &amp; Frontier</span></div>
            <div class="pill"><span class="pill-dot"></span><span><b>SupaDB Ready:</b> Supabase PostgreSQL + SQLite dual-mode</span></div>
          </div>
        </div>
        <div style="font-size: 11px; color: var(--dim); margin-top: 30px;">
          DeepMind Advanced Agentic Coding &middot; TokenMinGate Architecture
        </div>
      </div>

      <div class="auth-form-wrap">
        <div class="auth-tabs">
          <button class="auth-subtab active" onclick="switchAuthTab('login')">Employee Login</button>
          <button class="auth-subtab" onclick="switchAuthTab('register')">Register New</button>
        </div>

        <!-- Quick 1-Click Demo Profiles -->
        <div style="margin-bottom: 20px;">
          <span style="font-size: 11px; color: var(--muted); text-transform: uppercase; font-weight: 600; letter-spacing: 0.05em;">1-Click Demo Access</span>
          <div class="demo-users-grid" id="demoUsersList">
            <!-- Rendered by JS -->
          </div>
        </div>

        <div id="authLoginForm">
          <div class="form-group">
            <label>Employee Email</label>
            <input type="email" id="loginEmail" class="form-input" placeholder="alice@company.internal" value="alice@company.internal" />
          </div>
          <div class="form-group">
            <label>Password</label>
            <input type="password" id="loginPassword" class="form-input" placeholder="••••••••" value="alice123" />
          </div>
          <button class="btn-primary" onclick="handleLogin()">
            <span>Sign In to TokenMinGate</span>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
          </button>
        </div>

        <div id="authRegisterForm" style="display:none;">
          <div class="form-group">
            <label>Full Name</label>
            <input type="text" id="regName" class="form-input" placeholder="Sarah Connor" />
          </div>
          <div class="form-group">
            <label>Work Email</label>
            <input type="email" id="regEmail" class="form-input" placeholder="sarah@company.internal" />
          </div>
          <div class="form-group">
            <label>Password</label>
            <input type="password" id="regPassword" class="form-input" placeholder="••••••••" />
          </div>
          <div class="form-group">
            <label>Assigned Team</label>
            <select id="regTeam" class="form-select">
              <option value="support">Customer Support</option>
              <option value="engineering">Core Engineering</option>
              <option value="finance">Finance &amp; Ops</option>
              <option value="platform">Platform &amp; AI</option>
            </select>
          </div>
          <button class="btn-primary" onclick="handleRegister()">Create Employee Account</button>
        </div>
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
              <span>Employee Query Composer</span>
            </div>
            <div class="panel-subtitle">Submit prompts through TokenMinGate to watch the live reduction layers</div>
          </div>
          <span class="step-badge badge-tier" id="activeKeyBadge">sk-gw-alice</span>
        </div>

        <div class="form-group">
          <label>Prompt Text</label>
          <textarea id="promptInput" class="prompt-textarea" placeholder="Type your question or choose a research preset below..."></textarea>
        </div>

        <div class="presets-bar">
          <span style="font-size: 11px; color: var(--muted); align-self: center;">Paper presets:</span>
          <button class="preset-btn" onclick="setPrompt('How do I reset my VPN password?')">VPN Reset (FAQ)</button>
          <button class="preset-btn" onclick="setPrompt('Can you please tell me: VPN password reset steps? Thanks!')">VPN Paraphrase (L2 Hit)</button>
          <button class="preset-btn" onclick="setPrompt('What is our refund policy for enterprise customers?')">Enterprise Refund</button>
          <button class="preset-btn" onclick="setPrompt('Write a Python function to parse a CSV file and return a dict.')">CSV Parser (Code)</button>
          <button class="preset-btn" onclick="setPrompt('Derive the time complexity of merge sort and justify each step with proofs.')">Merge Sort (Reasoning)</button>
        </div>

        <div class="config-grid">
          <div class="form-group">
            <label>Lifespan T<sub>k</sub> (TTL)</label>
            <select id="topicTtlSelect" class="form-select">
              <option value="86400">1 Day (Fast Changing)</option>
              <option value="604800" selected>7 Days (Operations)</option>
              <option value="2592000">30 Days (Stable Policies)</option>
            </select>
          </div>
          <div class="form-group">
            <label>Base &tau; Threshold</label>
            <select id="tauSelect" class="form-select">
              <option value="0.70">0.70 (Aggressive)</option>
              <option value="0.75">0.75 (Max TRRnet)</option>
              <option value="0.80">0.80 (Balanced)</option>
              <option value="0.84" selected>0.84 (Paper Choice &middot; P&ge;0.98)</option>
              <option value="0.90">0.90 (Conservative)</option>
            </select>
          </div>
          <div class="form-group">
            <label>Gateway Mode</label>
            <select id="modelModeSelect" class="form-select">
              <option value="tokenmingate" selected>TokenMinGate (Auto-Tier)</option>
              <option value="mock-echo">Mock Echo Provider</option>
              <option value="mock-cheap">Mock Cheap Tier</option>
            </select>
          </div>
        </div>

        <button class="btn-primary" id="btnSendPrompt" onclick="executeGatewayRequest()">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
          <span>Send Request Through TokenMinGate</span>
        </button>

        <!-- Response Area -->
        <div class="response-box" id="responseBox" style="display:none;">
          <div class="response-title">Assistant Reply</div>
          <div class="response-content" id="responseOutput"></div>
          <div id="l2FeedbackControls" style="margin-top: 12px; display: none;">
            <span style="font-size: 11px; color: var(--muted); margin-right: 8px;">Was this L2 semantic cache answer accurate?</span>
            <button class="btn-feedback" id="btnFeedbackGood" onclick="submitFeedback(false)">👍 Yes, accurate</button>
            <button class="btn-feedback" id="btnFeedbackBad" onclick="submitFeedback(true)">👎 No, wrong answer</button>
          </div>
        </div>

        <div class="savings-banner" id="savingsBanner" style="display:none;">
          <div class="sb-item">
            <span class="sb-k">Money Saved &Delta;C</span>
            <span class="sb-v cyan" id="bannerDeltaC">0%</span>
          </div>
          <div class="sb-item">
            <span class="sb-k">Billed Cost C<sub>TMG</sub></span>
            <span class="sb-v" id="bannerCost">$0.00</span>
          </div>
          <div class="sb-item">
            <span class="sb-k">Tokens Saved</span>
            <span class="sb-v glow" id="bannerTokensSaved">0</span>
          </div>
          <div class="sb-item">
            <span class="sb-k">Latency</span>
            <span class="sb-v" id="bannerLatency">0 ms</span>
          </div>
        </div>

      </div>

      <!-- Right: Live Pipeline Visualizer -->
      <div class="panel">
        <div class="panel-hd">
          <div>
            <div class="panel-title">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--cyan)" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
              <span>Algorithm 1 Live Execution Trace</span>
            </div>
            <div class="panel-subtitle">Transparent visualization of each layer's decisions</div>
          </div>
          <span class="step-badge" id="pipelineStatusBadge">Awaiting Request</span>
        </div>

        <div class="pipeline-flow">
          <!-- Step 1: Namespace -->
          <div class="pipeline-step" id="stepNamespace">
            <div class="step-head">
              <span class="step-title">
                <span class="pill-dot"></span>
                <span>1. Tenant Namespace Isolation (N)</span>
              </span>
              <span class="step-badge badge-tier" id="stepNamespaceBadge">Ready</span>
            </div>
            <div class="step-body">
              <div>Formula: <code class="mono">N = SHA256(team_id || system_prompt || provider || temp)</code></div>
              <div class="step-data-row"><span>Namespace Hash N:</span><span class="step-val" id="valNamespace">--</span></div>
            </div>
          </div>

          <!-- Step 2: L1 Exact Match -->
          <div class="pipeline-step" id="stepL1">
            <div class="step-head">
              <span class="step-title">
                <span class="pill-dot"></span>
                <span>2. L1 Exact-Match Cache</span>
              </span>
              <span class="step-badge" id="stepL1Badge">Pending</span>
            </div>
            <div class="step-body">
              <div>Check: <code class="mono">SHA256(N || u) in Memory</code></div>
              <div class="step-data-row"><span>Status:</span><span class="step-val" id="valL1Status">--</span></div>
              <div class="step-data-row"><span>Token Cost if Hit:</span><span class="step-val">0 tokens &middot; $0.00</span></div>
            </div>
          </div>

          <!-- Step 3: L2 Semantic Cache -->
          <div class="pipeline-step" id="stepL2">
            <div class="step-head">
              <span class="step-title">
                <span class="pill-dot"></span>
                <span>3. L2 Semantic Cache (FAISS + Elastic &tau;<sub>eff</sub>)</span>
              </span>
              <span class="step-badge" id="stepL2Badge">Pending</span>
            </div>
            <div class="step-body">
              <div>Cut-off rule: <code class="mono">&tau;<sub>eff</sub>(a<sub>i</sub>) = &tau; + (1-&tau;)&middot;min(1, a<sub>i</sub>/T<sub>k</sub>)</code></div>
              <div class="step-data-row"><span>Cosine Similarity s<sub>i</sub>:</span><span class="step-val" id="valL2Sim">--</span></div>
              <div class="step-data-row"><span>Required &tau;<sub>eff</sub>:</span><span class="step-val" id="valL2Tau">--</span></div>
              <div class="step-data-row"><span>Answer Age a<sub>i</sub>:</span><span class="step-val" id="valL2Age">--</span></div>
            </div>
          </div>

          <!-- Step 4: Prompt Pruning -->
          <div class="pipeline-step" id="stepPrune">
            <div class="step-head">
              <span class="step-title">
                <span class="pill-dot"></span>
                <span>4. Syntax-Safe Prompt Pruning (u &rarr; u')</span>
              </span>
              <span class="step-badge" id="stepPruneBadge">Pending</span>
            </div>
            <div class="step-body">
              <div>Removes polite filler &amp; redundant whitespace while preserving code/JSON</div>
              <div class="step-data-row"><span>Original vs Pruned Tokens:</span><span class="step-val" id="valPrunedTokens">--</span></div>
              <div class="step-data-row"><span>Pruning Savings:</span><span class="step-val" id="valPrunedSaved">--</span></div>
            </div>
          </div>

          <!-- Step 5: Complexity Routing -->
          <div class="pipeline-step" id="stepRoute">
            <div class="step-head">
              <span class="step-title">
                <span class="pill-dot"></span>
                <span>5. Complexity Router &amp; Tier Dispatch</span>
              </span>
              <span class="step-badge" id="stepRouteBadge">Pending</span>
            </div>
            <div class="step-body">
              <div>Score: <code class="mono">S(u) = w1&middot;len + w2&middot;inst + w3&middot;reason + w4&middot;code</code></div>
              <div class="signal-bars">
                <div class="signal-bar-box">
                  <div class="sb-label">Length</div>
                  <div class="sb-val" id="sigLen">0.0</div>
                  <div class="sb-progress"><div class="sb-fill" id="fillLen" style="width:0%"></div></div>
                </div>
                <div class="signal-bar-box">
                  <div class="sb-label">Instruct</div>
                  <div class="sb-val" id="sigInst">0.0</div>
                  <div class="sb-progress"><div class="sb-fill" id="fillInst" style="width:0%"></div></div>
                </div>
                <div class="signal-bar-box">
                  <div class="sb-label">Reason</div>
                  <div class="sb-val" id="sigReason">0.0</div>
                  <div class="sb-progress"><div class="sb-fill" id="fillReason" style="width:0%"></div></div>
                </div>
                <div class="signal-bar-box">
                  <div class="sb-label">Code</div>
                  <div class="sb-val" id="sigCode">0.0</div>
                  <div class="sb-progress"><div class="sb-fill" id="fillCode" style="width:0%"></div></div>
                </div>
              </div>
              <div class="step-data-row" style="margin-top: 10px;">
                <span>Total S(u'):</span><span class="step-val" id="valTotalScore">--</span>
              </div>
              <div class="step-data-row">
                <span>Selected Tier &amp; Model:</span><span class="step-val" id="valTierModel">--</span>
              </div>
            </div>
          </div>

        </div>
      </div>

    </div>
  </section>

  <!-- ===================================================================== -->
  <!-- VIEW 2: RESEARCH & PAPER REPLICATION OBSERVABILITY -->
  <!-- ===================================================================== -->
  <section id="paneResearch" class="tab-pane">
    <!-- Totals KPI Bar -->
    <section class="totals" id="totals" aria-label="portfolio totals" style="display:none;"></section>
    <div class="section-h" style="display:none;">
      <h2>Virtual keys</h2>
      <span class="count" id="keyCount"></span>
    </div>
    <section class="cards" id="cards" aria-label="per-key usage" style="display:none;"></section>

    <div class="metrics-totals" id="researchKpiBar">
      <div class="stat-card">
        <div class="stat-k">Token Reduction TRR</div>
        <div class="stat-v" style="color:var(--green);" id="kpiTrr">81.4%</div>
        <div class="stat-sub">Tokens saved vs baseline</div>
      </div>
      <div class="stat-card">
        <div class="stat-k">Fair Saving TRR<sub>net</sub></div>
        <div class="stat-v" style="color:var(--cyan);" id="kpiTrrNet">80.1%</div>
        <div class="stat-sub">Net of wrong cache answers</div>
      </div>
      <div class="stat-card">
        <div class="stat-k">Money Saved &Delta;C</div>
        <div class="stat-v" style="color:var(--cyan);" id="kpiDeltaC">74.2%</div>
        <div class="stat-sub">API cost reduction</div>
      </div>
      <div class="stat-card">
        <div class="stat-k">Cache Hit Rate H</div>
        <div class="stat-v" id="kpiHitRate">58.4%</div>
        <div class="stat-sub">L1 + L2 Semantic hits</div>
      </div>
      <div class="stat-card">
        <div class="stat-k">L2 Precision P</div>
        <div class="stat-v" style="color:var(--purple);" id="kpiPrecision">98.2%</div>
        <div class="stat-sub">Accuracy of semantic hits</div>
      </div>
    </div>

    <!-- Paper Replication Charts (Figure 2 & Figure 3) -->
    <div class="charts-grid">
      <div class="chart-box">
        <div class="table-title">
          <span>Figure 2: Elastic Age-decay Cut-off &tau;<sub>eff</sub>(a<sub>i</sub>)</span>
          <span class="step-badge badge-tier">&tau; &in; {0.75, 0.84, 0.90}</span>
        </div>
        <div class="table-desc">As an answer ages (normalized age a<sub>i</sub>/T<sub>k</sub>), required similarity rises to 1.0 to prevent stale reuse.</div>
        <svg class="chart-svg" viewBox="0 0 500 220" id="svgFig2"></svg>
      </div>

      <div class="chart-box">
        <div class="table-title">
          <span>Figure 3: Starting Cut-off &tau; vs Savings &amp; Precision</span>
          <span class="step-badge badge-purple">&tau; Operating Point</span>
        </div>
        <div class="table-desc">Trade-off curve between raw token reduction (TRR), net fair reduction (TRR<sub>net</sub>), and answer precision (P).</div>
        <svg class="chart-svg" viewBox="0 0 500 220" id="svgFig3"></svg>
      </div>
    </div>

    <!-- Table I: Results for Four Setups -->
    <div class="table-section">
      <div class="table-title">
        <span>Table I: Results for Four Setups (10,000 requests)</span>
        <span class="step-badge badge-hit">Replicated from Paper</span>
      </div>
      <div class="table-desc">Comparing Baseline (flat frontier) vs L1 exact only vs L1+L2 vs Full TokenMinGate setup.</div>
      <table class="paper-table" id="tableOneBody">
        <thead>
          <tr>
            <th>Metric</th>
            <th>Baseline</th>
            <th>L1 Only</th>
            <th>L1 + L2</th>
            <th>Full TokenMinGate</th>
          </tr>
        </thead>
        <tbody></tbody>
      </table>
    </div>

    <!-- Table II & Table III Grid -->
    <div class="charts-grid">
      <div class="table-section">
        <div class="table-title">
          <span>Table II: Cut-off &tau; Sweep (Savings vs Accuracy)</span>
        </div>
        <table class="paper-table" id="tableTwoBody">
          <thead>
            <tr>
              <th>Base &tau;</th>
              <th>Hit Rate H</th>
              <th>Precision P</th>
              <th>Raw TRR</th>
              <th>TRR<sub>net</sub></th>
            </tr>
          </thead>
          <tbody></tbody>
        </table>
      </div>

      <div class="table-section">
        <div class="table-title">
          <span>Table III: Cost of 10,000 Requests</span>
        </div>
        <table class="paper-table" id="tableThreeBody">
          <thead>
            <tr>
              <th>Operational Strategy</th>
              <th>Cost (USD)</th>
              <th>&Delta;C Saved</th>
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
    demoUsers: [],
    lastLogId: null,
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

  // Initialize
  document.addEventListener("DOMContentLoaded", function() {
    initAuth();
    loadDemoUsers();
    renderCharts();
    loadSchemaSql();
    // Fetch /admin/usage for observability metrics
    fetch("/admin/usage").catch(function() {});
  });

  function initAuth() {
    var stored = localStorage.getItem("tokenmingate_user");
    if (stored) {
      try {
        state.currentUser = JSON.parse(stored);
        showApp();
        return;
      } catch (e) {
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
    loadResearchData();
    loadDbStatus();
  }

  function switchTab(tabId) {
    state.activeTab = tabId;
    var tabs = document.querySelectorAll(".nav-tab");
    tabs.forEach(function(t) { t.classList.remove("active"); });
    
    hideAllPanes();

    if (tabId === 'playground') {
      tabs[0].classList.add("active");
      document.getElementById("panePlayground").classList.add("active");
    } else if (tabId === 'research') {
      tabs[1].classList.add("active");
      document.getElementById("paneResearch").classList.add("active");
      loadResearchData();
    } else if (tabId === 'ledger') {
      tabs[2].classList.add("active");
      document.getElementById("paneLedger").classList.add("active");
      loadLedger();
    } else if (tabId === 'cache') {
      tabs[3].classList.add("active");
      document.getElementById("paneCache").classList.add("active");
      loadCacheEntries();
    } else if (tabId === 'supadb') {
      tabs[4].classList.add("active");
      document.getElementById("paneSupadb").classList.add("active");
      loadDbStatus();
    }
  }

  function hideAllPanes() {
    document.querySelectorAll(".tab-pane").forEach(function(p) { p.classList.remove("active"); });
  }

  function switchAuthTab(type) {
    state.activeAuthTab = type;
    var subtabs = document.querySelectorAll(".auth-subtab");
    subtabs[0].classList.toggle("active", type === 'login');
    subtabs[1].classList.toggle("active", type === 'register');
    document.getElementById("authLoginForm").style.display = (type === 'login' ? "block" : "none");
    document.getElementById("authRegisterForm").style.display = (type === 'register' ? "block" : "none");
  }

  function loadDemoUsers() {
    fetch("/auth/demo-users")
      .then(function(r) { return r.json(); })
      .then(function(users) {
        state.demoUsers = users;
        var html = users.map(function(u) {
          return '<button class="demo-user-card" onclick="loginDemo(\'' + u.email + '\')">' +
            '<div class="duc-name">' + esc(u.name) + '</div>' +
            '<div class="duc-role">' + esc(u.role).toUpperCase() + '</div>' +
            '<div class="duc-team">Team: ' + esc(u.team_id) + '</div>' +
            '</button>';
        }).join("");
        document.getElementById("demoUsersList").innerHTML = html;
      });
  }

  window.loginDemo = function(email) {
    var u = state.demoUsers.find(function(x) { return x.email === email; });
    if (!u) return;
    document.getElementById("loginEmail").value = u.email;
    document.getElementById("loginPassword").value = "demo";
    handleLogin();
  };

  function handleLogin() {
    var email = document.getElementById("loginEmail").value;
    var password = document.getElementById("loginPassword").value;

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
      localStorage.setItem("tokenmingate_user", JSON.stringify(user));
      showApp();
    })
    .catch(function(err) {
      alert("Login failed: " + err.message);
    });
  }

  function handleRegister() {
    var name = document.getElementById("regName").value;
    var email = document.getElementById("regEmail").value;
    var password = document.getElementById("regPassword").value;
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
      localStorage.setItem("tokenmingate_user", JSON.stringify(user));
      showApp();
    })
    .catch(function(err) {
      alert(err.message);
    });
  }

  function signOut() {
    state.currentUser = null;
    localStorage.removeItem("tokenmingate_user");
    showAuth();
  }

  function setPrompt(txt) {
    document.getElementById("promptInput").value = txt;
  }

  // Execute Gateway Request with Full Pipeline Extraction
  function executeGatewayRequest() {
    var prompt = document.getElementById("promptInput").value.trim();
    if (!prompt) {
      alert("Please enter a prompt first");
      return;
    }

    var btn = document.getElementById("btnSendPrompt");
    btn.disabled = true;
    btn.innerHTML = '<span>Processing Algorithm 1 Pipeline...</span>';

    var ttl = parseInt(document.getElementById("topicTtlSelect").value, 10);
    var tau = parseFloat(document.getElementById("tauSelect").value);
    var model = document.getElementById("modelModeSelect").value;

    var payload = {
      model: model,
      messages: [{ role: "user", content: prompt }],
      team_id: state.currentUser.team_id,
      user_id: state.currentUser.id,
      app_id: state.currentUser.app_id || "web",
      ttl_seconds: ttl,
      tau: tau,
      temperature: 0.0
    };

    fetch("/api/chat/pipeline", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + state.currentUser.api_key
      },
      body: JSON.stringify(payload)
    })
    .then(function(r) {
      if (!r.ok) return r.json().then(function(e) { throw new Error(e.detail || e.error?.message || "Request failed"); });
      return r.json();
    })
    .then(function(res) {
      renderPipelineExecution(res);
      btn.disabled = false;
      btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg><span>Send Request Through TokenMinGate</span>';
    })
    .catch(function(err) {
      alert("Gateway error: " + err.message);
      btn.disabled = false;
      btn.innerHTML = '<span>Try Again</span>';
    });
  }

  function renderPipelineExecution(data) {
    var p = data.pipeline;
    state.lastLogId = p.log_id;

    document.getElementById("pipelineStatusBadge").textContent = (data.cache_hit ? "CACHE HIT: ZERO TOKENS" : "DISPATCHED TO " + p.tier.toUpperCase());
    document.getElementById("pipelineStatusBadge").className = "step-badge " + (data.cache_hit ? "badge-hit" : "badge-tier");

    // 1. Namespace
    document.getElementById("valNamespace").textContent = p.namespace.hash.substring(0, 16) + "...";
    document.getElementById("stepNamespaceBadge").textContent = "Team: " + p.namespace.team_id;

    // 2. L1 Exact Match
    var l1 = p.l1_cache;
    var stepL1 = document.getElementById("stepL1");
    stepL1.classList.toggle("hit", l1.hit);
    document.getElementById("stepL1Badge").textContent = l1.hit ? "HIT (0 LLM TOKENS)" : "MISS";
    document.getElementById("stepL1Badge").className = "step-badge " + (l1.hit ? "badge-hit" : "badge-miss");
    document.getElementById("valL1Status").textContent = l1.hit ? "Key match in RAM! Billed $0.00" : "Not found in L1 hash table";

    // 3. L2 Semantic Cache
    var l2 = p.l2_cache;
    var stepL2 = document.getElementById("stepL2");
    stepL2.classList.toggle("hit", l2.hit);
    document.getElementById("stepL2Badge").textContent = l2.hit ? "SEMANTIC HIT" : (l1.hit ? "SKIPPED (L1 HIT)" : "MISS");
    document.getElementById("stepL2Badge").className = "step-badge " + (l2.hit ? "badge-hit" : (l1.hit ? "badge-tier" : "badge-miss"));
    document.getElementById("valL2Sim").textContent = l2.similarity != null ? l2.similarity.toFixed(4) : "N/A";
    document.getElementById("valL2Tau").textContent = l2.effective_threshold != null ? l2.effective_threshold.toFixed(4) : "N/A";
    document.getElementById("valL2Age").textContent = l2.age_seconds != null ? (l2.age_seconds + "s (Lifespan: " + l2.ttl_seconds + "s)") : "N/A";

    // 4. Pruning
    var pr = p.pruning;
    document.getElementById("valPrunedTokens").textContent = pr.original_tokens + " &rarr; " + pr.pruned_tokens + " tokens";
    document.getElementById("valPrunedSaved").textContent = pr.tokens_saved + " tokens saved (" + pr.reduction_pct + "%)";
    document.getElementById("stepPruneBadge").textContent = pr.tokens_saved > 0 ? ("-" + pr.tokens_saved + " TOKENS") : "PRESERVED";
    document.getElementById("stepPruneBadge").className = "step-badge " + (pr.tokens_saved > 0 ? "badge-hit" : "badge-tier");

    // 5. Complexity Router
    var cr = p.complexity;
    document.getElementById("sigLen").textContent = cr.signals.length.toFixed(2);
    document.getElementById("fillLen").style.width = (cr.signals.length * 100) + "%";
    document.getElementById("sigInst").textContent = cr.signals.instruction.toFixed(2);
    document.getElementById("fillInst").style.width = (cr.signals.instruction * 100) + "%";
    document.getElementById("sigReason").textContent = cr.signals.reasoning.toFixed(2);
    document.getElementById("fillReason").style.width = (cr.signals.reasoning * 100) + "%";
    document.getElementById("sigCode").textContent = cr.signals.code.toFixed(2);
    document.getElementById("fillCode").style.width = (cr.signals.code * 100) + "%";

    document.getElementById("valTotalScore").textContent = cr.score.toFixed(4) + " (Cutoffs: 0.35 / 0.75)";
    document.getElementById("valTierModel").textContent = cr.tier.toUpperCase() + " (" + cr.model + ")";
    document.getElementById("stepRouteBadge").textContent = cr.tier.toUpperCase();
    document.getElementById("stepRouteBadge").className = "step-badge " + (cr.tier === "economy" ? "badge-hit" : (cr.tier === "balanced" ? "badge-tier" : "badge-miss"));

    // Response & Savings
    document.getElementById("responseBox").style.display = "block";
    document.getElementById("responseOutput").textContent = data.choices[0].message.content;

    var sv = p.savings;
    document.getElementById("savingsBanner").style.display = "grid";
    document.getElementById("bannerDeltaC").textContent = sv.delta_c_pct + "%";
    document.getElementById("bannerCost").textContent = fmtUsd(sv.cost_usd);
    document.getElementById("bannerTokensSaved").textContent = fmtInt(sv.tokens_saved);
    document.getElementById("bannerLatency").textContent = sv.latency_ms + " ms";

    // Show feedback buttons if L2 hit
    document.getElementById("l2FeedbackControls").style.display = (l2.hit ? "block" : "none");
    document.getElementById("btnFeedbackGood").className = "btn-feedback";
    document.getElementById("btnFeedbackBad").className = "btn-feedback";
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
