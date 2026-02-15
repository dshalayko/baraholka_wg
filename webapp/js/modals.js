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

function openCommentsOverviewModal() {
  elements.commentsOverviewModal.hidden = false;
  elements.commentsOverviewModal.style.display = "flex";
}

function closeCommentsOverviewModal() {
  elements.commentsOverviewModal.hidden = true;
  elements.commentsOverviewModal.style.display = "none";
}

function resetEditModal() {
  state.editModal.id = null;
  state.editModal.photoFileIds = [];
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
  elements.editPhotos.value = "";
  elements.editPhotoGrid.innerHTML = "";
  renderEditPhotoPreviews();
}

function openEditModal(ad) {
  state.editModal.id = ad.id;
  state.editModal.photoFileIds = ad.photo_file_ids || [];
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
  elements.editPrice.value = ad.price || "";
  elements.editPriceInDescription.checked = !!ad.price_in_description;
  applyPriceInDescriptionToggle(elements.editPriceInDescription, elements.editPrice, elements.editPriceField);
  renderEditPhotoPreviews();
  elements.editModal.hidden = false;
  elements.editModal.style.display = "flex";
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
}
