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
    throw new Error(text || `HTTP ${response.status}`);
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
    await apiFetch(`/api/announcements/${id}`, { method: "DELETE" });
    await refreshAds();
    showToast(t("deletedToast"), "danger");
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
