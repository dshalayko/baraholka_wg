function closeSettingsMenu() {
  elements.settingsMenu.hidden = true;
}

function renderStatsSummary() {
  if (!elements.statsGrid) return;
  elements.statsGrid.innerHTML = "";
  const summary = state.statsSummary;
  if (!state.isAdmin || !summary) {
    return;
  }
  const counters = summary.counters || {};
  const totals = summary.totals || {};
  const items = [
    { label: t("statsAppOpen"), value: counters.app_open || 0 },
    { label: t("statsPublishSuccess"), value: counters.publish_success || 0 },
    { label: t("statsPublishFail"), value: counters.publish_fail || 0 },
    { label: t("statsOpenComments"), value: counters.open_comments || 0 },
    { label: t("statsApiErrors"), value: counters.api_errors || 0 },
    { label: t("statsAdsTotal"), value: totals.ads_total || 0 },
    { label: t("statsAdsPublished"), value: totals.ads_published || 0 },
  ];
  items.forEach((item) => {
    const card = document.createElement("div");
    card.className = "stats-card";

    const label = document.createElement("div");
    label.className = "stats-card-label";
    label.textContent = item.label;

    const value = document.createElement("div");
    value.className = "stats-card-value";
    value.textContent = String(item.value);

    card.append(label, value);
    elements.statsGrid.appendChild(card);
  });

  const adsListTitle = document.createElement("div");
  adsListTitle.className = "stats-list-title";
  adsListTitle.textContent = t("statsAdsList");
  elements.statsGrid.appendChild(adsListTitle);

  const ads = Array.isArray(summary.ads) ? summary.ads : [];
  if (!ads.length) {
    const empty = document.createElement("div");
    empty.className = "stats-ads-empty";
    empty.textContent = t("statsNoAds");
    elements.statsGrid.appendChild(empty);
    return;
  }

  ads.forEach((ad) => {
    const row = document.createElement("div");
    row.className = "stats-ad-row";

    const ownerValue = ad.username ? `@${ad.username}` : `id:${ad.user_id}`;
    const owner = document.createElement("div");
    owner.className = "stats-ad-owner";
    owner.textContent = `${t("statsOwner")}: ${ownerValue}`;

    const statusKey =
      ad.status === "draft" ? "statusDraft" : ad.status === "updated" ? "statusUpdated" : "statusPublished";
    const status = document.createElement("span");
    status.className = `stats-ad-status is-${ad.status}`;
    status.textContent = t(statusKey);

    const head = document.createElement("div");
    head.className = "stats-ad-head";
    head.append(owner, status);

    const desc = document.createElement("div");
    desc.className = "stats-ad-desc";
    desc.textContent = toShortDescription(ad.description || "");

    row.append(head, desc);
    elements.statsGrid.appendChild(row);
  });
}

