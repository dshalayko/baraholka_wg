function applyTranslations() {
  document.documentElement.lang = state.languageCode?.startsWith("ru") ? "ru" : "en";
  elements.tabMyAds.textContent = t("myAds");
  elements.tabCreate.textContent = t("create");
  elements.cancelFormBtn.textContent = t("cancel");
  elements.descLabel.textContent = t("description");
  elements.contactLabel.textContent = t("contactLabel");
  elements.priceLabel.textContent = t("price");
  elements.priceInDescriptionLabel.textContent = t("priceInDescriptionLabel");
  elements.photosLabel.textContent = t("photos");
  elements.emptyState.textContent = t("noAds");
  elements.description.placeholder = t("descPlaceholder");
  elements.price.placeholder = t("pricePlaceholder");
  elements.themeToggle.textContent = isDarkTheme() ? "◐" : "◑";
  elements.saveAdBtn.textContent = t("saveDraft");
  elements.publishBtn.textContent = t("publishNow");
  elements.addMorePhotosBtn.textContent = t("addMore");
  elements.editModalTitle.textContent = t("editTitle");
  elements.editDescLabel.textContent = t("description");
  elements.editContactLabel.textContent = t("contactLabel");
  elements.editPriceLabel.textContent = t("price");
  elements.editPriceInDescriptionLabel.textContent = t("priceInDescriptionLabel");
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
  elements.themeToggle.addEventListener("click", toggleTheme);
  elements.editAddMorePhotosBtn.addEventListener("click", (event) => {
    event.preventDefault();
    elements.editPhotos.click();
  });
  elements.editDescription.addEventListener("input", () => {
    autoResizeTextarea(elements.editDescription);
    setFieldInvalid(elements.editDescription, false);
  });
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
initTheme();
closeDeleteConfirm();
closeEditModal();
closeErrorModal();
