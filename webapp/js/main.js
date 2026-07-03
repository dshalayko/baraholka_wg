function closeSettingsMenu() {
  if (elements.settingsMenu) elements.settingsMenu.hidden = true;
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
  if (elements.settingsMenu) elements.settingsMenu.hidden = !elements.settingsMenu.hidden;
}

function setLanguage(languageCode) {
  if (!languageCode) return;
  state.languageCode = languageCode;
  localStorage.setItem("language", languageCode);
  applyTranslations();
  renderAds();
}

// "Auto" language: drop the saved choice and follow Telegram's language.
function setLanguageAuto() {
  localStorage.removeItem("language");
  state.languageCode = tg?.initDataUnsafe?.user?.language_code || "ru";
  applyTranslations();
  renderAds();
}

function syncSettingsOptions() {
  const savedTheme = localStorage.getItem("theme");
  elements.themeAutoBtn?.classList.toggle("active", savedTheme !== "light" && savedTheme !== "dark");
  elements.themeLightBtn.classList.toggle("active", savedTheme === "light");
  elements.themeDarkBtn.classList.toggle("active", savedTheme === "dark");

  const savedLang = localStorage.getItem("language");
  elements.languageAutoBtn?.classList.toggle("active", !savedLang);
  elements.languageRuBtn.classList.toggle("active", !!savedLang && savedLang.startsWith("ru"));
  elements.languageEnBtn.classList.toggle("active", !!savedLang && !savedLang.startsWith("ru"));
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
  if (elements.appTitleText) elements.appTitleText.textContent = t("appTitle");
  if (elements.tabMyAdsText) elements.tabMyAdsText.textContent = t("myAds");
  if (elements.tabCreateText) elements.tabCreateText.textContent = t("create");
  if (elements.tabSettingsText) elements.tabSettingsText.textContent = t("settings");
  if (elements.settingsToggle) elements.settingsToggle.setAttribute("aria-label", t("settings"));
  elements.statsToggle.setAttribute("aria-label", t("stats"));
  if (elements.statsMenuText) elements.statsMenuText.textContent = t("stats");
  elements.commentsToggle.setAttribute("aria-label", t("comments"));
  if (elements.commentsMenuText) elements.commentsMenuText.textContent = t("comments");
  elements.feedbackToggle.setAttribute("aria-label", t("feedback"));
  if (elements.feedbackMenuText) elements.feedbackMenuText.textContent = t("feedback");
  elements.settingsThemeLabel.textContent = t("settingsTheme");
  elements.settingsLanguageLabel.textContent = t("settingsLanguage");
  if (elements.themeAutoBtn) elements.themeAutoBtn.textContent = t("themeAuto");
  elements.themeLightBtn.textContent = t("themeLight");
  elements.themeDarkBtn.textContent = t("themeDark");
  if (elements.languageAutoBtn) elements.languageAutoBtn.textContent = t("languageAuto");
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
  if (elements.emptyStateText) elements.emptyStateText.textContent = t("noAds");
  if (elements.emptyStateBtn) elements.emptyStateBtn.textContent = t("createFirstAd");
  elements.description.placeholder = t("descPlaceholder");
  elements.price.placeholder = t("pricePlaceholder");
  elements.saveAdBtn.textContent = t("saveDraft");
  elements.publishBtn.textContent = t("publishNow");
  elements.addMorePhotosBtn.textContent = t("addMore");
  if (elements.photoUploadText) elements.photoUploadText.textContent = t("addMore");
  if (elements.photoUploadHint) elements.photoUploadHint.textContent = t("photoHint");
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
  if (elements.editPhotoUploadText) elements.editPhotoUploadText.textContent = t("addMore");
  if (elements.editPhotoUploadHint) elements.editPhotoUploadHint.textContent = t("photoHint");
  elements.editCancelBtn.textContent = t("editCancel");
  elements.editPublishBtn.textContent = t("editPublish");
  elements.confirmTitle.textContent = t("confirmTitle");
  elements.confirmText.textContent = t("deleteConfirm");
  elements.confirmYesBtn.textContent = t("confirmYes");
  elements.confirmNoBtn.textContent = t("confirmNo");
  elements.discardConfirmTitle.textContent = t("discardConfirmTitle");
  elements.discardConfirmText.textContent = t("discardConfirmText");
  elements.discardConfirmLeaveBtn.textContent = t("discardConfirmLeave");
  elements.discardConfirmStayBtn.textContent = t("discardConfirmStay");
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
  if (elements.adTypeSectionTitle) elements.adTypeSectionTitle.textContent = t("adTypeSectionTitle");
  if (elements.adTypeFixedBtn) elements.adTypeFixedBtn.textContent = t("adTypeFixed");
  if (elements.adTypeAuctionBtn) elements.adTypeAuctionBtn.textContent = t("adTypeAuction");
  if (elements.auctionSectionTitle) elements.auctionSectionTitle.textContent = t("auctionParams");
  if (elements.auctionStartPriceLabel) elements.auctionStartPriceLabel.textContent = t("auctionStartPrice");
  if (elements.auctionMinStepLabel) elements.auctionMinStepLabel.textContent = t("auctionMinStep");
  if (elements.auctionDurationLabel) elements.auctionDurationLabel.textContent = t("auctionDuration");
  if (elements.auctionCurrencyLabel) elements.auctionCurrencyLabel.textContent = t("auctionCurrency");
  if (elements.auctionStartPrice) elements.auctionStartPrice.placeholder = t("auctionStartPricePlaceholder");
  if (elements.auctionMinStep) elements.auctionMinStep.placeholder = t("auctionMinStepPlaceholder");
  if (elements.auctionBuyoutLabel) elements.auctionBuyoutLabel.textContent = t("auctionBuyoutPrice");
  if (elements.auctionBuyout) elements.auctionBuyout.placeholder = t("auctionBuyoutPlaceholder");
  if (elements.auctionDuration) {
    const durationOptions = elements.auctionDuration.options;
    const durationKeys = ["duration1h", "duration3h", "duration6h", "duration12h", "duration24h", "duration48h"];
    for (let i = 0; i < durationOptions.length && i < durationKeys.length; i++) {
      durationOptions[i].textContent = t(durationKeys[i]);
    }
  }
  if (elements.bidScreenHeaderTitle) elements.bidScreenHeaderTitle.textContent = t("bidScreenTitle");
  if (elements.bidAmountLabel) elements.bidAmountLabel.textContent = t("bidAmountLabel");
  if (elements.bidAmount) elements.bidAmount.placeholder = t("bidAmountPlaceholder");
  if (elements.bidSubmitText) elements.bidSubmitText.textContent = t("bidSubmit");
  if (elements.bidBackToPostText) elements.bidBackToPostText.textContent = t("bidBackToPost");
  if (elements.bidsScreenHeaderTitle) elements.bidsScreenHeaderTitle.textContent = t("bidsScreenTitle");
  renderCommentsOverview();
  renderStatsSummary();
  renderExpiredAdsList();
  syncSettingsOptions();
}