function renderExpiredAdsList() {
  if (!elements.expiredAdsList) return;
  elements.expiredAdsList.innerHTML = "";
  const expiredItems = Array.isArray(state.expiredAds) ? state.expiredAds : [];
  const draftItems = Array.isArray(state.adminDrafts) ? state.adminDrafts : [];

  const expiredTitle = document.createElement("div");
  expiredTitle.className = "expired-section-title";
  expiredTitle.textContent = t("statsExpiredTitle");
  elements.expiredAdsList.appendChild(expiredTitle);

  if (!expiredItems.length) {
    const empty = document.createElement("div");
    empty.className = "expired-ads-empty";
    empty.textContent = t("statsExpiredEmpty");
    elements.expiredAdsList.appendChild(empty);
  }

  expiredItems.forEach((ad) => {
    const row = document.createElement("div");
    row.className = "expired-ad-row";

    const top = document.createElement("div");
    top.className = "expired-ad-top";

    const owner = document.createElement("div");
    owner.className = "expired-ad-owner";
    const ownerValue = ad.username ? `@${ad.username}` : `id:${ad.user_id}`;
    owner.textContent = `${t("statsOwner")}: ${ownerValue}`;

    const age = document.createElement("span");
    age.className = "expired-ad-age";
    age.textContent = `${t("statsAgeDays")}: ${Number(ad.age_days) || 0}`;
    top.append(owner, age);

    const desc = document.createElement("div");
    desc.className = "expired-ad-desc";
    desc.textContent = toShortDescription(ad.description || "");

    const date = document.createElement("div");
    date.className = "expired-ad-date";
    date.textContent = `${t("statsPublishedDate")}: ${formatPublishedAt(ad.published_at)}`;

    row.append(top, desc, date);

    if (ad.post_link) {
      const openBtn = document.createElement("button");
      openBtn.type = "button";
      openBtn.className = "ghost expired-ad-open";
      openBtn.textContent = t("open");
      openBtn.setAttribute("data-expired-link", ad.post_link);
      row.appendChild(openBtn);
    }

    elements.expiredAdsList.appendChild(row);
  });

  const draftsTitle = document.createElement("div");
  draftsTitle.className = "expired-section-title";
  draftsTitle.textContent = t("statsDraftsTitle");
  elements.expiredAdsList.appendChild(draftsTitle);

  if (!draftItems.length) {
    const empty = document.createElement("div");
    empty.className = "expired-ads-empty";
    empty.textContent = t("statsDraftsEmpty");
    elements.expiredAdsList.appendChild(empty);
    return;
  }

  draftItems.forEach((ad) => {
    const row = document.createElement("div");
    row.className = "draft-ad-row";

    const top = document.createElement("div");
    top.className = "expired-ad-top";

    const owner = document.createElement("div");
    owner.className = "expired-ad-owner";
    const ownerValue = ad.username ? `@${ad.username}` : `id:${ad.user_id}`;
    owner.textContent = `${t("statsOwner")}: ${ownerValue}`;
    top.appendChild(owner);

    const desc = document.createElement("div");
    desc.className = "expired-ad-desc";
    desc.textContent = toShortDescription(ad.description || "");

    const updated = document.createElement("div");
    updated.className = "expired-ad-date";
    updated.textContent = `${t("editedAt")}: ${formatPublishedAt(ad.updated_at)}`;

    const actions = document.createElement("div");
    actions.className = "expired-draft-actions";

    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "danger expired-ad-delete";
    deleteBtn.textContent = t("delete");
    deleteBtn.setAttribute("data-draft-delete-id", String(ad.id));
    actions.appendChild(deleteBtn);

    row.append(top, desc, updated, actions);
    elements.expiredAdsList.appendChild(row);
  });
}

function toggleSettingsMenu() {
  elements.settingsMenu.hidden = !elements.settingsMenu.hidden;
}

function setLanguage(languageCode) {
  if (!languageCode) return;
  state.languageCode = languageCode;
  localStorage.setItem("language", languageCode);
  applyTranslations();
  renderAds();
}

function syncSettingsOptions() {
  const isDark = isDarkTheme();
  const isRu = state.languageCode?.startsWith("ru");
  elements.themeDarkBtn.classList.toggle("active", isDark);
  elements.themeLightBtn.classList.toggle("active", !isDark);
  elements.languageRuBtn.classList.toggle("active", isRu);
  elements.languageEnBtn.classList.toggle("active", !isRu);
}

function setToolButton(button, marker, label, tagName = "span") {
  button.title = label;
  button.setAttribute("aria-label", label);
  button.textContent = "";

  const markerNode = document.createElement(tagName);
  markerNode.className = "tool-btn-marker";
  markerNode.textContent = marker;

  const labelNode = document.createElement("span");
  labelNode.className = "tool-btn-label";
  labelNode.textContent = label;

  button.appendChild(markerNode);
  button.appendChild(labelNode);
}

function applyFormatToolLabels(buttons) {
  setToolButton(buttons.bold, "B", t("formatBold"), "strong");
  setToolButton(buttons.italic, "I", t("formatItalic"), "em");
  setToolButton(buttons.underline, "U", t("formatUnderline"), "u");
  setToolButton(buttons.strike, "S", t("formatStrike"), "s");
  setToolButton(buttons.quote, ">", t("formatQuote"));
  setToolButton(buttons.mono, "{ }", t("formatMono"), "code");
  setToolButton(buttons.spoiler, "SP", t("formatSpoiler"));
}

