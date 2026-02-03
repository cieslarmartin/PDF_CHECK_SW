# pdf_dokucheck_pro_v41_with_api.py
# PDF DokuCheck PRO - Build 41 (Flask verze s API + Agent data)
# AKTUALIZACE 41: Excel export, TSA filtr, příprava pro licenční systém
# Režimy: "Z Agenta" (primární) | "Lokální" (upload/disk)
#
# © 2025 Ing. Martin Cieślar
#
# Spuštění: python pdf_check_web_main.py

from flask import Flask, request, jsonify, render_template_string, render_template, Response, redirect, url_for, session, flash
import io
import re
import os
import json
import subprocess
import threading
import webbrowser

# NOVÉ IMPORTY PRO API:
from api_endpoint import register_api_routes, consume_one_time_token
from database import Database

# NOVÉ: Admin systém
from admin_routes import admin_bp
from version import WEB_BUILD

# =============================================================================
# AUTOMATICKÉ UVOLNĚNÍ PORTU
# =============================================================================

def kill_port(port=5000):
    """Zabije všechny procesy na daném portu před spuštěním"""
    try:
        result = subprocess.run(
            f'netstat -ano | findstr :{port}',
            shell=True, capture_output=True, text=True
        )
        killed = []
        for line in result.stdout.strip().split('\n'):
            if 'LISTENING' in line:
                parts = line.strip().split()
                if parts:
                    pid = parts[-1]
                    if pid not in killed and pid.isdigit():
                        subprocess.run(f'taskkill /F /PID {pid}', shell=True, 
                                      capture_output=True, stderr=subprocess.DEVNULL)
                        killed.append(pid)
        if killed:
            print(f"  Uvolněn port {port} (ukončeno {len(killed)} procesů)")
    except:
        pass

app = Flask(__name__, template_folder='templates')
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

# NOVÉ: Secret key pro sessions (admin panel)
import os
app.secret_key = os.environ.get('SECRET_KEY', 'pdfcheck_secret_key_2025_change_in_production')
app.config['SESSION_COOKIE_SECURE'] = False  # V produkci nastavit na True s HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 hodin

