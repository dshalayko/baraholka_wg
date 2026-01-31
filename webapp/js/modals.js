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
  elements.editPrice.value = "";
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
  elements.editPrice.value = ad.price || "";
  renderEditPhotoPreviews();
  elements.editModal.hidden = false;
  elements.editModal.style.display = "flex";
  autoResizeTextarea(elements.editDescription);
}

function closeEditModal() {
  elements.editModal.hidden = true;
  elements.editModal.style.display = "none";
  resetEditModal();
}