function applyTranslations() {
  document.documentElement.lang = state.languageCode?.startsWith("ru") ? "ru" : "en";
  elements.appTitleText.textContent = t("appTitle");
  elements.appBadgeText.textContent = t("beta");
  elements.tabMyAds.textContent = t("myAds");
  elements.tabCreate.textContent = t("create");
  elements.settingsToggle.setAttribute("aria-label", t("settings"));
  elements.statsToggle.setAttribute("aria-label", t("stats"));
  elements.commentsToggle.setAttribute("aria-label", t("comments"));
  elements.feedbackToggle.setAttribute("aria-label", t("feedback"));
  elements.settingsThemeLabel.textContent = t("settingsTheme");
  elements.settingsLanguageLabel.textContent = t("settingsLanguage");
  elements.themeLightBtn.textContent = t("themeLight");
  elements.themeDarkBtn.textContent = t("themeDark");
  elements.languageRuBtn.textContent = t("languageRu");
  elements.languageEnBtn.textContent = t("languageEn");
  elements.cancelFormBtn.textContent = t("cancel");
  elements.descLabel.textContent = t("description");
  applyFormatToolLabels({
    bold: elements.descBoldBtn,
    italic: elements.descItalicBtn,
    underline: elements.descUnderlineBtn,
    strike: elements.descStrikeBtn,
    quote: elements.descQuoteBtn,
    mono: elements.descMonoBtn,
    spoiler: elements.descSpoilerBtn,
  });
  elements.contactLabel.textContent = t("contactLabel");
  elements.priceLabel.textContent = t("price");
  elements.priceInDescriptionLabel.textContent = t("priceInDescriptionLabel");
  elements.priceInDescriptionYesLabel.textContent = t("priceToggleYes");
  elements.priceInDescriptionNoLabel.textContent = t("priceToggleNo");
  elements.photosLabel.textContent = t("photos");
  elements.emptyState.textContent = t("noAds");
  elements.description.placeholder = t("descPlaceholder");
  elements.price.placeholder = t("pricePlaceholder");
  elements.saveAdBtn.textContent = t("saveDraft");
  elements.publishBtn.textContent = t("publishNow");
  elements.addMorePhotosBtn.textContent = t("addMore");
  elements.editModalTitle.textContent = t("editTitle");
  elements.editDescLabel.textContent = t("description");
  applyFormatToolLabels({
    bold: elements.editDescBoldBtn,
    italic: elements.editDescItalicBtn,
    underline: elements.editDescUnderlineBtn,
    strike: elements.editDescStrikeBtn,
    quote: elements.editDescQuoteBtn,
    mono: elements.editDescMonoBtn,
    spoiler: elements.editDescSpoilerBtn,
  });
  elements.editContactLabel.textContent = t("contactLabel");
  elements.editPriceLabel.textContent = t("price");
  elements.editPriceInDescriptionLabel.textContent = t("priceInDescriptionLabel");
  elements.editPriceInDescriptionYesLabel.textContent = t("priceToggleYes");
  elements.editPriceInDescriptionNoLabel.textContent = t("priceToggleNo");
  elements.editPhotosLabel.textContent = t("photos");
  elements.editDescription.placeholder = t("descPlaceholder");
  elements.editPrice.placeholder = t("pricePlaceholder");
  elements.contactInfo.placeholder = t("contactPlaceholder");
  elements.editContactInfo.placeholder = t("contactPlaceholder");
  elements.editAddMorePhotosBtn.textContent = t("addMore");
  elements.editCancelBtn.textContent = t("editCancel");
  elements.editPublishBtn.textContent = t("editPublish");
  elements.confirmTitle.textContent = t("confirmTitle");
  elements.confirmText.textContent = t("deleteConfirm");
  elements.confirmYesBtn.textContent = t("confirmYes");
  elements.confirmNoBtn.textContent = t("confirmNo");
  elements.errorTitle.textContent = t("errorTitle");
  elements.errorCloseBtn.textContent = t("errorClose");
  elements.errorReportBtn.textContent = t("reportError");
  elements.commentsOverviewTitle.textContent = t("commentsOverviewTitle");
  elements.commentsOverviewCloseBtn.textContent = t("close");
  elements.statsTitle.textContent = t("stats");
  elements.statsExpiredBtn.textContent = t("statsExpiredBtn");
  elements.statsCloseBtn.textContent = t("close");
  elements.expiredAdsTitle.textContent = t("statsExpiredTitle");
  elements.expiredAdsCloseBtn.textContent = t("close");
  elements.feedbackTitle.textContent = t("feedbackTitle");
  elements.feedbackLabel.textContent = t("feedbackLabel");
  elements.feedbackInput.placeholder = t("feedbackPlaceholder");
  elements.feedbackCancelBtn.textContent = t("cancel");
  elements.feedbackSendBtn.textContent = t("feedbackSend");
  elements.unauthorizedTitle.textContent = t("unauthorizedTitle");
  elements.unauthorizedText.textContent = t("unauthorizedText");
  renderCommentsOverview();
  renderStatsSummary();
  renderExpiredAdsList();
  syncSettingsOptions();
}

