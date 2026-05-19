const state = {
  auth: {
    user: null,
    permissions: [],
    permissionCatalog: [],
    managerLimit: 10,
  },
  users: [],
  auditLogs: [],
  backups: [],
  servers: [],
  outbounds: [],
  alerts: [],
  incidents: [],
  notificationChannels: [],
  license: null,
  history: {
    serverId: null,
    outboundId: null,
    metrics: [],
    checks: [],
  },
  serverDetail: {
    serverId: null,
    focusOutboundId: null,
    metrics: [],
    checks: [],
  },
  editingServer: null,
  editingUser: null,
  notifiedAlerts: new Set(JSON.parse(localStorage.getItem("outpanelNotifiedAlerts") || "[]")),
};
// Expose state globally for enhancement modules
window.state = state;

const els = {
  authScreen: document.getElementById("authScreen"),
  appShell: document.getElementById("appShell"),
  authTitle: document.getElementById("authTitle"),
  authHint: document.getElementById("authHint"),
  setupForm: document.getElementById("setupForm"),
  loginForm: document.getElementById("loginForm"),
  lastUpdated: document.getElementById("lastUpdated"),
  currentUserLabel: document.getElementById("currentUserLabel"),
  statServers: document.getElementById("statServers"),
  statOnline: document.getElementById("statOnline"),
  statOutbounds: document.getElementById("statOutbounds"),
  statBad: document.getElementById("statBad"),
  statAlerts: document.getElementById("statAlerts"),
  statIncidents: document.getElementById("statIncidents"),
  statOpenIncidents: document.getElementById("statOpenIncidents"),
  statResources: document.getElementById("statResources"),
  serverRows: document.getElementById("serverRows"),
  outboundRows: document.getElementById("outboundRows"),
  alertList: document.getElementById("alertList"),
  incidentList: document.getElementById("incidentList"),
  notificationForm: document.getElementById("notificationForm"),
  notificationList: document.getElementById("notificationList"),
  passwordForm: document.getElementById("passwordForm"),
  securityUserLabel: document.getElementById("securityUserLabel"),
  securityUserMeta: document.getElementById("securityUserMeta"),
  userForm: document.getElementById("userForm"),
  userList: document.getElementById("userList"),
  auditList: document.getElementById("auditList"),
  backupList: document.getElementById("backupList"),
  managerPermissionGrid: document.getElementById("managerPermissionGrid"),
  cancelUserEditBtn: document.getElementById("cancelUserEditBtn"),
  licenseStatus: document.getElementById("licenseStatus"),
  licensePlans: document.getElementById("licensePlans"),
  serverHistorySelect: document.getElementById("serverHistorySelect"),
  outboundHistorySelect: document.getElementById("outboundHistorySelect"),
  resourceChart: document.getElementById("resourceChart"),
  pingChart: document.getElementById("pingChart"),
  resourceChartMeta: document.getElementById("resourceChartMeta"),
  pingChartMeta: document.getElementById("pingChartMeta"),
  serverDetailTitle: document.getElementById("serverDetailTitle"),
  serverDetailSubtitle: document.getElementById("serverDetailSubtitle"),
  serverDetailBody: document.getElementById("serverDetailBody"),
  detailSyncBtn: document.getElementById("detailSyncBtn"),
  detailPingBtn: document.getElementById("detailPingBtn"),
  detailEditBtn: document.getElementById("detailEditBtn"),
  detailGoIncidentsBtn: document.getElementById("detailGoIncidentsBtn"),
  toast: document.getElementById("toast"),
  dialog: document.getElementById("serverDialog"),
  form: document.getElementById("serverForm"),
  dialogTitle: document.getElementById("dialogTitle"),
  deleteServerBtn: document.getElementById("deleteServerBtn"),
};

document.getElementById("refreshBtn").addEventListener("click", () => loadOverview(true));
document.getElementById("runMonitorBtn").addEventListener("click", runMonitor);
document.getElementById("addServerBtn").addEventListener("click", () => openServerDialog());
document.getElementById("closeDialogBtn").addEventListener("click", closeServerDialog);
document.getElementById("cancelDialogBtn").addEventListener("click", closeServerDialog);
document.getElementById("notifyBtn").addEventListener("click", requestNotifications);
document.getElementById("logoutBtn").addEventListener("click", logoutUser);
document.getElementById("licenseForm").addEventListener("submit", activateLicense);
document.getElementById("refreshIncidentsBtn").addEventListener("click", () => loadOverview(true));
document.getElementById("createBackupBtn").addEventListener("click", createBackup);
els.detailSyncBtn.addEventListener("click", () => syncSelectedServer(els.detailSyncBtn));
els.detailPingBtn.addEventListener("click", () => pingSelectedServerOutbounds(els.detailPingBtn));
els.detailEditBtn.addEventListener("click", () => editSelectedServer());
els.detailGoIncidentsBtn.addEventListener("click", () => {
  document.querySelector('a[href="#incidents"]')?.click();
  document.getElementById("incidents")?.scrollIntoView({ behavior: "smooth", block: "start" });
});
els.setupForm.addEventListener("submit", setupOwner);
els.loginForm.addEventListener("submit", loginUser);
els.passwordForm.addEventListener("submit", changeOwnPassword);
els.notificationForm.addEventListener("submit", saveNotificationChannel);
els.notificationForm.elements.type.addEventListener("change", renderNotificationFormMode);
els.userForm.addEventListener("submit", saveUser);
els.cancelUserEditBtn.addEventListener("click", resetUserForm);
els.serverHistorySelect.addEventListener("change", () => {
  state.history.serverId = Number(els.serverHistorySelect.value) || null;
  state.history.outboundId = null;
  renderHistoryControls();
  loadHistory(true);
});
els.outboundHistorySelect.addEventListener("change", () => {
  state.history.outboundId = Number(els.outboundHistorySelect.value) || null;
  loadHistory(true);
});
els.deleteServerBtn.addEventListener("click", deleteCurrentServer);
els.form.addEventListener("submit", saveServer);

els.serverRows.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-action]");
  if (button) {
    const id = Number(button.dataset.id);
    if (button.dataset.action === "view-server") selectServerDetail(id, true);
    if (button.dataset.action === "edit-server") openServerDialog(id);
    if (button.dataset.action === "sync-server") syncServer(id, button);
    if (button.dataset.action === "delete-server") deleteServer(id);
    return;
  }
  const row = event.target.closest("tr[data-server-id]");
  if (row) selectServerDetail(Number(row.dataset.serverId), true);
});

els.outboundRows.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-action='ping-outbound']");
  if (button) pingOutbound(Number(button.dataset.id), button);
});

els.serverDetailBody.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const id = Number(button.dataset.id);
  if (button.dataset.action === "ping-detail-outbound") pingOutbound(id, button);
  if (button.dataset.action === "focus-detail-outbound") focusServerDetailOutbound(id, true);
});

els.incidentList.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const id = Number(button.dataset.id);
  if (button.dataset.action === "ack-incident") acknowledgeIncident(id, button);
  if (button.dataset.action === "recover-incident") recoverIncident(id, button);
});

els.notificationList.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const id = Number(button.dataset.id);
  if (button.dataset.action === "test-channel") testNotificationChannel(id, button);
  if (button.dataset.action === "toggle-channel") toggleNotificationChannel(id, button);
  if (button.dataset.action === "delete-channel") deleteNotificationChannel(id, button);
});

els.userList.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const id = Number(button.dataset.id);
  if (button.dataset.action === "edit-user") openUserEditor(id);
  if (button.dataset.action === "toggle-user") toggleUser(id, button);
  if (button.dataset.action === "delete-user") deleteUser(id, button);
});

els.backupList.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const name = button.dataset.name;
  if (button.dataset.action === "download-backup") downloadBackup(name);
  if (button.dataset.action === "restore-backup") restoreBackup(name, button);
  if (button.dataset.action === "delete-backup") deleteBackup(name, button);
});

document.querySelectorAll(".nav-list a").forEach((link) => {
  link.addEventListener("click", () => {
    document.querySelectorAll(".nav-list a").forEach((item) => item.classList.remove("active"));
    link.classList.add("active");
  });
});

initAuth();
setInterval(() => {
  if (state.auth.user) loadOverview(false);
}, 10000);

async function initAuth() {
  try {
    const data = await api("/api/auth/status", { skipUnauthorizedHandler: true });
    state.auth.permissionCatalog = data.permissions || [];
    state.auth.managerLimit = data.manager_limit || 10;
    renderPermissionGrid();
    if (data.requires_setup) {
      showAuth("setup");
      return;
    }
    if (!data.authenticated) {
      showAuth("login");
      return;
    }
    await enterApp(data.user);
  } catch (error) {
    showAuth("login");
    toast(error.message);
  }
}

async function enterApp(user) {
  state.auth.user = user;
  state.auth.permissions = user?.permissions || [];
  els.authScreen.classList.add("hidden");
  els.appShell.classList.remove("hidden");
  els.currentUserLabel.textContent = `${user.display_name || user.username} · ${user.role === "owner" ? "ادمین اصلی" : "مدیر"}`;
  renderAccountSecurity();
  applyAccess();
  await loadOverview(false);
  if (can("notifications")) await loadNotificationChannels();
  if (can("users")) await loadUsersAndAudit();
  if (can("maintenance")) await loadBackups();
  renderNotificationFormMode();
}