# =============================================================================
# HTML ŠABLONA - NOVÝ DESIGN V26 se splash screenem
# =============================================================================

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="cs">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PDF DokuCheck PRO</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            font-family: 'Segoe UI', Tahoma, sans-serif; 
            min-height: 100vh; 
            background: #f3f4f6;
            color: #374151;
            font-size: 14px;
        }

        /* ===== HLAVNÍ APLIKACE ===== */
        #main-app { min-height: 100vh; display: flex; flex-direction: column; }

        /* Header */
        #header {
            background: white;
            border-bottom: 2px solid #1e5a8a;
            padding: 8px 16px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        .header-logo { display: flex; align-items: center; gap: 12px; }
        .header-logo-text { text-align: left; }
        .header-logo-title { font-size: 1.1em; font-weight: 700; }
        .header-logo-title .pdf { color: #1e5a8a; }
        .header-logo-title .doku { color: #374151; }
        .header-logo-title .pro { color: #9ca3af; font-weight: 400; }
        .header-logo-subtitle { color: #9ca3af; font-size: 0.7em; }
        .header-actions { display: flex; align-items: center; gap: 12px; }
        .header-btn {
            padding: 6px 12px;
            background: transparent;
            border: none;
            color: #6b7280;
            font-size: 0.85em;
            cursor: pointer;
        }
        .header-btn:hover { color: #1e5a8a; }
        .header-divider { width: 1px; height: 20px; background: #e5e7eb; }
        .header-build { font-size: 0.7em; color: #d1d5db; }

        /* License Badge */
        .license-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 0.75em;
            font-weight: 600;
        }
        .license-badge.free { background: #f3f4f6; color: #6b7280; }
        .license-badge.basic { background: #dbeafe; color: #1d4ed8; }
        .license-badge.pro { background: #ede9fe; color: #7c3aed; }
        .license-badge.enterprise { background: #fef3c7; color: #b45309; }
        .license-badge-icon { font-size: 1.1em; }

        /* Feature Lock */
        .feature-locked {
            position: relative;
            opacity: 0.6;
            pointer-events: none;
        }
        .feature-locked::after {
            content: '🔒';
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-size: 1.2em;
        }
        .lock-icon { color: #9ca3af; margin-left: 4px; }
        .upgrade-hint {
            font-size: 0.7em;
            color: #7c3aed;
            background: #ede9fe;
            padding: 2px 6px;
            border-radius: 4px;
            cursor: pointer;
        }
        .upgrade-hint:hover { background: #ddd6fe; }

        /* Layout */
        #layout { display: flex; flex: 1; overflow: hidden; }

        /* Sidebar */
        #sidebar {
            width: 280px;
            background: white;
            border-right: 1px solid #e5e7eb;
            display: flex;
            flex-direction: column;
        }
        .sidebar-content { flex: 1; overflow-y: auto; padding: 12px; }
        .sidebar-footer { padding: 12px; border-top: 1px solid #e5e7eb; }

        /* Mode switcher */
        .mode-switcher { display: flex; background: #f3f4f6; border-radius: 8px; padding: 4px; margin-bottom: 12px; }
        .mode-btn {
            flex: 1;
            padding: 10px;
            border: none;
            border-radius: 6px;
            font-size: 0.85em;
            font-weight: 500;
            cursor: pointer;
            background: transparent;
            color: #6b7280;
        }
        .mode-btn.active { background: #1e5a8a; color: white; }
        .mode-btn:not(.active):hover { background: #e5e7eb; }

        /* Drop zone */
        .drop-zone {
            border: 2px dashed #d1d5db;
            border-radius: 8px;
            padding: 24px;
            text-align: center;
            cursor: pointer;
            margin-bottom: 12px;
            background: #f9fafb;
        }
        .drop-zone:hover, .drop-zone.dragover { border-color: #1e5a8a; background: #eff6ff; }
        .drop-zone-icon { font-size: 2em; opacity: 0.5; margin-bottom: 8px; }
        .drop-zone-text { font-weight: 500; color: #374151; }
        .drop-zone-hint { font-size: 0.75em; color: #9ca3af; }

        /* Buttons */
        .btn {
            width: 100%;
            padding: 10px 16px;
            border: none;
            border-radius: 8px;
            font-size: 0.85em;
            font-weight: 500;
            cursor: pointer;
            margin-bottom: 8px;
        }
        .btn-primary { background: #1e5a8a; color: white; }
        .btn-primary:hover { background: #174a6e; }
        .btn-cyan { background: #0891b2; color: white; }
        .btn-cyan:hover { background: #0e7490; }
        .btn-green { background: #16a34a; color: white; }
        .btn-green:hover { background: #15803d; }
        .btn-orange { background: #ea580c; color: white; }
        .btn-orange:hover { background: #c2410c; }
        .btn-gray { background: #6b7280; color: white; }
        .btn-gray:hover { background: #4b5563; }

        /* Disk mode */
        .disk-mode { background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; }
        .disk-path {
            padding: 8px;
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 4px;
            font-size: 0.75em;
            color: #6b7280;
            margin-bottom: 8px;
            word-break: break-all;
        }
        .disk-tip { margin-top: 12px; padding: 8px; background: #eff6ff; border-radius: 4px; font-size: 0.75em; color: #1e5a8a; }

        /* Filters */
        .filter-section { margin-top: 16px; padding-top: 12px; border-top: 1px solid #e5e7eb; }
        .filter-title { font-size: 0.7em; font-weight: 600; color: #9ca3af; text-transform: uppercase; margin-bottom: 8px; }
        .filter-buttons { display: flex; gap: 4px; }
        .filter-btn {
            flex: 1;
            padding: 4px 6px;
            border: 1px solid #e5e7eb;
            border-radius: 4px;
            background: white;
            font-size: 0.7em;
            cursor: pointer;
            color: #6b7280;
        }
        .filter-btn.active { background: #1e5a8a; color: white; border-color: #1e5a8a; }
        .filter-btn:not(.active):hover { border-color: #1e5a8a; }
        .sort-select { width: 100%; padding: 8px; border: 1px solid #e5e7eb; border-radius: 4px; font-size: 0.75em; }

        /* Legend */
        .legend { margin-top: 16px; padding: 8px; background: #f9fafb; border-radius: 4px; font-size: 0.7em; color: #6b7280; }
        .legend-title { font-weight: 600; color: #374151; margin-bottom: 4px; }
        .legend-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 4px; }
        .legend-item { display: flex; align-items: center; gap: 4px; }

        /* Main content */
        #main-content { flex: 1; display: flex; flex-direction: column; overflow: hidden; padding: 12px; }

        /* Summary */
        .summary-bar {
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 8px 16px;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 8px;
        }
        .summary-total { font-weight: 600; color: #374151; }
        .summary-total span { color: #1e5a8a; }
        .summary-stats { display: flex; gap: 16px; font-size: 0.8em; }
        .stat-ok { color: #16a34a; }
        .stat-fail { color: #dc2626; }

        /* Actions */
        .actions-bar { display: flex; gap: 8px; margin-bottom: 8px; }
        .action-btn {
            padding: 6px 12px;
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 4px;
            font-size: 0.75em;
            cursor: pointer;
        }
        .action-btn:hover { background: #f9fafb; }
        .action-btn.danger { color: #dc2626; border-color: #fecaca; }
        .action-btn.danger:hover { background: #fef2f2; }

        /* Active filter */
        .active-filter {
            background: #eff6ff;
            border: 1px solid #bfdbfe;
            border-radius: 8px;
            padding: 8px 12px;
            margin-bottom: 8px;
            display: none;
            align-items: center;
            gap: 12px;
            font-size: 0.8em;
            color: #1e5a8a;
        }
        .active-filter.visible { display: flex; }
        .active-filter-clear {
            background: white;
            border: 1px solid #bfdbfe;
            border-radius: 4px;
            padding: 4px 8px;
            font-size: 0.75em;
            cursor: pointer;
            font-weight: 600;
        }
        .active-filter-clear:hover { background: #1e5a8a; color: white; }

        /* Table header */
        .table-header {
            background: #1f2937;
            color: white;
            border-radius: 8px 8px 0 0;
            display: grid;
            grid-template-columns: 3fr 1fr 1fr 2.5fr 1.5fr 1.5fr;
            gap: 4px;
            font-size: 0.75em;
            font-weight: 600;
        }
        .table-header-cell { padding: 10px 8px; position: relative; }
        .table-header-btn {
            background: transparent;
            border: none;
            color: white;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 4px;
            width: 100%;
            font-weight: 600;
            font-size: 1em;
        }
        .table-header-btn:hover { color: #93c5fd; }
        .table-header-btn .arrow { opacity: 0.5; font-size: 0.8em; }

        /* Filter dropdown */
        .filter-dropdown {
            position: absolute;
            top: 100%;
            left: 0;
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 100;
            min-width: 160px;
            max-height: 250px;
            overflow-y: auto;
            display: none;
        }
        .filter-dropdown.visible { display: block; }
        .filter-dropdown-item {
            padding: 8px 12px;
            font-size: 0.85em;
            cursor: pointer;
            color: #374151;
            display: flex;
            align-items: center;
            gap: 8px;
            border: none;
            background: transparent;
            width: 100%;
            text-align: left;
        }
        .filter-dropdown-item:hover { background: #eff6ff; }
        .filter-dropdown-item.clear { border-bottom: 1px solid #e5e7eb; font-weight: 500; color: #6b7280; }
        .filter-dot { width: 8px; height: 8px; border-radius: 50%; }
        .filter-dropdown-search { padding: 8px; border-bottom: 1px solid #e5e7eb; }
        .filter-dropdown-search input {
            width: 100%;
            padding: 6px 8px;
            border: 1px solid #e5e7eb;
            border-radius: 4px;
            font-size: 0.85em;
        }

        /* Results */
        .results-container {
            flex: 1;
            background: white;
            border: 1px solid #e5e7eb;
            border-top: none;
            border-radius: 0 0 8px 8px;
            overflow-y: auto;
        }

        /* Batch */
        .batch { border-bottom: 1px solid #e5e7eb; }
        .batch:last-child { border-bottom: none; }
        .batch-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 8px 12px;
            background: #f9fafb;
            cursor: pointer;
        }
        .batch-header:hover { background: #f3f4f6; }
        .batch-header-left { display: flex; align-items: center; gap: 8px; }
        .batch-arrow { color: #9ca3af; font-size: 0.8em; transition: transform 0.2s; }
        .batch-arrow.collapsed { transform: rotate(-90deg); }
        .batch-name { font-weight: 500; color: #374151; }
        .batch-time { font-size: 0.75em; color: #9ca3af; }
        .batch-folder { font-size: 0.7em; color: #6b7280; margin-left: 8px; padding: 2px 6px; background: #f3f4f6; border-radius: 4px; }
        .batch-header-right { display: flex; align-items: center; gap: 12px; font-size: 0.75em; }
        .batch-stat { color: #16a34a; }
        .batch-count { color: #9ca3af; }
        .batch-btn {
            padding: 4px 8px;
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 4px;
            font-size: 0.8em;
            cursor: pointer;
        }
        .batch-btn:hover { background: #f9fafb; }
        .batch-btn.delete:hover { background: #fef2f2; border-color: #fecaca; color: #dc2626; }
        .batch-content { display: none; padding-left: 6px; }
        .batch-content.visible { display: block; }

        /* Folder */
        .folder { border-left: 1px dashed #e5e7eb; margin-left: 3px; }
        .folder-header { display: flex; align-items: center; gap: 6px; padding: 4px 8px; cursor: pointer; }
        .folder-header:hover { background: #f9fafb; }
        .folder-arrow { color: #9ca3af; font-size: 0.7em; transition: transform 0.2s; flex-shrink: 0; }
        .folder-arrow.collapsed { transform: rotate(-90deg); }
        .folder-icon { color: #fbbf24; flex-shrink: 0; }
        .folder-name { font-weight: 500; color: #374151; font-size: 0.8em; min-width: 0; }
        .folder-stats { font-size: 0.7em; color: #9ca3af; flex-shrink: 0; }
        .folder-content { display: none; margin-left: 3px; border-left: 1px dashed #e5e7eb; padding-left: 3px; }
        .folder-content.visible { display: block; }
        .folder-flat { padding: 0; }

        /* File row */
        .file-row-wrapper { border-bottom: 1px solid #f3f4f6; }
        .file-row-wrapper:last-child { border-bottom: none; }
        .file-row {
            display: grid;
            grid-template-columns: 3fr 1fr 1fr 2.5fr 1.5fr 1.5fr;
            gap: 4px;
            padding: 8px;
            align-items: center;
        }
        .file-row:hover { background: #eff6ff; }
        .file-row.has-sigs { cursor: pointer; }
        .file-row.has-sigs:hover { background: #dbeafe; }
        .file-name { font-weight: 500; color: #374151; font-size: 0.8em; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .file-cell { text-align: center; font-size: 0.75em; }
        .file-signer { color: #6b7280; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .file-signer.sig-expandable { color: #1e5a8a; font-weight: 600; cursor: pointer; }
        .file-ckait { font-family: monospace; color: #1e5a8a; }

        /* Rozbalovací podpisy */
        .signatures-detail {
            display: none;
            background: #f8fafc;
            border-top: 1px solid #e5e7eb;
            padding: 8px 8px 8px 32px;
        }
        .signatures-detail.visible { display: block; }
        .signature-row {
            display: grid;
            grid-template-columns: 40px 2fr 1.2fr 80px 1fr;
            gap: 8px;
            padding: 6px 8px;
            background: white;
            border-radius: 4px;
            margin-bottom: 4px;
            font-size: 0.75em;
            align-items: center;
            border: 1px solid #e5e7eb;
        }
        .signature-row:last-child { margin-bottom: 0; }
        .sig-index { color: #9ca3af; font-weight: 600; }
        .sig-name { color: #374151; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .sig-ckait { font-family: monospace; color: #1e5a8a; text-align: center; }
        .sig-tsa { text-align: center; }
        .sig-date { color: #6b7280; font-size: 0.9em; }

        /* Badges */
        .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75em; font-weight: 600; }
        .badge-green { background: #dcfce7; color: #16a34a; }
        .badge-yellow { background: #fef9c3; color: #ca8a04; }
        .badge-orange { background: #ffedd5; color: #ea580c; }
        .badge-red { background: #fee2e2; color: #dc2626; }
        .badge-gray { background: #f3f4f6; color: #9ca3af; }

        /* Footer */
        #footer {
            background: white;
            border-top: 1px solid #e5e7eb;
            padding: 8px 16px;
            text-align: center;
            font-size: 0.7em;
            color: #9ca3af;
        }
        #footer strong { color: #6b7280; }

        /* Modal */
        .modal-overlay {
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.5);
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 1000;
            padding: 20px;
        }
        .modal-overlay.visible { display: flex; }
        .modal {
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            max-width: 500px;
            width: 100%;
            max-height: 80vh;
            overflow: hidden;
        }
        .modal-header {
            background: linear-gradient(135deg, #1e5a8a, #2d7ab8);
            color: white;
            padding: 16px 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .modal-header h3 { font-weight: 600; }
        .modal-close { background: transparent; border: none; color: rgba(255,255,255,0.8); font-size: 1.5em; cursor: pointer; }
        .modal-close:hover { color: white; }
        .modal-tabs { display: flex; border-bottom: 1px solid #e5e7eb; background: #f9fafb; }
        .modal-tab {
            flex: 1;
            padding: 12px;
            border: none;
            background: transparent;
            font-size: 0.85em;
            font-weight: 500;
            color: #6b7280;
            cursor: pointer;
        }
        .modal-tab.active { background: white; color: #1e5a8a; border-bottom: 2px solid #1e5a8a; }
        .modal-tab:hover:not(.active) { background: #f3f4f6; }
        .modal-content { padding: 20px; overflow-y: auto; max-height: 50vh; font-size: 0.9em; line-height: 1.6; }
        .modal-content h4 { font-size: 1.1em; margin-bottom: 12px; color: #1f2937; }
        .modal-content ul { margin-left: 16px; margin-bottom: 12px; }
        .modal-content li { margin-bottom: 4px; }
        .modal-content .info-box { padding: 12px; border-radius: 8px; margin: 12px 0; }
        .modal-content .info-box.green { background: #dcfce7; border: 1px solid #bbf7d0; color: #166534; }
        .modal-content .info-box.blue { background: #dbeafe; border: 1px solid #bfdbfe; color: #1e40af; }
        .modal-content .info-box.yellow { background: #fef9c3; border: 1px solid #fef08a; color: #854d0e; }
        .modal-footer { padding: 12px 20px; background: #fffbeb; border-top: 1px solid #fef08a; font-size: 0.75em; color: #92400e; }

        .hidden { display: none !important; }

        /* Preview file list */
        .preview-file-item {
            display: flex;
            justify-content: space-between;
            padding: 8px 12px;
            border-bottom: 1px solid #f3f4f6;
            font-size: 0.85em;
        }
        .preview-file-item:hover { background: #f9fafb; }
        .preview-file-name {
            color: #374151;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            flex: 1;
            margin-right: 12px;
        }
        .preview-file-size { color: #9ca3af; white-space: nowrap; }
        .preview-more {
            padding: 12px;
            text-align: center;
            color: #6b7280;
            font-style: italic;
            background: #f9fafb;
        }
    </style>
</head>
<body>
    <!-- Diagnostika: zobrazí chybu JS přímo na stránce (nemusíte otevírat F12) -->
    <div id="js-error-box" style="display:none;position:fixed;top:0;left:0;right:0;z-index:99999;background:#dc2626;color:white;padding:14px 20px;font-family:Consolas,monospace;font-size:13px;line-height:1.4;box-shadow:0 4px 12px rgba(0,0,0,0.3);max-height:50vh;overflow:auto;">
        <strong>Chyba na stránce:</strong><br>
        <span id="js-error-text"></span>
        <div style="margin-top:10px;font-size:11px;opacity:0.9;">Pošlete tento text vývojáři. Konzole: F12 → záložka Console.</div>
        <button onclick="document.getElementById('js-error-box').style.display='none'" style="margin-top:10px;padding:6px 12px;background:rgba(255,255,255,0.2);border:1px solid white;color:white;cursor:pointer;border-radius:4px;">Skrýt</button>
    </div>
    <script>
    window.onerror = function(msg, url, line, col, err) {
        var box = document.getElementById('js-error-box');
        var text = document.getElementById('js-error-text');
        if (box && text) {
            text.textContent = msg + (url ? ' | ' + url + ':' + line : '');
            box.style.display = 'block';
        }
        return false;
    };
    window.addEventListener('unhandledrejection', function(e) {
        var box = document.getElementById('js-error-box');
        var text = document.getElementById('js-error-text');
        if (box && text) {
            text.textContent = 'Promise: ' + (e.reason && e.reason.message ? e.reason.message : String(e.reason));
            box.style.display = 'block';
        }
    });
    </script>
    <!-- ===== HLAVNÍ APLIKACE ===== -->
    <div id="main-app">
        <header id="header">
            <div class="header-logo">
                <svg width="36" height="45" viewBox="0 0 64 80" fill="none">
                    <path d="M8 8H48L56 16V72C56 74.2 54.2 76 52 76H12C9.8 76 8 74.2 8 72V8Z" fill="#E5E7EB"/>
                    <path d="M4 4H44L52 12V68C52 70.2 50.2 72 48 72H8C5.8 72 4 70.2 4 68V4Z" fill="white" stroke="#9CA3AF" stroke-width="2"/>
                    <path d="M44 4V12H52" stroke="#9CA3AF" stroke-width="2" fill="#F3F4F6"/>
                    <rect x="8" y="10" width="28" height="14" rx="3" fill="#1e5a8a"/>
                    <text x="22" y="21" text-anchor="middle" fill="white" font-size="9" font-weight="bold">PDF</text>
                    <g fill="#22c55e" font-size="14" font-weight="bold">
                        <text x="12" y="42">✓</text><text x="26" y="42">✓</text>
                        <text x="12" y="54">✓</text><text x="26" y="54">✓</text>
                        <text x="12" y="66">✓</text><text x="26" y="66">✓</text>
                    </g>
                </svg>
                <div class="header-logo-text">
                    <div class="header-logo-title">
                        <span class="pdf">PDF</span> <span class="doku">DokuCheck</span> <span class="pro">PRO</span>
                    </div>
                    <div class="header-logo-subtitle">Kontrola projektové dokumentace</div>
                </div>
            </div>
            <div class="header-actions">
                <span id="logged-in-area" style="display:none;font-size:0.85em;color:#6b7280;">
                    Přihlášen jako: <strong id="logged-in-display"></strong>
                    <button type="button" class="header-btn" onclick="doLogout()" style="margin-left:8px;">Odhlásit</button>
                </span>
                <button type="button" id="header-login-btn" class="header-btn" onclick="focusLogin()" style="font-weight:600;color:#1e5a8a;">Přihlásit se</button>
                <span id="script-ok-test" style="font-size:10px;color:#9ca3af;margin-right:8px;" title="Pokud se zde zobrazí Script OK, skript se načetl."></span>
                <span id="license-badge" class="license-badge free">
                    <span class="license-badge-icon">🆓</span>
                    <span id="license-tier-name">Free</span>
                </span>
                <div class="header-divider"></div>
                <button class="header-btn" onclick="showHelpModal()">❓ Nápověda</button>
                <div class="header-divider"></div>
                <button class="header-btn" onclick="showInfoModal()">📘 Info</button>
                <span class="header-build">v42</span>
            </div>
        </header>

        <div id="layout">
            <div id="sidebar">
                <div class="sidebar-content">
                    <div class="mode-switcher">
                        <button class="mode-btn active" id="mode-agent" onclick="setMode('agent')">🌐 Z Agenta</button>
                        <button class="mode-btn" id="mode-local" onclick="setMode('local')">💻 Lokální</button>
                    </div>

                    <!-- AGENT MODE - načítání dat z API -->
                    <div id="agent-mode">
                        <div id="login-block" style="padding:12px;background:#f9fafb;border-radius:8px;margin-bottom:12px;border:1px solid #e5e7eb;">
                            <div style="font-size:0.85em;font-weight:600;color:#374151;margin-bottom:8px;">Přihlášení (e-mail + heslo)</div>
                            <input type="text" id="login-email" placeholder="E-mail" style="width:100%;padding:8px 10px;margin-bottom:6px;border:1px solid #e5e7eb;border-radius:6px;font-size:0.9em;" onkeydown="if(event.key==='Enter'){ event.preventDefault(); doLogin(); }">
                            <input type="password" id="login-password" placeholder="Heslo" style="width:100%;padding:8px 10px;margin-bottom:8px;border:1px solid #e5e7eb;border-radius:6px;font-size:0.9em;" onkeydown="if(event.key==='Enter'){ event.preventDefault(); doLogin(); }">
                            <button type="button" class="btn btn-primary" onclick="doLogin()" style="width:100%;padding:8px;">Přihlásit</button>
                        </div>
                        <div style="text-align:center;padding:16px;background:#eff6ff;border-radius:8px;margin-bottom:12px;">
                            <div style="font-size:2em;margin-bottom:8px;">🌐</div>
                            <div style="font-weight:600;color:#1e5a8a;">Výsledky z Desktop Agenta</div>
                            <div style="font-size:0.8em;color:#6b7280;margin-top:4px;">Data odeslaná z lokální aplikace</div>
                        </div>
                        <button class="btn btn-primary" onclick="loadAgentResults()">🔄 Načíst výsledky</button>
                        <div id="agent-stats" style="margin-top:16px;padding:12px;background:#f9fafb;border-radius:8px;display:none;">
                            <div style="font-size:0.75em;color:#6b7280;margin-bottom:8px;">STATISTIKY</div>
                            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                                <div style="text-align:center;padding:8px;background:white;border-radius:4px;">
                                    <div style="font-size:1.5em;font-weight:700;color:#1e5a8a;" id="agent-total">0</div>
                                    <div style="font-size:0.7em;color:#6b7280;">Celkem</div>
                                </div>
                                <div style="text-align:center;padding:8px;background:white;border-radius:4px;">
                                    <div style="font-size:1.5em;font-weight:700;color:#16a34a;" id="agent-pdfa-ok">0</div>
                                    <div style="font-size:0.7em;color:#6b7280;">PDF/A-3</div>
                                </div>
                            </div>
                        </div>
                        <div id="free-trial-hint" style="margin-top:12px;padding:12px;background:#fef3c7;border:1px solid #f59e0b;border-radius:8px;font-size:0.85em;">
                            <strong>Bez přihlášení (Free trial):</strong> Zkontrolovat PDF můžete v režimu <strong>Lokální</strong> – klikněte vlevo na „Lokální“ a přetáhněte soubory nebo vyberte soubory (max 5).
                        </div>
                        <div class="disk-tip" style="margin-top:12px;">
                            💡 <strong>Tip:</strong> Desktop agent kontroluje PDF lokálně a odesílá výsledky sem.
                        </div>
                    </div>

                    <!-- UPLOAD MODE - původní funkcionalita -->
                    <div id="upload-mode" class="hidden">
                        <div class="drop-zone" id="drop-zone">
                            <div class="drop-zone-icon">📂</div>
                            <div class="drop-zone-text">Přetáhněte PDF soubory</div>
                            <div class="drop-zone-hint">nebo složky sem</div>
                        </div>
                        <button class="btn btn-primary" onclick="selectFiles()">📄 Vybrat soubory</button>
                        <button class="btn btn-cyan" onclick="selectFolder()">📁 Vybrat složku</button>
                        <input type="file" id="file-input" multiple accept=".pdf" style="display:none">
                        <input type="file" id="folder-input" webkitdirectory style="display:none">
                    </div>

                    <div id="disk-mode" class="hidden">
                        <div class="disk-mode">
                            <div class="disk-path" id="disk-path">Vyberte složku pro skenování</div>
                            <button class="btn btn-cyan" onclick="selectDiskFolder()">📁 Vybrat složku na disku</button>
                            <div id="disk-scan-section" class="hidden">
                                <div style="font-size:0.75em;color:#6b7280;margin:8px 0;" id="disk-count"></div>
                                <button class="btn btn-green" onclick="scanDiskFolder()">🔍 Skenovat složku</button>
                            </div>
                            <div class="disk-tip">💡 <strong>Tip:</strong> Disk mód čte soubory přímo bez uploadu.</div>
                        </div>
                    </div>

                    <div class="filter-section">
                        <div class="filter-title">Filtr PDF/A-3</div>
                        <div class="filter-buttons" id="filter-pdfa">
                            <button class="filter-btn active" data-value="all">Vše</button>
                            <button class="filter-btn" data-value="ok">✓ A-3</button>
                            <button class="filter-btn" data-value="fail">✗ A-3</button>
                        </div>
                    </div>

                    <div class="filter-section" style="margin-top:10px;padding-top:0;border-top:none;">
                        <div class="filter-title">Filtr Podpis</div>
                        <div class="filter-buttons" id="filter-sig">
                            <button class="filter-btn active" data-value="all">Vše</button>
                            <button class="filter-btn" data-value="ok">✓ Podpis</button>
                            <button class="filter-btn" data-value="fail">✗ Podpis</button>
                        </div>
                    </div>

                    <div class="filter-section" style="margin-top:10px;padding-top:0;border-top:none;">
                        <div class="filter-title">Filtr Razítko (VČR)</div>
                        <div class="filter-buttons" id="filter-tsa">
                            <button class="filter-btn active" data-value="all">Vše</button>
                            <button class="filter-btn" data-value="tsa">✓ VČR</button>
                            <button class="filter-btn" data-value="local">LOK</button>
                            <button class="filter-btn" data-value="none">Bez razítka</button>
                        </div>
                    </div>

                    <div class="filter-section" style="margin-top:10px;padding-top:0;border-top:none;">
                        <div class="filter-title">Řazení</div>
                        <select class="sort-select" id="sort-select" onchange="renderResults()">
                            <option value="name-asc">Podle názvu (A-Z)</option>
                            <option value="name-desc">Podle názvu (Z-A)</option>
                            <option value="path-asc">Podle cesty (A-Z)</option>
                            <option value="pdfa-desc">PDF/A-3 (ANO první)</option>
                            <option value="pdfa-asc">PDF/A-3 (NE první)</option>
                            <option value="sig-desc">Podpis (ANO první)</option>
                            <option value="sig-asc">Podpis (NE první)</option>
                        </select>
                    </div>

                    <div class="legend">
                        <div class="legend-title">Legenda:</div>
                        <div class="legend-grid">
                            <div class="legend-item"><span class="badge badge-green">A-3</span> Správně</div>
                            <div class="legend-item"><span class="badge badge-red">A-2 / A-1 / NE</span> Špatně</div>
                            <div class="legend-item"><span class="badge badge-green">VČR</span> Vlož. čas. razítko</div>
                            <div class="legend-item"><span class="badge badge-red">LOK</span> Z hodin PC</div>
                            <div class="legend-item"><span class="badge badge-red">Bez razítka</span> Žádné</div>
                        </div>
                    </div>
                </div>

                <div class="sidebar-footer">
                    <button class="btn btn-orange" id="btn-export-csv" onclick="exportCSV()" title="Export CSV (Pro)">📊 Export CSV <span id="csv-lock" class="lock-icon" style="display:none;">🔒</span></button>
                    <button class="btn btn-green" id="btn-export-excel" onclick="exportExcel()" title="Export do Excelu (Pro)">
                        📑 Export Excel <span id="excel-lock" class="lock-icon" style="display:none;">🔒</span>
                    </button>
                    <button class="btn btn-gray" onclick="clearAll()">🗑️ Vymazat vše</button>
                </div>
            </div>

            <div id="main-content">
                <div class="summary-bar">
                    <span class="summary-total">Celkem: <span id="total-count">0</span> souborů</span>
                    <div class="summary-stats">
                        <span class="stat-ok">PDF/A-3: <span id="pdfa-ok">0</span> ✓</span>
                        <span class="stat-fail">PDF/A-3: <span id="pdfa-fail">0</span> ✗</span>
                        <span class="stat-ok">Podpis: <span id="sig-ok">0</span> ✓</span>
                    </div>
                </div>

                <div class="actions-bar">
                    <button class="action-btn" onclick="expandAll()">▼ Rozbalit vše</button>
                    <button class="action-btn" onclick="collapseAll()">▲ Sbalit vše</button>
                    <span style="color:#9ca3af;margin:0 4px;">|</span>
                    <button class="action-btn" onclick="expandLevel(1)" title="Rozbalit 1. úroveň">L1</button>
                    <button class="action-btn" onclick="expandLevel(2)" title="Rozbalit do 2. úrovně">L2</button>
                    <button class="action-btn" onclick="expandLevel(3)" title="Rozbalit do 3. úrovně">L3</button>
                    <button class="action-btn danger" onclick="deleteAllBatches()">Smazat vše ze serveru</button>
                </div>

                <div class="active-filter" id="active-filter">
                    <span>🔍 Filtr: <strong id="filter-column"></strong> = <span id="filter-value"></span></span>
                    <button class="active-filter-clear" onclick="clearHeaderFilter()">✕ Zrušit</button>
                </div>

                <div id="only-your-checks-label" style="display:none;padding:6px 12px;background:#eff6ff;border-radius:6px;font-size:0.85em;color:#1e5a8a;margin-bottom:8px;">✓ Zobrazeny pouze vaše kontroly a historie (pod vaším přihlašovacím jménem)</div>

                <div class="table-header">
                    <div class="table-header-cell">Název souboru</div>
                    <div class="table-header-cell">
                        <button class="table-header-btn" onclick="toggleDropdown('pdfa',event)">PDF/A <span class="arrow">▼</span></button>
                        <div class="filter-dropdown" id="dropdown-pdfa">
                            <button class="filter-dropdown-item clear" onclick="setHeaderFilter(null,null)">✕ Zobrazit vše</button>
                            <button class="filter-dropdown-item" onclick="setHeaderFilter('pdfa','A3')"><span class="filter-dot" style="background:#22c55e"></span>PDF/A-3 (správně)</button>
                            <button class="filter-dropdown-item" onclick="setHeaderFilter('pdfa','A2')"><span class="filter-dot" style="background:#ef4444"></span>PDF/A-2</button>
                            <button class="filter-dropdown-item" onclick="setHeaderFilter('pdfa','A1')"><span class="filter-dot" style="background:#ef4444"></span>PDF/A-1</button>
                            <button class="filter-dropdown-item" onclick="setHeaderFilter('pdfa','NONE')"><span class="filter-dot" style="background:#ef4444"></span>Není PDF/A</button>
                        </div>
                    </div>
                    <div class="table-header-cell">
                        <button class="table-header-btn" onclick="toggleDropdown('sig',event)">Podpis <span class="arrow">▼</span></button>
                        <div class="filter-dropdown" id="dropdown-sig">
                            <button class="filter-dropdown-item clear" onclick="setHeaderFilter(null,null)">✕ Zobrazit vše</button>
                            <button class="filter-dropdown-item" onclick="setHeaderFilter('sig','OK')"><span class="filter-dot" style="background:#22c55e"></span>Autorizovaná osoba</button>
                            <button class="filter-dropdown-item" onclick="setHeaderFilter('sig','PARTIAL')"><span class="filter-dot" style="background:#ef4444"></span>Podpis (ne autor.)</button>
                            <button class="filter-dropdown-item" onclick="setHeaderFilter('sig','FAIL')"><span class="filter-dot" style="background:#ef4444"></span>Žádný podpis</button>
                        </div>
                    </div>
                    <div class="table-header-cell">
                        <button class="table-header-btn" onclick="toggleDropdown('signer',event)">Jméno (CN) <span class="arrow">▼</span></button>
                        <div class="filter-dropdown" id="dropdown-signer">
                            <div class="filter-dropdown-search"><input type="text" placeholder="Hledat jméno..." id="search-signer" oninput="filterSignerList()"></div>
                            <button class="filter-dropdown-item clear" onclick="setHeaderFilter(null,null)">✕ Zobrazit vše</button>
                            <div id="signer-list"></div>
                        </div>
                    </div>
                    <div class="table-header-cell">
                        <button class="table-header-btn" onclick="toggleDropdown('ckait',event)">ČKAIT <span class="arrow">▼</span></button>
                        <div class="filter-dropdown" id="dropdown-ckait">
                            <div class="filter-dropdown-search"><input type="text" placeholder="Hledat číslo..." id="search-ckait" oninput="filterCkaitList()"></div>
                            <button class="filter-dropdown-item clear" onclick="setHeaderFilter(null,null)">✕ Zobrazit vše</button>
                            <div id="ckait-list"></div>
                        </div>
                    </div>
                    <div class="table-header-cell">
                        <button class="table-header-btn" onclick="toggleDropdown('tsa',event)">Čas. razítko <span class="arrow">▼</span></button>
                        <div class="filter-dropdown" id="dropdown-tsa" style="right:0;left:auto;">
                            <button class="filter-dropdown-item clear" onclick="setHeaderFilter(null,null)">✕ Zobrazit vše</button>
                            <button class="filter-dropdown-item" onclick="setHeaderFilter('tsa','TSA')"><span class="filter-dot" style="background:#22c55e"></span>VČR (vlož. čas. razítko)</button>
                            <button class="filter-dropdown-item" onclick="setHeaderFilter('tsa','LOCAL')"><span class="filter-dot" style="background:#ef4444"></span>LOK (z hodin PC)</button>
                            <button class="filter-dropdown-item" onclick="setHeaderFilter('tsa','NONE')"><span class="filter-dot" style="background:#ef4444"></span>Bez razítka</button>
                        </div>
                    </div>
                </div>

                <div class="results-container" id="results-container">
                    <div style="padding:40px;text-align:center;color:#9ca3af;">
                        <div style="font-size:3em;margin-bottom:16px;">📂</div>
                        <div>Nahrajte PDF soubory pro kontrolu</div>
                    </div>
                </div>
            </div>
        </div>

        <footer id="footer">
            <strong>⚠️</strong> Výsledky mají informativní charakter a nenahrazují Portál stavebníka. Autor neručí za správnost.
            <span style="margin:0 8px;">|</span>
            v42 | Verze z prosince 2025 | © Ing. Martin Cieślar
        </footer>
    </div>

    <!-- ===== INFO MODAL ===== -->
    <div class="modal-overlay" id="info-modal">
        <div class="modal">
            <div class="modal-header">
                <h3>📘 Informace o aplikaci</h3>
                <button class="modal-close" onclick="hideInfoModal()">×</button>
            </div>
            <div class="modal-tabs">
                <button class="modal-tab active" onclick="setInfoTab('about',this)">O aplikaci</button>
                <button class="modal-tab" onclick="setInfoTab('pdfa',this)">Proč PDF/A?</button>
                <button class="modal-tab" onclick="setInfoTab('ckait',this)">Proč ČKAIT?</button>
                <button class="modal-tab" onclick="setInfoTab('contact',this)">Kontakt</button>
            </div>
            <div class="modal-content">
                <div id="tab-about">
                    <h4>📝 O aplikaci PDF DokuCheck PRO</h4>
                    <p>PDF DokuCheck PRO je nástroj pro <strong>projektanty, autorizované osoby, stavební firmy a veřejnou správu</strong>.</p>
                    <p style="margin-top:12px;"><strong>Aplikace kontroluje:</strong></p>
                    <ul>
                        <li>✓ Formát <strong>PDF/A-3</strong> (vyžadovaný Portálem stavebníka)</li>
                        <li>✓ Autorizované razítko <strong>ČKAIT/ČKA</strong></li>
                        <li>✓ Elektronický podpis</li>
                        <li>✓ Časové razítko (VČR / LOK / bez razítka)</li>
                    </ul>
                    <div class="info-box green"><strong>Cíl:</strong> Odstranit problémy při elektronickém podání dokumentace.</div>
                </div>
                <div id="tab-pdfa" class="hidden">
                    <h4>📌 Proč PDF/A-3?</h4>
                    <p>Podle <strong>vyhlášky č. 190/2024 Sb.</strong> musí být projektová dokumentace ve formátu PDF/A-3.</p>
                    <div class="info-box blue">PDF DokuCheck PRO ověří formát ještě před nahráním na Portál stavebníka.</div>
                    <p style="margin-top:12px;"><strong>Verze PDF/A:</strong></p>
                    <ul>
                        <li><span style="color:#16a34a;font-weight:bold;">PDF/A-3</span> — Aktuální standard, podporuje přílohy</li>
                        <li><span style="color:#ca8a04;font-weight:bold;">PDF/A-2</span> — Starší verze, může být odmítnuta</li>
                        <li><span style="color:#ea580c;font-weight:bold;">PDF/A-1</span> — Nejstarší, pravděpodobně bude odmítnuta</li>
                    </ul>
                </div>
                <div id="tab-ckait" class="hidden">
                    <h4>🏛️ Proč ČKAIT?</h4>
                    <p>Podle <strong>zákona č. 360/1992 Sb.</strong> musí být projektová dokumentace opatřena autorizovaným razítkem.</p>
                    <div class="info-box yellow">PDF DokuCheck PRO ověří přítomnost čísla ČKAIT/ČKA v certifikátu elektronického podpisu.</div>
                    <p style="margin-top:12px;">Číslo ČKAIT je 7místné číslo (např. 0012345) uložené v poli OU certifikátu.</p>
                </div>
                <div id="tab-contact" class="hidden">
                    <h4>📧 Kontakt</h4>
                    <div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:8px;padding:16px;margin:12px 0;">
                        <p style="font-size:1.1em;font-weight:bold;color:#374151;">Ing. Martin Cieślar</p>
                    </div>
                    <p style="font-size:0.8em;color:#9ca3af;margin-top:16px;">v42 | Verze z prosince 2025</p>
                </div>
            </div>
            <div class="modal-footer">
                <strong>⚖️ Právní upozornění:</strong> Výsledky kontroly mají pouze informativní charakter a nenahrazují Portál stavebníka.
            </div>
        </div>
    </div>

    <!-- ===== UPLOAD PREVIEW MODAL ===== -->
    <div class="modal-overlay" id="upload-preview-modal">
        <div class="modal" style="max-width:600px;">
            <div class="modal-header">
                <h3>📋 Náhled souborů k analýze</h3>
                <button class="modal-close" onclick="hideUploadPreview()">×</button>
            </div>
            <div class="modal-content" style="padding:0;">
                <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:1px;background:#e5e7eb;">
                    <div style="background:white;padding:16px;text-align:center;">
                        <div style="font-size:2em;color:#1e5a8a;">📄</div>
                        <div style="font-size:1.5em;font-weight:bold;color:#1e5a8a;" id="preview-file-count">0</div>
                        <div style="font-size:0.8em;color:#6b7280;">PDF souborů</div>
                    </div>
                    <div style="background:white;padding:16px;text-align:center;">
                        <div style="font-size:2em;color:#0891b2;">📁</div>
                        <div style="font-size:1.5em;font-weight:bold;color:#0891b2;" id="preview-folder-count">0</div>
                        <div style="font-size:0.8em;color:#6b7280;">složek</div>
                    </div>
                    <div style="background:white;padding:16px;text-align:center;">
                        <div style="font-size:2em;color:#16a34a;">💾</div>
                        <div style="font-size:1.5em;font-weight:bold;color:#16a34a;" id="preview-total-size">0 MB</div>
                        <div style="font-size:0.8em;color:#6b7280;">celkem</div>
                    </div>
                </div>
                <div style="padding:16px;max-height:300px;overflow-y:auto;" id="preview-file-list">
                </div>
            </div>
            <div style="padding:16px;border-top:1px solid #e5e7eb;display:flex;gap:12px;justify-content:flex-end;">
                <button onclick="hideUploadPreview()" style="padding:10px 20px;background:#f3f4f6;border:1px solid #d1d5db;border-radius:8px;cursor:pointer;">Zrušit</button>
                <button onclick="confirmUpload()" style="padding:10px 24px;background:linear-gradient(135deg,#22c55e,#16a34a);color:white;border:none;border-radius:8px;font-weight:600;cursor:pointer;">✓ Spustit analýzu</button>
            </div>
        </div>
    </div>

    <!-- ===== UPLOAD PROGRESS MODAL ===== -->
    <div class="modal-overlay" id="upload-progress-modal">
        <div class="modal" style="max-width:500px;">
            <div class="modal-header" style="background:linear-gradient(135deg,#0891b2,#0e7490);">
                <h3>⏳ Analyzuji soubory...</h3>
            </div>
            <div class="modal-content" style="text-align:center;padding:32px;">
                <div style="margin-bottom:24px;">
                    <div style="height:24px;background:#e5e7eb;border-radius:12px;overflow:hidden;">
                        <div id="upload-progress-bar" style="height:100%;background:linear-gradient(90deg,#1e5a8a,#2d7ab8);border-radius:12px;transition:width 0.3s;width:0%;"></div>
                    </div>
                    <div style="margin-top:12px;font-size:1.2em;font-weight:600;color:#1e5a8a;" id="upload-progress-text">0 / 0 (0%)</div>
                </div>
                <div style="font-size:0.9em;color:#6b7280;">
                    <span>Aktuálně: </span>
                    <span id="upload-progress-file" style="font-weight:500;color:#374151;">—</span>
                </div>
            </div>
        </div>
    </div>

    <!-- ===== DISK SCAN PROGRESS MODAL ===== -->
    <div class="modal-overlay" id="disk-progress-modal">
        <div class="modal" style="max-width:500px;">
            <div class="modal-header" style="background:linear-gradient(135deg,#7c3aed,#6d28d9);">
                <h3>🔍 Skenování složky...</h3>
            </div>
            <div class="modal-content" style="text-align:center;padding:32px;">
                <div style="margin-bottom:24px;">
                    <div style="height:24px;background:#e5e7eb;border-radius:12px;overflow:hidden;">
                        <div id="disk-progress-bar" style="height:100%;background:linear-gradient(90deg,#7c3aed,#8b5cf6);border-radius:12px;transition:width 0.3s;width:0%;"></div>
                    </div>
                    <div style="margin-top:12px;font-size:1.2em;font-weight:600;color:#7c3aed;" id="disk-progress-text">0 / 0 (0%)</div>
                </div>
                <div style="font-size:0.9em;color:#6b7280;">
                    <span>Aktuálně: </span>
                    <span id="disk-progress-file" style="font-weight:500;color:#374151;">—</span>
                </div>
            </div>
        </div>
    </div>

    <!-- ===== HELP MODAL ===== -->
    <div class="modal-overlay" id="help-modal">
        <div class="modal" style="max-width:600px;">
            <div class="modal-header" style="background:linear-gradient(135deg,#059669,#047857);">
                <h3>❓ Návod na používání</h3>
                <button class="modal-close" onclick="hideHelpModal()">×</button>
            </div>
            <div class="modal-content" style="padding:24px;font-size:0.9em;line-height:1.7;">
                <h4 style="color:#1e5a8a;margin:0 0 12px 0;">1. NAHRÁNÍ SOUBORŮ</h4>
                <p style="margin:0 0 16px 0;color:#4b5563;">
                    • Přetáhněte PDF soubory nebo složku do šedé zóny<br>
                    • Nebo klikněte na <strong>„Vybrat soubory"</strong> / <strong>„Vybrat složku"</strong><br>
                    • Zobrazí se náhled s počtem souborů - potvrďte tlačítkem <strong>„Spustit analýzu"</strong>
                </p>

                <h4 style="color:#1e5a8a;margin:0 0 12px 0;">2. CO SE KONTROLUJE</h4>
                <p style="margin:0 0 16px 0;color:#4b5563;">
                    • <strong>PDF/A-3</strong> – formát vyžadovaný Portálem stavebníka<br>
                    • <strong>Elektronický podpis</strong> – přítomnost a platnost<br>
                    • <strong>ČKAIT/ČKA</strong> – číslo autorizace v certifikátu<br>
                    • <strong>Časové razítko</strong> – VČR (vložené) správně, LOK (z PC) nebo bez razítka špatně
                </p>

                <h4 style="color:#1e5a8a;margin:0 0 12px 0;">3. VÝSLEDKY</h4>
                <p style="margin:0 0 16px 0;color:#4b5563;">
                    • <span style="background:#dcfce7;color:#16a34a;padding:2px 8px;border-radius:4px;font-weight:600;">Zelené</span> = vše v pořádku<br>
                    • <span style="background:#fef9c3;color:#ca8a04;padding:2px 8px;border-radius:4px;font-weight:600;">Žluté</span> = varování (starší verze, lokální razítko)<br>
                    • <span style="background:#fee2e2;color:#dc2626;padding:2px 8px;border-radius:4px;font-weight:600;">Červené</span> = problém (chybí podpis, není PDF/A)
                </p>

                <h4 style="color:#1e5a8a;margin:0 0 12px 0;">4. VÍCE PODPISŮ</h4>
                <p style="margin:0 0 16px 0;color:#4b5563;">
                    • Pokud má dokument více podpisů, zobrazí se <strong>„▶ X podpisy"</strong><br>
                    • Kliknutím rozbalíte detail všech podpisů
                </p>

                <h4 style="color:#1e5a8a;margin:0 0 12px 0;">5. EXPORT</h4>
                <p style="margin:0 0 8px 0;color:#4b5563;">
                    • Tlačítko <strong>„Exportovat CSV"</strong> uloží výsledky do tabulky<br>
                    • Lze otevřít v Excelu nebo jiném tabulkovém procesoru
                </p>

                <div style="margin-top:20px;padding:12px;background:#fef3c7;border-radius:8px;border:1px solid #fcd34d;">
                    <strong style="color:#92400e;">⚠️ Upozornění:</strong>
                    <span style="color:#92400e;"> Výsledky mají informativní charakter a nenahrazují oficiální validaci na Portálu stavebníka.</span>
                </div>
            </div>
        </div>
    </div>

<script>
// ===== GLOBÁLNÍ STAV =====
let batches = [];
let batchCounter = 0;
let currentMode = 'upload';
let selectedDiskPath = '';
let sidebarFilters = { pdfa: 'all', sig: 'all', tsa: 'all' };
let headerFilter = { column: null, value: null };
let treeCollapsedIds = new Set();

// ===== MODE =====
function setMode(mode) {
    currentMode = mode;

    // Hlavní přepínač: agent vs local
    document.getElementById('mode-agent').classList.toggle('active', mode === 'agent');
    document.getElementById('mode-local').classList.toggle('active', mode === 'local' || mode === 'upload' || mode === 'disk');

    // Zobrazení panelů
    document.getElementById('agent-mode').classList.toggle('hidden', mode !== 'agent');
    document.getElementById('upload-mode').classList.toggle('hidden', mode !== 'upload' && mode !== 'local');
    document.getElementById('disk-mode').classList.toggle('hidden', mode !== 'disk');

    // Pokud lokální, zobraz upload jako default
    if (mode === 'local') {
        document.getElementById('upload-mode').classList.remove('hidden');
    }

    // Při přepnutí na agent, automaticky načti data
    if (mode === 'agent') {
        loadAgentResults();
    }
}

// ===== FILE UPLOAD =====
function selectFiles() { document.getElementById('file-input').click(); }
function selectFolder() { document.getElementById('folder-input').click(); }

document.getElementById('file-input').addEventListener('change', function(e) {
    if (e.target.files.length > 0) {
        const files = Array.from(e.target.files).filter(f => f.name.toLowerCase().endsWith('.pdf'));
        if (files.length > 0) {
            showUploadPreview(files);
        } else {
            alert('Nebyly vybrány žádné PDF soubory.');
        }
    }
    this.value = ''; // Reset pro opakovaný výběr stejných souborů
});
document.getElementById('folder-input').addEventListener('change', function(e) {
    console.log('Složka vybrána, souborů:', e.target.files.length);
    if (e.target.files.length > 0) {
        const files = Array.from(e.target.files);
        console.log('Soubory:', files.map(f => f.name));
        const pdfFiles = files.filter(f => f.name.toLowerCase().endsWith('.pdf'));
        console.log('PDF souborů:', pdfFiles.length);
        if (pdfFiles.length > 0) {
            showUploadPreview(pdfFiles);
        } else {
            alert('Ve vybrané složce nebyly nalezeny žádné PDF soubory.');
        }
    }
    this.value = ''; // Reset
});

// Drop zone
const dropZone = document.getElementById('drop-zone');
dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', () => { dropZone.classList.remove('dragover'); });
dropZone.addEventListener('drop', async (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    
    // Zobrazit loading
    dropZone.innerHTML = '<div class="drop-zone-icon">⏳</div><div class="drop-zone-text">Načítám soubory...</div>';
    
    const allFiles = [];
    const items = e.dataTransfer.items;
    
    if (items && items.length > 0) {
        const promises = [];
        for (let i = 0; i < items.length; i++) {
            const item = items[i];
            if (item.kind === 'file') {
                const entry = item.webkitGetAsEntry ? item.webkitGetAsEntry() : null;
                if (entry) {
                    promises.push(traverseFileTree(entry, ''));
                } else {
                    const file = item.getAsFile();
                    if (file && file.name.toLowerCase().endsWith('.pdf')) {
                        allFiles.push(file);
                    }
                }
            }
        }
        
        const results = await Promise.all(promises);
        results.forEach(files => allFiles.push(...files));
    } else {
        const files = Array.from(e.dataTransfer.files).filter(f => f.name.toLowerCase().endsWith('.pdf'));
        allFiles.push(...files);
    }
    
    // Obnovit drop zone
    dropZone.innerHTML = '<div class="drop-zone-icon">📂</div><div class="drop-zone-text">Přetáhněte PDF soubory</div><div class="drop-zone-hint">nebo složky sem</div>';
    
    if (allFiles.length > 0) {
        showUploadPreview(allFiles);
    } else {
        alert('Nebyly nalezeny žádné PDF soubory.');
    }
});

// Pomocná funkce pro procházení složek - OPRAVENO pro více než 100 souborů
async function traverseFileTree(entry, path) {
    const files = [];
    
    if (entry.isFile) {
        try {
            const file = await new Promise((resolve, reject) => {
                entry.file(resolve, reject);
            });
            if (file.name.toLowerCase().endsWith('.pdf')) {
                Object.defineProperty(file, 'webkitRelativePath', { 
                    value: path + file.name,
                    writable: false 
                });
                files.push(file);
            }
        } catch (err) {
            console.error('Chyba při čtení souboru:', err);
        }
    } else if (entry.isDirectory) {
        const reader = entry.createReader();
        
        // Musíme volat readEntries opakovaně dokud nevrátí prázdné pole
        const readAllEntries = async () => {
            const allEntries = [];
            let entries;
            do {
                entries = await new Promise((resolve, reject) => {
                    reader.readEntries(resolve, reject);
                });
                allEntries.push(...entries);
            } while (entries.length > 0);
            return allEntries;
        };
        
        try {
            const entries = await readAllEntries();
            for (const subEntry of entries) {
                const subFiles = await traverseFileTree(subEntry, path + entry.name + '/');
                files.push(...subFiles);
            }
        } catch (err) {
            console.error('Chyba při čtení složky:', err);
        }
    }
    return files;
}

// Formátování velikosti
function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

// Náhled před uploadem
let pendingFiles = [];

function showUploadPreview(files) {
    pendingFiles = files;
    const totalSize = files.reduce((sum, f) => sum + f.size, 0);
    
    // Spočítat složky
    const folders = new Set();
    files.forEach(f => {
        const path = f.webkitRelativePath || f.name;
        const parts = path.split('/');
        if (parts.length > 1) {
            folders.add(parts.slice(0, -1).join('/'));
        }
    });
    
    const modal = document.getElementById('upload-preview-modal');
    document.getElementById('preview-file-count').textContent = files.length;
    document.getElementById('preview-folder-count').textContent = folders.size;
    document.getElementById('preview-total-size').textContent = formatFileSize(totalSize);
    
    // Seznam souborů
    const listHtml = files.slice(0, 50).map(f => {
        const path = f.webkitRelativePath || f.name;
        return `<div class="preview-file-item">
            <span class="preview-file-name" title="${path}">${path}</span>
            <span class="preview-file-size">${formatFileSize(f.size)}</span>
        </div>`;
    }).join('');
    
    document.getElementById('preview-file-list').innerHTML = listHtml + 
        (files.length > 50 ? `<div class="preview-more">... a dalších ${files.length - 50} souborů</div>` : '');
    
    modal.classList.add('visible');
}

function hideUploadPreview() {
    document.getElementById('upload-preview-modal').classList.remove('visible');
}

function confirmUpload() {
    const filesToProcess = [...pendingFiles]; // Uložit kopii PŘED vymazáním
    pendingFiles = [];
    hideUploadPreview();
    if (filesToProcess.length > 0) {
        processFilesWithProgress(filesToProcess);
    }
}

// Upload s progress barem (bez přihlášení = Free trial max 5 souborů)
async function processFilesWithProgress(files) {
    let pdfFiles = files.filter(f => f.name.toLowerCase().endsWith('.pdf'));
    if (pdfFiles.length === 0) return;

    const user = getStoredUser();
    const tier = user && user.tier !== undefined ? user.tier : 0;
    const maxFiles = tier === 2 || tier === 3 ? 99999 : (tier === 1 ? 100 : 5);
    if (pdfFiles.length > maxFiles) {
        pdfFiles = pdfFiles.slice(0, maxFiles);
        alert('Limit licence: Free max 5, Basic max 100 souborů. Zkontrolováno prvních ' + maxFiles + '. Pro více zvolte Pro licenci.');
    }

    // Zobrazit progress modal
    const progressModal = document.getElementById('upload-progress-modal');
    const progressBar = document.getElementById('upload-progress-bar');
    const progressText = document.getElementById('upload-progress-text');
    const progressFile = document.getElementById('upload-progress-file');
    progressModal.classList.add('visible');
    
    const batchName = pdfFiles.length === 1 ? pdfFiles[0].name : 
        (pdfFiles[0].webkitRelativePath ? pdfFiles[0].webkitRelativePath.split('/')[0] : 'Upload_' + new Date().toLocaleTimeString());

    const batch = { id: ++batchCounter, name: batchName, timestamp: new Date().toLocaleTimeString().slice(0,5), files: [], collapsed: false };

    const totalPdf = pdfFiles.length;
    for (let i = 0; i < totalPdf; i++) {
        const file = pdfFiles[i];
        const percent = Math.round(((i + 1) / totalPdf) * 100);
        
        progressBar.style.width = percent + '%';
        progressText.textContent = `${i + 1} / ${totalPdf} (${percent}%)`;
        progressFile.textContent = file.name;
        
        const formData = new FormData();
        formData.append('file', file);
        try {
            const response = await fetch('/analyze', { method: 'POST', body: formData });
            const result = await response.json();
            batch.files.push({ path: file.webkitRelativePath || file.name, name: file.name, ...result });
        } catch (error) {
            batch.files.push({ path: file.webkitRelativePath || file.name, name: file.name, pdfaVersion: null, pdfaStatus: 'FAIL', sig: 'FAIL', signer: '—', ckait: '—', tsa: 'NONE' });
        }
    }
    
    // Skrýt progress modal
    progressModal.classList.remove('visible');
    
    batches.push(batch);
    renderResults();
    updateFilterLists();
}

// Původní processFiles pro zpětnou kompatibilitu
async function processFiles(files) {
    showUploadPreview(files);
}

// ===== DISK MODE =====
function selectDiskFolder() {
    fetch('/select_folder').then(r => r.json()).then(data => {
        if (data.path) {
            selectedDiskPath = data.path;
            document.getElementById('disk-path').textContent = data.path;
            document.getElementById('disk-count').textContent = 'Nalezeno ' + (data.pdf_count || data.count || 0) + ' PDF souborů';
            document.getElementById('disk-scan-section').classList.remove('hidden');
        }
    });
}

function scanDiskFolder() {
    if (!selectedDiskPath) return;
    
    // Zobrazit progress modal
    const progressModal = document.getElementById('disk-progress-modal');
    const progressBar = document.getElementById('disk-progress-bar');
    const progressText = document.getElementById('disk-progress-text');
    const progressFile = document.getElementById('disk-progress-file');
    
    progressBar.style.width = '0%';
    progressText.textContent = 'Připravuji...';
    progressFile.textContent = '—';
    progressModal.classList.add('visible');
    
    // SSE pro průběžný progress
    const eventSource = new EventSource('/api/scan-folder-stream?path=' + encodeURIComponent(selectedDiskPath));
    
    eventSource.onmessage = function(e) {
        const data = JSON.parse(e.data);
        
        if (data.type === 'progress') {
            const percent = Math.round((data.current / data.total) * 100);
            progressBar.style.width = percent + '%';
            progressText.textContent = data.current + ' / ' + data.total + ' (' + percent + '%)';
            progressFile.textContent = data.file;
        } else if (data.type === 'complete') {
            eventSource.close();
            progressModal.classList.remove('visible');
            
            if (data.results && data.results.length > 0) {
                const batch = { id: ++batchCounter, name: selectedDiskPath.split(/[\\\\/]/).pop(), timestamp: new Date().toLocaleTimeString().slice(0,5), files: data.results, collapsed: false };
                batches.push(batch);
                renderResults();
                updateFilterLists();
            }
        } else if (data.type === 'error') {
            eventSource.close();
            progressModal.classList.remove('visible');
            alert('Chyba: ' + data.message);
        }
    };
    
    eventSource.onerror = function() {
        eventSource.close();
        progressModal.classList.remove('visible');
        alert('Chyba při skenování složky');
    };
}

// ===== SIDEBAR FILTERS =====
document.querySelectorAll('.filter-buttons').forEach(container => {
    container.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            container.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            let type = 'pdfa';
            if (container.id === 'filter-sig') type = 'sig';
            else if (container.id === 'filter-tsa') type = 'tsa';
            else if (container.id === 'filter-pdfa') type = 'pdfa';
            sidebarFilters[type] = this.dataset.value;
            renderResults();
        });
    });
});

// ===== HEADER FILTERS =====
function toggleDropdown(col, event) {
    event.stopPropagation();
    const dropdown = document.getElementById('dropdown-' + col);
    const wasVisible = dropdown.classList.contains('visible');
    document.querySelectorAll('.filter-dropdown').forEach(d => d.classList.remove('visible'));
    if (!wasVisible) dropdown.classList.add('visible');
}

function setHeaderFilter(column, value) {
    headerFilter = { column, value };
    document.querySelectorAll('.filter-dropdown').forEach(d => d.classList.remove('visible'));
    const filterBar = document.getElementById('active-filter');
    if (column && value) {
        filterBar.classList.add('visible');
        document.getElementById('filter-column').textContent = column;
        document.getElementById('filter-value').textContent = value;
    } else {
        filterBar.classList.remove('visible');
    }
    renderResults();
}

function clearHeaderFilter() { setHeaderFilter(null, null); }

document.addEventListener('click', () => {
    document.querySelectorAll('.filter-dropdown').forEach(d => d.classList.remove('visible'));
});

// ===== FILTER LISTS =====
function updateFilterLists() {
    const allFiles = batches.flatMap(b => b.files);
    const signers = [...new Set(allFiles.map(f => f.signer).filter(s => s && s !== '—'))];
    const ckaits = [...new Set(allFiles.map(f => f.ckait).filter(c => c && c !== '—'))];
    document.getElementById('signer-list').innerHTML = signers.map(s => 
        '<button class="filter-dropdown-item" onclick="setHeaderFilter(\\'signer\\',\\'' + s + '\\')">' + s + '</button>').join('');
    document.getElementById('ckait-list').innerHTML = ckaits.map(c => 
        '<button class="filter-dropdown-item" style="font-family:monospace" onclick="setHeaderFilter(\\'ckait\\',\\'' + c + '\\')">' + c + '</button>').join('');
}

function filterSignerList() {
    const search = document.getElementById('search-signer').value.toLowerCase();
    const allFiles = batches.flatMap(b => b.files);
    const signers = [...new Set(allFiles.map(f => f.signer).filter(s => s && s !== '—' && s.toLowerCase().includes(search)))];
    document.getElementById('signer-list').innerHTML = signers.map(s => 
        '<button class="filter-dropdown-item" onclick="setHeaderFilter(\\'signer\\',\\'' + s + '\\')">' + s + '</button>').join('');
}

function filterCkaitList() {
    const search = document.getElementById('search-ckait').value;
    const allFiles = batches.flatMap(b => b.files);
    const ckaits = [...new Set(allFiles.map(f => f.ckait).filter(c => c && c !== '—' && c.includes(search)))];
    document.getElementById('ckait-list').innerHTML = ckaits.map(c => 
        '<button class="filter-dropdown-item" style="font-family:monospace" onclick="setHeaderFilter(\\'ckait\\',\\'' + c + '\\')">' + c + '</button>').join('');
}

// ===== RENDER =====
function renderResults() {
    const container = document.getElementById('results-container');
    if (batches.length === 0) {
        container.innerHTML = '<div style="padding:40px;text-align:center;color:#9ca3af;"><div style="font-size:3em;margin-bottom:16px;">📂</div><div>Nahrajte PDF soubory pro kontrolu</div></div>';
        updateStats();
        return;
    }

    let html = '';
    for (const batch of batches) {
        let filteredFiles = filterFiles(batch.files);
        filteredFiles = sortFiles(filteredFiles);
        const stats = getStats(batch.files);

        html += '<div class="batch"><div class="batch-header" onclick="toggleBatch(' + batch.id + ')">';
        html += '<div class="batch-header-left"><span class="batch-arrow' + (batch.collapsed ? ' collapsed' : '') + '">▼</span>';
        html += '<span class="batch-name">📦 ' + batch.name + '</span><span class="batch-time">— ' + batch.timestamp + '</span>';
        if (batch.source_folder) html += '<span class="batch-folder" title="' + batch.source_folder + '">📂 ' + batch.source_folder.split(/[/\\\\]/).pop() + '</span>';
        html += '</div>';
        html += '<div class="batch-header-right"><span class="batch-stat">A-3: ' + stats.pdfaOk + '✓</span>';
        html += '<span class="batch-stat">Podpis: ' + stats.sigOk + '✓</span><span class="batch-count">(' + batch.files.length + ')</span>';
        // Export - použij server API pokud máme batch_id
        if (batch.batch_id) {
            html += '<button class="batch-btn" onclick="event.stopPropagation();exportBatchFromServer(\\'' + batch.batch_id + '\\')">CSV</button>';
        } else {
            html += '<button class="batch-btn" onclick="event.stopPropagation();exportBatchCSV(' + batch.id + ')">CSV</button>';
        }
        html += '<button class="batch-btn delete" onclick="event.stopPropagation();deleteBatch(' + batch.id + ')">✕</button></div></div>';
        html += '<div class="batch-content' + (batch.collapsed ? '' : ' visible') + '" id="batch-content-' + batch.id + '">';

        // Použij stromovou strukturu
        const folderTree = buildFolderTree(filteredFiles);

        // Pokud jsou soubory jen v rootu (žádné podsložky), zobraz je přímo
        const hasSubfolders = Object.keys(folderTree.folders).length > 0;

        if (hasSubfolders) {
            // Renderuj stromovou strukturu
            html += renderFolderTree(folderTree, batch.id, 0);
        } else {
            // Soubory přímo v rootu - bez obalující složky
            html += '<div class="folder-flat">';
            for (const file of folderTree.files) {
                html += renderFileRow(file, batch.id, 0);
            }
            html += '</div>';
        }

        html += '</div></div>';
    }
    container.innerHTML = html;
    updateStats();
}

function filterFiles(files) {
    return files.filter(f => {
        if (sidebarFilters.pdfa === 'ok' && f.pdfaStatus !== 'OK') return false;
        if (sidebarFilters.pdfa === 'fail' && f.pdfaStatus === 'OK') return false;
        if (sidebarFilters.sig === 'ok' && f.sig !== 'OK') return false;
        if (sidebarFilters.sig === 'fail' && f.sig === 'OK') return false;
        if (sidebarFilters.tsa === 'tsa' && f.tsa !== 'TSA') return false;
        if (sidebarFilters.tsa === 'local' && f.tsa !== 'LOCAL') return false;
        if (sidebarFilters.tsa === 'none' && f.tsa !== 'NONE') return false;
        if (headerFilter.column && headerFilter.value) {
            if (headerFilter.column === 'pdfa') {
                if (headerFilter.value === 'A3' && f.pdfaVersion !== 3) return false;
                if (headerFilter.value === 'A2' && f.pdfaVersion !== 2) return false;
                if (headerFilter.value === 'A1' && f.pdfaVersion !== 1) return false;
                if (headerFilter.value === 'NONE' && f.pdfaVersion !== null) return false;
            }
            if (headerFilter.column === 'sig' && f.sig !== headerFilter.value) return false;
            if (headerFilter.column === 'signer' && f.signer !== headerFilter.value) return false;
            if (headerFilter.column === 'ckait' && f.ckait !== headerFilter.value) return false;
            if (headerFilter.column === 'tsa' && f.tsa !== headerFilter.value) return false;
        }
        return true;
    });
}

function sortFiles(files) {
    const sortBy = document.getElementById('sort-select').value;
    return [...files].sort((a, b) => {
        switch (sortBy) {
            case 'name-asc': return a.name.localeCompare(b.name);
            case 'name-desc': return b.name.localeCompare(a.name);
            case 'path-asc': return a.path.localeCompare(b.path);
            case 'pdfa-desc': return (b.pdfaStatus === 'OK' ? 1 : 0) - (a.pdfaStatus === 'OK' ? 1 : 0);
            case 'pdfa-asc': return (a.pdfaStatus === 'OK' ? 1 : 0) - (b.pdfaStatus === 'OK' ? 1 : 0);
            case 'sig-desc': return (b.sig === 'OK' ? 1 : 0) - (a.sig === 'OK' ? 1 : 0);
            case 'sig-asc': return (a.sig === 'OK' ? 1 : 0) - (b.sig === 'OK' ? 1 : 0);
            default: return 0;
        }
    });
}

// Vytvoří skutečnou stromovou strukturu složek
function buildFolderTree(files) {
    const tree = { name: '__root', folders: {}, files: [], collapsed: false };

    for (const file of files) {
        const normalizedPath = file.path.replace(/\\\\/g, '/');
        const parts = normalizedPath.split('/');

        if (parts.length === 1) {
            // Soubor v rootu
            tree.files.push(file);
        } else {
            // Soubor v podsložce - projdi cestu a vytvoř strukturu
            let current = tree;
            for (let i = 0; i < parts.length - 1; i++) {
                const folderName = parts[i];
                if (!current.folders[folderName]) {
                    current.folders[folderName] = {
                        name: folderName,
                        path: parts.slice(0, i + 1).join('/'),
                        folders: {},
                        files: [],
                        collapsed: false
                    };
                }
                current = current.folders[folderName];
            }
            current.files.push(file);
        }
    }

    return tree;
}

// Rekurzivně renderuje stromovou strukturu složek
const TREE_INDENT_PX = 3;
function renderFolderTree(node, batchId, level = 0) {
    let html = '';
    const indent = level * TREE_INDENT_PX;

    // Nejprve podsložky (seřazené abecedně)
    const folderNames = Object.keys(node.folders).sort();
    for (const folderName of folderNames) {
        const folder = node.folders[folderName];
        const folderId = batchId + '-' + folder.path.replace(/[^a-z0-9]/gi, '_');
        const folderStats = getFolderStats(folder);
        const hasContent = folder.files.length > 0 || Object.keys(folder.folders).length > 0;

        if (hasContent) {
            const isCollapsed = treeCollapsedIds.has(folderId);
            html += '<div class="folder" style="margin-left:' + indent + 'px">';
            html += '<div class="folder-header" onclick="toggleTreeFolder(\\'' + folderId + '\\')">';
            html += '<span class="folder-arrow' + (isCollapsed ? ' collapsed' : '') + '" id="arrow-' + folderId + '">▼</span>';
            html += '<span class="folder-icon">📁</span>';
            html += '<span class="folder-name">' + folderName + '</span>';
            html += '<span class="folder-stats">(' + folderStats.total + ') A3:' + folderStats.pdfaOk + '✓ P:' + folderStats.sigOk + '✓</span>';
            html += '</div>';
            html += '<div class="folder-content' + (isCollapsed ? '' : ' visible') + '" id="folder-' + folderId + '">';

            // Rekurzivně renderuj podsložky
            html += renderFolderTree(folder, batchId, level + 1);

            html += '</div></div>';
        }
    }

    // Pak soubory v této složce
    for (const file of node.files) {
        html += renderFileRow(file, batchId, indent);
    }

    return html;
}

// Spočítá statistiky pro složku včetně podsložek
function getFolderStats(folder) {
    let total = folder.files.length;
    let pdfaOk = folder.files.filter(f => f.pdfaStatus === 'OK').length;
    let sigOk = folder.files.filter(f => f.sig === 'OK').length;

    for (const subFolder of Object.values(folder.folders)) {
        const subStats = getFolderStats(subFolder);
        total += subStats.total;
        pdfaOk += subStats.pdfaOk;
        sigOk += subStats.sigOk;
    }

    return { total, pdfaOk, sigOk };
}

// Renderuje řádek souboru
function renderFileRow(file, batchId, indent = 0) {
    const sigCount = file.sig_count || (file.signatures ? file.signatures.length : 0);
    const hasMultipleSigs = sigCount > 1;
    const fileId = 'file-' + batchId + '-' + Math.random().toString(36).substr(2, 9);

    let html = '<div class="file-row-wrapper" style="margin-left:' + indent + 'px">';
    html += '<div class="file-row' + (hasMultipleSigs ? ' has-sigs' : '') + '" ' + (hasMultipleSigs ? 'onclick="toggleSignatures(\\'' + fileId + '\\')"' : '') + '>';
    html += '<div class="file-name" title="' + file.path + '">' + file.name + '</div>';
    html += '<div class="file-cell">' + getPdfaBadge(file) + '</div>';
    html += '<div class="file-cell">' + getSigBadge(file) + '</div>';

    if (hasMultipleSigs) {
        html += '<div class="file-cell file-signer sig-expandable">▶ ' + sigCount + ' podpisy</div>';
    } else {
        html += '<div class="file-cell file-signer">' + (file.signer || '—') + '</div>';
    }

    html += '<div class="file-cell file-ckait">' + (hasMultipleSigs ? '—' : (file.ckait || '—')) + '</div>';
    html += '<div class="file-cell">' + getTsaBadge(file) + '</div></div>';

    if (hasMultipleSigs && file.signatures) {
        html += '<div class="signatures-detail" id="' + fileId + '">';
        for (const sig of file.signatures) {
            html += '<div class="signature-row">';
            html += '<div class="sig-index">#' + sig.index + '</div>';
            html += '<div class="sig-name">' + (sig.signer || '—') + '</div>';
            html += '<div class="sig-ckait">' + (sig.ckait || '—') + '</div>';
            html += '<div class="sig-tsa">' + getTsaBadgeForSig(sig.tsa) + '</div>';
            html += '<div class="sig-date">' + (sig.date || '—') + '</div>';
            html += '</div>';
        }
        html += '</div>';
    }

    html += '</div>';
    return html;
}

// Toggle pro stromovou složku (stav se pamatuje pro Rozbalit/Sbalit vše)
function toggleTreeFolder(folderId) {
    if (treeCollapsedIds.has(folderId)) treeCollapsedIds.delete(folderId);
    else treeCollapsedIds.add(folderId);
    const content = document.getElementById('folder-' + folderId);
    const arrow = document.getElementById('arrow-' + folderId);
    if (content && arrow) {
        content.classList.toggle('visible');
        arrow.classList.toggle('collapsed');
    }
}

// Sebere všechna folder id z jednoho stromu (pro collapseAll)
function collectFolderIdsFromTree(node, batchId, out) {
    for (const folderName of Object.keys(node.folders || {})) {
        const folder = node.folders[folderName];
        const folderId = batchId + '-' + folder.path.replace(/[^a-z0-9]/gi, '_');
        out.push(folderId);
        collectFolderIdsFromTree(folder, batchId, out);
    }
}

// Rozbalit/sbalit úroveň
function expandLevel(level) {
    // level 0 = batche, level 1 = první úroveň složek, atd.
    document.querySelectorAll('.folder').forEach(folder => {
        const depth = (folder.style.marginLeft ? parseInt(folder.style.marginLeft) / TREE_INDENT_PX : 0);
        const content = folder.querySelector('.folder-content');
        const arrow = folder.querySelector('.folder-arrow');
        if (content && arrow) {
            if (depth < level) {
                content.classList.add('visible');
                arrow.classList.remove('collapsed');
            } else {
                content.classList.remove('visible');
                arrow.classList.add('collapsed');
            }
        }
    });
}

function getStats(files) {
    return {
        total: files.length,
        pdfaOk: files.filter(f => f.pdfaStatus === 'OK').length,
        pdfaFail: files.filter(f => f.pdfaStatus !== 'OK').length,
        sigOk: files.filter(f => f.sig === 'OK').length
    };
}

function updateStats() {
    const allFiles = batches.flatMap(b => b.files);
    const stats = getStats(allFiles);
    document.getElementById('total-count').textContent = stats.total;
    document.getElementById('pdfa-ok').textContent = stats.pdfaOk;
    document.getElementById('pdfa-fail').textContent = stats.pdfaFail;
    document.getElementById('sig-ok').textContent = stats.sigOk;
}

// ===== BADGES =====
// PDF/A: zeleně A-3 / A-3b / A-3a (úroveň shody), červeně A-2, A-1, NE. Title = verze PDF (např. 1.7)
function getPdfaBadge(f) {
    const title = f.pdfVersion ? ('PDF ' + f.pdfVersion) : '';
    if (f.pdfaStatus === 'OK') {
        const label = (f.pdfaLevel && f.pdfaLevel !== 'A-3') ? f.pdfaLevel : 'A-3';
        return '<span class="badge badge-green" title="' + title + '">' + label + '</span>';
    }
    if (f.pdfaVersion === 2) return '<span class="badge badge-red" title="' + title + '">A-2</span>';
    if (f.pdfaVersion === 1) return '<span class="badge badge-red" title="' + title + '">A-1</span>';
    return '<span class="badge badge-red" title="' + title + '">NE</span>';
}
// Podpis: zeleně autorizovaná osoba (ČKAIT), červeně podpis bez autor. / žádný podpis
function getSigBadge(f) {
    if (f.sig === 'OK') return '<span class="badge badge-green">Autor. osoba</span>';
    if (f.sig === 'PARTIAL') return '<span class="badge badge-red">Podpis (ne autor.)</span>';
    return '<span class="badge badge-red">Žádný podpis</span>';
}
// Razítko: VČR (vložené časové) = zeleně, LOK / bez razítka = červeně
function getTsaBadge(f) {
    if (f.tsa === 'TSA') return '<span class="badge badge-green">VČR</span>';
    if (f.tsa === 'PARTIAL') return '<span class="badge badge-red">MIX</span>';
    if (f.tsa === 'LOCAL') return '<span class="badge badge-red">LOK</span>';
    return '<span class="badge badge-red">Bez razítka</span>';
}
function getTsaBadgeForSig(tsa) {
    if (tsa === 'TSA') return '<span class="badge badge-green">VČR</span>';
    if (tsa === 'LOCAL') return '<span class="badge badge-red">LOK</span>';
    return '<span class="badge badge-red">Bez razítka</span>';
}

// ===== SIGNATURES EXPAND =====
function toggleSignatures(fileId) {
    const detail = document.getElementById(fileId);
    if (detail) {
        detail.classList.toggle('visible');
        // Změň šipku
        const row = detail.previousElementSibling;
        if (row) {
            const sigCell = row.querySelector('.sig-expandable');
            if (sigCell) {
                if (detail.classList.contains('visible')) {
                    sigCell.innerHTML = sigCell.innerHTML.replace('▶', '▼');
                } else {
                    sigCell.innerHTML = sigCell.innerHTML.replace('▼', '▶');
                }
            }
        }
    }
}

// ===== EXPAND/COLLAPSE =====
function toggleBatch(id) {
    const batch = batches.find(b => b.id === id);
    if (batch) { batch.collapsed = !batch.collapsed; renderResults(); }
}
function toggleFolder(folderId) {
    if (treeCollapsedIds.has(folderId)) treeCollapsedIds.delete(folderId);
    else treeCollapsedIds.add(folderId);
    const content = document.getElementById('folder-' + folderId);
    const arrow = document.getElementById('arrow-' + folderId);
    if (content && arrow) { content.classList.toggle('visible'); arrow.classList.toggle('collapsed'); }
}
function expandAll() {
    treeCollapsedIds.clear();
    batches.forEach(b => b.collapsed = false);
    renderResults();
}
function collapseAll() {
    const allIds = [];
    for (const batch of batches) {
        const filtered = filterFiles(batch.files);
        const folderTree = buildFolderTree(filtered);
        collectFolderIdsFromTree(folderTree, batch.id, allIds);
    }
    treeCollapsedIds = new Set(allIds);
    batches.forEach(b => b.collapsed = true);
    renderResults();
}

// ===== BATCH OPS =====
async function deleteBatch(id) {
    const batch = batches.find(b => b.id === id);
    if (!batch) return;

    if (batch.batch_id && !batch.batch_id.startsWith('legacy_')) {
        if (!confirm('Smazat dávku "' + batch.name + '" i ze serveru?')) return;
        const user = getStoredUser();
        if (!user || !user.api_key) {
            alert('Pro mazání ze serveru se přihlaste.');
            return;
        }
        try {
            const resp = await fetch('/api/batch/' + batch.batch_id, {
                method: 'DELETE',
                headers: { 'Authorization': 'Bearer ' + user.api_key }
            });
            if (!resp.ok) {
                const d = await resp.json().catch(() => ({}));
                alert(d.error || 'Mazání se nezdařilo.');
                return;
            }
        } catch (e) { console.error('Chyba mazání ze serveru:', e); return; }
    }

    batches = batches.filter(b => b.id !== id);
    renderResults();
    updateFilterLists();
}
function clearAll() {
    if (confirm('Vymazat lokální zobrazení?')) {
        batches = [];
        renderResults();
        updateFilterLists();
    }
}

async function deleteAllBatches() {
    const user = getStoredUser();
    if (!user || !user.api_key) {
        alert('Pro mazání dat se přihlaste. Smažou se pouze vaše kontroly.');
        return;
    }
    if (!confirm('Opravdu smazat VAŠE data ze serveru?\\n\\nSmažou se pouze vaše kontroly (nikoli data jiných uživatelů).')) return;

    try {
        const resp = await fetch('/api/all-data', {
            method: 'DELETE',
            headers: { 'Authorization': 'Bearer ' + user.api_key }
        });
        const data = await resp.json();

        if (resp.ok) {
            alert('Vaše data byla smazána ze serveru');
            batches = [];
            renderResults();
            updateFilterLists();
            // Reset statistik
            document.getElementById('agent-total').textContent = '0';
            document.getElementById('agent-pdfa-ok').textContent = '0';
        } else {
            alert('Chyba při mazání: ' + (data.error || 'Neznámá chyba'));
        }
    } catch (e) {
        console.error(e);
        alert('Chyba při mazání dat');
    }
}

// Stahování s Authorization (API vyžaduje přihlášení)
async function fetchWithAuthAndDownload(url, defaultFilename) {
    const user = getStoredUser();
    if (!user || !user.api_key) {
        alert('Pro export se přihlaste.');
        return;
    }
    const resp = await fetch(url, { headers: { 'Authorization': 'Bearer ' + user.api_key } });
    if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        alert(err.error || 'Export se nezdařil.');
        return;
    }
    const blob = await resp.blob();
    const disp = resp.headers.get('Content-Disposition');
    const filename = (disp && disp.match(/filename=(.+)/)) ? disp.match(/filename=(.+)/)[1].trim().replace(/\"/g,'') : defaultFilename;
    const blobUrl = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = blobUrl; a.download = filename; a.click();
    setTimeout(function() { URL.revokeObjectURL(blobUrl); }, 100);
}

// ===== EXCEL / CSV EXPORT (Pro+ má oba, Basic nemá žádný) =====
function exportCSV() {
    if (!checkFeatureAccess('export_csv')) return;
    fetchWithAuthAndDownload('/api/agent/export-all', 'export_vse.xlsx');
}
function exportBatchCSV(id) {
    // Fallback pro lokální batch (bez batch_id)
    const b = batches.find(b => b.id === id);
    if (b) downloadLocalCSV(b.files, b.name + '.csv');
}
function downloadLocalCSV(files, filename) {
    const BOM = '\\uFEFF';
    const header = 'Cesta;Název;PDF/A;PDF verze;Podpis;Jméno;ČKAIT;Čas.razítko\\n';
    const pdfaCol = f => (f.pdfaLevel || (f.pdfaVersion ? 'A-' + f.pdfaVersion : '') || 'NE');
    const pdfVerCol = f => (f.pdfVersion || '');
    const rows = files.map(f => f.path + ';' + f.name + ';' + pdfaCol(f) + ';' + pdfVerCol(f) + ';' + f.sig + ';' + f.signer + ';' + f.ckait + ';' + f.tsa).join('\\n');
    const blob = new Blob([BOM + header + rows], { type: 'text/csv;charset=utf-8' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = filename; a.click();
}

// ===== MODAL =====
function showInfoModal() { document.getElementById('info-modal').classList.add('visible'); }
function hideInfoModal() { document.getElementById('info-modal').classList.remove('visible'); }
function showHelpModal() { document.getElementById('help-modal').classList.add('visible'); }
function hideHelpModal() { document.getElementById('help-modal').classList.remove('visible'); }
function setInfoTab(tabId, btn) {
    document.querySelectorAll('.modal-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.modal-content > div').forEach(c => c.classList.add('hidden'));
    btn.classList.add('active');
    document.getElementById('tab-' + tabId).classList.remove('hidden');
}
// Listenery pro modaly se registrují v DOMContentLoaded (až je DOM připraven)

// ===== AGENT MODE - NAČÍTÁNÍ Z API (v40 - batch podpora) =====
function clearResultsView() {
    batches = [];
    const container = document.getElementById('results-container');
    if (container) {
        container.innerHTML = '<div style="padding:40px;text-align:center;color:#6b7280;"><div style="font-size:2em;margin-bottom:16px;">🔄</div><div>Po přihlášení / odhlášení jsou data vymazána.</div><div style="font-size:0.85em;margin-top:8px;">Klikněte na „Načíst výsledky“ pro zobrazení pouze vašich kontrol.</div></div>';
    }
    const statsDiv = document.getElementById('agent-stats');
    if (statsDiv) statsDiv.style.display = 'none';
    const onlyYourLabel = document.getElementById('only-your-checks-label');
    if (onlyYourLabel) onlyYourLabel.style.display = 'none';
}

async function loadAgentResults() {
    try {
        document.getElementById('results-container').innerHTML = '<div style="padding:40px;text-align:center;color:#1e5a8a;"><div style="font-size:2em;margin-bottom:16px;">⏳</div><div>Načítám data z agenta...</div></div>';

        const user = getStoredUser();
        const headers = {};
        if (user && user.api_key) {
            headers['Authorization'] = 'Bearer ' + user.api_key;
        }
        const response = await fetch('/api/agent/results', { headers });
        var data;
        try {
            data = await response.json();
        } catch (parseErr) {
            console.error('Parse response error:', parseErr);
            document.getElementById('results-container').innerHTML = '<div style="padding:40px;text-align:center;color:#dc2626;">Chyba odpovědi serveru. Zkuste obnovit stránku.</div>';
            return;
        }

        if (data.error) {
            document.getElementById('results-container').innerHTML = '<div style="padding:40px;text-align:center;color:#dc2626;"><div style="font-size:2em;margin-bottom:16px;">❌</div><div>' + data.error + '</div></div>';
            return;
        }

        // Aktualizuj licenci podle odpovědi serveru (tier z api_key, pod kterým jsou data)
        if (data.license) {
            licenseState.tier = data.license.tier !== undefined ? data.license.tier : 0;
            licenseState.tierName = data.license.tier_name || 'Free';
            updateLicenseBadge();
            updateFeatureLocks();
        }

        // Zobraz statistiky
        const statsDiv = document.getElementById('agent-stats');
        statsDiv.style.display = 'block';
        document.getElementById('agent-total').textContent = data.stats.total_checks;
        document.getElementById('agent-pdfa-ok').textContent = data.stats.pdf_a3_count;

        // NOVÉ v40: API vrací data.batches (seskupené podle batch_id)
        if (data.batches && data.batches.length > 0) {
            batches = data.batches.map((batch, i) => {
                // Převeď výsledky z batche do formátu pro renderování
                const files = (batch.results || []).map(r => {
                    const parsed = r.parsed_results || {};
                    const pdfFormat = parsed.results?.pdf_format || {};
                    const signatures = parsed.results?.signatures || [];

                    // Cesta - použij folder_path + file_name pro správnou stromovou strukturu
                    const folderPath = r.folder_path || '.';
                    const filePath = (folderPath && folderPath !== '.') ? (folderPath + '/' + r.file_name) : r.file_name;

                    return {
                        name: r.file_name,
                        path: filePath,
                        pdfaVersion: pdfFormat.is_pdf_a3 ? 3 : (pdfFormat.exact_version?.includes('2') ? 2 : (pdfFormat.exact_version?.includes('1') ? 1 : null)),
                        pdfaStatus: pdfFormat.is_pdf_a3 ? 'OK' : 'FAIL',
                        sig: signatures.length > 0 ? (signatures.every(s => s.valid !== false) ? 'OK' : 'PARTIAL') : 'FAIL',
                        signer: signatures.map(s => s.name).filter(n => n && n !== '—').join(', ') || '—',
                        ckait: signatures.map(s => s.ckait_number).filter(n => n && n !== '—').join(', ') || '—',
                        tsa: signatures.some(s => s.timestamp_valid) ? 'TSA' : (signatures.length > 0 ? 'LOCAL' : 'NONE'),
                        sig_count: signatures.length,
                        signatures: signatures.map((s, idx) => ({
                            index: idx + 1,
                            signer: s.name || '—',
                            ckait: s.ckait_number || '—',
                            tsa: s.timestamp_valid ? 'TSA' : 'LOCAL',
                            date: s.date || '—'
                        }))
                    };
                });

                // Název batche
                const batchName = batch.batch_name || ('Kontrola - ' + (batch.created_at || 'Neznámé'));
                const timestamp = batch.created_at ? batch.created_at.split(' ')[0] : '';

                return {
                    id: i + 1,
                    batch_id: batch.batch_id,  // Pro export
                    name: batchName,
                    timestamp: timestamp,
                    source_folder: batch.source_folder,
                    files: files,
                    collapsed: i > 0  // Rozbalený jen první batch
                };
            });

            renderResults();
            updateFilterLists();
            const onlyYourLabel = document.getElementById('only-your-checks-label');
            if (onlyYourLabel) onlyYourLabel.style.display = 'block';
        } else {
            const user = getStoredUser();
            const msg = user
                ? '<div style="padding:40px;text-align:center;color:#9ca3af;"><div style="font-size:3em;margin-bottom:16px;">📭</div><div>Zatím žádné výsledky z agenta</div><div style="font-size:0.85em;margin-top:8px;">Spusťte desktop agenta a zkontrolujte nějaké PDF soubory. Zobrazují se pouze vaše kontroly.</div></div>'
                : '<div style="padding:40px;text-align:center;color:#6b7280;"><div style="font-size:3em;margin-bottom:16px;">🔐</div><div>Pro zobrazení výsledků se přihlaste</div><div style="font-size:0.85em;margin-top:8px;">Pod přihlašovacím jménem uvidíte pouze své kontroly a historii. Žádná data jiných uživatelů.</div></div>';
            document.getElementById('results-container').innerHTML = msg;
            const onlyYourLabel = document.getElementById('only-your-checks-label');
            if (onlyYourLabel) onlyYourLabel.style.display = 'none';
        }

    } catch (error) {
        console.error('Chyba při načítání:', error);
        document.getElementById('results-container').innerHTML = '<div style="padding:40px;text-align:center;color:#dc2626;"><div style="font-size:2em;margin-bottom:16px;">❌</div><div>Chyba při načítání dat: ' + error.message + '</div></div>';
    }
}

// Export batch ze serveru (vyžaduje přihlášení – jen vlastní dávka)
async function exportBatchFromServer(batchId) {
    if (!batchId || batchId.startsWith('legacy_')) {
        const batch = batches.find(b => b.batch_id === batchId || b.id === parseInt(batchId));
        if (batch) exportBatchCSV(batch.id);
        return;
    }
    await fetchWithAuthAndDownload('/api/agent/batch/' + batchId + '/export?format=csv', 'batch_export.xlsx');
}

// =============================================================================
// LICENSE & FEATURE MANAGEMENT (v41)
// =============================================================================

// Přihlášení uživatele: ukládá se do localStorage prohlížeče (klíč pdfcheck_user).
// Žádná MAC adresa – jen údaje v tomto prohlížeči na tomto PC. Jiný prohlížeč / jiný PC = znovu přihlásit.
const USER_STORAGE_KEY = 'pdfcheck_user';
function getStoredUser() {
    try {
        const s = localStorage.getItem(USER_STORAGE_KEY);
        return s ? JSON.parse(s) : null;
    } catch (e) { return null; }
}
function setStoredUser(obj) { localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(obj)); }
function clearStoredUser() { localStorage.removeItem(USER_STORAGE_KEY); }

function focusLogin() {
    setMode('agent');
    setTimeout(function() {
        const el = document.getElementById('login-email');
        if (el) { el.focus(); el.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); }
    }, 100);
}

function updateLoggedInUI() {
    const u = getStoredUser();
    const area = document.getElementById('logged-in-area');
    const loginBlock = document.getElementById('login-block');
    const headerLoginBtn = document.getElementById('header-login-btn');
    const freeTrialHint = document.getElementById('free-trial-hint');
    if (u) {
        if (area) {
            area.style.display = '';
            const disp = document.getElementById('logged-in-display');
            if (disp) disp.textContent = (u.email || u.user_name || 'Účet') + ' (' + (u.tier_name || 'Free') + ')';
        }
        if (headerLoginBtn) headerLoginBtn.style.display = 'none';
        if (loginBlock) loginBlock.style.display = 'none';
        if (freeTrialHint) freeTrialHint.style.display = 'none';
        licenseState.tier = u.tier !== undefined ? u.tier : 0;
        licenseState.tierName = u.tier_name || 'Free';
    } else {
        if (area) area.style.display = 'none';
        if (headerLoginBtn) headerLoginBtn.style.display = 'inline';
        if (loginBlock) loginBlock.style.display = 'block';
        if (freeTrialHint) freeTrialHint.style.display = 'block';
        licenseState.tier = 0;
        licenseState.tierName = 'Free';
    }
    updateLicenseBadge();
    updateFeatureLocks();
}

async function doLogin() {
    const emailEl = document.getElementById('login-email');
    const passEl = document.getElementById('login-password');
    const email = (emailEl && emailEl.value) ? emailEl.value.trim() : '';
    const password = passEl ? passEl.value : '';
    if (!email || !password) {
        alert('Zadejte e-mail a heslo');
        return;
    }
    try {
        const resp = await fetch('/api/auth/user-login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: email, password: password })
        });
        var data;
        try {
            data = await resp.json();
        } catch (e) {
            alert('Chyba odpovědi serveru. Zkuste znovu.');
            return;
        }
        if (data.success) {
            setStoredUser({
                api_key: data.api_key,
                email: data.email,
                user_name: data.user_name,
                tier: data.tier !== undefined ? data.tier : 0,
                tier_name: data.tier_name || 'Free'
            });
            clearResultsView();
            updateLoggedInUI();
            if (passEl) passEl.value = '';
            loadAgentResults();
        } else {
            alert(data.error || 'Přihlášení se nezdařilo');
        }
    } catch (e) {
        alert('Chyba: ' + e.message);
    }
}

function doLogout() {
    clearStoredUser();
    clearResultsView();
    updateLoggedInUI();
}

// Aktuální stav licence (default: FREE)
let licenseState = {
    tier: 0,
    tierName: 'Free',
    features: ['pdf_check', 'signature_check'],
    limits: { max_files_per_batch: 5, rate_limit_per_hour: 3 },
    isValid: true
};

// Tier konfigurace pro UI
const TIER_CONFIG = {
    0: { name: 'Free', icon: '🆓', class: 'free' },
    1: { name: 'Basic', icon: '⭐', class: 'basic' },
    2: { name: 'Pro', icon: '💎', class: 'pro' },
    3: { name: 'Enterprise', icon: '🏢', class: 'enterprise' }
};

// Feature requirements: Free 5 | Basic 100 bez exportu | Pro vše
const FEATURE_REQUIREMENTS = {
    'export_excel': 2,      // jen Pro+
    'export_csv': 2,        // jen Pro+
    'batch_upload': 1,      // Basic+
    'tree_structure': 2,    // Pro+
    'tsa_filter': 2,       // Pro+
    'advanced_filters': 2,  // Pro+
    'export_all': 2         // Pro+
};

function updateLicenseBadge() {
    const badge = document.getElementById('license-badge');
    const tierName = document.getElementById('license-tier-name');
    const config = TIER_CONFIG[licenseState.tier] || TIER_CONFIG[0];

    // Odstraň staré třídy
    badge.className = 'license-badge ' + config.class;

    // Aktualizuj obsah
    badge.querySelector('.license-badge-icon').textContent = config.icon;
    tierName.textContent = config.name;
}

function hasFeature(featureName) {
    // Pokud je feature v seznamu dostupných features
    if (licenseState.features && licenseState.features.includes(featureName)) {
        return true;
    }

    // Nebo zkontroluj podle tier requirements
    const requiredTier = FEATURE_REQUIREMENTS[featureName];
    if (requiredTier === undefined) return true; // Neomezená funkce
    return licenseState.tier >= requiredTier;
}

function checkFeatureAccess(featureName) {
    if (hasFeature(featureName)) {
        return true;
    }

    // Zobraz upgrade hint
    const requiredTier = FEATURE_REQUIREMENTS[featureName];
    const config = TIER_CONFIG[requiredTier] || TIER_CONFIG[1];
    alert('Tato funkce vyžaduje ' + config.name + ' licenci nebo vyšší.\\n\\nUpgradujte pro odemčení všech funkcí.');
    return false;
}

function updateFeatureLocks() {
    const hasExcel = hasFeature('export_excel');
    const hasCsv = hasFeature('export_csv');
    const excelLock = document.getElementById('excel-lock');
    if (excelLock) excelLock.style.display = hasExcel ? 'none' : 'inline';
    const csvLock = document.getElementById('csv-lock');
    if (csvLock) csvLock.style.display = hasCsv ? 'none' : 'inline';
    const btnExportCsv = document.getElementById('btn-export-csv');
    if (btnExportCsv) {
        if (!hasCsv) btnExportCsv.classList.add('feature-locked');
        else btnExportCsv.classList.remove('feature-locked');
    }
    const exportAllBtn = document.getElementById('btn-export-all');
    if (exportAllBtn) {
        if (!hasFeature('export_all')) exportAllBtn.classList.add('feature-locked');
        else exportAllBtn.classList.remove('feature-locked');
    }
}

// Excel export – jen vlastní dávka (vyžaduje přihlášení)
function exportExcel() {
    if (!checkFeatureAccess('export_excel')) return;
    if (batches.length === 0) {
        alert('Nejsou žádná data k exportu.');
        return;
    }
    const batchId = batches[0].batch_id;
    if (batchId && !batchId.startsWith('legacy_')) {
        fetchWithAuthAndDownload('/api/agent/batch/' + batchId + '/export?format=xlsx', 'batch.xlsx');
    } else {
        alert('Pro Excel export je potřeba batch z agenta (ne legacy data).');
    }
}

// Export všech dat (Pro+) – jen vaše data
function exportAllExcel() {
    if (!checkFeatureAccess('export_all')) return;
    fetchWithAuthAndDownload('/api/agent/export-all', 'export_vse.xlsx');
}

// Automaticky načíst data při startu: bez přihlášení defaultně Lokální (free trial), s přihlášením Z Agenta
document.addEventListener('DOMContentLoaded', function() {
    try {
        var im = document.getElementById('info-modal');
        if (im) im.addEventListener('click', function(e) { if (e.target === this) hideInfoModal(); });
        var hm = document.getElementById('help-modal');
        if (hm) hm.addEventListener('click', function(e) { if (e.target === this) hideHelpModal(); });
        updateLoggedInUI();
        // Jednorázový přihlašovací odkaz z agenta (?login_token=xxx) – automatické přihlášení
        var params = new URLSearchParams(window.location.search);
        var loginToken = params.get('login_token');
        if (loginToken) {
            history.replaceState(null, '', window.location.pathname || '/');
            (async function() {
                try {
                    var resp = await fetch('/api/auth/session-from-token?token=' + encodeURIComponent(loginToken));
                    var data = await resp.json().catch(function() { return {}; });
                    if (data.success) {
                        setStoredUser({
                            api_key: data.api_key,
                            email: data.email,
                            user_name: data.user_name,
                            tier: data.tier !== undefined ? data.tier : 0,
                            tier_name: data.tier_name || 'Free'
                        });
                        updateLoggedInUI();
                        setMode('agent');
                        loadAgentResults();
                    } else {
                        if (data.error && resp.status !== 401) {
                            alert(data.error || 'Přihlášení z odkazu se nezdařilo.');
                        }
                    }
                } catch (e) {
                    console.error('login_token error:', e);
                }
            })();
            return;
        }
        var user = getStoredUser();
        if (user) {
            setMode('agent');
        } else {
            setMode('local');
        }
        var testEl = document.getElementById('script-ok-test');
        if (testEl) testEl.textContent = 'Script OK';
    } catch (e) {
        console.error('Startup error:', e);
        if (window.onerror) window.onerror(e.message, e.filename, e.lineno, e.colno, e);
    }
});
</script>
</body>
</html>
'''

# =============================================================================
# BACKEND - ANALÝZA PDF (z v25)
# =============================================================================

def check_pdfa_version(content):
    """Zjistí verzi PDF/A, verzi PDF (např. 1.7) a úroveň shody (3a, 3b, 3u, 3y).
    Vrací (part, status, pdf_version, conformance).
    pdf_version = např. '1.7', conformance = 'a'|'b'|'u'|'y'|'' (prázdné pokud neznámé).
    """
    pdf_version = ''
    conformance = ''
    try:
        # Verze PDF z hlavičky: %PDF-1.7 nebo %PDF-1.6
        pdf_header = re.search(rb'%PDF-(\d+\.\d+)', content[:100])
        if pdf_header:
            pdf_version = pdf_header.group(1).decode('ascii')
    except Exception:
        pass

    try:
        # Úroveň shody PDF/A z XMP: pdfaid:conformance="B" nebo conformance='A'
        conf_match = re.search(rb"pdfaid:conformance=['\"]?([ABUYabuy])['\"]?", content, re.IGNORECASE)
        if conf_match:
            conformance = conf_match.group(1).decode('ascii').lower()
        # Nebo z textu: PDF/A-3b, PDF/A-3a, PDF/A-3u, PDF/A-3y
        if not conformance:
            for level in [b'PDF/A-3y', b'PDF/A-3u', b'PDF/A-3b', b'PDF/A-3a']:
                if level in content:
                    conformance = level.decode('ascii')[-1].lower()  # y, u, b, a
                    break
    except Exception:
        pass

    try:
        # Část PDF/A (1, 2, 3) – XMP nebo text
        patterns = [
            (rb"pdfaid:part=['\"]?3", 3),
            (rb'pdfaid:part>3<', 3),
            (rb"pdfaid:part=['\"]?2", 2),
            (rb'pdfaid:part>2<', 2),
            (rb"pdfaid:part=['\"]?1", 1),
            (rb'pdfaid:part>1<', 1),
        ]
        for pattern, version in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                status = 'OK' if version == 3 else 'FAIL'
                return version, status, pdf_version, conformance
        if b'PDF/A-3' in content:
            return 3, 'OK', pdf_version, conformance
        if b'PDF/A-2' in content:
            return 2, 'FAIL', pdf_version, conformance
        if b'PDF/A-1' in content:
            return 1, 'FAIL', pdf_version, conformance
        return None, 'FAIL', pdf_version, conformance
    except Exception:
        return None, 'FAIL', pdf_version, conformance

def extract_all_signatures(content):
    """Extrahuje VŠECHNY podpisy z PDF"""
    signatures = []
    
    # Najdi všechny /ByteRange - každý představuje jeden podpis
    byteranges = list(re.finditer(rb'/ByteRange\s*\[([^\]]+)\]', content))
    
    for i, br in enumerate(byteranges):
        sig_info = {
            'index': i + 1,
            'signer': '—',
            'ckait': '—',
            'tsa': 'NONE',
            'date': '—'
        }
        
        br_pos = br.start()
        
        # Hledej v okolí ByteRange (celý signature dictionary)
        # Contents může být i hodně před ByteRange, rozšířit hledání
        search_start = max(0, br_pos - 25000)
        search_end = min(len(content), br_pos + 50000)
        search_area = content[search_start:search_end]
        
        # /Name – v PDF může být UTF-16BE (BOM \xfe\xff), PDFDocEncoding, nebo escape \ddd (octal)
        name_match = re.search(rb'/Name\s*\(([^)]+)\)', search_area)
        if name_match:
            raw_name = name_match.group(1)
            # Odstranit PDF escape sekvence: \n \r \t \b \f \( \) \\ a \ddd (octal)
            def unescape_pdf_string(b):
                out = []
                i = 0
                while i < len(b):
                    if b[i:i+1] == b'\\' and i + 1 < len(b):
                        n = b[i+1:i+2]
                        if n in b'nrtbf':
                            out.append(bytes([{b'n': 10, b'r': 13, b't': 9, b'b': 8, b'f': 12}[n]]))
                            i += 1
                        elif n in b'()\\':
                            out.append(b[i+1:i+2])
                            i += 1
                        elif n.isdigit():
                            octal_len = 1
                            if i + 2 < len(b) and b[i+2:i+3].isdigit():
                                octal_len = 2
                                if i + 3 < len(b) and b[i+3:i+4].isdigit():
                                    octal_len = 3
                            out.append(bytes([int(b[i+1:i+1+octal_len].decode('ascii'), 8)]))
                            i += octal_len
                        i += 1
                    else:
                        out.append(b[i:i+1])
                    i += 1
                return b''.join(out)
            raw_name = unescape_pdf_string(raw_name)
            if raw_name.startswith(b'\xfe\xff'):
                sig_info['signer'] = raw_name[2:].decode('utf-16-be', errors='replace')
            elif b'\x00' in raw_name[:min(20, len(raw_name))]:
                sig_info['signer'] = raw_name.decode('utf-16-be', errors='replace')
            else:
                # České znaky: cp1250 (Windows-1250) před utf-8
                for enc in ['cp1250', 'utf-8', 'windows-1250', 'latin-1']:
                    try:
                        sig_info['signer'] = raw_name.decode(enc, errors='replace')
                        if sig_info['signer'] and not any(ord(c) == 0xFFFD for c in sig_info['signer'][:20]):
                            break
                    except Exception:
                        continue
            sig_info['signer'] = sig_info['signer'].replace('\n', '').replace('\r', '').replace('\ufffd', '?').strip()
            if sig_info['signer'].lower() == 'default' or len(sig_info['signer']) < 2:
                sig_info['signer'] = '—'
        
        # /M (datum)
        m_match = re.search(rb'/M\s*\(D:(\d{14})', search_area)
        if m_match:
            d = m_match.group(1).decode('ascii')
            sig_info['date'] = f"{d[:4]}-{d[4:6]}-{d[6:8]} {d[8:10]}:{d[10:12]}"
        
        # /Contents<hex> - PKCS7 data
        contents_match = re.search(rb'/Contents\s*<([0-9a-fA-F]+)>', search_area)
        if contents_match:
            try:
                hex_data = contents_match.group(1).decode('ascii')
                pkcs7 = bytes.fromhex(hex_data)
                pkcs7_hex = pkcs7.hex()
                
                # TSA OID
                tsa_oid = bytes.fromhex('060b2a864886f70d010910020e')
                if tsa_oid in pkcs7:
                    sig_info['tsa'] = 'TSA'
                elif m_match:
                    sig_info['tsa'] = 'LOCAL'
                
                # ČKAIT (OU s 7 číslicemi) nebo ČKA (5 číslic)
                # Hledáme délky: 7 (ČKAIT), 6 (ČKAIT), 5 (ČKA), 4 (ČKA)

                # Délka 7 - ČKAIT
                ou_match = re.search(r'060355040b(?:0c|13)07([0-9a-f]{14})', pkcs7_hex, re.I)
                if ou_match:
                    ckait = bytes.fromhex(ou_match.group(1)).decode('utf-8', errors='ignore')
                    if re.match(r'^\d{7}$', ckait):
                        sig_info['ckait'] = ckait  # ČKAIT 7 číslic

                # Délka 6 - ČKAIT
                if sig_info['ckait'] == '—':
                    ou_match = re.search(r'060355040b(?:0c|13)06([0-9a-f]{12})', pkcs7_hex, re.I)
                    if ou_match:
                        ckait = bytes.fromhex(ou_match.group(1)).decode('utf-8', errors='ignore')
                        if re.match(r'^\d{6}$', ckait):
                            sig_info['ckait'] = ckait  # ČKAIT 6 číslic

                # Délka 5 - ČKA (Česká komora architektů)
                if sig_info['ckait'] == '—':
                    ou_match = re.search(r'060355040b(?:0c|13)05([0-9a-f]{10})', pkcs7_hex, re.I)
                    if ou_match:
                        cka = bytes.fromhex(ou_match.group(1)).decode('utf-8', errors='ignore')
                        if re.match(r'^\d{5}$', cka):
                            sig_info['ckait'] = cka  # ČKA 5 číslic (uloženo do stejného pole)

                # Délka 4 - ČKA alternativní formát
                if sig_info['ckait'] == '—':
                    ou_match = re.search(r'060355040b(?:0c|13)04([0-9a-f]{8})', pkcs7_hex, re.I)
                    if ou_match:
                        cka = bytes.fromhex(ou_match.group(1)).decode('utf-8', errors='ignore')
                        if re.match(r'^\d{4}$', cka):
                            sig_info['ckait'] = cka  # ČKA 4 číslice
                
                # Fallback pro jméno z PKCS7 (CN) - vyfiltrovat CA certifikáty
                if sig_info['signer'] == '—':
                    ca_keywords = ['postsignum', 'root', 'qca', 'tsa', 'tsu', 'ocsp', 'acaeid', 'qualified ca', 'i.ca', 'eidentity']
                    found_cns = []
                    
                    for typ in ['0c', '13']:  # UTF8String, PrintableString
                        for length in range(5, 80):
                            hex_len = format(length, '02x')
                            pattern = f'0603550403{typ}{hex_len}([0-9a-f]{{{length*2}}})'
                            for cn_match in re.finditer(pattern, pkcs7_hex, re.I):
                                try:
                                    cn = bytes.fromhex(cn_match.group(1)).decode('utf-8', errors='ignore')
                                    if len(cn) > 3:
                                        is_ca = any(kw in cn.lower() for kw in ca_keywords)
                                        found_cns.append((cn, is_ca, cn_match.start()))
                                except:
                                    pass
                    
                    # Seřadit podle pozice (první v certifikátu je obvykle subjekt)
                    found_cns.sort(key=lambda x: x[2])
                    
                    # Vzít první ne-CA CN
                    for cn, is_ca, pos in found_cns:
                        if not is_ca:
                            sig_info['signer'] = cn
                            break
            except:
                pass
        
        signatures.append(sig_info)
    
    return signatures

def check_signature_data(content):
    """Extrahuje informace o podpisech - podporuje více podpisů"""
    result = {
        'has_signature': False, 
        'signer_name': '—', 
        'ckait_number': '—',
        'signatures': [],
        'sig_count': 0
    }
    
    try:
        # Kontrola přítomnosti podpisu
        if b'/Type /Sig' not in content and b'/Type/Sig' not in content:
            return result
        
        result['has_signature'] = True
        signatures = extract_all_signatures(content)
        result['signatures'] = signatures
        result['sig_count'] = len(signatures)
        
        # Sloučené hodnoty pro zpětnou kompatibilitu
        signers = list(dict.fromkeys([s['signer'] for s in signatures if s['signer'] != '—']))
        ckaits = list(dict.fromkeys([s['ckait'] for s in signatures if s['ckait'] != '—']))
        
        result['signer_name'] = ', '.join(signers) if signers else '—'
        result['ckait_number'] = ', '.join(ckaits) if ckaits else '—'
        
        return result
    except:
        return result

def check_timestamp(content):
    """Kontrola časového razítka - TSA vs lokální vs žádné (pro všechny podpisy)"""
    try:
        if b'/Type /Sig' not in content and b'/Type/Sig' not in content:
            return 'NONE'
        
        signatures = extract_all_signatures(content)
        
        if not signatures:
            return 'NONE'
        
        tsas = [s['tsa'] for s in signatures]
        
        # Souhrn: TSA pokud všechny mají TSA, PARTIAL pokud některé, LOCAL/NONE jinak
        if all(t == 'TSA' for t in tsas):
            return 'TSA'
        elif any(t == 'TSA' for t in tsas):
            return 'PARTIAL'  # Některé mají TSA, některé ne
        elif any(t == 'LOCAL' for t in tsas):
            return 'LOCAL'
        else:
            return 'NONE'
    except:
        return 'NONE'

def analyze_pdf(content):
    """Kompletní analýza"""
    pdfa_version, pdfa_status, pdf_version, pdfa_conformance = check_pdfa_version(content)
    sig_data = check_signature_data(content)
    tsa = check_timestamp(content)
    
    if sig_data['has_signature']:
        # Kontrola: všechny podpisy mají ČKAIT?
        if sig_data['sig_count'] > 0:
            all_have_ckait = all(s['ckait'] != '—' for s in sig_data['signatures'])
            all_have_name = all(s['signer'] != '—' for s in sig_data['signatures'])
            if all_have_ckait and all_have_name:
                sig_status = 'OK'
            elif sig_data['ckait_number'] != '—' or sig_data['signer_name'] != '—':
                sig_status = 'PARTIAL'
            else:
                sig_status = 'PARTIAL'
        else:
            sig_status = 'PARTIAL'
    else:
        sig_status = 'FAIL'
    
    # Úroveň shody jako text: A-3b, A-3a, A-3, atd.
    pdfa_level = ''
    if pdfa_version == 3 and pdfa_conformance:
        pdfa_level = f'A-3{pdfa_conformance}'
    elif pdfa_version:
        pdfa_level = f'A-{pdfa_version}'
    return {
        'pdfaVersion': pdfa_version,
        'pdfaStatus': pdfa_status,
        'pdfVersion': pdf_version or None,
        'pdfaConformance': pdfa_conformance or None,
        'pdfaLevel': pdfa_level or None,
        'sig': sig_status,
        'signer': sig_data['signer_name'],
        'ckait': sig_data['ckait_number'],
        'tsa': tsa,
        'sig_count': sig_data.get('sig_count', 0),
        'signatures': sig_data.get('signatures', [])
    }

def analyze_pdf_file(filepath):
    """Analýza souboru z disku"""
    try:
        file_size = os.path.getsize(filepath)
        with open(filepath, 'rb') as f:
            if file_size <= 2 * 1024 * 1024:
                content = f.read()
            else:
                content = f.read(150 * 1024)
                f.seek(-1024 * 1024, 2)
                content += f.read()
        result = analyze_pdf(content)
        result['name'] = os.path.basename(filepath)
        return result
    except Exception as e:
        return {'name': os.path.basename(filepath), 'pdfaVersion': None, 'pdfaStatus': 'FAIL', 'pdfVersion': None, 'pdfaConformance': None, 'pdfaLevel': None, 'sig': 'FAIL', 'signer': '—', 'ckait': '—', 'tsa': 'NONE', 'error': str(e)}

def count_pdfs_in_folder(folder_path):
    """Spočítá PDF"""
    count = 0
    for root, dirs, files in os.walk(folder_path):
        count += sum(1 for f in files if f.lower().endswith('.pdf'))
    return count

# =============================================================================
# FLASK ROUTES
# =============================================================================

@app.route('/')
def index():
    """Landing page DokuCheck."""
    return render_template('landing.html')


@app.route('/auth/from-agent-token')
def auth_from_agent_token():
    """
    Přihlášení z Agenta: jednorázový token z URL přihlásí uživatele (session)
    a přesměruje rovnou na /app (kontroly), ne na landing.
    """
    token = request.args.get('login_token', '').strip()
    if not token:
        return redirect(url_for('app_main'))
    api_key, license_info = consume_one_time_token(token)
    if not api_key or not license_info:
        return redirect(url_for('app_main'))
    session['portal_user'] = {
        'api_key': api_key,
        'email': license_info.get('email'),
        'user_name': license_info.get('user_name'),
        'tier_name': license_info.get('tier_name'),
    }
    session.permanent = True
    return redirect(url_for('app_main'))


@app.route('/app')
def app_main():
    """Hlavní aplikace – kontrola PDF (původní UI)."""
    return render_template_string(HTML_TEMPLATE)


@app.route('/download')
def download():
    """Stránka stažení desktop agenta – propojení na budoucí odkaz ke stažení."""
    return redirect(url_for('app_main'))


@app.route('/online-check')
def online_check():
    """ONLINE Check – Drag&Drop max. 3 PDF, max. 2 MB na soubor, kontrola na serveru (cloud)."""
    return render_template('online_check.html')


@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    """Fakturační formulář. POST ukládá do pending_orders a zobrazí poděkování."""
    TARIF_LABELS = {'basic': 'BASIC', 'standard': 'STANDARD', 'premium': 'PREMIUM'}
    if request.method == 'POST':
        jmeno_firma = (request.form.get('jmeno_firma') or '').strip()
        ico = (request.form.get('ico') or '').strip()
        email = (request.form.get('email') or '').strip()
        tarif = (request.form.get('tarif') or 'standard').strip().lower()
        if not jmeno_firma or not email:
            flash('Vyplňte jméno/firmu a e-mail', 'error')
            return redirect(url_for('checkout', tarif=tarif))
        db = Database()
        order_id = db.insert_pending_order(jmeno_firma, ico, email, tarif, status='pending')
        if order_id:
            return render_template('checkout_thanks.html')
        flash('Chyba při odeslání. Zkuste to znovu.', 'error')
        return redirect(request.url)
    tarif = (request.args.get('tarif') or 'standard').strip().lower()
    if tarif not in TARIF_LABELS:
        tarif = 'standard'
    return render_template('checkout.html', tarif=tarif, tarif_label=TARIF_LABELS.get(tarif, 'STANDARD'))


@app.route('/portal', methods=['GET', 'POST'])
def portal():
    """Uživatelský portál: přihlášení e-mail + heslo (api_keys)."""
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip()
        password = request.form.get('password', '')
        if not email or not password:
            return render_template('portal_login.html', error='Vyplňte e-mail a heslo')
        db = Database()
        ok, data = db.verify_license_password(email, password)
        if not ok:
            return render_template('portal_login.html', error=data)
        session['portal_user'] = {
            'api_key': data['api_key'],
            'email': data.get('email'),
            'user_name': data.get('user_name'),
            'tier_name': data.get('tier_name'),
        }
        session.permanent = True
        return redirect(url_for('portal'))
    if session.get('portal_user'):
        db = Database()
        lic = db.get_user_license(session['portal_user']['api_key'])
        tier_name = (lic or {}).get('tier_name') or session['portal_user'].get('tier_name')
        exp = (lic or {}).get('license_expires')
        license_expires_label = exp[:10] if exp and len(exp) >= 10 else (exp or 'Neomezeno')
        return render_template('portal_dashboard.html',
                               tier_name=tier_name,
                               license_expires_label=license_expires_label,
                               pw_message=None, pw_error=False)
    return render_template('portal_login.html')


@app.route('/portal/logout')
def portal_logout():
    """Odhlášení z uživatelského portálu."""
    session.pop('portal_user', None)
    return redirect(url_for('index'))


@app.route('/portal/change-password', methods=['POST'])
def portal_change_password():
    """Změna hesla přihlášeného uživatele (portal)."""
    if not session.get('portal_user'):
        return redirect(url_for('portal'))
    api_key = session['portal_user']['api_key']
    current = request.form.get('current_password', '')
    new_pass = request.form.get('new_password', '')
    new_pass2 = request.form.get('new_password2', '')
    if not current or not new_pass or not new_pass2:
        return _portal_dashboard_with_message('Vyplňte všechna pole hesla', error=True)
    if new_pass != new_pass2:
        return _portal_dashboard_with_message('Nové heslo a potvrzení se neshodují', error=True)
    if len(new_pass) < 6:
        return _portal_dashboard_with_message('Heslo musí mít alespoň 6 znaků', error=True)
    db = Database()
    lic = db.get_license_by_email(session['portal_user'].get('email'))
    if not lic or not db._verify_password(current, lic.get('password_hash') or ''):
        return _portal_dashboard_with_message('Aktuální heslo není správné', error=True)
    if db.admin_set_license_password(api_key, new_pass):
        return _portal_dashboard_with_message('Heslo bylo změněno', error=False)
    return _portal_dashboard_with_message('Nepodařilo se změnit heslo', error=True)


def _portal_dashboard_with_message(message, error=True):
    """Pomocná: vykreslí portal dashboard s hláškou."""
    if not session.get('portal_user'):
        return redirect(url_for('portal'))
    db = Database()
    lic = db.get_user_license(session['portal_user']['api_key'])
    tier_name = (lic or {}).get('tier_name') or session['portal_user'].get('tier_name')
    exp = (lic or {}).get('license_expires')
    license_expires_label = exp[:10] if exp and len(exp) >= 10 else (exp or 'Neomezeno')
    return render_template('portal_dashboard.html',
                           tier_name=tier_name,
                           license_expires_label=license_expires_label,
                           pw_message=message, pw_error=error)


# Online Demo: max 3 soubory (vynuceno na frontendu), max 2 MB na soubor
ONLINE_DEMO_MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MB


@app.route('/analyze', methods=['POST'])
def analyze():
    """Kontrola jednoho PDF – serverové Body B (Online Demo). Max 2 MB, logování do online_demo_log."""
    if 'file' not in request.files:
        return jsonify({'error': 'Žádný soubor'}), 400
    file = request.files['file']
    try:
        content = file.read()
        if len(content) > ONLINE_DEMO_MAX_FILE_SIZE:
            return jsonify({'error': 'Soubor je větší než 2 MB. Pro větší soubory použijte Desktop aplikaci.'}), 400
        # Log pro admin statistiku (IP, počet souborů = 1 per request)
        try:
            db = Database()
            db.insert_online_demo_log(ip_address=request.remote_addr, file_count=1)
        except Exception:
            pass
        return jsonify(analyze_pdf(content))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/select_folder')
def select_folder_route():
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        folder_path = filedialog.askdirectory(title='Vyberte složku s PDF')
        root.destroy()
        if folder_path:
            return jsonify({'path': folder_path, 'pdf_count': count_pdfs_in_folder(folder_path)})
        return jsonify({'path': '', 'pdf_count': 0})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/scan-folder-stream')
def scan_folder_stream():
    """SSE endpoint pro skenování složky s průběžným progress"""
    folder_path = request.args.get('path', '')
    
    if not folder_path or not os.path.isdir(folder_path):
        def error_gen():
            yield f"data: {json.dumps({'type': 'error', 'message': 'Neplatná cesta'})}\n\n"
        return Response(error_gen(), mimetype='text/event-stream')
    
    def generate():
        # Najdi všechny PDF soubory
        pdf_files = []
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if file.lower().endswith('.pdf'):
                    pdf_files.append(os.path.join(root, file))
        
        total = len(pdf_files)
        if total == 0:
            yield f"data: {json.dumps({'type': 'complete', 'results': [], 'total': 0})}\n\n"
            return
        
        results = []
        for i, filepath in enumerate(pdf_files):
            filename = os.path.basename(filepath)
            rel_path = os.path.relpath(filepath, folder_path)
            
            # Pošli progress
            yield f"data: {json.dumps({'type': 'progress', 'current': i + 1, 'total': total, 'file': filename})}\n\n"
            
            # Analyzuj soubor
            result = analyze_pdf_file(filepath)
            result['path'] = rel_path
            results.append(result)
        
        # Pošli výsledky
        yield f"data: {json.dumps({'type': 'complete', 'results': results, 'total': total})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

@app.route('/api/scan-folder', methods=['POST'])
def scan_folder():
    data = request.get_json()
    folder_path = data.get('path', '')
    if not folder_path or not os.path.isdir(folder_path):
        return jsonify({'error': 'Neplatná cesta'}), 400
    results = []
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith('.pdf'):
                filepath = os.path.join(root, file)
                rel_path = os.path.relpath(filepath, folder_path)
                result = analyze_pdf_file(filepath)
                result['path'] = rel_path
                results.append(result)
    return jsonify({'results': results, 'total': len(results)})

# =============================================================================
# BUILD PRO ŠABLONY (jedno místo – version.py; při změně zvyš WEB_BUILD)
# =============================================================================
@app.context_processor
def inject_web_build():
    """Do všech šablon přidá web_build (např. 44) pro zobrazení verze na webu."""
    return {'web_build': WEB_BUILD}

# =============================================================================
# REGISTRACE ADMIN BLUEPRINTU
# =============================================================================
# Zaregistruj admin routes pro správu licencí
app.register_blueprint(admin_bp)

# =============================================================================
# REGISTRACE API ENDPOINTŮ
# =============================================================================
# Zaregistruj API endpointy pro desktop agenta
register_api_routes(app)

# =============================================================================
# SPUŠTĚNÍ
# =============================================================================

if __name__ == '__main__':
    print("")
    print("=" * 60)
    print("  PDF DokuCheck PRO")
    print("  Web build", WEB_BUILD, "| © Ing. Martin Cieślar")
    print("  API endpointy: AKTIVNI")
    print("  Admin panel: AKTIVNI")
    print("=" * 60)
    print("")
    kill_port(5000)
    print("  Aplikace bezi na: http://127.0.0.1:5000/")
    print("  API bezi na: http://127.0.0.1:5000/api/")
    print("  Admin panel: http://127.0.0.1:5000/login")
    print("  Pro ukonceni stisknete CTRL+C")
    print("=" * 60)

    def open_browser():
        webbrowser.open('http://127.0.0.1:5000/')
    threading.Timer(1.5, open_browser).start()

    app.run(debug=False, host='0.0.0.0', port=5000)
