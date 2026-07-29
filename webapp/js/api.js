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
  const { noUnauthorizedMode, ...fetchOptions } = options;
  const response = await fetch(path, { ...fetchOptions, headers });
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
    if (response.status === 401 && !noUnauthorizedMode) {
      setUnauthorizedMode(true);
    }
    throw error;
  }
  if (state.unauthorized) {
    setUnauthorizedMode(false);
  }
  return response.json();
}

// Photo endpoints require auth, and the initData credential must travel in a
// header — never in the URL, where server access logs would capture it. So
// images are fetched manually and shown via object URLs, cached per URL to
// avoid re-downloading on re-renders (the bid screen re-renders every 6s).
const authedImagePromises = new Map();

function resolveAuthedImageUrl(url) {
  if (!url || !url.startsWith("/api/")) return Promise.resolve(url);
  if (!authedImagePromises.has(url)) {
    const promise = (async () => {
      const headers = { "ngrok-skip-browser-warning": "1" };
      const initData = await waitTelegramInitData();
      if (initData) {
        headers["X-Telegram-Init-Data"] = initData;
      }
      const response = await fetch(url, { headers });
      if (!response.ok) {
        throw new Error(`Photo load failed: HTTP ${response.status}`);
      }
      return URL.createObjectURL(await response.blob());
    })();
    promise.catch(() => authedImagePromises.delete(url));
    authedImagePromises.set(url, promise);
  }
  return authedImagePromises.get(url);
}

function setAuthedImage(img, url) {
  // Shimmer placeholder while the bytes are fetched, so cards keep their
  // shape instead of jumping when the image arrives.
  img.classList.add("photo-loading");
  resolveAuthedImageUrl(url)
    .then((objectUrl) => {
      img.src = objectUrl;
      return img.decode ? img.decode().catch(() => {}) : null;
    })
    .catch(() => {})
    .finally(() => img.classList.remove("photo-loading"));
}