function showAuth(mode) {
  state.auth.user = null;
  els.appShell.classList.add("hidden");
  els.authScreen.classList.remove("hidden");
  els.setupForm.classList.toggle("hidden", mode !== "setup");
  els.loginForm.classList.toggle("hidden", mode !== "login");
  els.authTitle.textContent = mode === "setup" ? "ساخت ادمین اصلی" : "ورود به پنل";
  els.authHint.textContent =
    mode === "setup"
      ? "برای شروع Veltrix، حساب ادمین اصلی را بسازید. این حساب دسترسی کامل دارد."
      : "با حساب ادمین اصلی یا مدیر وارد شوید.";
}

async function api(path, options = {}) {
  const { skipUnauthorizedHandler, ...requestOptions } = options;
  const headers = {
    Accept: "application/json",
    ...(requestOptions.headers || {}),
  };
  if (requestOptions.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(path, { ...requestOptions, headers, credentials: "same-origin" });
  if (response.status === 401) {
    if (!skipUnauthorizedHandler) showAuth("login");
    throw new Error("دسترسی رد شد.");
  }
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error || "درخواست ناموفق بود.");
  }
  return payload;
}

async function setupOwner(event) {
  event.preventDefault();
  const button = event.currentTarget.querySelector("button[type='submit']");
  await withBusy(button, async () => {
    const formData = new FormData(els.setupForm);
    const data = await api("/api/auth/setup", {
      method: "POST",
      body: JSON.stringify({
        display_name: formData.get("display_name"),
        username: formData.get("username"),
        password: formData.get("password"),
      }),
    });
    state.auth.permissionCatalog = data.permissions || state.auth.permissionCatalog;
    renderPermissionGrid();
    toast("ادمین اصلی ساخته شد.");
    await enterApp(data.user);
  });
}

async function loginUser(event) {
  event.preventDefault();
  const button = event.currentTarget.querySelector("button[type='submit']");
  await withBusy(button, async () => {
    const formData = new FormData(els.loginForm);
    const data = await api("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({
        username: formData.get("username"),
        password: formData.get("password"),
      }),
    });
    state.auth.permissionCatalog = data.permissions || state.auth.permissionCatalog;
    renderPermissionGrid();
    els.loginForm.reset();
    toast("ورود انجام شد.");
    await enterApp(data.user);
  });
}

async function logoutUser() {
  await api("/api/auth/logout", { method: "POST" }).catch(() => null);
  state.auth.user = null;
  showAuth("login");
}

function renderAccountSecurity() {
  const user = state.auth.user;
  if (!user) return;
  els.securityUserLabel.textContent = `${user.display_name || user.username} · ${user.role === "owner" ? "ادمین اصلی" : "مدیر"}`;
  els.securityUserMeta.textContent = `نام کاربری: ${user.username} · آخرین ورود: ${formatDate(user.last_login_at)}`;
}

async function changeOwnPassword(event) {
  event.preventDefault();
  const formData = new FormData(els.passwordForm);
  const currentPassword = String(formData.get("current_password") || "");
  const newPassword = String(formData.get("new_password") || "");
  const confirmPassword = String(formData.get("confirm_password") || "");
  if (newPassword !== confirmPassword) {
    toast("تکرار رمز جدید با رمز جدید یکسان نیست.");
    return;
  }
  const button = els.passwordForm.querySelector("button[type='submit']");
  await withBusy(button, async () => {
    await api("/api/auth/password", {
      method: "POST",
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
      }),
    });
    els.passwordForm.reset();
    toast("رمز عبور تغییر کرد. نشست‌های دیگر این کاربر بسته شدند.");
    if (can("users")) await loadUsersAndAudit();
  });
}

function can(permission) {
  return state.auth.permissions.includes(permission);
}

function applyAccess() {
  document.querySelectorAll("[data-permission]").forEach((item) => {
    const allowed = can(item.dataset.permission);
    item.classList.toggle("hidden", !allowed);
  });
  const firstVisibleLink = document.querySelector(".nav-list a:not(.hidden)");
  document.querySelectorAll(".nav-list a").forEach((item) => item.classList.remove("active"));
  if (firstVisibleLink) firstVisibleLink.classList.add("active");
}

function renderPermissionGrid() {
  const managerPermissions = (state.auth.permissionCatalog || []).filter((item) => item.key !== "users");
  els.managerPermissionGrid.innerHTML = managerPermissions
    .map(
      (permission) => `
        <label class="permission-option">
          <input type="checkbox" name="permissions" value="${escapeHtml(permission.key)}" />
          <span>
            <strong>${escapeHtml(permission.label)}</strong>
            <small>${escapeHtml(permission.description)}</small>
          </span>
        </label>`
    )
    .join("");
}

async function loadOverview(showToast) {
  try {
    const data = await api("/api/overview");
    state.servers = data.servers || [];
    state.outbounds = data.outbounds || [];
    state.alerts = data.alerts || [];
    state.incidents = data.incidents || [];
    state.license = data.license || null;
    renderAll(data.counts || {});
    if (can("history")) {
      await Promise.all([loadHistory(false), loadServerDetailTelemetry(false)]);
    } else {
      state.history.metrics = [];
      state.history.checks = [];
      state.serverDetail.metrics = [];
      state.serverDetail.checks = [];
      renderServerDetail();
    }
    notifyNewAlerts();
    if (showToast) toast("داشبورد بروزرسانی شد.");
  } catch (error) {
    toast(error.message);
  }
}

