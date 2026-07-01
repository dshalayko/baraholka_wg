// Telegram's native Back button drives the full-screen "page" modals.
function syncPageBackButton() {
  if (!tg?.BackButton) return;
  const pages = [
    elements.editModal,
    elements.commentsOverviewModal,
    elements.statsModal,
    elements.expiredAdsModal,
  ];
  const anyOpen = pages.some((el) => el && !el.hidden);
  if (anyOpen) tg.BackButton.show();
  else tg.BackButton.hide();
}

function handlePageBackButton() {
  if (!elements.editModal.hidden) { closeEditModal(); return; }
  if (!elements.commentsOverviewModal.hidden) { closeCommentsOverviewModal(); return; }
  if (!elements.statsModal.hidden) { closeStatsModal(); return; }
  if (!elements.expiredAdsModal.hidden) { closeExpiredAdsModal(); return; }
}

if (tg?.BackButton?.onClick) {
  tg.BackButton.onClick(handlePageBackButton);
}

function openDeleteConfirm(id) {
  state.pendingDeleteId = id;
  elements.confirmModal.hidden = false;
  elements.confirmModal.style.display = "flex";
}

function closeDeleteConfirm() {
  state.pendingDeleteId = null;
  elements.confirmModal.hidden = true;
  elements.confirmModal.style.display = "none";
}

function openErrorModal(message, details) {
  elements.errorTitle.textContent = t("errorTitle");
  elements.errorText.textContent = message || t("deleteFailed");
  if (details) {
    elements.errorDetails.hidden = false;
    elements.errorDetails.textContent = `${t("errorDetails")} ${details}`;
  } else {
    elements.errorDetails.hidden = true;
    elements.errorDetails.textContent = "";
  }
  elements.errorModal.hidden = false;
  elements.errorModal.style.display = "flex";
}

function closeErrorModal() {
  elements.errorModal.hidden = true;
  elements.errorModal.style.display = "none";
}

function openPhotoViewer(src) {
  if (!src) return;
  elements.photoViewerImage.src = src;
  elements.photoViewer.hidden = false;
  elements.photoViewer.style.display = "flex";
}

function closePhotoViewer() {
  elements.photoViewer.hidden = true;
  elements.photoViewer.style.display = "none";
  elements.photoViewerImage.src = "";
}

function openCommentsOverviewModal() {
  elements.commentsOverviewModal.hidden = false;
  elements.commentsOverviewModal.style.display = "flex";
  syncPageBackButton();
}

function closeCommentsOverviewModal() {
  elements.commentsOverviewModal.hidden = true;
  elements.commentsOverviewModal.style.display = "none";
  syncPageBackButton();
}

function openStatsModal() {
  elements.statsModal.hidden = false;
  elements.statsModal.style.display = "flex";
  syncPageBackButton();
}

function closeStatsModal() {
  elements.statsModal.hidden = true;
  elements.statsModal.style.display = "none";
  syncPageBackButton();
}

function openExpiredAdsModal() {
  elements.expiredAdsModal.hidden = false;
  elements.expiredAdsModal.style.display = "flex";
  syncPageBackButton();
}

function closeExpiredAdsModal() {
  elements.expiredAdsModal.hidden = true;
  elements.expiredAdsModal.style.display = "none";
  syncPageBackButton();
}

function openFeedbackModal() {
  elements.feedbackModal.hidden = false;
  elements.feedbackModal.style.display = "flex";
  if (elements.feedbackInput) {
    elements.feedbackInput.focus();
  }
}

function closeFeedbackModal() {
  elements.feedbackModal.hidden = true;
  elements.feedbackModal.style.display = "none";
  if (elements.feedbackInput) {
    elements.feedbackInput.value = "";
  }
}