function bindEvents() {
  elements.tabMyAds.addEventListener("click", () => {
    confirmLeaveForm(() => showTab("list"));
  });

  elements.tabCreate.addEventListener("click", () => {
    confirmLeaveForm(() => {
      resetForm();
      showTab("form");
    });
  });

  elements.tabSettings?.addEventListener("click", () => {
    confirmLeaveForm(() => showTab("settings"));
  });

  elements.emptyStateBtn?.addEventListener("click", () => {
    resetForm();
    showTab("form");
  });

  elements.cancelFormBtn.addEventListener("click", () => {
    confirmLeaveForm(() => {
      resetForm();
      showTab("list");
    });
  });

  elements.discardConfirmStayBtn.addEventListener("click", closeDiscardConfirm);
  elements.discardConfirmLeaveBtn.addEventListener("click", () => {
    const action = state.pendingDiscardAction;
    closeDiscardConfirm();
    if (action) action();
  });
  elements.discardConfirmModal.addEventListener("click", (event) => {
    if (event.target === elements.discardConfirmModal) {
      closeDiscardConfirm();
    }
  });

  elements.saveAdBtn.addEventListener("click", saveAd);
  elements.publishBtn.addEventListener("click", async () => {
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
        descriptionError: elements.descError,
        priceError: elements.priceError,
        contactError: elements.contactError,
      });
      const auctionValid = validateAuctionFields();
      if (!descValid || !auctionValid) return;
      payload = {
        description,
        price: "",
        price_in_description: false,
        contact_info: contactInfo,
        photo_file_ids: state.photoFileIds,
        ...getAuctionPayloadFields(),
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
        descriptionError: elements.descError,
        priceError: elements.priceError,
        contactError: elements.contactError,
      });
      if (!isValid) return;
      payload = {
        description,
        price,
        price_in_description: priceInDescription,
        contact_info: contactInfo,
        photo_file_ids: state.photoFileIds,
        ad_type: "fixed",
      };
    }

    haptic("medium");
    setBusy(true, t("busyPublishing"));
    let publishSucceeded = false;
    try {
      if (!state.editingId) {
        const created = await apiFetch("/api/announcements", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        if (created?.id) {
          await apiFetch(`/api/announcements/${created.id}/publish`, { method: "POST" });
        }
      } else {
        await apiFetch(`/api/announcements/${state.editingId}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        await apiFetch(`/api/announcements/${state.editingId}/publish`, { method: "POST" });
      }
      publishSucceeded = true;
    } catch (err) {
      const errorId = err?.data?.error_id;
      const detail = err?.data?.error_detail;
      const message = errorId ? `${t("publishFailed")} #${errorId}` : t("publishFailed");
      state.lastError = {
        action: "publish_ad",
        ad_id: state.editingId || null,
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
    if (!publishSucceeded) return;
    haptic("success");
    showToast(t("publishedToast"), "success");
    resetForm();
    showTab("list");
    await refreshAds();
  });
  elements.description.addEventListener("input", () => {
    updateCounts();
    autoResizeDescription();
    setFieldInvalid(elements.description, false);
    setFieldError(elements.descError, "");
    updateCharCounter(elements.description, elements.descCounter, 800);
  });
  elements.contactInfo.addEventListener("input", () => {
    setFieldInvalid(elements.contactInfo, false);
    setFieldError(elements.contactError, "");
  });
  elements.price.addEventListener("input", () => {
    updateCounts();
    setFieldInvalid(elements.price, false);
    setFieldError(elements.priceError, "");
  });
  elements.priceInDescription.addEventListener("change", () => {
    applyPriceInDescriptionToggle(elements.priceInDescription, elements.price, elements.priceField);
    updateCounts();
  });
  elements.photoUploadZone?.addEventListener("click", () => {
    elements.photos.click();
  });
  elements.addMorePhotosBtn.addEventListener("click", (event) => {
    event.preventDefault();
    elements.photos.click();
  });
  elements.formatToggleBtn?.addEventListener("click", () => {
    const willShow = elements.descToolbar.hidden;
    elements.descToolbar.hidden = !willShow;
    elements.formatToggleBtn.classList.toggle("active", willShow);
  });
  new MutationObserver(() => {
    const count = elements.photoGrid.children.length;
    if (elements.photoUploadZone) elements.photoUploadZone.hidden = count > 0;
    elements.addMorePhotosBtn.hidden = count === 0 || count >= 10;
  }).observe(elements.photoGrid, { childList: true });
  elements.photos.addEventListener("change", handlePhotoInput);
  enablePhotoDropZone(elements.photoUploadZone);
  enablePhotoDropZone(elements.photoGrid);
  elements.descBoldBtn.addEventListener("click", () => wrapSelection(elements.description, "**"));
  elements.descItalicBtn.addEventListener("click", () => wrapSelection(elements.description, "_"));
  elements.descUnderlineBtn.addEventListener("click", () => wrapSelection(elements.description, "__"));
  elements.descStrikeBtn.addEventListener("click", () => wrapSelection(elements.description, "~~"));
  elements.descQuoteBtn.addEventListener("click", () => prefixSelectionLines(elements.description, "> "));
  elements.descMonoBtn.addEventListener("click", () => wrapSelection(elements.description, "`"));
  elements.descSpoilerBtn.addEventListener("click", () => wrapSelection(elements.description, "||"));
  elements.settingsToggle?.addEventListener("click", (event) => {
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
    } catch (err) {
      showToast(err?.message || t("loadFailed"), "danger");
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
  elements.settingsMenu?.addEventListener("click", (event) => {
    event.stopPropagation();
  });
  elements.themeAutoBtn?.addEventListener("click", () => {
    setThemeAuto();
    closeSettingsMenu();
  });
  elements.themeLightBtn.addEventListener("click", () => {
    setTheme("light");
    closeSettingsMenu();
  });
  elements.themeDarkBtn.addEventListener("click", () => {
    setTheme("dark");
    closeSettingsMenu();
  });
  elements.languageAutoBtn?.addEventListener("click", () => {
    setLanguageAuto();
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
  elements.editPhotoUploadZone?.addEventListener("click", () => {
    elements.editPhotos.click();
  });
  elements.editFormatToggleBtn?.addEventListener("click", () => {
    const willShow = elements.editDescToolbar.hidden;
    elements.editDescToolbar.hidden = !willShow;
    elements.editFormatToggleBtn.classList.toggle("active", willShow);
  });
  new MutationObserver(() => {
    const count = elements.editPhotoGrid.children.length;
    if (elements.editPhotoUploadZone) elements.editPhotoUploadZone.hidden = count > 0;
    elements.editAddMorePhotosBtn.hidden = count === 0 || count >= 10;
  }).observe(elements.editPhotoGrid, { childList: true });
  elements.editDescription.addEventListener("input", () => {
    autoResizeTextarea(elements.editDescription);
    setFieldInvalid(elements.editDescription, false);
    setFieldError(elements.editDescError, "");
    updateCharCounter(elements.editDescription, elements.editDescCounter, 800);
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
    setFieldError(elements.editContactError, "");
  });
  elements.editPrice.addEventListener("input", () => {
    setFieldInvalid(elements.editPrice, false);
    setFieldError(elements.editPriceError, "");
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
    confirmLeaveEditModal(() => {
      closeEditModal();
      showToast(t("editCanceled"));
    });
  });
  elements.editModal.addEventListener("click", (event) => {
    if (event.target === elements.editModal) {
      confirmLeaveEditModal(() => {
        closeEditModal();
        showToast(t("editCanceled"));
      });
    }
  });
  elements.editPublishBtn.addEventListener("click", async () => {
    const description = elements.editDescription.value.trim();
    const contactInfo = elements.editContactInfo.value.trim();
    const isAuction = state.editModal.adType === "auction";

    let payload;
    if (isAuction) {
      const descValid = validateAdForm({
        description,
        price: "",
        priceInDescription: true,
        contactInfo,
        requireContact: !state.hasUsername,
        descriptionInput: elements.editDescription,
        priceInput: elements.editPrice,
        contactInput: elements.editContactInfo,
        descriptionError: elements.editDescError,
        priceError: elements.editPriceError,
        contactError: elements.editContactError,
      });
      const minStep = parseInt(elements.editAuctionMinStep?.value, 10);
      let stepValid = true;
      if (!minStep || minStep <= 0) {
        stepValid = false;
        if (elements.editAuctionMinStepError) setFieldError(elements.editAuctionMinStepError, t("auctionMinStepMin"));
        setFieldInvalid(elements.editAuctionMinStep, true);
      }
      const buyoutPrice = parseInt(elements.editAuctionBuyout?.value, 10) || null;
      let buyoutValid = true;
      if (elements.editAuctionBuyout?.value && (!buyoutPrice || (state.editModal.startPrice && buyoutPrice <= state.editModal.startPrice))) {
        buyoutValid = false;
        if (elements.editAuctionBuyoutError) setFieldError(elements.editAuctionBuyoutError, t("auctionBuyoutMin"));
        setFieldInvalid(elements.editAuctionBuyout, true);
      }
      if (!descValid || !stepValid || !buyoutValid) return;
      payload = {
        description,
        price: "",
        price_in_description: false,
        contact_info: contactInfo,
        photo_file_ids: state.editModal.photoFileIds,
        ad_type: "auction",
        start_price: state.editModal.startPrice,
        min_step: minStep,
        buyout_price: buyoutPrice,
        // Empty = keep the current end time; a value sets end = now + duration.
        auction_duration_hours: parseInt(elements.editAuctionDuration?.value, 10) || null,
        currency: state.editModal.currency,
      };
    } else {
      const priceInDescription = elements.editPriceInDescription.checked;
      const price = priceInDescription ? "" : elements.editPrice.value.trim();
      const isValid = validateAdForm({
        description,
        price,
        priceInDescription,
        contactInfo,
        requireContact: !state.hasUsername,
        descriptionInput: elements.editDescription,
        priceInput: elements.editPrice,
        contactInput: elements.editContactInfo,
        descriptionError: elements.editDescError,
        priceError: elements.editPriceError,
        contactError: elements.editContactError,
      });
      if (!isValid) return;
      payload = {
        description,
        price,
        price_in_description: priceInDescription,
        contact_info: contactInfo,
        photo_file_ids: state.editModal.photoFileIds,
      };
    }
    if (!state.editModal.id) {
      closeEditModal();
      return;
    }
    // A running auction whose photos didn't change is edited in place (the same
    // channel post is updated); otherwise (and for fixed ads) it's republished.
    const photosUnchanged =
      JSON.stringify(state.editModal.originalPhotoFileIds || []) ===
      JSON.stringify(state.editModal.photoFileIds || []);
    const editInPlace = isAuction && photosUnchanged;

    haptic("medium");
    setBusy(true, t("busyPublishing"));
    let publishSucceeded = false;
    try {
      if (editInPlace) {
        await editAuctionInPlace(state.editModal.id, payload);
      } else {
        await apiFetch(`/api/announcements/${state.editModal.id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        await apiFetch(`/api/announcements/${state.editModal.id}/publish`, { method: "POST" });
      }
      publishSucceeded = true;
    } catch (err) {
      const errorId = err?.data?.error_id;
      const detail = err?.data?.error_detail;
      const message = errorId ? `${t("publishFailed")} #${errorId}` : t("publishFailed");
      state.lastError = {
        action: "edit_publish_ad",
        ad_id: state.editModal.id,
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
    if (!publishSucceeded) return;
    closeEditModal();
    haptic("success");
    showToast(t("editedPublished"), "success");
    await refreshAds();
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
          try {
            await refreshAdminExpiredAds();
          } catch (err) {
            void silentBugReport({ action: "refresh_expired_after_admin_delete", status: err?.status, message: err?.message });
          }
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

  // Hide the floating tab bar while the on-screen keyboard is up so it
  // doesn't float over the focused field.
  const KEYBOARD_INPUT_TYPES = new Set(["text", "number", "tel", "email", "url", "search", "password"]);
  const opensKeyboard = (el) =>
    el?.tagName === "TEXTAREA" || (el?.tagName === "INPUT" && KEYBOARD_INPUT_TYPES.has(el.type));
  document.addEventListener("focusin", (event) => {
    if (opensKeyboard(event.target)) {
      elements.topBar?.classList.add("top-bar-hidden");
    }
  });
  document.addEventListener("focusout", (event) => {
    if (opensKeyboard(event.target)) {
      elements.topBar?.classList.remove("top-bar-hidden");
    }
  });
}

function getAuctionPayloadFields() {
  return {
    ad_type: "auction",
    start_price: parseInt(elements.auctionStartPrice?.value, 10) || null,
    min_step: parseInt(elements.auctionMinStep?.value, 10) || null,
    buyout_price: parseInt(elements.auctionBuyout?.value, 10) || null,
    auction_duration_hours: parseInt(elements.auctionDuration?.value, 10) || 24,
    currency: state.auctionCurrency,
  };
}

function setAuctionCurrency(currency) {
  state.auctionCurrency = currency === "EUR" ? "EUR" : "RSD";
  elements.auctionCurrencyRsdBtn?.classList.toggle("active", state.auctionCurrency === "RSD");
  elements.auctionCurrencyEurBtn?.classList.toggle("active", state.auctionCurrency === "EUR");
}

function setEditAuctionCurrency(currency) {
  state.editModal.currency = currency === "EUR" ? "EUR" : "RSD";
  elements.editAuctionCurrencyRsdBtn?.classList.toggle("active", state.editModal.currency === "RSD");
  elements.editAuctionCurrencyEurBtn?.classList.toggle("active", state.editModal.currency === "EUR");
}

function validateAuctionFields() {
  const startPrice = parseInt(elements.auctionStartPrice?.value, 10);
  const minStep = parseInt(elements.auctionMinStep?.value, 10);
  let valid = true;
  if (!startPrice || startPrice <= 0) {
    if (elements.auctionStartPriceError) {
      setFieldError(elements.auctionStartPriceError, t("auctionStartPriceMin"));
      setFieldInvalid(elements.auctionStartPrice, true);
    }
    valid = false;
  }
  if (!minStep || minStep <= 0) {
    if (elements.auctionMinStepError) {
      setFieldError(elements.auctionMinStepError, t("auctionMinStepMin"));
      setFieldInvalid(elements.auctionMinStep, true);
    }
    valid = false;
  }
  // Buyout price is optional, but when set it must beat the starting price.
  const buyoutPrice = parseInt(elements.auctionBuyout?.value, 10);
  if (elements.auctionBuyout?.value && (!buyoutPrice || (startPrice && buyoutPrice <= startPrice))) {
    if (elements.auctionBuyoutError) {
      setFieldError(elements.auctionBuyoutError, t("auctionBuyoutMin"));
      setFieldInvalid(elements.auctionBuyout, true);
    }
    valid = false;
  }
  return valid;
}

function renderBidScreen(data) {
  if (!elements.bidAuctionInfo) return;
  elements.bidAuctionInfo.innerHTML = "";

  // Opt-in banner: without write access the bot can't tell the user if outbid.
  if (!state.writeAccessGranted && tg?.requestWriteAccess) {
    const banner = document.createElement("div");
    banner.className = "bid-notif-banner";
    const txt = document.createElement("span");
    txt.className = "bid-notif-text";
    txt.textContent = t("bidNotifOff");
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "bid-notif-enable";
    btn.textContent = t("bidNotifEnable");
    btn.addEventListener("click", async () => {
      haptic("light");
      const granted = await ensureWriteAccess();
      if (granted) {
        showToast(t("bidNotifOn"), "success");
        void refreshBidInfo(state.bidScreenAnnId);
      }
    });
    banner.append(txt, btn);
    elements.bidAuctionInfo.appendChild(banner);
  }

  const addRow = (label, value, cls) => {
    const row = document.createElement("div");
    row.className = "bid-info-row";
    const lbl = document.createElement("span");
    lbl.className = "bid-info-label";
    lbl.textContent = label;
    const val = document.createElement("span");
    val.className = "bid-info-value" + (cls ? ` ${cls}` : "");
    val.textContent = value;
    row.append(lbl, val);
    elements.bidAuctionInfo.appendChild(row);
  };

  const photos = Array.isArray(data.photo_file_ids) ? data.photo_file_ids : [];
  if (photos.length) {
    const gallery = document.createElement("div");
    gallery.className = "bid-photos";
    photos.forEach((fileId) => {
      const img = document.createElement("img");
      img.className = "bid-photo";
      img.loading = "lazy";
      const photoUrl = `/api/auctions/${data.id}/photo?file_id=${encodeURIComponent(fileId)}`;
      setAuthedImage(img, `${photoUrl}&size=thumb`);
      img.alt = data.description || "photo";
      img.addEventListener("click", () => openAuthedPhotoViewer(photoUrl));
      gallery.appendChild(img);
    });
    elements.bidAuctionInfo.appendChild(gallery);
  }

  const descEl = document.createElement("div");
  descEl.className = "bid-info-desc";
  descEl.textContent = data.description || "";
  elements.bidAuctionInfo.appendChild(descEl);

  const cur = data.currency || "RSD";
  if (data.start_price != null) {
    addRow(`${t("auctionStartPrice")}:`, formatMoney(data.start_price, cur));
  }

  if (data.current_price != null) {
    addRow(`${t("auctionLastBid")}:`, formatMoney(data.current_price, cur), "bid-current-price");
    if (data.winner_username) {
      addRow(`${t("auctionLastBidder")}:`, data.winner_username);
    }
  } else {
    addRow(`${t("auctionLastBid")}:`, t("auctionNoBids"));
  }

  // First bid must be at least start_price + step; later bids at least current + step.
  const minRequired = data.current_price != null
    ? data.current_price + (data.min_step || 0)
    : (data.start_price || 0) + (data.min_step || 0);
  state.bidMinRequired = minRequired || null;
  if (minRequired) {
    addRow(`${t("bidMinRequired")}:`, formatMoney(minRequired, cur));
  }
  if (elements.bidAmount) {
    // Spinner arrows step by the auction's min step, not by 1.
    elements.bidAmount.step = String(data.min_step || 1);
    if (minRequired) elements.bidAmount.min = String(minRequired);
  }

  if (data.buyout_price != null) {
    addRow(`${t("auctionBuyoutRow")}:`, formatMoney(data.buyout_price, cur));
  }

  if (data.auction_end_at) {
    addRow(`${t("auctionEndAt")}:`, formatAuctionEnd(data.auction_end_at));
  }

  if (data.bids_count > 0) {
    addRow(`${t("auctionBidsCount")}:`, String(data.bids_count));
  }

  // "Buy now" wins the auction on the spot at the seller's buyout price.
  state.bidBuyoutPrice = data.buyout_price || null;
  state.bidBuyoutLabel = data.buyout_price != null ? formatMoney(data.buyout_price, cur) : null;
  if (elements.bidBuyoutBtn) {
    elements.bidBuyoutBtn.hidden = data.buyout_price == null;
    if (elements.bidBuyoutText && state.bidBuyoutLabel) {
      elements.bidBuyoutText.textContent = t("bidBuyoutBtn").replace("{price}", state.bidBuyoutLabel);
    }
  }
}

function updateBackToPostBtn(postLink) {
  state.bidPostLink = postLink || null;
  if (elements.bidBackToPostBtn) elements.bidBackToPostBtn.hidden = !postLink;
}

// Ask the user to allow the bot to message them (for outbid/finish notifications).
// Resolves regardless of the answer so the bid flow is never blocked.
function ensureWriteAccess() {
  return new Promise((resolve) => {
    if (!tg?.requestWriteAccess) {
      resolve(false);
      return;
    }
    try {
      tg.requestWriteAccess((granted) => {
        if (granted) state.writeAccessGranted = true;
        resolve(!!granted);
      });
    } catch (_) {
      resolve(false);
    }
  });
}

// Localize an auction API error by its backend code (falls back to the raw message).
function bidErrorMessage(err) {
  const code = err?.data?.code;
  switch (code) {
    case "bid_too_low": {
      const min = err?.data?.min_required ?? state.bidMinRequired;
      return min ? `${t("bidMinRequired")}: ${min}` : t("bidFailed");
    }
    case "auction_ended":
    case "auction_not_active":
      return t("bidAuctionEnded");
    case "own_auction":
      return t("bidOwnAuction");
    case "no_buyout":
      return t("bidNoBuyout");
    case "auction_not_found":
      return t("loadFailed");
    default:
      return err?.message || t("bidFailed");
  }
}

let bidPollTimer = null;

function stopBidPolling() {
  if (bidPollTimer) {
    clearInterval(bidPollTimer);
    bidPollTimer = null;
  }
}

// Re-fetch the auction and re-render the info card so the shown price/minimum
// stay in sync with other people's bids. Does not touch the input or error.
async function refreshBidInfo(annId) {
  if (state.bidScreenAnnId !== annId) return;
  let data;
  try {
    data = await getAuctionInfo(annId);
  } catch (err) {
    return; // keep current info on transient errors
  }
  if (state.bidScreenAnnId !== annId) return;
  updateBackToPostBtn(data.post_link);
  if (data.auction_status === "finished") {
    stopBidPolling();
    if (elements.bidAuctionInfo) elements.bidAuctionInfo.innerHTML = `<div class="bid-info-ended">${t("bidAuctionEnded")}</div>`;
    if (elements.bidSubmitBtn) elements.bidSubmitBtn.disabled = true;
    if (elements.bidBuyoutBtn) elements.bidBuyoutBtn.hidden = true;
    return;
  }
  renderBidScreen(data);
}

async function openBidScreen(annId) {
  stopBidPolling();
  state.bidScreenAnnId = annId;
  if (elements.bidScreen) elements.bidScreen.hidden = false;
  if (elements.bidAuctionInfo) elements.bidAuctionInfo.innerHTML = `<div class="bid-info-loading">${t("busyLoading")}</div>`;
  if (elements.bidAmount) elements.bidAmount.value = "";
  if (elements.bidAmountError) setFieldError(elements.bidAmountError, "");
  if (elements.bidSubmitBtn) elements.bidSubmitBtn.disabled = false;
  if (elements.bidBuyoutBtn) {
    elements.bidBuyoutBtn.hidden = true;
    elements.bidBuyoutBtn.disabled = false;
  }
  updateBackToPostBtn(null);

  try {
    const data = await getAuctionInfo(annId);
    updateBackToPostBtn(data.post_link);
    if (data.auction_status === "finished") {
      if (elements.bidAuctionInfo) elements.bidAuctionInfo.innerHTML = `<div class="bid-info-ended">${t("bidAuctionEnded")}</div>`;
      if (elements.bidSubmitBtn) elements.bidSubmitBtn.disabled = true;
      if (elements.bidBuyoutBtn) elements.bidBuyoutBtn.hidden = true;
      return;
    }
    renderBidScreen(data);
    // Keep the screen live while it's open.
    bidPollTimer = setInterval(() => { void refreshBidInfo(annId); }, 6000);
  } catch (err) {
    if (elements.bidAuctionInfo) elements.bidAuctionInfo.innerHTML = `<div class="bid-info-error">${err?.message || t("loadFailed")}</div>`;
  }
}

function closeBidScreen() {
  stopBidPolling();
  state.bidScreenAnnId = null;
  if (elements.bidScreen) elements.bidScreen.hidden = true;
}

function renderBidsScreen(data) {
  if (elements.bidsAuctionInfo) {
    elements.bidsAuctionInfo.innerHTML = "";
    const descEl = document.createElement("div");
    descEl.className = "bid-info-desc";
    descEl.textContent = data.description || "";
    elements.bidsAuctionInfo.appendChild(descEl);

    const addRow = (label, value, cls) => {
      const row = document.createElement("div");
      row.className = "bid-info-row";
      const lbl = document.createElement("span");
      lbl.className = "bid-info-label";
      lbl.textContent = label;
      const val = document.createElement("span");
      val.className = "bid-info-value" + (cls ? ` ${cls}` : "");
      val.textContent = value;
      row.append(lbl, val);
      elements.bidsAuctionInfo.appendChild(row);
    };
    const cur = data.currency || "RSD";
    if (data.start_price != null) addRow(`${t("auctionStartPrice")}:`, formatMoney(data.start_price, cur));
    if (data.current_price != null) addRow(`${t("auctionCurrentBid")}:`, formatMoney(data.current_price, cur), "bid-current-price");
    addRow(`${t("auctionBidsCount")}:`, String((data.bids || []).length));
  }

  if (!elements.bidsList) return;
  elements.bidsList.innerHTML = "";
  const bids = Array.isArray(data.bids) ? data.bids : [];
  if (!bids.length) {
    const empty = document.createElement("div");
    empty.className = "bids-empty";
    empty.textContent = t("auctionNoBids");
    elements.bidsList.appendChild(empty);
    return;
  }
  bids.forEach((bid, idx) => {
    const item = document.createElement("div");
    item.className = "bids-item" + (idx === 0 ? " bids-item-top" : "");
    const left = document.createElement("div");
    left.className = "bids-item-left";
    const who = document.createElement("div");
    who.className = "bids-item-user";
    who.textContent = bid.username || "—";
    // If the bidder has a @username, make it tap-to-open their Telegram profile.
    const handle = (bid.username || "").trim();
    if (handle.startsWith("@") && handle.length > 1) {
      who.classList.add("bids-item-user-link");
      who.addEventListener("click", () => {
        haptic("light");
        const url = `https://t.me/${handle.slice(1)}`;
        if (tg?.openTelegramLink) tg.openTelegramLink(url);
        else window.open(url, "_blank");
      });
    }
    const when = document.createElement("div");
    when.className = "bids-item-time";
    when.textContent = bid.created_at || "";
    left.append(who, when);
    const amount = document.createElement("div");
    amount.className = "bids-item-amount";
    amount.textContent = formatMoney(bid.amount, data.currency || "RSD");
    item.append(left, amount);
    elements.bidsList.appendChild(item);
  });
}

async function openBidsScreen(annId) {
  if (elements.bidsScreen) elements.bidsScreen.hidden = false;
  if (elements.bidsAuctionInfo) elements.bidsAuctionInfo.innerHTML = `<div class="bid-info-loading">${t("busyLoading")}</div>`;
  if (elements.bidsList) elements.bidsList.innerHTML = "";

  try {
    const data = await getAuctionBids(annId);
    renderBidsScreen(data);
  } catch (err) {
    if (elements.bidsAuctionInfo) elements.bidsAuctionInfo.innerHTML = `<div class="bid-info-error">${err?.message || t("loadFailed")}</div>`;
  }
}

function bindAuctionEvents() {
  elements.adTypeFixedBtn?.addEventListener("click", () => {
    haptic("light");
    setAdType("fixed");
  });
  elements.adTypeAuctionBtn?.addEventListener("click", () => {
    haptic("light");
    setAdType("auction");
  });
  elements.auctionCurrencyRsdBtn?.addEventListener("click", () => { haptic("light"); setAuctionCurrency("RSD"); });
  elements.auctionCurrencyEurBtn?.addEventListener("click", () => { haptic("light"); setAuctionCurrency("EUR"); });
  elements.editAuctionCurrencyRsdBtn?.addEventListener("click", () => { haptic("light"); setEditAuctionCurrency("RSD"); });
  elements.editAuctionCurrencyEurBtn?.addEventListener("click", () => { haptic("light"); setEditAuctionCurrency("EUR"); });
  elements.auctionStartPrice?.addEventListener("input", () => {
    setFieldInvalid(elements.auctionStartPrice, false);
    if (elements.auctionStartPriceError) setFieldError(elements.auctionStartPriceError, "");
  });
  elements.auctionMinStep?.addEventListener("input", () => {
    setFieldInvalid(elements.auctionMinStep, false);
    if (elements.auctionMinStepError) setFieldError(elements.auctionMinStepError, "");
  });
  elements.auctionBuyout?.addEventListener("input", () => {
    setFieldInvalid(elements.auctionBuyout, false);
    if (elements.auctionBuyoutError) setFieldError(elements.auctionBuyoutError, "");
  });
  const goToAuctionPost = () => {
    const link = state.bidPostLink;
    if (!link) return;
    haptic("light");
    if (tg?.openTelegramLink) {
      tg.openTelegramLink(link);
    } else {
      window.open(link, "_blank");
    }
  };
  // The bid screen is only reached via a deep link from the channel, so "back"
  // returns to the Telegram chat by closing the Mini App.
  elements.bidScreenBackBtn?.addEventListener("click", () => {
    haptic("light");
    if (tg?.close) {
      tg.close();
    } else {
      closeBidScreen();
    }
  });
  elements.bidBackToPostBtn?.addEventListener("click", goToAuctionPost);
  // The bids screen belongs to the owner, so "back" returns to their listings
  // (loading them if the screen was opened directly from the notification).
  elements.bidsScreenBackBtn?.addEventListener("click", () => {
    haptic("light");
    if (elements.bidsScreen) elements.bidsScreen.hidden = true;
    showTab("list");
    if (!state.ads.length) {
      refreshAds();
      refreshAdminStats();
    }
  });
  elements.bidSubmitBtn?.addEventListener("click", async () => {
    const annId = state.bidScreenAnnId;
    if (!annId) return;
    // Only a clean positive integer is allowed — reject leading zeros,
    // decimals ("263.5") and any non-digit input ("00330").
    const rawAmount = (elements.bidAmount?.value || "").trim();
    if (!/^[1-9]\d*$/.test(rawAmount)) {
      if (elements.bidAmountError) setFieldError(elements.bidAmountError, t("bidInvalidAmount"));
      setFieldInvalid(elements.bidAmount, true);
      return;
    }
    const amount = parseInt(rawAmount, 10);
    const minRequired = state.bidMinRequired;
    if (minRequired && amount < minRequired) {
      if (elements.bidAmountError) setFieldError(elements.bidAmountError, `${t("bidMinRequired")}: ${minRequired}`);
      setFieldInvalid(elements.bidAmount, true);
      return;
    }
    setFieldInvalid(elements.bidAmount, false);
    if (elements.bidAmountError) setFieldError(elements.bidAmountError, "");
    // Ask once for permission to message the user, so the bot can notify them
    // when they get outbid or the auction ends (otherwise Telegram blocks it).
    if (!state.askedWriteAccess) {
      state.askedWriteAccess = true;
      await ensureWriteAccess();
    }
    setBusy(true, t("busyBidding"));
    try {
      await placeBid(annId, amount);
      if (elements.bidSubmitBtn) elements.bidSubmitBtn.disabled = true;
      showToast(t("bidSuccess"), "success");
      await openBidScreen(annId);
    } catch (err) {
      if (err?.status === 401) {
        if (elements.bidAmountError) setFieldError(elements.bidAmountError, t("bidOpenInTelegram"));
        setFieldInvalid(elements.bidAmount, true);
      } else {
        // The bid likely lost to a newer one — resync the shown price/minimum,
        // then surface a localized message based on the backend error code.
        await refreshBidInfo(annId);
        if (elements.bidAmountError) setFieldError(elements.bidAmountError, bidErrorMessage(err));
        setFieldInvalid(elements.bidAmount, true);
      }
    } finally {
      setBusy(false);
    }
  });
  elements.bidBuyoutBtn?.addEventListener("click", () => {
    const annId = state.bidScreenAnnId;
    if (!annId || !state.bidBuyoutPrice) return;
    haptic("medium");
    const doBuyout = async () => {
      // Same one-time write-access ask as for bids, so the bot can DM the winner.
      if (!state.askedWriteAccess) {
        state.askedWriteAccess = true;
        await ensureWriteAccess();
      }
      setBusy(true, t("busyBuyingOut"));
      try {
        await buyoutAuction(annId);
        showToast(t("bidBuyoutSuccess"), "success");
        await openBidScreen(annId);
      } catch (err) {
        if (err?.status === 401) {
          if (elements.bidAmountError) setFieldError(elements.bidAmountError, t("bidOpenInTelegram"));
        } else {
          // Someone may have bought or finished it first — resync, then explain.
          await refreshBidInfo(annId);
          if (elements.bidAmountError) setFieldError(elements.bidAmountError, bidErrorMessage(err));
        }
      } finally {
        setBusy(false);
      }
    };
    const confirmText = t("bidBuyoutConfirm").replace("{price}", state.bidBuyoutLabel || String(state.bidBuyoutPrice));
    if (tg?.showConfirm) {
      tg.showConfirm(confirmText, (ok) => { if (ok) void doBuyout(); });
    } else if (window.confirm(confirmText)) {
      void doBuyout();
    }
  });
}

applyTranslations();
applyContactFieldVisibility();
bindEvents();
bindAuctionEvents();
updateCounts();
showTab("list");
window.addEventListener("resize", () => moveTabIndicator(document.querySelector(".tab.active")));
showAdsSkeleton();
initTheme();
closeDeleteConfirm();
closeDiscardConfirm();
closeEditModal();
closeErrorModal();
closePhotoViewer();
closeCommentsOverviewModal();
closeStatsModal();
closeExpiredAdsModal();
closeFeedbackModal();

// Detect bid mode before any API calls.
// GET /api/auctions/{id} is public — bid screen loads even in browser.
// In bid mode, skip refreshAds/refreshAdminStats (not needed for bidding).
(function () {
  const startParam = tg?.initDataUnsafe?.start_param || "";
  const params = new URLSearchParams(window.location.search);

  // Owner bids-overview mode (opened from the new-bid notification button).
  let bidsAnnId = 0;
  if (startParam.startsWith("bids_")) {
    bidsAnnId = parseInt(startParam.slice(5), 10);
  }
  if (!bidsAnnId) {
    bidsAnnId = parseInt(params.get("bids") || "0", 10);
  }

  // Bidder mode (opened from the channel post bid link).
  let annId = 0;
  if (startParam.startsWith("bid_")) {
    annId = parseInt(startParam.slice(4), 10);
  }
  if (!annId) {
    annId = parseInt(params.get("bid") || "0", 10);
  }

  if (bidsAnnId > 0) {
    void openBidsScreen(bidsAnnId);
  } else if (annId > 0) {
    void openBidScreen(annId);
  } else {
    refreshAds();
    refreshAdminStats();
  }
  if (!state.sentAppOpenEvent) {
    state.sentAppOpenEvent = true;
    void trackEvent("app_open");
  }
})();