function renderAll(counts) {
  els.statServers.textContent = toFa(counts.servers || 0);
  els.statOnline.textContent = `${toFa(counts.online_servers || 0)} آنلاین از ${toFa(counts.enabled_servers || 0)} فعال`;
  els.statOutbounds.textContent = toFa(counts.outbounds || 0);
  els.statBad.textContent = `${toFa(counts.bad_outbounds || 0)} نیازمند بررسی`;
  els.statAlerts.textContent = toFa(counts.active_alerts || 0);
  els.statIncidents.textContent = toFa(counts.active_incidents || 0);
  els.statOpenIncidents.textContent = `${toFa(counts.open_incidents || 0)} نیازمند اقدام`;
  els.statResources.textContent = formatResourceAverage(state.servers);
  ensureSelectedServerDetail();
  els.lastUpdated.textContent = new Intl.DateTimeFormat("fa-IR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date());

  renderServers();
  renderOutbounds();
  renderServerDetail();
  renderAlerts();
  renderIncidents();
  renderLicense();
  renderHistoryControls();
  renderHistoryCharts();
}

function renderServers() {
  if (!state.servers.length) {
    els.serverRows.innerHTML = `<tr><td colspan="8" class="empty-state">هنوز سروری ثبت نشده است.</td></tr>`;
    return;
  }
  els.serverRows.innerHTML = state.servers
    .map((server) => {
      const status = server.enabled ? server.last_status || "unknown" : "disabled";
      const selected = Number(server.id) === Number(state.serverDetail.serverId);
      return `
        <tr class="${selected ? "selected-row" : ""}" data-server-id="${server.id}">
          <td>
            <div class="row-title">
              <strong>${escapeHtml(server.name)}</strong>
              <span class="muted">${escapeHtml(server.panel_url || "بدون پنل")}</span>
            </div>
          </td>
          <td>${escapeHtml(server.host)}</td>
          <td>${badge(status, labelStatus(status))}</td>
          <td>${meter(server.cpu_percent)}</td>
          <td>${meter(server.ram_percent)}</td>
          <td>${escapeHtml(server.xray_status || "-")}</td>
          <td>${toFa(server.outbound_count || 0)}</td>
          <td>
            <div class="table-actions">
              <button class="primary" data-action="view-server" data-id="${server.id}">جزئیات</button>
              <button class="secondary" data-action="sync-server" data-id="${server.id}">همگام</button>
              <button class="ghost" data-action="edit-server" data-id="${server.id}">ویرایش</button>
              <button class="ghost danger" data-action="delete-server" data-id="${server.id}">حذف</button>
            </div>
          </td>
        </tr>`;
    })
    .join("");
}

function renderOutbounds() {
  if (!state.outbounds.length) {
    els.outboundRows.innerHTML = `<tr><td colspan="9" class="empty-state">بعد از همگام‌سازی x-ui، اوت‌باندها اینجا دیده می‌شوند.</td></tr>`;
    return;
  }
  els.outboundRows.innerHTML = state.outbounds
    .map((outbound) => {
      const traffic = `${formatBytes(outbound.up_bytes)} / ${formatBytes(outbound.down_bytes)}`;
      const ping = outbound.last_ping_ms == null ? "-" : `${toFa(outbound.last_ping_ms)} ms`;
      return `
        <tr>
          <td>
            <div class="row-title">
              <strong>${escapeHtml(outbound.remark)}</strong>
              ${badge(outbound.last_status || "unknown", labelStatus(outbound.last_status))}
            </div>
          </td>
          <td>${escapeHtml(outbound.server_name || "-")}</td>
          <td>${escapeHtml(outbound.protocol || "-")}</td>
          <td>${escapeHtml(outbound.address || "-")}</td>
          <td>${toFa(outbound.port || "-")}</td>
          <td>${ping}</td>
          <td>${traffic}</td>
          <td>${formatDate(outbound.last_checked_at)}</td>
          <td>
            <div class="table-actions">
              <button class="secondary" data-action="ping-outbound" data-id="${outbound.id}">تست پینگ</button>
            </div>
          </td>
        </tr>`;
    })
    .join("");
}

function renderAlerts() {
  if (!state.alerts.length) {
    els.alertList.innerHTML = `<div class="empty-state">اعلان فعالی وجود ندارد.</div>`;
    return;
  }
  els.alertList.innerHTML = state.alerts
    .map(
      (alert) => `
        <article class="alert-item ${escapeHtml(alert.severity)}">
          <div>
            <strong>${escapeHtml(alert.message)}</strong>
            <div class="subtle">${escapeHtml(alert.server_name || "")} ${formatDate(alert.created_at)}</div>
          </div>
          ${badge(alert.severity, alert.severity === "critical" ? "بحرانی" : "هشدار")}
        </article>`
    )
    .join("");
}

function renderIncidents() {
  if (!state.incidents.length) {
    els.incidentList.innerHTML = `<div class="empty-state">رخداد باز وجود ندارد.</div>`;
    return;
  }
  els.incidentList.innerHTML = state.incidents
    .map((incident) => {
      const scope = [incident.server_name, incident.outbound_remark].filter(Boolean).join(" / ") || "-";
      return `
        <article class="incident-item ${escapeHtml(incident.severity)} ${escapeHtml(incident.status)}">
          <div class="incident-main">
            <div class="incident-title">
              ${badge(incident.status, labelIncidentStatus(incident.status))}
              ${badge(incident.severity, incident.severity === "critical" ? "بحرانی" : "هشدار")}
              <strong>${escapeHtml(incident.title || incident.kind)}</strong>
            </div>
            <p>${escapeHtml(incident.message)}</p>
            <div class="subtle">
              ${escapeHtml(scope)}
              · شروع: ${formatDate(incident.first_seen_at)}
              · آخرین مشاهده: ${formatDate(incident.last_seen_at)}
              · مدت: ${formatDuration(incident.duration_seconds)}
            </div>
          </div>
          <div class="incident-actions">
            <button class="secondary" data-action="ack-incident" data-id="${incident.id}" ${incident.status === "acknowledged" ? "disabled" : ""}>تایید</button>
            <button class="ghost" data-action="recover-incident" data-id="${incident.id}">بستن دستی</button>
          </div>
        </article>`;
    })
    .join("");
}

function renderServerDetail() {
  const server = getSelectedServer();
  if (!server) {
    els.serverDetailTitle.textContent = "جزئیات سرور";
    els.serverDetailSubtitle.textContent = "هنوز سروری برای نمایش وجود ندارد.";
    els.serverDetailBody.innerHTML = `<div class="empty-state">برای شروع، یک سرور اضافه کنید تا نمای عملیاتی آن اینجا نمایش داده شود.</div>`;
    toggleDetailActions(false);
    return;
  }

  toggleDetailActions(true);
  const outbounds = getServerOutbounds(server.id);
  const incidents = getServerIncidents(server.id);
  const alerts = getServerAlerts(server.id);
  const health = calculateServerHealth(server, outbounds, incidents, alerts);
  const metrics = state.serverDetail.metrics || [];
  const checks = state.serverDetail.checks || [];
  const focusOutbound = outbounds.find((outbound) => Number(outbound.id) === Number(state.serverDetail.focusOutboundId));
  const lastProblem = getLastServerProblem(server, outbounds, incidents, alerts);

  els.serverDetailTitle.textContent = server.name || "جزئیات سرور";
  els.serverDetailSubtitle.textContent = `${server.host || "-"} · ${server.panel_url || "بدون پنل x-ui"} · آخرین بررسی ${formatDate(server.last_checked_at || server.metrics_at)}`;

  els.serverDetailBody.innerHTML = `
    <div class="server-detail-overview">
      <article class="health-card ${health.level}">
        <div class="health-ring" style="--score: ${health.score}">
          <strong>${toFa(health.score)}</strong>
          <span>Health</span>
        </div>
        <div class="health-copy">
          ${badge(health.level, health.label)}
          <strong>${escapeHtml(health.summary)}</strong>
          <span>${escapeHtml(health.reason)}</span>
        </div>
      </article>

      <div class="detail-facts">
        ${detailFact("وضعیت سرور", badge(server.enabled ? server.last_status || "unknown" : "disabled", labelStatus(server.enabled ? server.last_status || "unknown" : "disabled")))}
        ${detailFact("CPU", meter(server.cpu_percent))}
        ${detailFact("RAM", meter(server.ram_percent))}
        ${detailFact("x-ui / Xray", escapeHtml(server.xray_status || "-"))}
        ${detailFact("Uptime", escapeHtml(server.uptime || "-"))}
        ${detailFact("اوت‌باندها", `${toFa(outbounds.length)} مورد`)}
      </div>
    </div>

    <div class="detail-section-grid">
      <article class="detail-card">
        <div class="detail-card-head">
          <div>
            <p class="eyebrow">Resource Trend</p>
            <h3>منابع سرور</h3>
          </div>
          <span class="subtle">${metrics.length ? `${toFa(metrics.length)} نمونه` : "بدون داده"}</span>
        </div>
        <div id="serverDetailResourceChart" class="chart-box compact-chart"></div>
      </article>

      <article class="detail-card">
        <div class="detail-card-head">
          <div>
            <p class="eyebrow">Focused Ping</p>
            <h3>${focusOutbound ? escapeHtml(focusOutbound.remark) : "پینگ اوتباند"}</h3>
          </div>
          <span class="subtle">${checks.length ? `${toFa(checks.length)} تست` : "بدون داده"}</span>
        </div>
        <div id="serverDetailPingChart" class="chart-box compact-chart"></div>
      </article>
    </div>

    <div class="detail-section-grid detail-section-grid-wide">
      <article class="detail-card">
        <div class="detail-card-head">
          <div>
            <p class="eyebrow">Outbound Watch</p>
            <h3>اوت‌باندهای این سرور</h3>
          </div>
          <span class="subtle">${toFa(outbounds.filter(isBadOutbound).length)} نیازمند بررسی</span>
        </div>
        ${renderServerOutboundList(outbounds)}
      </article>

      <article class="detail-card">
        <div class="detail-card-head">
          <div>
            <p class="eyebrow">Risk Notes</p>
            <h3>رخداد و خطای اخیر</h3>
          </div>
          <span class="subtle">${toFa(incidents.length + alerts.length)} مورد فعال</span>
        </div>
        ${renderServerProblemList(lastProblem, incidents, alerts)}
      </article>
    </div>`;

  renderServerDetailCharts(metrics, checks);
}

function renderServerOutboundList(outbounds) {
  if (!can("outbounds")) {
    return `<div class="empty-state">برای مشاهده اوتباندها، دسترسی بخش اوت‌باند لازم است.</div>`;
  }
  if (!outbounds.length) {
    return `<div class="empty-state">برای این سرور هنوز اوت‌باندی ثبت نشده است. ابتدا x-ui را همگام‌سازی کنید.</div>`;
  }
  return `
    <div class="detail-outbound-list">
      ${outbounds
        .map((outbound) => {
          const selected = Number(outbound.id) === Number(state.serverDetail.focusOutboundId);
          const ping = outbound.last_ping_ms == null ? "-" : `${toFa(outbound.last_ping_ms)} ms`;
          return `
            <div class="detail-outbound-item ${selected ? "selected" : ""}">
              <div class="outbound-status-line">
                ${badge(outbound.last_status || "unknown", labelStatus(outbound.last_status))}
                <strong>${escapeHtml(outbound.remark)}</strong>
              </div>
              <div class="subtle">${escapeHtml(outbound.protocol || "-")} · ${escapeHtml(outbound.address || "-")}:${toFa(outbound.port || "-")} · ${formatDate(outbound.last_checked_at)}</div>
              <div class="outbound-metrics">
                <span>Ping ${ping}</span>
                <span>Avg ${outbound.avg_ping_ms == null ? "-" : `${toFa(outbound.avg_ping_ms)} ms`}</span>
                <span>Availability ${outbound.availability_percent == null ? "-" : `${toFa(outbound.availability_percent)}%`}</span>
                <span>${formatBytes(outbound.up_bytes)} / ${formatBytes(outbound.down_bytes)}</span>
              </div>
              <div class="table-actions">
                <button class="secondary" data-action="ping-detail-outbound" data-id="${outbound.id}">تست پینگ</button>
                ${can("history") ? `<button class="ghost" data-action="focus-detail-outbound" data-id="${outbound.id}">نمودار</button>` : ""}
              </div>
            </div>`;
        })
        .join("")}
    </div>`;
}

function renderServerProblemList(lastProblem, incidents, alerts) {
  const items = [];
  if (lastProblem) {
    items.push(`
      <div class="problem-item ${escapeHtml(lastProblem.level)}">
        <strong>${escapeHtml(lastProblem.title)}</strong>
        <span>${escapeHtml(lastProblem.message)}</span>
        <small>${formatDate(lastProblem.date)}</small>
      </div>`);
  }
  incidents.slice(0, 4).forEach((incident) => {
    items.push(`
      <div class="problem-item ${escapeHtml(incident.severity || "warning")}">
        <strong>${escapeHtml(incident.title || incident.kind)}</strong>
        <span>${escapeHtml(incident.message || "-")}</span>
        <small>${labelIncidentStatus(incident.status)} · ${formatDate(incident.last_seen_at)}</small>
      </div>`);
  });
  alerts.slice(0, 4).forEach((alert) => {
    items.push(`
      <div class="problem-item ${escapeHtml(alert.severity || "warning")}">
        <strong>${escapeHtml(alert.kind || "alert")}</strong>
        <span>${escapeHtml(alert.message || "-")}</span>
        <small>${formatDate(alert.created_at)}</small>
      </div>`);
  });
  if (!items.length) {
    return `<div class="empty-state">خطا یا رخداد فعالی برای این سرور وجود ندارد.</div>`;
  }
  return `<div class="problem-list">${items.join("")}</div>`;
}

function renderServerDetailCharts(metrics, checks) {
  const resourceChart = document.getElementById("serverDetailResourceChart");
  const pingChart = document.getElementById("serverDetailPingChart");
  if (!resourceChart || !pingChart) return;
  if (!can("history")) {
    renderEmptyChart(resourceChart, "برای مشاهده نمودار منابع، دسترسی تحلیل لازم است.");
    renderEmptyChart(pingChart, "برای مشاهده نمودار پینگ، دسترسی تحلیل لازم است.");
    return;
  }
  if (!metrics.length) {
    renderEmptyChart(resourceChart, "بعد از همگام‌سازی x-ui، روند CPU و RAM این سرور اینجا دیده می‌شود.");
  } else {
    renderLineChart(resourceChart, {
      min: 0,
      max: 100,
      series: [
        {
          color: "#00bfa6",
          values: metrics.map((item) => numberOrNull(item.cpu_percent)),
        },
        {
          color: "#6d5bd0",
          values: metrics.map((item) => numberOrNull(item.ram_percent)),
        },
      ],
    });
  }

  if (!checks.length) {
    renderEmptyChart(pingChart, "برای اوتباند انتخاب‌شده هنوز تاریخچه پینگ ثبت نشده است.");
  } else {
    const values = checks.map((item) => numberOrNull(item.latency_ms));
    const maxValue = Math.max(100, ...values.filter((value) => value != null));
    renderLineChart(pingChart, {
      min: 0,
      max: Math.ceil(maxValue * 1.18),
      series: [
        {
          color: "#00bfa6",
          values,
        },
      ],
      points: checks.map((item, index) => ({
        index,
        value: numberOrNull(item.latency_ms),
        status: item.status,
      })),
    });
  }
}

function detailFact(label, value) {
  return `
    <div class="detail-fact">
      <span>${escapeHtml(label)}</span>
      <strong>${value}</strong>
    </div>`;
}

function toggleDetailActions(enabled) {
  [els.detailSyncBtn, els.detailPingBtn, els.detailEditBtn, els.detailGoIncidentsBtn].forEach((button) => {
    if (button) button.disabled = !enabled;
  });
}

function ensureSelectedServerDetail() {
  const serverIds = new Set(state.servers.map((server) => Number(server.id)));
  if (!state.serverDetail.serverId || !serverIds.has(Number(state.serverDetail.serverId))) {
    state.serverDetail.serverId = state.servers[0]?.id || null;
    state.serverDetail.focusOutboundId = null;
    state.serverDetail.metrics = [];
    state.serverDetail.checks = [];
  }
  const outbounds = getServerOutbounds(state.serverDetail.serverId);
  const outboundIds = new Set(outbounds.map((outbound) => Number(outbound.id)));
  if (!state.serverDetail.focusOutboundId || !outboundIds.has(Number(state.serverDetail.focusOutboundId))) {
    state.serverDetail.focusOutboundId = pickFocusOutbound(outbounds)?.id || null;
    state.serverDetail.checks = [];
  }
}

function getSelectedServer() {
  return state.servers.find((server) => Number(server.id) === Number(state.serverDetail.serverId)) || null;
}

function getServerOutbounds(serverId) {
  if (!serverId) return [];
  return state.outbounds.filter((outbound) => Number(outbound.server_id) === Number(serverId));
}

function getServerIncidents(serverId) {
  if (!serverId || !can("incidents")) return [];
  return state.incidents.filter((incident) => Number(incident.server_id) === Number(serverId));
}

function getServerAlerts(serverId) {
  if (!serverId || !can("incidents")) return [];
  return state.alerts.filter((alert) => Number(alert.server_id) === Number(serverId));
}

function pickFocusOutbound(outbounds) {
  if (!outbounds.length) return null;
  return [...outbounds].sort((a, b) => outboundRiskRank(b) - outboundRiskRank(a))[0];
}

function outboundRiskRank(outbound) {
  const rank = {
    timeout: 6,
    error: 5,
    high: 4,
    warning: 3,
    unknown: 2,
    ok: 1,
  };
  return rank[outbound.last_status] || 0;
}

function isBadOutbound(outbound) {
  return ["high", "timeout", "error", "warning"].includes(outbound.last_status);
}

function calculateServerHealth(server, outbounds, incidents, alerts) {
  if (!server.enabled) {
    return {
      score: 0,
      level: "disabled",
      label: "غیرفعال",
      summary: "این سرور از پایش خارج شده است.",
      reason: "برای شروع مانیتورینگ، سرور را فعال کنید.",
    };
  }

  let score = 100;
  const reasons = [];
  const status = server.last_status || "unknown";
  if (status !== "online") {
    score -= status === "unknown" ? 16 : 34;
    reasons.push(`وضعیت ${labelStatus(status)}`);
  }
  score -= resourcePenalty(server.cpu_percent, server.cpu_warn, "CPU", reasons);
  score -= resourcePenalty(server.ram_percent, server.ram_warn, "RAM", reasons);

  const badOutbounds = outbounds.filter(isBadOutbound);
  if (badOutbounds.length) {
    score -= Math.min(34, badOutbounds.length * 8);
    reasons.push(`${toFa(badOutbounds.length)} اوتباند مشکل‌دار`);
  }

  const criticalIncidents = incidents.filter((incident) => incident.severity === "critical").length;
  const warningIncidents = incidents.length - criticalIncidents;
  if (criticalIncidents) {
    score -= Math.min(36, criticalIncidents * 18);
    reasons.push(`${toFa(criticalIncidents)} رخداد بحرانی`);
  }
  if (warningIncidents) {
    score -= Math.min(20, warningIncidents * 8);
    reasons.push(`${toFa(warningIncidents)} رخداد هشدار`);
  }
  if (alerts.length) {
    score -= Math.min(18, alerts.length * 5);
  }

  score = Math.max(0, Math.min(100, Math.round(score)));
  const level = score < 50 || criticalIncidents || status === "error" ? "critical" : score < 80 || badOutbounds.length ? "warning" : "ok";
  const label = level === "ok" ? "سالم" : level === "warning" ? "نیازمند بررسی" : "بحرانی";
  return {
    score,
    level,
    label,
    summary: level === "ok" ? "وضعیت عملیاتی سرور پایدار است." : "این سرور نیاز به توجه دارد.",
    reason: reasons.slice(0, 3).join(" · ") || "هیچ نشانه فعال از اختلال دیده نشد.",
  };
}

function resourcePenalty(value, warn, label, reasons) {
  const number = Number(value);
  if (!Number.isFinite(number)) return 0;
  const threshold = Number(warn || 85);
  if (number >= 95) {
    reasons.push(`${label} بسیار بالا`);
    return 24;
  }
  if (number >= threshold) {
    reasons.push(`${label} بالاتر از آستانه`);
    return 14;
  }
  return 0;
}

function getLastServerProblem(server, outbounds, incidents, alerts) {
  if (incidents.length) {
    const incident = incidents[0];
    return {
      level: incident.severity || "warning",
      title: incident.title || "رخداد فعال",
      message: incident.message || "-",
      date: incident.last_seen_at,
    };
  }
  if (alerts.length) {
    const alert = alerts[0];
    return {
      level: alert.severity || "warning",
      title: "اعلان فعال",
      message: alert.message || "-",
      date: alert.created_at,
    };
  }
  const badOutbound = outbounds.find(isBadOutbound);
  if (badOutbound?.last_error) {
    return {
      level: badOutbound.last_status || "warning",
      title: badOutbound.remark || "خطای اوتباند",
      message: badOutbound.last_error,
      date: badOutbound.last_checked_at,
    };
  }
  if (server.last_error) {
    return {
      level: server.last_status || "warning",
      title: "خطای سرور",
      message: server.last_error,
      date: server.last_checked_at,
    };
  }
  return null;
}

function renderNotificationChannels() {
  if (!state.notificationChannels.length) {
    els.notificationList.innerHTML = `<div class="empty-state">هنوز کانال اعلانی ثبت نشده است.</div>`;
    return;
  }
  els.notificationList.innerHTML = state.notificationChannels
    .map((channel) => {
      const config = channel.config || {};
      const target = channel.type === "telegram" ? config.chat_id : config.url;
      return `
        <article class="notification-item ${channel.enabled ? "enabled" : "disabled"}">
          <div class="notification-main">
            <div class="incident-title">
              ${badge(channel.enabled ? "ok" : "disabled", channel.enabled ? "فعال" : "غیرفعال")}
              <strong>${escapeHtml(channel.name)}</strong>
              <span class="subtle">${escapeHtml(channel.type)}</span>
            </div>
            <div class="subtle">
              مقصد: ${escapeHtml(target || "-")}
              · آخرین ارسال: ${formatDate(channel.last_sent_at)}
              ${channel.last_error ? `· خطا: ${escapeHtml(channel.last_error)}` : ""}
            </div>
          </div>
          <div class="incident-actions">
            <button class="secondary" data-action="test-channel" data-id="${channel.id}">تست</button>
            <button class="ghost" data-action="toggle-channel" data-id="${channel.id}">${channel.enabled ? "غیرفعال" : "فعال"}</button>
            <button class="ghost danger" data-action="delete-channel" data-id="${channel.id}">حذف</button>
          </div>
        </article>`;
    })
    .join("");
}

function renderNotificationFormMode() {
  const type = els.notificationForm.elements.type.value;
  document.querySelectorAll(".notification-telegram").forEach((item) => {
    item.classList.toggle("hidden", type !== "telegram");
  });
  document.querySelectorAll(".notification-webhook").forEach((item) => {
    item.classList.toggle("hidden", type !== "webhook");
  });
}

async function loadUsersAndAudit() {
  if (!can("users")) return;
  try {
    const [usersData, auditData] = await Promise.all([
      api("/api/users"),
      api("/api/audit-logs?limit=80"),
    ]);
    state.users = usersData.users || [];
    state.auth.permissionCatalog = usersData.permissions || state.auth.permissionCatalog;
    state.auth.managerLimit = usersData.manager_limit || state.auth.managerLimit;
    state.auditLogs = auditData.logs || [];
    renderPermissionGrid();
    renderUsers();
    renderAuditLogs();
  } catch (error) {
    toast(error.message);
  }
}

function renderUsers() {
  const managers = state.users.filter((user) => user.role === "manager");
  if (!state.users.length) {
    els.userList.innerHTML = `<div class="empty-state">هنوز کاربری ثبت نشده است.</div>`;
    return;
  }
  els.userList.innerHTML = `
    <div class="access-summary">
      <strong>${toFa(managers.length)} از ${toFa(state.auth.managerLimit)} مدیر ساخته شده</strong>
      <span>ادمین اصلی همیشه دسترسی کامل دارد.</span>
    </div>
    ${state.users
      .map((user) => {
        const permissions = user.role === "owner" ? ["دسترسی کامل"] : labelsForPermissions(user.permissions);
        return `
          <article class="user-item ${user.active ? "active" : "disabled"}">
            <div class="notification-main">
              <div class="incident-title">
                ${badge(user.active ? "ok" : "disabled", user.active ? "فعال" : "غیرفعال")}
                <strong>${escapeHtml(user.display_name || user.username)}</strong>
                <span class="subtle">${user.role === "owner" ? "ادمین اصلی" : "مدیر"}</span>
              </div>
              <div class="subtle">
                ${escapeHtml(user.username)}
                · آخرین ورود: ${formatDate(user.last_login_at)}
              </div>
              <div class="permission-tags">${permissions
                .map((label) => `<span>${escapeHtml(label)}</span>`)
                .join("")}</div>
            </div>
            <div class="incident-actions">
              ${
                user.role === "manager"
                  ? `
                    <button class="secondary" data-action="edit-user" data-id="${user.id}">ویرایش</button>
                    <button class="ghost" data-action="toggle-user" data-id="${user.id}">${user.active ? "غیرفعال" : "فعال"}</button>
                    <button class="ghost danger" data-action="delete-user" data-id="${user.id}">حذف</button>
                  `
                  : ""
              }
            </div>
          </article>`;
      })
      .join("")}`;
}

function renderAuditLogs() {
  if (!state.auditLogs.length) {
    els.auditList.innerHTML = `<div class="empty-state">هنوز لاگی ثبت نشده است.</div>`;
    return;
  }
  els.auditList.innerHTML = state.auditLogs
    .map(
      (log) => `
        <article class="audit-item">
          <strong>${escapeHtml(actionLabel(log.action))}</strong>
          <span>${escapeHtml(log.actor_username || "system")} · ${formatDate(log.created_at)}</span>
          <small>${escapeHtml(log.target_type || "-")} ${escapeHtml(log.target_id || "")}</small>
        </article>`
    )
    .join("");
}

async function loadBackups() {
  if (!can("maintenance")) return;
  try {
    const data = await api("/api/backups");
    state.backups = data.backups || [];
    renderBackups();
  } catch (error) {
    toast(error.message);
  }
}

function renderBackups() {
  if (!state.backups.length) {
    els.backupList.innerHTML = `<div class="empty-state">هنوز بکاپی ساخته نشده است.</div>`;
    return;
  }
  els.backupList.innerHTML = state.backups
    .map(
      (backup) => `
        <article class="backup-item">
          <div class="notification-main">
            <div class="incident-title">
              ${badge("ok", "ZIP")}
              <strong>${escapeHtml(backup.name)}</strong>
              <span class="subtle">نسخه ${escapeHtml(backup.version || "-")}</span>
            </div>
            <div class="subtle">
              زمان ساخت: ${formatDate(backup.created_at)}
              · حجم: ${formatBytes(backup.size)}
              · نوع: ${escapeHtml(backup.reason || "manual")}
            </div>
          </div>
          <div class="incident-actions">
            <button class="secondary" data-action="download-backup" data-name="${escapeHtml(backup.name)}">دانلود</button>
            <button class="ghost" data-action="restore-backup" data-name="${escapeHtml(backup.name)}">ریستور</button>
            <button class="ghost danger" data-action="delete-backup" data-name="${escapeHtml(backup.name)}">حذف</button>
          </div>
        </article>`
    )
    .join("");
}

async function createBackup() {
  const button = document.getElementById("createBackupBtn");
  await withBusy(button, async () => {
    await api("/api/backups", { method: "POST" });
    toast("بکاپ ساخته شد.");
    await loadBackups();
    if (can("users")) await loadUsersAndAudit();
  });
}

function downloadBackup(name) {
  window.location.href = `/api/backups/${encodeURIComponent(name)}/download`;
}

async function restoreBackup(name, button) {
  const confirmed = confirm(
    "ریستور، دیتابیس فعلی Veltrix را با این بکاپ جایگزین می‌کند. قبل از ریستور یک بکاپ ایمنی ساخته می‌شود. ادامه می‌دهید؟"
  );
  if (!confirmed) return;
  await withBusy(button, async () => {
    await api(`/api/backups/${encodeURIComponent(name)}/restore`, { method: "POST" });
    toast("ریستور انجام شد. دوباره وارد شوید.");
    showAuth("login");
    await initAuth();
  });
}

async function deleteBackup(name, button) {
  if (!confirm(`بکاپ ${name} حذف شود؟`)) return;
  await withBusy(button, async () => {
    await api(`/api/backups/${encodeURIComponent(name)}`, { method: "DELETE" });
    toast("بکاپ حذف شد.");
    await loadBackups();
    if (can("users")) await loadUsersAndAudit();
  });
}

function openUserEditor(id) {
  const user = state.users.find((item) => Number(item.id) === Number(id));
  if (!user || user.role !== "manager") return;
  state.editingUser = user;
  els.userForm.elements.id.value = user.id;
  els.userForm.elements.display_name.value = user.display_name || "";
  els.userForm.elements.username.value = user.username || "";
  els.userForm.elements.password.value = "";
  els.userForm.elements.password.placeholder = "برای تغییر رمز، مقدار جدید وارد کنید";
  els.userForm.elements.active.checked = Boolean(user.active);
  setSelectedPermissions(user.permissions || []);
  els.cancelUserEditBtn.classList.remove("hidden");
  document.getElementById("users").scrollIntoView({ behavior: "smooth", block: "start" });
}

function resetUserForm() {
  state.editingUser = null;
  els.userForm.reset();
  els.userForm.elements.id.value = "";
  els.userForm.elements.active.checked = true;
  els.userForm.elements.password.placeholder = "";
  setSelectedPermissions([]);
  els.cancelUserEditBtn.classList.add("hidden");
}

async function saveUser(event) {
  event.preventDefault();
  const button = els.userForm.querySelector("button[type='submit']");
  await withBusy(button, async () => {
    const formData = new FormData(els.userForm);
    const id = formData.get("id");
    const payload = {
      display_name: formData.get("display_name"),
      username: formData.get("username"),
      password: formData.get("password"),
      active: formData.has("active"),
      permissions: formData.getAll("permissions"),
    };
    if (id && !payload.password) delete payload.password;
    await api(id ? `/api/users/${id}` : "/api/users", {
      method: id ? "PUT" : "POST",
      body: JSON.stringify(payload),
    });
    toast(id ? "مدیر بروزرسانی شد." : "مدیر جدید ساخته شد.");
    resetUserForm();
    await loadUsersAndAudit();
  });
}

async function toggleUser(id, button) {
  const user = state.users.find((item) => Number(item.id) === Number(id));
  if (!user) return;
  await withBusy(button, async () => {
    await api(`/api/users/${id}`, {
      method: "PUT",
      body: JSON.stringify(userToPayload(user, !user.active)),
    });
    toast("وضعیت مدیر تغییر کرد.");
    await loadUsersAndAudit();
  });
}

async function deleteUser(id, button) {
  const user = state.users.find((item) => Number(item.id) === Number(id));
  if (!confirm(`مدیر ${user?.display_name || user?.username || id} حذف شود؟`)) return;
  await withBusy(button, async () => {
    await api(`/api/users/${id}`, { method: "DELETE" });
    toast("مدیر حذف شد.");
    resetUserForm();
    await loadUsersAndAudit();
  });
}

function userToPayload(user, active) {
  return {
    display_name: user.display_name,
    username: user.username,
    active,
    permissions: user.permissions || [],
  };
}

function setSelectedPermissions(permissions) {
  const selected = new Set(permissions || []);
  els.managerPermissionGrid.querySelectorAll("input[name='permissions']").forEach((input) => {
    input.checked = selected.has(input.value);
  });
}

function labelsForPermissions(permissions) {
  const labels = new Map((state.auth.permissionCatalog || []).map((item) => [item.key, item.label]));
  return (permissions || []).map((permission) => labels.get(permission) || permission);
}

function actionLabel(action) {
  const labels = {
    "auth.setup_owner": "ساخت ادمین اصلی",
    "auth.login": "ورود",
    "auth.logout": "خروج",
    "auth.login_failed": "ورود ناموفق",
    "auth.password_change": "تغییر رمز",
    "auth.password_change_failed": "تغییر رمز ناموفق",
    "users.create_manager": "ساخت مدیر",
    "users.update_manager": "ویرایش مدیر",
    "users.delete_manager": "حذف مدیر",
    "servers.create": "افزودن سرور",
    "servers.update": "ویرایش سرور",
    "servers.delete": "حذف سرور",
    "servers.sync": "همگام‌سازی سرور",
    "outbounds.ping": "تست پینگ",
    "incidents.acknowledge": "تایید رخداد",
    "incidents.recover": "بستن رخداد",
    "notifications.create_channel": "ساخت کانال اعلان",
    "notifications.update_channel": "ویرایش کانال اعلان",
    "notifications.delete_channel": "حذف کانال اعلان",
    "notifications.test_channel": "تست کانال اعلان",
    "maintenance.create_backup": "ساخت بکاپ",
    "maintenance.restore_backup": "ریستور بکاپ",
    "maintenance.delete_backup": "حذف بکاپ",
    "license.activate": "فعال‌سازی لایسنس",
    "monitor.run": "پایش فوری",
  };
  return labels[action] || action;
}

function renderLicense() {
  const license = state.license;
  if (!license) return;
  const plans = license.available_plans || {};

  const stateLabel = license.state === "active" ? "فعال" : "بدون لایسنس";
  const stateClass = license.state === "active" ? "ok" : license.state === "invalid_ip" ? "error" : "warning";
  const stateText = licenseStateLabel(license.state);
  const planLabel = license.plan?.name || "ثبت نشده";
  const durationLabel = license.duration?.label || "ثبت نشده";
  els.licenseStatus.innerHTML = [
    badge(stateClass, stateText || stateLabel),
    badge("unknown", `پلن: ${planLabel}`),
    badge("unknown", `دوره: ${durationLabel}`),
    badge(ipBadgeClass(license), `IP مجاز: ${license.bound_ip || "ثبت نشده"}`),
    badge("unknown", `IP سرور: ${license.detected_ip || "نامشخص"}`),
    badge("unknown", `Instance: ${shortId(license.instance_id)}`),
  ].join("");

  els.licensePlans.innerHTML = Object.entries(plans)
    .map(([key, plan]) => {
      const isActive = license.plan_key === key;
      const limits = [
        `${toFa(plan.max_servers)} سرور`,
        plan.max_outbounds ? `${toFa(plan.max_outbounds)} اوت‌باند` : "اوت‌باند بدون سقف فعلی",
      ].join(" / ");
      return `
        <article class="plan-card ${escapeHtml(key)}">
          <div class="row-title">
            <strong>${plan.name} ${isActive ? badge("ok", "فعال") : ""}</strong>
            <span class="muted">${limits}</span>
          </div>
          <span class="subtle">${escapeHtml(plan.recommended_for)}</span>
          <ul>${plan.features.map((feature) => `<li>${escapeHtml(feature)}</li>`).join("")}</ul>
        </article>`;
    })
    .join("");
}

function renderHistoryControls() {
  const serverOptions = state.servers
    .map((server) => `<option value="${server.id}">${escapeHtml(server.name)}</option>`)
    .join("");
  els.serverHistorySelect.innerHTML = serverOptions || `<option value="">سروری ثبت نشده</option>`;

  const serverIds = new Set(state.servers.map((server) => Number(server.id)));
  if (!state.history.serverId || !serverIds.has(Number(state.history.serverId))) {
    state.history.serverId = state.servers[0]?.id || null;
  }
  els.serverHistorySelect.value = state.history.serverId || "";

  const outbounds = state.history.serverId
    ? state.outbounds.filter((outbound) => Number(outbound.server_id) === Number(state.history.serverId))
    : state.outbounds;
  const outboundOptions = outbounds
    .map((outbound) => `<option value="${outbound.id}">${escapeHtml(outbound.remark)}</option>`)
    .join("");
  els.outboundHistorySelect.innerHTML = outboundOptions || `<option value="">اوت‌باندی ثبت نشده</option>`;

  const outboundIds = new Set(outbounds.map((outbound) => Number(outbound.id)));
  if (!state.history.outboundId || !outboundIds.has(Number(state.history.outboundId))) {
    state.history.outboundId = outbounds[0]?.id || null;
  }
  els.outboundHistorySelect.value = state.history.outboundId || "";
}

async function selectServerDetail(serverId, scrollToDetail) {
  state.serverDetail.serverId = serverId;
  state.serverDetail.focusOutboundId = null;
  state.serverDetail.metrics = [];
  state.serverDetail.checks = [];
  ensureSelectedServerDetail();
  renderServers();
  renderServerDetail();
  if (can("history")) {
    state.history.serverId = serverId;
    state.history.outboundId = state.serverDetail.focusOutboundId;
    renderHistoryControls();
    await Promise.all([loadHistory(false), loadServerDetailTelemetry(false)]);
  }
  if (scrollToDetail) {
    document.querySelector('a[href="#server-detail"]')?.click();
    document.getElementById("server-detail")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

async function focusServerDetailOutbound(outboundId, showToast) {
  state.serverDetail.focusOutboundId = outboundId;
  renderServerDetail();
  if (can("history")) {
    state.history.outboundId = outboundId;
    renderHistoryControls();
    await Promise.all([loadHistory(false), loadServerDetailTelemetry(false)]);
  }
  if (showToast) toast("نمودار پینگ اوتباند انتخاب شد.");
}

async function loadServerDetailTelemetry(showToast) {
  const server = getSelectedServer();
  if (!server || !can("history")) {
    state.serverDetail.metrics = [];
    state.serverDetail.checks = [];
    renderServerDetail();
    return;
  }

  ensureSelectedServerDetail();
  try {
    const [metricsData, checksData] = await Promise.all([
      api(`/api/servers/${server.id}/metrics?limit=50`),
      state.serverDetail.focusOutboundId
        ? api(`/api/outbounds/${state.serverDetail.focusOutboundId}/checks?limit=70`)
        : Promise.resolve({ checks: [] }),
    ]);
    state.serverDetail.metrics = metricsData.metrics || [];
    state.serverDetail.checks = checksData.checks || [];
    renderServerDetail();
    if (showToast) toast("جزئیات سرور بروزرسانی شد.");
  } catch (error) {
    toast(error.message);
  }
}

async function loadHistory(showToast) {
  try {
    const [metricsData, checksData] = await Promise.all([
      state.history.serverId
        ? api(`/api/servers/${state.history.serverId}/metrics?limit=80`)
        : Promise.resolve({ metrics: [] }),
      state.history.outboundId
        ? api(`/api/outbounds/${state.history.outboundId}/checks?limit=120`)
        : Promise.resolve({ checks: [] }),
    ]);
    state.history.metrics = metricsData.metrics || [];
    state.history.checks = checksData.checks || [];
    renderHistoryCharts();
    if (showToast) toast("تاریخچه بروزرسانی شد.");
  } catch (error) {
    toast(error.message);
  }
}

function renderHistoryCharts() {
  renderResourceChart();
  renderPingChart();
}

function renderResourceChart() {
  const metrics = state.history.metrics || [];
  els.resourceChartMeta.textContent = metrics.length
    ? `${toFa(metrics.length)} نمونه / آخرین: ${formatDate(metrics.at(-1)?.created_at)}`
    : "بدون داده";
  if (!metrics.length) {
    renderEmptyChart(els.resourceChart, "بعد از همگام‌سازی x-ui، نمودار منابع اینجا دیده می‌شود.");
    return;
  }
  renderLineChart(els.resourceChart, {
    min: 0,
    max: 100,
    series: [
      {
        color: "#00bfa6",
        values: metrics.map((item) => numberOrNull(item.cpu_percent)),
      },
      {
        color: "#6d5bd0",
        values: metrics.map((item) => numberOrNull(item.ram_percent)),
      },
    ],
  });
}

function renderPingChart() {
  const checks = state.history.checks || [];
  els.pingChartMeta.textContent = checks.length
    ? `${toFa(checks.length)} تست / آخرین: ${formatDate(checks.at(-1)?.created_at)}`
    : "بدون داده";
  if (!checks.length) {
    renderEmptyChart(els.pingChart, "بعد از تست پینگ، نمودار latency اینجا دیده می‌شود.");
    return;
  }
  const values = checks.map((item) => numberOrNull(item.latency_ms));
  const maxValue = Math.max(100, ...values.filter((value) => value != null));
  renderLineChart(els.pingChart, {
    min: 0,
    max: Math.ceil(maxValue * 1.18),
    series: [
      {
        color: "#00bfa6",
        values,
      },
    ],
    points: checks.map((item, index) => ({
      index,
      value: numberOrNull(item.latency_ms),
      status: item.status,
    })),
  });
}

function renderEmptyChart(container, message) {
  container.innerHTML = `<div class="chart-empty">${escapeHtml(message)}</div>`;
}

function renderLineChart(container, config) {
  const width = 640;
  const height = 230;
  const pad = 26;
  const min = config.min;
  const max = config.max === min ? min + 1 : config.max;
  const count = Math.max(1, ...config.series.map((serie) => serie.values.length));
  const xFor = (index) => pad + (count === 1 ? 0 : (index / (count - 1)) * (width - pad * 2));
  const yFor = (value) => height - pad - ((value - min) / (max - min)) * (height - pad * 2);

  const paths = config.series
    .map((serie) => {
      const d = linePath(serie.values, xFor, yFor);
      return d ? `<path d="${d}" fill="none" stroke="${serie.color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />` : "";
    })
    .join("");

  const points = (config.points || [])
    .filter((point) => point.value != null && point.status && point.status !== "ok")
    .map((point) => {
      const color = point.status === "high" ? "#b7791f" : "#b42318";
      return `<circle cx="${xFor(point.index)}" cy="${yFor(point.value)}" r="4" fill="${color}" />`;
    })
    .join("");

  const grid = [0, 25, 50, 75, 100]
    .map((percent) => {
      const y = pad + ((100 - percent) / 100) * (height - pad * 2);
      return `<line x1="${pad}" y1="${y}" x2="${width - pad}" y2="${y}" class="chart-grid-line" />`;
    })
    .join("");

  container.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="history chart">
      ${grid}
      <line x1="${pad}" y1="${height - pad}" x2="${width - pad}" y2="${height - pad}" class="chart-axis" />
      ${paths}
      ${points}
    </svg>`;
}

function linePath(values, xFor, yFor) {
  let d = "";
  values.forEach((value, index) => {
    if (value == null) return;
    d += `${d ? " L" : "M"} ${xFor(index).toFixed(1)} ${yFor(value).toFixed(1)}`;
  });
  return d;
}

function numberOrNull(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function licenseStateLabel(state) {
  const labels = {
    active: "لایسنس فعال",
    unlicensed: "بدون لایسنس",
    pending_ip_binding: "در انتظار ثبت IP",
    ip_unverified: "IP قابل تایید نیست",
    invalid_ip: "IP نامعتبر",
  };
  return labels[state] || state;
}

function ipBadgeClass(license) {
  if (license.ip_match === true) return "ok";
  if (license.ip_match === false) return "error";
  return "warning";
}

function openServerDialog(serverId) {
  const server = state.servers.find((item) => item.id === serverId) || null;
  state.editingServer = server;
  els.dialogTitle.textContent = server ? "ویرایش سرور" : "سرور جدید";
  els.deleteServerBtn.style.visibility = server ? "visible" : "hidden";
  els.form.reset();
  els.form.elements.id.value = server?.id || "";
  els.form.elements.name.value = server?.name || "";
  els.form.elements.host.value = server?.host || "";
  els.form.elements.panel_url.value = server?.panel_url || "";
  els.form.elements.username.value = server?.username || "";
  els.form.elements.password.value = "";
  els.form.elements.password.placeholder = server?.has_password
    ? "برای تغییر رمز x-ui مقدار جدید وارد کنید"
    : "";
  // Auth mode
  const authMode = server?.api_token ? "api_token" : "credentials";
  const authModeSelect = document.getElementById("serverAuthMode");
  if (authModeSelect) authModeSelect.value = authMode;
  const apiTokenInput = els.form.elements.api_token;
  if (apiTokenInput) {
    apiTokenInput.value = "";
    apiTokenInput.placeholder = server?.has_api_token ? "توکن فعلی ذخیره شده — برای تغییر مقدار جدید وارد کنید" : "";
  }
  toggleServerAuthMode(authMode);

  els.form.elements.cpu_warn.value = server?.cpu_warn || 85;
  els.form.elements.ram_warn.value = server?.ram_warn || 85;
  els.form.elements.ping_warn_ms.value = server?.ping_warn_ms || 350;
  els.form.elements.timeout_ms.value = server?.timeout_ms || 2500;
  els.form.elements.verify_tls.checked = server ? Boolean(server.verify_tls) : true;
  els.form.elements.enabled.checked = server ? Boolean(server.enabled) : true;
  els.dialog.showModal();
}

function toggleServerAuthMode(mode) {
  const credFields = document.getElementById("authCredentialsFields");
  const tokenFields = document.getElementById("authTokenFields");
  if (credFields) credFields.classList.toggle("hidden", mode === "api_token");
  if (tokenFields) tokenFields.classList.toggle("hidden", mode !== "api_token");
}

// Auth mode change listener
document.getElementById("serverAuthMode")?.addEventListener("change", function() {
  toggleServerAuthMode(this.value);
});

function closeServerDialog() {
  els.dialog.close();
}

async function saveServer(event) {
  event.preventDefault();
  const data = formDataToServer(new FormData(els.form));
  const id = els.form.elements.id.value;
  const submitButton = els.form.querySelector("button[type='submit']");
  await withBusy(submitButton, async () => {
    if (id) {
      await api(`/api/servers/${id}`, { method: "PUT", body: JSON.stringify(data) });
      toast("سرور بروزرسانی شد.");
    } else {
      await api("/api/servers", { method: "POST", body: JSON.stringify(data) });
      toast("سرور اضافه شد.");
    }
    closeServerDialog();
    await loadOverview(false);
  });
}

async function deleteCurrentServer() {
  if (!state.editingServer) return;
  await deleteServer(state.editingServer.id);
  closeServerDialog();
}

async function deleteServer(id) {
  const server = state.servers.find((item) => item.id === id);
  if (!confirm(`سرور ${server?.name || id} حذف شود؟`)) return;
  await api(`/api/servers/${id}`, { method: "DELETE" });
  toast("سرور حذف شد.");
  await loadOverview(false);
}

async function syncServer(id, button) {
  await withBusy(button, async () => {
    const result = await api(`/api/servers/${id}/sync`, { method: "POST" });
    toast(result.status === "online" ? `همگام‌سازی انجام شد: ${toFa(result.synced)} مورد` : result.error || "همگام‌سازی ناموفق بود.");
    await loadOverview(false);
  });
}

async function syncSelectedServer(button) {
  const server = getSelectedServer();
  if (!server) return;
  await syncServer(server.id, button);
}

async function editSelectedServer() {
  const server = getSelectedServer();
  if (server) openServerDialog(server.id);
}

async function pingOutbound(id, button) {
  await withBusy(button, async () => {
    const result = await api(`/api/outbounds/${id}/ping`, { method: "POST" });
    toast(result.latency_ms == null ? labelStatus(result.status) : `${toFa(result.latency_ms)} ms`);
    await loadOverview(false);
  });
}

async function pingSelectedServerOutbounds(button) {
  const server = getSelectedServer();
  if (!server) return;
  const outbounds = getServerOutbounds(server.id);
  if (!outbounds.length) {
    toast("برای این سرور اوتباندی وجود ندارد.");
    return;
  }
  await withBusy(button, async () => {
    const results = await runPool(outbounds, 6, (outbound) => api(`/api/outbounds/${outbound.id}/ping`, { method: "POST" }));
    const okCount = results.filter((result) => result.status === "fulfilled" && ["ok", "high"].includes(result.value.status)).length;
    toast(`تست پینگ انجام شد: ${toFa(okCount)} از ${toFa(outbounds.length)} پاسخ معتبر`);
    await loadOverview(false);
  });
}

async function runPool(items, limit, worker) {
  const results = [];
  let index = 0;
  async function runner() {
    while (index < items.length) {
      const currentIndex = index;
      index += 1;
      try {
        results[currentIndex] = { status: "fulfilled", value: await worker(items[currentIndex], currentIndex) };
      } catch (error) {
        results[currentIndex] = { status: "rejected", reason: error };
      }
    }
  }
  const workers = Array.from({ length: Math.min(limit, items.length) }, runner);
  await Promise.all(workers);
  return results;
}

async function runMonitor() {
  const button = document.getElementById("runMonitorBtn");
  await withBusy(button, async () => {
    await api("/api/monitor/run", { method: "POST" });
    toast("پایش فوری کامل شد.");
    await loadOverview(false);
  });
}

async function acknowledgeIncident(id, button) {
  await withBusy(button, async () => {
    await api(`/api/incidents/${id}/ack`, {
      method: "POST",
      body: JSON.stringify({ by: "operator" }),
    });
    toast("رخداد تایید شد.");
    await loadOverview(false);
  });
}

async function recoverIncident(id, button) {
  if (!confirm("این رخداد به صورت دستی بسته شود؟")) return;
  await withBusy(button, async () => {
    await api(`/api/incidents/${id}/recover`, {
      method: "POST",
      body: JSON.stringify({ message: "Recovered manually from dashboard." }),
    });
    toast("رخداد بسته شد.");
    await loadOverview(false);
  });
}

async function loadNotificationChannels() {
  try {
    const data = await api("/api/notification-channels");
    state.notificationChannels = data.channels || [];
    renderNotificationChannels();
  } catch (error) {
    toast(error.message);
  }
}

async function saveNotificationChannel(event) {
  event.preventDefault();
  const button = els.notificationForm.querySelector("button[type='submit']");
  await withBusy(button, async () => {
    const formData = new FormData(els.notificationForm);
    const type = formData.get("type");
    const payload = {
      name: formData.get("name") || type,
      type,
      enabled: formData.has("enabled"),
      config:
        type === "telegram"
          ? {
              bot_token: formData.get("bot_token"),
              chat_id: formData.get("chat_id"),
            }
          : {
              url: formData.get("url"),
              secret: formData.get("secret"),
            },
    };
    await api("/api/notification-channels", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    toast("کانال اعلان ذخیره شد.");
    els.notificationForm.reset();
    els.notificationForm.elements.enabled.checked = true;
    renderNotificationFormMode();
    await loadNotificationChannels();
  });
}

async function testNotificationChannel(id, button) {
  await withBusy(button, async () => {
    await api(`/api/notification-channels/${id}/test`, { method: "POST" });
    toast("اعلان تست ارسال شد.");
    await loadNotificationChannels();
  });
}

async function toggleNotificationChannel(id, button) {
  const channel = state.notificationChannels.find((item) => Number(item.id) === Number(id));
  if (!channel) return;
  await withBusy(button, async () => {
    await api(`/api/notification-channels/${id}`, {
      method: "PUT",
      body: JSON.stringify(channelToUpdatePayload(channel, !channel.enabled)),
    });
    toast("وضعیت کانال تغییر کرد.");
    await loadNotificationChannels();
  });
}

async function deleteNotificationChannel(id, button) {
  if (!confirm("این کانال اعلان حذف شود؟")) return;
  await withBusy(button, async () => {
    await api(`/api/notification-channels/${id}`, { method: "DELETE" });
    toast("کانال اعلان حذف شد.");
    await loadNotificationChannels();
  });
}

function channelToUpdatePayload(channel, enabled) {
  const config = channel.config || {};
  return {
    name: channel.name,
    type: channel.type,
    enabled,
    config:
      channel.type === "telegram"
        ? {
            bot_token: "keep-existing-token",
            chat_id: config.chat_id || "",
            message_thread_id: config.message_thread_id || "",
          }
        : {
            url: config.url || "",
            secret: config.secret ? "keep-existing-secret" : "",
          },
  };
}

async function activateLicense(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector("button");
  const licenseKey = form.elements.license_key.value.trim().toUpperCase();
  await withBusy(button, async () => {
    const result = await api("/api/license/activate", {
      method: "POST",
      body: JSON.stringify({ license_key: licenseKey }),
    });
    const state = result.status?.state || result.license?.state;
    toast(state === "active" ? "لایسنس Veltrix فعال شد." : licenseStateLabel(state));
    form.reset();
    await loadOverview(false);
  });
}

function requestNotifications() {
  if (!("Notification" in window)) {
    toast("مرورگر از اعلان پشتیبانی نمی‌کند.");
    return;
  }
  Notification.requestPermission().then((permission) => {
    toast(permission === "granted" ? "اعلان مرورگر فعال شد." : "اعلان مرورگر فعال نشد.");
  });
}

function notifyNewAlerts() {
  if (!("Notification" in window) || Notification.permission !== "granted") return;
  state.alerts.forEach((alert) => {
    if (state.notifiedAlerts.has(alert.id)) return;
    new Notification("OutPanel", { body: alert.message });
    state.notifiedAlerts.add(alert.id);
  });
  localStorage.setItem("outpanelNotifiedAlerts", JSON.stringify([...state.notifiedAlerts].slice(-300)));
}

function shortId(value) {
  if (!value) return "-";
  return `${value.slice(0, 8)}…`;
}

function formDataToServer(formData) {
  const authMode = formData.get("auth_mode") || "credentials";
  const payload = {
    name: formData.get("name"),
    host: formData.get("host"),
    panel_url: formData.get("panel_url"),
    auth_mode: authMode,
    verify_tls: formData.has("verify_tls"),
    enabled: formData.has("enabled"),
    cpu_warn: Number(formData.get("cpu_warn")),
    ram_warn: Number(formData.get("ram_warn")),
    ping_warn_ms: Number(formData.get("ping_warn_ms")),
    timeout_ms: Number(formData.get("timeout_ms")),
  };

  if (authMode === "api_token") {
    // API Token authentication
    const apiToken = String(formData.get("api_token") || "").trim();
    if (apiToken || !formData.get("id")) {
      payload.api_token = apiToken;
    }
    payload.username = "";
    payload.password = "";
  } else {
    // Username/Password authentication
    payload.username = formData.get("username");
    const password = String(formData.get("password") || "").trim();
    if (password || !formData.get("id")) {
      payload.password = password;
    }
    payload.api_token = "";
  }

  return payload;
}

async function withBusy(button, task) {
  const oldText = button?.textContent;
  if (button) {
    button.disabled = true;
    button.textContent = "در حال انجام";
  }
  try {
    await task();
  } catch (error) {
    toast(error.message);
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = oldText;
    }
  }
}

function badge(status = "unknown", label = status) {
  return `<span class="badge ${escapeHtml(status)}">${escapeHtml(label || "-")}</span>`;
}

function labelStatus(status) {
  const labels = {
    online: "آنلاین",
    ok: "سالم",
    high: "پینگ بالا",
    timeout: "تایم‌اوت",
    error: "خطا",
    warning: "هشدار",
    critical: "بحرانی",
    disabled: "غیرفعال",
    unknown: "نامشخص",
  };
  return labels[status] || status || "نامشخص";
}

function labelIncidentStatus(status) {
  const labels = {
    open: "باز",
    acknowledged: "تایید شده",
    recovered: "حل شده",
  };
  return labels[status] || status || "-";
}

function formatDuration(seconds) {
  const value = Math.max(0, Number(seconds || 0));
  if (value < 60) return `${toFa(value)} ثانیه`;
  const minutes = Math.floor(value / 60);
  if (minutes < 60) return `${toFa(minutes)} دقیقه`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return `${toFa(hours)} ساعت ${toFa(rest)} دقیقه`;
}

function meter(value) {
  if (value == null || Number.isNaN(Number(value))) return "-";
  const number = Math.max(0, Math.min(100, Number(value)));
  const cls = number >= 90 ? "bad" : number >= 75 ? "warn" : "";
  return `
    <div class="row-title">
      <span>${toFa(number.toFixed(1))}%</span>
      <div class="meter ${cls}" style="--value: ${number}%"><span></span></div>
    </div>`;
}

function formatResourceAverage(servers) {
  const cpuValues = servers.map((server) => Number(server.cpu_percent)).filter((value) => !Number.isNaN(value));
  const ramValues = servers.map((server) => Number(server.ram_percent)).filter((value) => !Number.isNaN(value));
  if (!cpuValues.length && !ramValues.length) return "-";
  const cpu = cpuValues.length ? `${toFa(average(cpuValues).toFixed(0))}%` : "-";
  const ram = ramValues.length ? `${toFa(average(ramValues).toFixed(0))}%` : "-";
  return `CPU ${cpu} / RAM ${ram}`;
}

function average(values) {
  if (!values.length) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function formatBytes(value) {
  const number = Number(value || 0);
  if (number < 1024) return `${toFa(number)} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let size = number / 1024;
  let unit = units.shift();
  while (size >= 1024 && units.length) {
    size /= 1024;
    unit = units.shift();
  }
  return `${toFa(size.toFixed(size >= 10 ? 1 : 2))} ${unit}`;
}

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return new Intl.DateTimeFormat("fa-IR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function toFa(value) {
  return String(value).replace(/\d/g, (digit) => "۰۱۲۳۴۵۶۷۸۹"[digit]);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function toast(message) {
  els.toast.textContent = message;
  els.toast.classList.add("show");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => els.toast.classList.remove("show"), 3200);
}