function resetEditModal() {
  state.editModal.id = null;
  state.editModal.photoFileIds = [];
  state.editModal.originalPhotoFileIds = [];
  state.editModal.photoPreviews.forEach((item) => {
    if (item.source === "local") {
      URL.revokeObjectURL(item.url);
    }
  });
  state.editModal.photoPreviews = [];
  elements.editDescription.value = "";
  elements.editContactInfo.value = "";
  elements.editPrice.value = "";
  elements.editPriceInDescription.checked = false;
  applyPriceInDescriptionToggle(elements.editPriceInDescription, elements.editPrice, elements.editPriceField);
  state.editModal.adType = "fixed";
  state.editModal.startPrice = null;
  state.editModal.currency = "RSD";
  if (elements.editAuctionSection) elements.editAuctionSection.hidden = true;
  if (elements.editAuctionMinStep) elements.editAuctionMinStep.value = "";
  if (elements.editPriceField) elements.editPriceField.hidden = false;
  if (elements.editPriceToggleField) elements.editPriceToggleField.hidden = false;
  elements.editPhotos.value = "";
  elements.editPhotoGrid.innerHTML = "";
  renderEditPhotoPreviews();
  updateCharCounter(elements.editDescription, elements.editDescCounter, 800);
}

function openEditModal(ad) {
  state.editModal.id = ad.id;
  state.editModal.photoFileIds = ad.photo_file_ids || [];
  state.editModal.originalPhotoFileIds = [...(ad.photo_file_ids || [])];
  state.editModal.photoPreviews = (ad.photo_file_ids || []).map((fileId, idx) => {
    const initData = encodeURIComponent(tg?.initData || "");
    return {
      source: "remote",
      url: `/api/announcements/${ad.id}/photo?file_id=${encodeURIComponent(fileId)}&initData=${initData}`,
      label: `#${idx + 1}`,
    };
  });
  elements.editDescription.value = ad.description || "";
  elements.editContactInfo.value = ad.contact_info || "";

  const isAuction = ad.ad_type === "auction";
  state.editModal.adType = isAuction ? "auction" : "fixed";
  state.editModal.startPrice = ad.start_price ?? null;
  if (isAuction) {
    // Auction: edit min step + end time (duration from now). Start price and the
    // price fields are not used.
    if (elements.editAuctionSection) elements.editAuctionSection.hidden = false;
    if (elements.editAuctionMinStepLabel) elements.editAuctionMinStepLabel.textContent = t("auctionMinStep");
    if (elements.editAuctionDurationLabel) elements.editAuctionDurationLabel.textContent = t("auctionDurationFromNow");
    if (elements.editAuctionCurrencyLabel) elements.editAuctionCurrencyLabel.textContent = t("auctionCurrency");
    setEditAuctionCurrency(ad.currency || "RSD");
    // Confirm the currency from the authoritative endpoint so it's never reset
    // to RSD just because the list payload was stale.
    if (ad.is_published && ad.id) {
      getAuctionInfo(ad.id)
        .then((info) => {
          if (state.editModal.id === ad.id && info && info.currency) {
            setEditAuctionCurrency(info.currency);
          }
        })
        .catch(() => {});
    }
    if (elements.editAuctionMinStep) elements.editAuctionMinStep.value = ad.min_step ?? "";
    if (elements.editAuctionDuration) {
      const opts = elements.editAuctionDuration.options;
      const durationKeys = ["duration1h", "duration3h", "duration6h", "duration12h", "duration24h", "duration48h"];
      if (opts.length) opts[0].textContent = t("auctionKeepEnd"); // value="" — keep current end
      for (let i = 1; i < opts.length; i += 1) {
        const key = durationKeys[i - 1];
        if (key) opts[i].textContent = t(key);
      }
      // Default to "keep current" so re-saving doesn't reset the deadline.
      elements.editAuctionDuration.value = "";
    }
    if (elements.editPriceField) elements.editPriceField.hidden = true;
    if (elements.editPriceToggleField) elements.editPriceToggleField.hidden = true;
  } else {
    if (elements.editAuctionSection) elements.editAuctionSection.hidden = true;
    if (elements.editPriceField) elements.editPriceField.hidden = false;
    if (elements.editPriceToggleField) elements.editPriceToggleField.hidden = false;
    elements.editPrice.value = ad.price || "";
    elements.editPriceInDescription.checked = !!ad.price_in_description;
    applyPriceInDescriptionToggle(elements.editPriceInDescription, elements.editPrice, elements.editPriceField);
  }
  renderEditPhotoPreviews();
  updateCharCounter(elements.editDescription, elements.editDescCounter, 800);
  elements.editModal.hidden = false;
  elements.editModal.style.display = "flex";
  syncPageBackButton();
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      autoResizeTextarea(elements.editDescription);
    });
  });
}

function closeEditModal() {
  elements.editModal.hidden = true;
  elements.editModal.style.display = "none";
  resetEditModal();
  syncPageBackButton();
}