function openAuthedPhotoViewer(url) {
  resolveAuthedImageUrl(url)
    .then((objectUrl) => openPhotoViewer(objectUrl))
    .catch(() => {});
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

async function refreshAppVersion() {
  if (!elements.appVersion) return;
  try {
    // noUnauthorizedMode: a missing version must never flip the whole app into
    // the "unauthorized" screen — it is a footnote, not a feature.
    const data = await apiFetch("/api/version", { noUnauthorizedMode: true });
    elements.appVersion.textContent = String(data?.version || "").trim();
  } catch (err) {
    // ignore: the line just stays empty
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
    if (err?.status === 401) return;
    if (!state.ads.length) {
      showToast(t("loadFailed"), "danger");
    }
    void silentBugReport({ action: "refresh_ads", status: err?.status, message: err?.message });
  } finally {
    setBusy(false);
  }
}

async function saveAd() {
  const isAuction = state.adType === "auction";
  const description = elements.description.value.trim();
  const contactInfo = elements.contactInfo.value.trim();

  let payload;
  if (isAuction) {
    const descValid = validateAdForm({
      description,
      price: "",
      priceInDescription: true,
      contactInfo,
      requireContact: !state.hasUsername,
      descriptionInput: elements.description,
      priceInput: elements.price,
      contactInput: elements.contactInfo,
    });
    if (!descValid) {
      tg?.showAlert?.(t("required"));
      return;
    }
    payload = {
      description,
      price: "",
      price_in_description: false,
      contact_info: contactInfo,
      photo_file_ids: state.photoFileIds,
      ad_type: "auction",
      start_price: parseInt(elements.auctionStartPrice?.value, 10) || null,
      min_step: parseInt(elements.auctionMinStep?.value, 10) || null,
      auction_duration_hours: parseInt(elements.auctionDuration?.value, 10) || 24,
      currency: state.auctionCurrency,
    };
  } else {
    const priceInDescription = elements.priceInDescription.checked;
    const price = priceInDescription ? "" : elements.price.value.trim();
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
    payload = {
      description,
      price,
      price_in_description: priceInDescription,
      contact_info: contactInfo,
      photo_file_ids: state.photoFileIds,
      ad_type: "fixed",
    };
  }

  setBusy(true, t("busySaving"));
  let saved = false;
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
    saved = true;
  } catch (err) {
    const errorId = err?.data?.error_id;
    const detail = err?.data?.error_detail;
    const message = errorId ? `${t("saveFailed")} #${errorId}` : t("saveFailed");
    state.lastError = {
      action: "save_ad",
      ad_id: state.editingId || null,
      status: err?.status,
      message: err?.message || t("saveFailed"),
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
  if (!saved) return;
  resetForm();
  showTab("list");
  await refreshAds();
}

async function deleteAd(id) {
  setBusy(true, t("busyDeleting"));
  try {
    const result = await apiFetch(`/api/announcements/${id}`, { method: "DELETE" });
    await refreshAds();
    if (result?.warning) {
      const ids = Array.isArray(result.not_deleted_message_ids) ? result.not_deleted_message_ids : [];
      const postLink = result.post_link || null;
      void silentBugReport({
        action: "delete_ad_warning",
        ad_id: id,
        status: 200,
        message: result.warning,
        error_detail: [ids.length ? `message_ids: ${ids.join(", ")}` : "", postLink ? `post_link: ${postLink}` : ""].filter(Boolean).join("\n"),
      });
    }
    showToast(t("deletedToast"), "danger");
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
    showToast(t("publishedToast"), "success");
    await refreshAds();
  } catch (err) {
    const errorId = err?.data?.error_id;
    const detail = err?.data?.error_detail;
    const message = errorId ? `${t("publishFailed")} #${errorId}` : t("publishFailed");
    state.lastError = {
      action: "publish_ad",
      ad_id: id,
      status: err?.status,
      message: err?.message || t("publishFailed"),
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

async function reserveAd(id, isReserved = false) {
  setBusy(true, t("busyReserving"));
  try {
    await apiFetch(`/api/announcements/${id}/reserve`, { method: "POST" });
    await refreshAds();
    showToast(t(isReserved ? "unreservedToast" : "reservedToast"), "success");
  } catch (err) {
    console.error(err);
    const errorId = err?.data?.error_id;
    const detail = err?.data?.error_detail;
    const postLink = err?.data?.post_link || null;
    const message = errorId ? `${t("reserveFailed")} #${errorId}` : t("reserveFailed");
    state.lastError = {
      action: "reserve_ad",
      ad_id: id,
      status: err?.status,
      message: err?.message || t("reserveFailed"),
      error_id: errorId,
      error_detail: detail,
      post_link: postLink,
      client_time: new Date().toISOString(),
      language: state.languageCode,
      user_agent: navigator.userAgent,
    };
    const modalDetail = [detail || err?.message, postLink ? `post_link: ${postLink}` : ""].filter(Boolean).join("\n");
    openErrorModal(message, modalDetail);
  } finally {
    setBusy(false);
  }
}

async function getAuctionInfo(annId) {
  return apiFetch(`/api/auctions/${annId}`);
}

async function getAuctionBids(annId) {
  return apiFetch(`/api/auctions/${annId}/bids`);
}

async function stopAuction(annId) {
  return apiFetch(`/api/auctions/${annId}/stop`, { method: "POST" });
}

async function editAuctionInPlace(annId, payload) {
  return apiFetch(`/api/auctions/${annId}/edit`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

async function buyoutAuction(annId) {
  return apiFetch(`/api/auctions/${annId}/buyout`, {
    method: "POST",
    noUnauthorizedMode: true,
  });
}

async function placeBid(annId, amount) {
  return apiFetch(`/api/auctions/${annId}/bid`, {
    method: "POST",
    body: JSON.stringify({ amount }),
    noUnauthorizedMode: true,
  });
}

async function reportBug(payload) {
  return apiFetch("/api/bug-report", {
    method: "POST",
    body: JSON.stringify(payload || {}),
  });
}

async function silentBugReport(payload) {
  try {
    await reportBug({
      ...payload,
      client_time: new Date().toISOString(),
      language: state.languageCode,
      user_agent: navigator.userAgent,
    });
  } catch (_) {
    // ignore — silent report, never surface to user
  }
}
