function extractInitDataFromLocation() {
  const tryDecode = (value) => {
    if (!value) return "";
    try {
      return decodeURIComponent(value);
    } catch (err) {
      return value;
    }
  };

  const query = new URLSearchParams(window.location.search || "");
  const hashRaw = (window.location.hash || "").replace(/^#/, "");
  const hash = new URLSearchParams(hashRaw);

  const fromQuery = query.get("initData") || query.get("tgWebAppData");
  if (fromQuery) return tryDecode(fromQuery);

  const fromHash = hash.get("initData") || hash.get("tgWebAppData");
  if (fromHash) return tryDecode(fromHash);

  return "";
}

function getTelegramInitData() {
  if (tg?.initData) return tg.initData;
  return extractInitDataFromLocation();
}

async function waitTelegramInitData(timeoutMs = 2000) {
  const started = Date.now();
  if (tg?.ready) {
    try {
      tg.ready();
    } catch (err) {
      // ignore
    }
  }
  while (Date.now() - started < timeoutMs) {
    const value = getTelegramInitData();
    if (value) return value;
    await new Promise((resolve) => setTimeout(resolve, 80));
  }
  return getTelegramInitData();
}

async function apiFetch(path, options = {}) {
  const headers = options.headers || {};
  headers["Content-Type"] = headers["Content-Type"] || "application/json";
  headers["ngrok-skip-browser-warning"] = "1";
  const initData = await waitTelegramInitData();
  if (initData) {
    headers["X-Telegram-Init-Data"] = initData;
  }
  const response = await fetch(path, { ...options, headers });
  if (!response.ok) {
    if (!String(path || "").startsWith("/api/stats/")) {
      void trackEvent("api_errors");
    }
    const text = await response.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch (err) {
      data = null;
    }
    const detail = data?.detail ?? data;
    const message = (detail && typeof detail === "object" ? detail.message : detail) || text || `HTTP ${response.status}`;
    const error = new Error(message);
    error.status = response.status;
    error.data = detail;
    if (response.status === 401) {
      setUnauthorizedMode(true);
    }
    throw error;
  }
  if (state.unauthorized) {
    setUnauthorizedMode(false);
  }
  return response.json();
}

async function trackEvent(eventName) {
  if (!eventName) return;
  const initData = await waitTelegramInitData(1200);
  if (!initData) return;
  try {
    await fetch("/api/stats/event", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "ngrok-skip-browser-warning": "1",
        "X-Telegram-Init-Data": initData,
      },
      body: JSON.stringify({ event: eventName }),
    });
  } catch (err) {
    // ignore analytics transport errors
  }
}

async function refreshAdminStats() {
  try {
    const data = await apiFetch("/api/stats/summary");
    state.isAdmin = true;
    state.statsSummary = data || null;
    elements.statsToggle.hidden = false;
  } catch (err) {
    if (err?.status === 401) {
      state.isAdmin = false;
      state.statsSummary = null;
      elements.statsToggle.hidden = true;
      renderStatsSummary();
      return;
    }
    state.isAdmin = false;
    state.statsSummary = null;
    elements.statsToggle.hidden = true;
  }
  renderStatsSummary();
}

async function refreshAdminExpiredAds() {
  try {
    const data = await apiFetch("/api/stats/expired-ads");
    state.isAdmin = true;
    state.expiredAds = Array.isArray(data?.items) ? data.items : [];
    state.adminDrafts = Array.isArray(data?.draft_items) ? data.draft_items : [];
    elements.statsToggle.hidden = false;
  } catch (err) {
    if (err?.status === 401 || err?.status === 403) {
      state.isAdmin = false;
      state.expiredAds = [];
      state.adminDrafts = [];
      elements.statsToggle.hidden = true;
      renderExpiredAdsList();
      return;
    }
    throw err;
  }
  renderExpiredAdsList();
}

async function deleteAdminDraft(id) {
  if (!id) return;
  return apiFetch(`/api/stats/drafts/${id}`, { method: "DELETE" });
}

async function refreshAds() {
  setBusy(true, t("busyLoading"));
  try {
    const data = await apiFetch("/api/announcements");
    state.ads = (data.items || []).slice();
    renderAds();
  } catch (err) {
    if (err?.status === 401) {
      return;
    }
    throw err;
  } finally {
    setBusy(false);
  }
}

async function saveAd() {
  const description = elements.description.value.trim();
  const priceInDescription = elements.priceInDescription.checked;
  const price = priceInDescription ? "" : elements.price.value.trim();
  const contactInfo = elements.contactInfo.value.trim();
  const isValid = validateAdForm({
    description,
    price,
    priceInDescription,
    contactInfo,
    requireContact: !state.hasUsername,
    descriptionInput: elements.description,
    priceInput: elements.price,
    contactInput: elements.contactInfo,
  });
  if (!isValid) {
    tg?.showAlert?.(t("required"));
    return;
  }

  const payload = {
    description,
    price,
    price_in_description: priceInDescription,
    contact_info: contactInfo,
    photo_file_ids: state.photoFileIds,
  };

  setBusy(true, t("busySaving"));
  try {
    if (state.editingId) {
      await apiFetch(`/api/announcements/${state.editingId}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
    } else {
      await apiFetch("/api/announcements", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    }

    resetForm();
    showTab("list");
    await refreshAds();
  } finally {
    setBusy(false);
  }
}

async function deleteAd(id) {
  setBusy(true, t("busyDeleting"));
  try {
    const result = await apiFetch(`/api/announcements/${id}`, { method: "DELETE" });
    await refreshAds();
    if (result?.warning) {
      const ids = Array.isArray(result.not_deleted_message_ids) ? result.not_deleted_message_ids : [];
      const detail = ids.length ? `message_ids: ${ids.join(", ")}` : "";
      const postLink = result.post_link || null;
      state.lastError = {
        action: "delete_ad_warning",
        ad_id: id,
        status: 200,
        message: result.warning,
        error_id: null,
        error_detail: detail,
        post_link: postLink,
        client_time: new Date().toISOString(),
        language: state.languageCode,
        user_agent: navigator.userAgent,
      };
      const modalDetail = [detail, postLink ? `post_link: ${postLink}` : ""].filter(Boolean).join("\n");
      openErrorModal(t("deletedWithWarning"), modalDetail);
    } else {
      showToast(t("deletedToast"), "danger");
    }
  } catch (err) {
    console.error(err);
    const errorId = err?.data?.error_id;
    const detail = err?.data?.error_detail;
    const message = errorId ? `${t("deleteFailed")} #${errorId}` : t("deleteFailed");
    state.lastError = {
      action: "delete_ad",
      ad_id: id,
      status: err?.status,
      message: err?.message || t("deleteFailed"),
      error_id: errorId,
      error_detail: detail,
      client_time: new Date().toISOString(),
      language: state.languageCode,
      user_agent: navigator.userAgent,
    };
    openErrorModal(message, detail || err?.message);
  } finally {
    setBusy(false);
  }
}

async function publishAd(id) {
  setBusy(true, t("busyPublishing"));
  try {
    await apiFetch(`/api/announcements/${id}/publish`, { method: "POST" });
    await refreshAds();
  } finally {
    setBusy(false);
  }
}

async function reportBug(payload) {
  return apiFetch("/api/bug-report", {
    method: "POST",
    body: JSON.stringify(payload || {}),
  });
}
