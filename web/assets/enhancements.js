/**
 * Veltrix Dashboard Enhancements
 * - Export/Report UI integration
 * - Improved charts with tooltips and time axis
 * - Table pagination
 * - Status filters
 * - Service Worker registration
 */

(function () {
  "use strict";

  // ---------------------------------------------------------------------------
  // 1. EXPORT & REPORT UI
  // ---------------------------------------------------------------------------

  function injectExportButtons() {
    // Add export buttons to servers panel
    const serversPanel = document.getElementById("servers");
    if (serversPanel) {
      const head = serversPanel.querySelector(".panel-head");
      if (head && !head.querySelector(".export-btn")) {
        const btn = createButton("ghost export-btn", "خروجی CSV", () => downloadExport("servers"));
        head.querySelector("div:last-child")?.appendChild(btn) || head.appendChild(btn);
      }
    }

    // Add export buttons to outbounds panel
    const outboundsPanel = document.getElementById("outbounds");
    if (outboundsPanel) {
      const head = outboundsPanel.querySelector(".panel-head");
      if (head && !head.querySelector(".export-btn")) {
        const btn = createButton("ghost export-btn", "خروجی CSV", () => downloadExport("outbounds"));
        head.querySelector("div:last-child")?.appendChild(btn) || head.appendChild(btn);
      }
    }

    // Add report button to history panel
    const historyPanel = document.getElementById("history");
    if (historyPanel) {
      const head = historyPanel.querySelector(".panel-head");
      if (head && !head.querySelector(".report-btn")) {
        const btnGroup = document.createElement("div");
        btnGroup.className = "actions";
        btnGroup.innerHTML = `
          <button class="ghost report-btn" type="button" onclick="window.__veltrix.generateReport('uptime')">گزارش Uptime</button>
          <button class="ghost report-btn" type="button" onclick="window.__veltrix.generateReport('outbounds')">گزارش اوت‌باندها</button>
        `;
        head.appendChild(btnGroup);
      }
    }

    // Add export to incidents
    const incidentsPanel = document.getElementById("incidents");
    if (incidentsPanel) {
      const head = incidentsPanel.querySelector(".panel-head");
      if (head && !head.querySelector(".export-btn")) {
        const btn = createButton("ghost export-btn", "خروجی CSV", () => downloadExport("incidents"));
        head.appendChild(btn);
      }
    }
  }

  async function downloadExport(type) {
    try {
      const response = await fetch(`/api/export/${type}`, { credentials: "same-origin" });
      if (!response.ok) throw new Error("خطا در دریافت فایل");
      const data = await response.json();
      if (data.csv) {
        // Add BOM for Excel compatibility
        const bom = "\uFEFF";
        const blob = new Blob([bom + data.csv], { type: "text/csv;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = data.filename || `veltrix-${type}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showToast(`فایل ${data.filename || type + ".csv"} دانلود شد.`);
      }
    } catch (err) {
      showToast(err.message);
    }
  }

  async function generateReport(type) {
    try {
      showToast("در حال تولید گزارش...");
      const days = 7;
      const response = await fetch(`/api/reports/${type}?days=${days}`, { credentials: "same-origin" });
      if (!response.ok) throw new Error("خطا در تولید گزارش");
      const report = await response.json();
      showReportModal(report);
    } catch (err) {
      showToast(err.message);
    }
  }

  function showReportModal(report) {
    // Create a modal to display the report
    let modal = document.getElementById("reportModal");
    if (!modal) {
      modal = document.createElement("dialog");
      modal.id = "reportModal";
      modal.innerHTML = `
        <div class="dialog-head">
          <div>
            <p class="eyebrow">Report</p>
            <h2 id="reportModalTitle">گزارش</h2>
          </div>
          <button class="icon-btn" type="button" onclick="document.getElementById('reportModal').close()">×</button>
        </div>
        <div id="reportModalBody" style="padding:20px;max-height:70vh;overflow-y:auto;"></div>
        <div class="dialog-actions" style="grid-template-columns:1fr auto;">
          <span></span>
          <button class="secondary" type="button" onclick="document.getElementById('reportModal').close()">بستن</button>
        </div>
      `;
      document.body.appendChild(modal);
    }

    const title = document.getElementById("reportModalTitle");
    const body = document.getElementById("reportModalBody");

    if (report.type === "uptime") {
      title.textContent = `گزارش Uptime — ${toFa(report.period_days)} روز`;
      body.innerHTML = renderUptimeReport(report);
    } else if (report.type === "outbound_performance") {
      title.textContent = `گزارش عملکرد اوت‌باندها — ${toFa(report.period_days)} روز`;
      body.innerHTML = renderOutboundReport(report);
    } else {
      title.textContent = "گزارش";
      body.innerHTML = `<pre style="direction:ltr;text-align:left;font-size:12px;overflow-x:auto;">${escapeHtml(JSON.stringify(report, null, 2))}</pre>`;
    }

    modal.showModal();
  }

  function renderUptimeReport(report) {
    const summary = report.summary || {};
    let html = `
      <div class="stats-grid" style="grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px;">
        <div class="stat-card" style="min-height:80px;padding:14px;">
          <span>میانگین Availability</span>
          <strong>${toFa(summary.average_availability || 0)}%</strong>
        </div>
        <div class="stat-card" style="min-height:80px;padding:14px;">
          <span>سرورهای بالای ۹۹٪</span>
          <strong>${toFa(summary.servers_above_99 || 0)}</strong>
        </div>
        <div class="stat-card" style="min-height:80px;padding:14px;">
          <span>سرورهای زیر ۹۵٪</span>
          <strong>${toFa(summary.servers_below_95 || 0)}</strong>
        </div>
        <div class="stat-card" style="min-height:80px;padding:14px;">
          <span>کل رخدادها</span>
          <strong>${toFa(summary.total_incidents || 0)}</strong>
        </div>
      </div>
      <div class="table-wrap" style="border:1px solid var(--line);border-radius:8px;">
        <table style="min-width:700px;">
          <thead>
            <tr>
              <th>سرور</th>
              <th>Availability</th>
              <th>Avg Latency</th>
              <th>Avg CPU</th>
              <th>Avg RAM</th>
              <th>رخدادها</th>
              <th>وضعیت</th>
            </tr>
          </thead>
          <tbody>
    `;
    for (const s of (report.servers || [])) {
      const avClass = s.availability_percent >= 99 ? "ok" : s.availability_percent >= 95 ? "warning" : "error";
      html += `
        <tr>
          <td><strong>${escapeHtml(s.server_name)}</strong><br><span class="muted">${escapeHtml(s.host)}</span></td>
          <td><span class="badge ${avClass}">${toFa(s.availability_percent)}%</span></td>
          <td>${toFa(s.avg_latency_ms)} ms</td>
          <td>${toFa(s.avg_cpu)}%</td>
          <td>${toFa(s.avg_ram)}%</td>
          <td>${toFa(s.incident_count)}</td>
          <td><span class="badge ${s.current_status}">${escapeHtml(s.current_status)}</span></td>
        </tr>
      `;
    }
    html += `</tbody></table></div>`;
    return html;
  }

  function renderOutboundReport(report) {
    let html = `
      <p class="subtle" style="margin-bottom:16px;">تعداد اوت‌باند: ${toFa(report.total_outbounds || 0)}</p>
      <div class="table-wrap" style="border:1px solid var(--line);border-radius:8px;">
        <table style="min-width:700px;">
          <thead>
            <tr>
              <th>اوت‌باند</th>
              <th>سرور</th>
              <th>Availability</th>
              <th>Avg Latency</th>
              <th>Min</th>
              <th>Max</th>
              <th>وضعیت</th>
            </tr>
          </thead>
          <tbody>
    `;
    for (const o of (report.outbounds || []).slice(0, 50)) {
      const avClass = o.availability_percent >= 99 ? "ok" : o.availability_percent >= 95 ? "warning" : "error";
      html += `
        <tr>
          <td><strong>${escapeHtml(o.remark)}</strong><br><span class="muted">${escapeHtml(o.protocol || "")} ${escapeHtml(o.address || "")}:${o.port || ""}</span></td>
          <td>${escapeHtml(o.server_name || "-")}</td>
          <td><span class="badge ${avClass}">${toFa(o.availability_percent)}%</span></td>
          <td>${toFa(o.avg_latency)} ms</td>
          <td>${toFa(o.min_latency)} ms</td>
          <td>${toFa(o.max_latency)} ms</td>
          <td><span class="badge ${o.last_status || "unknown"}">${escapeHtml(o.last_status || "-")}</span></td>
        </tr>
      `;
    }
    html += `</tbody></table></div>`;
    return html;
  }

  // ---------------------------------------------------------------------------
  // 2. IMPROVED CHARTS — Tooltips & Time Axis
  // ---------------------------------------------------------------------------

  function enhanceCharts() {
    // Add tooltip container
    if (!document.getElementById("chartTooltip")) {
      const tooltip = document.createElement("div");
      tooltip.id = "chartTooltip";
      tooltip.className = "chart-tooltip";
      tooltip.style.cssText = `
        position:fixed;z-index:9999;padding:8px 12px;border-radius:6px;
        background:rgba(7,16,19,0.92);color:#fff;font-size:12px;font-weight:600;
        pointer-events:none;opacity:0;transition:opacity 0.15s;white-space:nowrap;
        box-shadow:0 8px 24px rgba(0,0,0,0.3);direction:ltr;text-align:left;
      `;
      document.body.appendChild(tooltip);
    }

    // Attach hover listeners to chart SVGs
    document.addEventListener("mousemove", handleChartHover);
    document.addEventListener("mouseleave", hideChartTooltip, true);
  }

  function handleChartHover(event) {
    const circle = event.target.closest("circle");
    const path = event.target.closest("path");
    const svg = event.target.closest(".chart-box svg");
    const tooltip = document.getElementById("chartTooltip");
    if (!tooltip) return;

    if (circle && svg) {
      const cx = parseFloat(circle.getAttribute("cx"));
      const cy = parseFloat(circle.getAttribute("cy"));
      const status = circle.dataset?.status || "";
      tooltip.textContent = status ? `Status: ${status}` : `Point`;
      tooltip.style.left = `${event.clientX + 12}px`;
      tooltip.style.top = `${event.clientY - 30}px`;
      tooltip.style.opacity = "1";
      return;
    }

    if (svg && !circle) {
      // Show value based on mouse X position
      const rect = svg.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const width = rect.width;
      const percent = Math.round((x / width) * 100);
      // Find nearest data point from paths
      const paths = svg.querySelectorAll("path");
      if (paths.length > 0) {
        tooltip.textContent = `Position: ${percent}%`;
        tooltip.style.left = `${event.clientX + 12}px`;
        tooltip.style.top = `${event.clientY - 30}px`;
        tooltip.style.opacity = "1";
        return;
      }
    }

    hideChartTooltip();
  }

  function hideChartTooltip() {
    const tooltip = document.getElementById("chartTooltip");
    if (tooltip) tooltip.style.opacity = "0";
  }

  // ---------------------------------------------------------------------------
  // 3. TABLE PAGINATION
  // ---------------------------------------------------------------------------

  const PAGE_SIZE = 15;
  let serverPage = 1;
  let outboundPage = 1;
  let serverFilter = "";
  let outboundFilter = "";
  let serverStatusFilter = "";
  let outboundStatusFilter = "";

  function injectTableControls() {
    // Server table controls
    const serversPanel = document.getElementById("servers");
    if (serversPanel && !serversPanel.querySelector(".table-controls")) {
      const head = serversPanel.querySelector(".panel-head > div");
      if (head) {
        const controls = document.createElement("div");
        controls.className = "table-controls";
        controls.style.cssText = "display:flex;gap:10px;align-items:center;margin-top:10px;";
        controls.innerHTML = `
          <input type="search" class="table-search" placeholder="جستجوی سرور..." style="max-width:220px;min-height:34px;font-size:12.5px;" />
          <select class="table-filter" style="max-width:140px;min-height:34px;font-size:12.5px;">
            <option value="">همه وضعیت‌ها</option>
            <option value="online">آنلاین</option>
            <option value="error">خطا</option>
            <option value="disabled">غیرفعال</option>
            <option value="unknown">نامشخص</option>
          </select>
        `;
        head.appendChild(controls);

        controls.querySelector(".table-search").addEventListener("input", (e) => {
          serverFilter = e.target.value.toLowerCase();
          serverPage = 1;
          patchRenderServers();
        });
        controls.querySelector(".table-filter").addEventListener("change", (e) => {
          serverStatusFilter = e.target.value;
          serverPage = 1;
          patchRenderServers();
        });
      }
    }

    // Outbound table controls
    const outboundsPanel = document.getElementById("outbounds");
    if (outboundsPanel && !outboundsPanel.querySelector(".table-controls")) {
      const head = outboundsPanel.querySelector(".panel-head > div");
      if (head) {
        const controls = document.createElement("div");
        controls.className = "table-controls";
        controls.style.cssText = "display:flex;gap:10px;align-items:center;margin-top:10px;";
        controls.innerHTML = `
          <input type="search" class="table-search" placeholder="جستجوی اوت‌باند..." style="max-width:220px;min-height:34px;font-size:12.5px;" />
          <select class="table-filter" style="max-width:140px;min-height:34px;font-size:12.5px;">
            <option value="">همه وضعیت‌ها</option>
            <option value="ok">سالم</option>
            <option value="high">پینگ بالا</option>
            <option value="timeout">تایم‌اوت</option>
            <option value="error">خطا</option>
            <option value="disabled">غیرفعال</option>
          </select>
        `;
        head.appendChild(controls);

        controls.querySelector(".table-search").addEventListener("input", (e) => {
          outboundFilter = e.target.value.toLowerCase();
          outboundPage = 1;
          patchRenderOutbounds();
        });
        controls.querySelector(".table-filter").addEventListener("change", (e) => {
          outboundStatusFilter = e.target.value;
          outboundPage = 1;
          patchRenderOutbounds();
        });
      }
    }
  }

  function getFilteredServers() {
    let list = window.state?.servers || [];
    if (serverFilter) {
      list = list.filter((s) =>
        (s.name || "").toLowerCase().includes(serverFilter) ||
        (s.host || "").toLowerCase().includes(serverFilter) ||
        (s.panel_url || "").toLowerCase().includes(serverFilter)
      );
    }
    if (serverStatusFilter) {
      list = list.filter((s) => {
        const status = s.enabled ? (s.last_status || "unknown") : "disabled";
        return status === serverStatusFilter;
      });
    }
    return list;
  }

  function getFilteredOutbounds() {
    let list = window.state?.outbounds || [];
    if (outboundFilter) {
      list = list.filter((o) =>
        (o.remark || "").toLowerCase().includes(outboundFilter) ||
        (o.server_name || "").toLowerCase().includes(outboundFilter) ||
        (o.address || "").toLowerCase().includes(outboundFilter) ||
        (o.protocol || "").toLowerCase().includes(outboundFilter)
      );
    }
    if (outboundStatusFilter) {
      list = list.filter((o) => (o.last_status || "unknown") === outboundStatusFilter);
    }
    return list;
  }

  function patchRenderServers() {
    const tbody = document.getElementById("serverRows");
    if (!tbody) return;

    const filtered = getFilteredServers();
    const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
    serverPage = Math.min(serverPage, totalPages);
    const start = (serverPage - 1) * PAGE_SIZE;
    const pageItems = filtered.slice(start, start + PAGE_SIZE);

    if (!filtered.length) {
      tbody.innerHTML = `<tr><td colspan="8" class="empty-state">${serverFilter || serverStatusFilter ? "نتیجه‌ای یافت نشد." : "هنوز سروری ثبت نشده است."}</td></tr>`;
      removePagination(tbody);
      return;
    }

    // Use original renderServers logic but with filtered data
    const originalServers = window.state.servers;
    window.state.servers = pageItems;
    if (typeof window.renderServers === "function") {
      window.renderServers();
    }
    window.state.servers = originalServers;

    // Add pagination
    renderPagination(tbody, serverPage, totalPages, filtered.length, (page) => {
      serverPage = page;
      patchRenderServers();
    });
  }

  function patchRenderOutbounds() {
    const tbody = document.getElementById("outboundRows");
    if (!tbody) return;

    const filtered = getFilteredOutbounds();
    const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
    outboundPage = Math.min(outboundPage, totalPages);
    const start = (outboundPage - 1) * PAGE_SIZE;
    const pageItems = filtered.slice(start, start + PAGE_SIZE);

    if (!filtered.length) {
      tbody.innerHTML = `<tr><td colspan="9" class="empty-state">${outboundFilter || outboundStatusFilter ? "نتیجه‌ای یافت نشد." : "بعد از همگام‌سازی x-ui، اوت‌باندها اینجا دیده می‌شوند."}</td></tr>`;
      removePagination(tbody);
      return;
    }

    const originalOutbounds = window.state.outbounds;
    window.state.outbounds = pageItems;
    if (typeof window.renderOutbounds === "function") {
      window.renderOutbounds();
    }
    window.state.outbounds = originalOutbounds;

    renderPagination(tbody, outboundPage, totalPages, filtered.length, (page) => {
      outboundPage = page;
      patchRenderOutbounds();
    });
  }

  function renderPagination(tbody, currentPage, totalPages, totalItems, onPageChange) {
    const tableWrap = tbody.closest(".table-wrap");
    if (!tableWrap) return;

    let paginationEl = tableWrap.parentElement.querySelector(".pagination");
    if (!paginationEl) {
      paginationEl = document.createElement("div");
      paginationEl.className = "pagination";
      tableWrap.parentElement.appendChild(paginationEl);
    }

    if (totalPages <= 1) {
      paginationEl.innerHTML = `<span class="pagination-info">${toFa(totalItems)} مورد</span>`;
      return;
    }

    let buttons = "";
    // Previous
    buttons += `<button class="ghost pagination-btn" ${currentPage <= 1 ? "disabled" : ""} data-page="${currentPage - 1}">‹ قبلی</button>`;

    // Page numbers
    const maxVisible = 5;
    let startPage = Math.max(1, currentPage - Math.floor(maxVisible / 2));
    let endPage = Math.min(totalPages, startPage + maxVisible - 1);
    if (endPage - startPage < maxVisible - 1) {
      startPage = Math.max(1, endPage - maxVisible + 1);
    }

    if (startPage > 1) buttons += `<button class="ghost pagination-btn" data-page="1">${toFa(1)}</button>`;
    if (startPage > 2) buttons += `<span class="pagination-dots">…</span>`;

    for (let i = startPage; i <= endPage; i++) {
      buttons += `<button class="${i === currentPage ? "primary" : "ghost"} pagination-btn" data-page="${i}">${toFa(i)}</button>`;
    }

    if (endPage < totalPages - 1) buttons += `<span class="pagination-dots">…</span>`;
    if (endPage < totalPages) buttons += `<button class="ghost pagination-btn" data-page="${totalPages}">${toFa(totalPages)}</button>`;

    // Next
    buttons += `<button class="ghost pagination-btn" ${currentPage >= totalPages ? "disabled" : ""} data-page="${currentPage + 1}">بعدی ›</button>`;

    paginationEl.innerHTML = `
      <span class="pagination-info">صفحه ${toFa(currentPage)} از ${toFa(totalPages)} (${toFa(totalItems)} مورد)</span>
      <div class="pagination-buttons">${buttons}</div>
    `;

    paginationEl.querySelectorAll(".pagination-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const page = parseInt(btn.dataset.page);
        if (page >= 1 && page <= totalPages) onPageChange(page);
      });
    });
  }

  function removePagination(tbody) {
    const tableWrap = tbody.closest(".table-wrap");
    if (!tableWrap) return;
    const paginationEl = tableWrap.parentElement.querySelector(".pagination");
    if (paginationEl) paginationEl.innerHTML = "";
  }

  // ---------------------------------------------------------------------------
  // 4. SERVICE WORKER
  // ---------------------------------------------------------------------------

  function registerServiceWorker() {
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => {
        // SW registration failed — not critical
      });
    }
  }

  // ---------------------------------------------------------------------------
  // 5. SSE (Server-Sent Events) — Real-time updates
  // ---------------------------------------------------------------------------

  let sseConnection = null;
  let sseReconnectTimer = null;

  function connectSSE() {
    if (sseConnection) return;
    if (!window.state?.auth?.user) return;

    try {
      sseConnection = new EventSource("/api/events");

      sseConnection.addEventListener("connected", () => {
        console.log("[Veltrix] SSE connected");
      });

      sseConnection.addEventListener("server.status", (event) => {
        try {
          const data = JSON.parse(event.data);
          updateServerStatusInPlace(data);
        } catch (e) {}
      });

      sseConnection.addEventListener("outbound.ping", (event) => {
        try {
          const data = JSON.parse(event.data);
          updateOutboundStatusInPlace(data);
        } catch (e) {}
      });

      sseConnection.addEventListener("alert.new", (event) => {
        try {
          const data = JSON.parse(event.data);
          showToast(`⚠️ ${data.message || "اعلان جدید"}`);
          // Trigger browser notification
          if ("Notification" in window && Notification.permission === "granted") {
            new Notification("Veltrix Alert", { body: data.message });
          }
        } catch (e) {}
      });

      sseConnection.addEventListener("monitor.cycle", (event) => {
        try {
          const data = JSON.parse(event.data);
          // Update last-updated timestamp
          const el = document.getElementById("lastUpdated");
          if (el) {
            el.textContent = new Intl.DateTimeFormat("fa-IR", {
              hour: "2-digit", minute: "2-digit", second: "2-digit",
            }).format(new Date());
          }
        } catch (e) {}
      });

      sseConnection.addEventListener("incident.update", (event) => {
        try {
          const data = JSON.parse(event.data);
          showToast(`رخداد ${data.action}: #${toFa(data.incident_id)}`);
        } catch (e) {}
      });

      sseConnection.onerror = () => {
        sseConnection.close();
        sseConnection = null;
        // Reconnect after 5 seconds
        clearTimeout(sseReconnectTimer);
        sseReconnectTimer = setTimeout(connectSSE, 5000);
      };
    } catch (e) {
      sseConnection = null;
    }
  }

  function disconnectSSE() {
    if (sseConnection) {
      sseConnection.close();
      sseConnection = null;
    }
    clearTimeout(sseReconnectTimer);
  }

  function updateServerStatusInPlace(data) {
    // Update server status badge in the table without full reload
    const row = document.querySelector(`tr[data-server-id="${data.server_id}"]`);
    if (!row) return;
    const statusCell = row.querySelectorAll("td")[2];
    if (statusCell) {
      const status = data.status || "unknown";
      const labels = { online: "آنلاین", error: "خطا", disabled: "غیرفعال", unknown: "نامشخص" };
      statusCell.innerHTML = `<span class="badge ${escapeHtml(status)}">${escapeHtml(labels[status] || status)}</span>`;
    }
  }

  function updateOutboundStatusInPlace(data) {
    // Lightweight update for outbound ping results
    // Full re-render happens on next polling cycle
  }

  // ---------------------------------------------------------------------------
  // UTILITIES
  // ---------------------------------------------------------------------------

  function createButton(className, text, onClick) {
    const btn = document.createElement("button");
    btn.className = className;
    btn.type = "button";
    btn.textContent = text;
    btn.addEventListener("click", onClick);
    return btn;
  }

  function showToast(message) {
    if (typeof window.toast === "function") {
      window.toast(message);
    } else {
      const el = document.getElementById("toast");
      if (el) {
        el.textContent = message;
        el.classList.add("show");
        clearTimeout(showToast._timer);
        showToast._timer = setTimeout(() => el.classList.remove("show"), 3200);
      }
    }
  }

  function toFa(value) {
    return String(value).replace(/\d/g, (d) => "۰۱۲۳۴۵۶۷۸۹"[d]);
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  // ---------------------------------------------------------------------------
  // INITIALIZATION
  // ---------------------------------------------------------------------------

  function init() {
    // Wait for DOM and main app to load
    setTimeout(() => {
      injectExportButtons();
      injectTableControls();
      enhanceCharts();
      registerServiceWorker();
      connectSSE();
      // Load 2FA status and backup schedule
      if (window.__veltrix2fa) window.__veltrix2fa.loadStatus();
      if (window.__veltrixBackup) window.__veltrixBackup.loadSchedule();
    }, 800);

    // Re-inject after navigation
    const observer = new MutationObserver(() => {
      injectExportButtons();
      injectTableControls();
      // Reconnect SSE if user logged in
      if (window.state?.auth?.user && !sseConnection) {
        connectSSE();
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  // Expose API for inline scripts
  window.__veltrix = {
    generateReport,
    downloadExport,
    getFilteredServers,
    getFilteredOutbounds,
  };

  // 2FA API
  window.__veltrix2fa = {
    async enable() {
      try {
        const data = await fetch('/api/auth/2fa/enable', { method: 'POST', credentials: 'same-origin' }).then(r => r.json());
        if (data.secret) {
          document.getElementById('twofaSecret').textContent = data.secret;
          document.getElementById('twofaSetup').classList.remove('hidden');
          document.getElementById('enable2faBtn').classList.add('hidden');
        }
      } catch (e) { showToast(e.message || 'خطا'); }
    },
    async confirm() {
      const code = document.getElementById('twofaCode').value.trim();
      if (code.length !== 6) { showToast('کد باید ۶ رقم باشد.'); return; }
      try {
        const res = await fetch('/api/auth/2fa/confirm', {
          method: 'POST', credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ code }),
        }).then(r => r.json());
        if (res.ok) {
          showToast('2FA فعال شد.');
          document.getElementById('twofaSetup').classList.add('hidden');
          document.getElementById('twofaStatus').className = 'badge ok';
          document.getElementById('twofaStatus').textContent = 'فعال';
          document.getElementById('enable2faBtn').textContent = 'غیرفعال‌سازی 2FA';
          document.getElementById('enable2faBtn').classList.remove('hidden');
          document.getElementById('enable2faBtn').onclick = window.__veltrix2fa.disable;
        } else { showToast(res.error || 'کد نامعتبر'); }
      } catch (e) { showToast(e.message || 'خطا'); }
    },
    async disable() {
      const password = prompt('رمز فعلی خود را وارد کنید:');
      if (!password) return;
      try {
        const res = await fetch('/api/auth/2fa/disable', {
          method: 'POST', credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ password }),
        }).then(r => r.json());
        if (res.ok) {
          showToast('2FA غیرفعال شد.');
          document.getElementById('twofaStatus').className = 'badge disabled';
          document.getElementById('twofaStatus').textContent = 'غیرفعال';
          document.getElementById('enable2faBtn').textContent = 'فعال‌سازی 2FA';
          document.getElementById('enable2faBtn').onclick = window.__veltrix2fa.enable;
        } else { showToast(res.error || 'خطا'); }
      } catch (e) { showToast(e.message || 'خطا'); }
    },
    async loadStatus() {
      try {
        const data = await fetch('/api/auth/2fa/status', { credentials: 'same-origin' }).then(r => r.json());
        const el = document.getElementById('twofaStatus');
        const btn = document.getElementById('enable2faBtn');
        if (data.enabled) {
          el.className = 'badge ok'; el.textContent = 'فعال';
          btn.textContent = 'غیرفعال‌سازی 2FA';
          btn.onclick = window.__veltrix2fa.disable;
        } else {
          el.className = 'badge disabled'; el.textContent = 'غیرفعال';
          btn.textContent = 'فعال‌سازی 2FA';
          btn.onclick = window.__veltrix2fa.enable;
        }
      } catch (e) {}
    },
  };

  // Backup Schedule API
  window.__veltrixBackup = {
    async saveSchedule() {
      const hour = document.getElementById('backupHour').value;
      const retention = document.getElementById('backupRetention').value;
      const enabled = document.getElementById('backupAutoEnabled').checked;
      try {
        await fetch('/api/backups/schedule', {
          method: 'PUT', credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ hour: parseInt(hour), retention: parseInt(retention), enabled }),
        });
        showToast('تنظیمات بکاپ ذخیره شد.');
      } catch (e) { showToast(e.message || 'خطا'); }
    },
    async loadSchedule() {
      try {
        const data = await fetch('/api/backups/schedule', { credentials: 'same-origin' }).then(r => r.json());
        const hourEl = document.getElementById('backupHour');
        const retEl = document.getElementById('backupRetention');
        const enEl = document.getElementById('backupAutoEnabled');
        if (hourEl) hourEl.value = data.hour_utc || 3;
        if (retEl) retEl.value = data.retention || 7;
        if (enEl) enEl.checked = data.enabled !== false;
      } catch (e) {}
    },
  };

  // Make state accessible
  if (typeof window.state === "undefined") {
    Object.defineProperty(window, "state", {
      get: () => window.__veltrixState || {},
      set: (v) => { window.__veltrixState = v; },
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
