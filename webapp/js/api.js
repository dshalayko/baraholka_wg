async function apiFetch(path, options = {}) {
  const headers = options.headers || {};
  headers["Content-Type"] = headers["Content-Type"] || "application/json";
  headers["ngrok-skip-browser-warning"] = "1";
  if (tg?.initData) {
    headers["X-Telegram-Init-Data"] = tg.initData;
  }
  const response = await fetch(path, { ...options, headers });
  if (!response.ok) {
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
    throw error;
  }
  return response.json();
}

async function refreshAds() {
  setBusy(true, t("busyLoading"));
  try {
    const data = await apiFetch("/api/announcements");
    state.ads = (data.items || []).slice().sort((a, b) => (b.id || 0) - (a.id || 0));
    renderAds();
  } finally {
    setBusy(false);
  }
}

async function saveAd() {
  const description = elements.description.value.trim();
  const price = elements.price.value.trim();
  if (!description || !price) {
    tg?.showAlert?.(t("required"));
    return;
  }

  const payload = {
    description,
    price,
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