function bindEvents() {
  elements.tabMyAds.addEventListener("click", () => {
    showTab("list");
  });

  elements.tabCreate.addEventListener("click", () => {
    resetForm();
    showTab("form");
  });

  elements.cancelFormBtn.addEventListener("click", () => {
    resetForm();
    showTab("list");
  });

  elements.saveAdBtn.addEventListener("click", saveAd);
  elements.publishBtn.addEventListener("click", async () => {
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
    setBusy(true, t("busyPublishing"));
    try {
      if (!state.editingId) {
        const created = await apiFetch("/api/announcements", {
          method: "POST",
          body: JSON.stringify({
            description,
            price,
            price_in_description: priceInDescription,
            contact_info: contactInfo,
            photo_file_ids: state.photoFileIds,
          }),
        });
        if (created && created.id) {
          await publishAd(created.id);
          showToast(t("publishedToast"), "success");
        }
      } else {
        await apiFetch(`/api/announcements/${state.editingId}`, {
          method: "PUT",
          body: JSON.stringify({
            description,
            price,
            price_in_description: priceInDescription,
            contact_info: contactInfo,
            photo_file_ids: state.photoFileIds,
          }),
        });
        await publishAd(state.editingId);
        showToast(t("publishedToast"), "success");
      }
      await refreshAds();
      showTab("list");
    } finally {
      setBusy(false);
    }
  });
  elements.description.addEventListener("input", () => {
    updateCounts();
    autoResizeDescription();
    setFieldInvalid(elements.description, false);
  });
  elements.contactInfo.addEventListener("input", () => {
    setFieldInvalid(elements.contactInfo, false);
  });
  elements.price.addEventListener("input", () => {
    updateCounts();
    setFieldInvalid(elements.price, false);
  });
  elements.priceInDescription.addEventListener("change", () => {
    applyPriceInDescriptionToggle(elements.priceInDescription, elements.price, elements.priceField);
    updateCounts();
  });
  elements.addMorePhotosBtn.addEventListener("click", (event) => {
    event.preventDefault();
    elements.photos.click();
  });
  elements.photos.addEventListener("change", handlePhotoInput);
  elements.descBoldBtn.addEventListener("click", () => wrapSelection(elements.description, "**"));
  elements.descItalicBtn.addEventListener("click", () => wrapSelection(elements.description, "_"));
  elements.descUnderlineBtn.addEventListener("click", () => wrapSelection(elements.description, "__"));
  elements.descStrikeBtn.addEventListener("click", () => wrapSelection(elements.description, "~~"));
  elements.descQuoteBtn.addEventListener("click", () => prefixSelectionLines(elements.description, "> "));
  elements.descMonoBtn.addEventListener("click", () => wrapSelection(elements.description, "`"));
  elements.descSpoilerBtn.addEventListener("click", () => wrapSelection(elements.description, "||"));
  elements.settingsToggle.addEventListener("click", (event) => {
    event.stopPropagation();
    toggleSettingsMenu();
  });
  elements.statsToggle.addEventListener("click", async (event) => {
    event.stopPropagation();
    closeSettingsMenu();
    await refreshAdminStats();
    if (!state.isAdmin) return;
    openStatsModal();
  });
  elements.statsExpiredBtn.addEventListener("click", async () => {
    setBusy(true, t("busyLoading"));
    try {
      await refreshAdminExpiredAds();
      openExpiredAdsModal();
    } finally {
      setBusy(false);
    }
  });
  elements.commentsToggle.addEventListener("click", (event) => {
    event.stopPropagation();
    closeSettingsMenu();
    openCommentsOverviewModal();
  });
  elements.feedbackToggle.addEventListener("click", (event) => {
    event.stopPropagation();
    closeSettingsMenu();
    openFeedbackModal();
  });
  elements.settingsMenu.addEventListener("click", (event) => {
    event.stopPropagation();
  });
  elements.themeLightBtn.addEventListener("click", () => {
    setTheme("light");
    closeSettingsMenu();
  });
  elements.themeDarkBtn.addEventListener("click", () => {
    setTheme("dark");
    closeSettingsMenu();
  });
  elements.languageRuBtn.addEventListener("click", () => {
    setLanguage("ru");
    closeSettingsMenu();
  });
  elements.languageEnBtn.addEventListener("click", () => {
    setLanguage("en");
    closeSettingsMenu();
  });
  document.addEventListener("click", () => {
    closeSettingsMenu();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeSettingsMenu();
    }
  });
  elements.editAddMorePhotosBtn.addEventListener("click", (event) => {
    event.preventDefault();
    elements.editPhotos.click();
  });
  elements.editDescription.addEventListener("input", () => {
    autoResizeTextarea(elements.editDescription);
    setFieldInvalid(elements.editDescription, false);
  });
  elements.editDescBoldBtn.addEventListener("click", () => wrapSelection(elements.editDescription, "**"));
  elements.editDescItalicBtn.addEventListener("click", () => wrapSelection(elements.editDescription, "_"));
  elements.editDescUnderlineBtn.addEventListener("click", () => wrapSelection(elements.editDescription, "__"));
  elements.editDescStrikeBtn.addEventListener("click", () => wrapSelection(elements.editDescription, "~~"));
  elements.editDescQuoteBtn.addEventListener("click", () => prefixSelectionLines(elements.editDescription, "> "));
  elements.editDescMonoBtn.addEventListener("click", () => wrapSelection(elements.editDescription, "`"));
  elements.editDescSpoilerBtn.addEventListener("click", () => wrapSelection(elements.editDescription, "||"));
  elements.editContactInfo.addEventListener("input", () => {
    setFieldInvalid(elements.editContactInfo, false);
  });
  elements.editPrice.addEventListener("input", () => {
    setFieldInvalid(elements.editPrice, false);
  });
  elements.editPriceInDescription.addEventListener("change", () => {
    applyPriceInDescriptionToggle(elements.editPriceInDescription, elements.editPrice, elements.editPriceField);
  });
  elements.editPhotos.addEventListener("change", () => {
    const files = Array.from(elements.editPhotos.files || []);
    elements.editPhotos.value = "";
    if (!files.length) return;
    const hasExisting = state.editModal.photoFileIds.length > 0;
    const uploader = hasExisting ? appendEditPhotos : uploadEditPhotos;
    uploader(files)
      .then((fileIds) => {
        if (!hasExisting) {
          state.editModal.photoFileIds = fileIds;
        }
        state.editModal.photoPreviews = state.editModal.photoPreviews.map((item, idx) => ({
          ...item,
          label: `#${idx + 1}`,
        }));
        renderEditPhotoPreviews();
      })
      .catch((err) => {
        console.error(err);
        tg?.showAlert?.(err.message || t("uploadFailed"));
        setEditUploading(false);
      });
  });
  elements.editCancelBtn.addEventListener("click", () => {
    closeEditModal();
    showToast(t("editCanceled"));
  });
  elements.editModal.addEventListener("click", (event) => {
    if (event.target === elements.editModal) {
      closeEditModal();
      showToast(t("editCanceled"));
    }
  });
  elements.editPublishBtn.addEventListener("click", async () => {
    const description = elements.editDescription.value.trim();
    const priceInDescription = elements.editPriceInDescription.checked;
    const price = priceInDescription ? "" : elements.editPrice.value.trim();
    const contactInfo = elements.editContactInfo.value.trim();
    const isValid = validateAdForm({
      description,
      price,
      priceInDescription,
      contactInfo,
      requireContact: !state.hasUsername,
      descriptionInput: elements.editDescription,
      priceInput: elements.editPrice,
      contactInput: elements.editContactInfo,
    });
    if (!isValid) {
      tg?.showAlert?.(t("required"));
      return;
    }
    if (!state.editModal.id) {
      closeEditModal();
      return;
    }
    setBusy(true, t("busyPublishing"));
    try {
      await apiFetch(`/api/announcements/${state.editModal.id}`, {
        method: "PUT",
        body: JSON.stringify({
          description,
          price,
          price_in_description: priceInDescription,
          contact_info: contactInfo,
          photo_file_ids: state.editModal.photoFileIds,
        }),
      });
      await publishAd(state.editModal.id);
      closeEditModal();
      showToast(t("editedPublished"), "success");
    } finally {
      setBusy(false);
    }
  });
  elements.confirmNoBtn.addEventListener("click", closeDeleteConfirm);
  elements.confirmModal.addEventListener("click", (event) => {
    if (event.target === elements.confirmModal) {
      closeDeleteConfirm();
    }
  });
  elements.errorCloseBtn.addEventListener("click", closeErrorModal);
  elements.errorModal.addEventListener("click", (event) => {
    if (event.target === elements.errorModal) {
      closeErrorModal();
    }
  });
  elements.photoViewerCloseBtn.addEventListener("click", closePhotoViewer);
  elements.commentsOverviewCloseBtn.addEventListener("click", closeCommentsOverviewModal);
  elements.commentsOverviewModal.addEventListener("click", (event) => {
    if (event.target === elements.commentsOverviewModal) {
      closeCommentsOverviewModal();
    }
  });
  elements.commentsOverviewList.addEventListener("click", (event) => {
    const viewBtn = event.target.closest("button[data-comments-link]");
    if (!viewBtn) return;
    const link = viewBtn.getAttribute("data-comments-link");
    if (!link) return;
    closeCommentsOverviewModal();
    void trackEvent("open_comments");
    tg?.openTelegramLink?.(link);
  });
  elements.statsCloseBtn.addEventListener("click", closeStatsModal);
  elements.statsModal.addEventListener("click", (event) => {
    if (event.target === elements.statsModal) {
      closeStatsModal();
    }
  });
  elements.expiredAdsCloseBtn.addEventListener("click", closeExpiredAdsModal);
  elements.expiredAdsModal.addEventListener("click", (event) => {
    if (event.target === elements.expiredAdsModal) {
      closeExpiredAdsModal();
    }
  });
  elements.expiredAdsList.addEventListener("click", (event) => {
    const deleteBtn = event.target.closest("button[data-draft-delete-id]");
    if (deleteBtn) {
      const idRaw = deleteBtn.getAttribute("data-draft-delete-id");
      const draftId = Number(idRaw);
      if (!Number.isFinite(draftId) || draftId <= 0) return;
      if (!window.confirm(t("statsDeleteDraftConfirm"))) return;
      setBusy(true, t("busyDeleting"));
      deleteAdminDraft(draftId)
        .then(async () => {
          showToast(t("statsDraftDeleted"), "success");
          await refreshAdminStats();
          await refreshAdminExpiredAds();
        })
        .catch((err) => {
          console.error(err);
          showToast(err?.message || t("deleteFailed"), "danger");
        })
        .finally(() => {
          setBusy(false);
        });
      return;
    }

    const openBtn = event.target.closest("button[data-expired-link]");
    if (!openBtn) return;
    const link = openBtn.getAttribute("data-expired-link");
    if (!link) return;
    tg?.openTelegramLink?.(link);
  });
  elements.feedbackCancelBtn.addEventListener("click", closeFeedbackModal);
  elements.feedbackModal.addEventListener("click", (event) => {
    if (event.target === elements.feedbackModal) {
      closeFeedbackModal();
    }
  });
  elements.feedbackSendBtn.addEventListener("click", async () => {
    const message = (elements.feedbackInput.value || "").trim();
    if (!message) {
      tg?.showAlert?.(t("feedbackEmpty"));
      return;
    }
    setBusy(true, t("busySaving"));
    try {
      await reportBug({
        action: "feedback",
        status: "info",
        message,
        client_time: new Date().toISOString(),
        language: state.languageCode,
        user_agent: navigator.userAgent,
      });
      closeFeedbackModal();
      showToast(t("feedbackSent"), "success");
    } catch (err) {
      console.error(err);
      showToast(t("reportFailed"), "danger");
    } finally {
      setBusy(false);
    }
  });
  elements.errorReportBtn.addEventListener("click", async () => {
    if (!state.lastError) {
      closeErrorModal();
      return;
    }
    setBusy(true, t("busySaving"));
    try {
      await reportBug(state.lastError);
      showToast(t("reportSent"), "success");
      state.lastError = null;
      closeErrorModal();
    } catch (err) {
      console.error(err);
      showToast(t("reportFailed"), "danger");
    } finally {
      setBusy(false);
    }
  });
  elements.confirmYesBtn.addEventListener("click", async () => {
    if (!state.pendingDeleteId) {
      closeDeleteConfirm();
      return;
    }
    const id = state.pendingDeleteId;
    closeDeleteConfirm();
    await deleteAd(id);
  });
}

applyTranslations();
applyContactFieldVisibility();
bindEvents();
updateCounts();
showTab("list");
refreshAds();
refreshAdminStats();
if (!state.sentAppOpenEvent) {
  state.sentAppOpenEvent = true;
  void trackEvent("app_open");
}
initTheme();
closeDeleteConfirm();
closeEditModal();
closeErrorModal();
closePhotoViewer();
closeCommentsOverviewModal();
closeStatsModal();
closeExpiredAdsModal();
closeFeedbackModal();
