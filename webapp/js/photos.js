function updateCounts() {
  // Counters removed from UI; keep placeholder for future metrics if needed.
}

function buildUploadHeaders() {
  const headers = { "ngrok-skip-browser-warning": "1" };
  if (tg?.initData) {
    headers["X-Telegram-Init-Data"] = tg.initData;
  }
  return headers;
}

async function uploadFilesSequentially(files) {
  const fileIds = [];
  const headers = buildUploadHeaders();

  for (let index = 0; index < files.length; index += 1) {
    const formData = new FormData();
    formData.append("files", files[index]);

    const response = await fetch("/api/uploads", {
      method: "POST",
      headers,
      body: formData,
    });

    if (!response.ok) {
      const text = await response.text();
      const base = text || `HTTP ${response.status}`;
      throw new Error(`${base} (file ${index + 1}/${files.length})`);
    }

    const data = await response.json();
    const uploaded = data.file_ids || [];
    if (!uploaded.length || !uploaded[0]) {
      throw new Error(`Invalid upload response (file ${index + 1}/${files.length})`);
    }
    fileIds.push(uploaded[0]);
  }

  return fileIds;
}

function setUploading(isUploading) {
  elements.uploadSpinner.classList.toggle("active", isUploading);
  elements.photos.disabled = isUploading;
  elements.saveAdBtn.disabled = isUploading;
}

function setEditUploading(isUploading) {
  elements.editUploadSpinner.classList.toggle("active", isUploading);
  elements.editPhotos.disabled = isUploading;
  elements.editPublishBtn.disabled = isUploading;
}

function renderPhotoPreviews() {
  elements.photoChips.innerHTML = "";
  elements.photoGrid.innerHTML = "";

  if (state.photoPreviews.length === 0) {
    elements.addMorePhotosBtn.hidden = true;
    return;
  }

  const grid = document.createDocumentFragment();
  state.photoPreviews.forEach((item, index) => {
    const photoItem = document.createElement("div");
    photoItem.className = "photo-item";

    const img = document.createElement("img");
    img.src = item.url;
    img.alt = "photo";

    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "×";
    remove.onclick = (event) => {
      event.preventDefault();
      event.stopPropagation();
      removePhotoAt(index);
    };

    photoItem.append(img, remove);
    grid.appendChild(photoItem);
  });

  elements.photoGrid.appendChild(grid);
  elements.addMorePhotosBtn.hidden = false;
}

function renderEditPhotoPreviews() {
  elements.editPhotoGrid.innerHTML = "";

  if (state.editModal.photoPreviews.length === 0) {
    elements.editAddMorePhotosBtn.hidden = false;
    return;
  }

  const grid = document.createDocumentFragment();
  state.editModal.photoPreviews.forEach((item, index) => {
    const photoItem = document.createElement("div");
    photoItem.className = "photo-item";

    const img = document.createElement("img");
    img.src = item.url;
    img.alt = "photo";

    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "×";
    remove.onclick = (event) => {
      event.preventDefault();
      event.stopPropagation();
      removeEditPhotoAt(index);
    };

    photoItem.append(img, remove);
    grid.appendChild(photoItem);
  });

  elements.editPhotoGrid.appendChild(grid);
  elements.editAddMorePhotosBtn.hidden = false;
}

function removePhotoAt(index) {
  const removed = state.photoPreviews.splice(index, 1)[0];
  state.photoFileIds.splice(index, 1);
  if (removed && removed.source === "local") {
    URL.revokeObjectURL(removed.url);
  }
  renderPhotoPreviews();
}

function removeEditPhotoAt(index) {
  const removed = state.editModal.photoPreviews.splice(index, 1)[0];
  state.editModal.photoFileIds.splice(index, 1);
  if (removed && removed.source === "local") {
    URL.revokeObjectURL(removed.url);
  }
  renderEditPhotoPreviews();
}

async function appendPhotos(files) {
  if (!files.length) {
    return;
  }
  if (state.photoFileIds.length + files.length > 10) {
    throw new Error(t("tooManyPhotos"));
  }
  setBusy(true, t("busyUploading"));
  setUploading(true);
  const prevPreviews = [...state.photoPreviews];
  const prevFileIds = [...state.photoFileIds];
  let newPreviews = [];
  try {
    const startIndex = state.photoPreviews.length;
    newPreviews = files.map((file, idx) => ({
      source: "local",
      url: URL.createObjectURL(file),
      label: `#${startIndex + idx + 1}`,
    }));
    state.photoPreviews = [...state.photoPreviews, ...newPreviews];
    renderPhotoPreviews();
    const newFileIds = await uploadFilesSequentially(files);
    state.photoFileIds = [...state.photoFileIds, ...newFileIds];
  } catch (error) {
    newPreviews.forEach((item) => {
      if (item?.source === "local") {
        URL.revokeObjectURL(item.url);
      }
    });
    state.photoPreviews = prevPreviews;
    state.photoFileIds = prevFileIds;
    renderPhotoPreviews();
    throw error;
  } finally {
    setUploading(false);
    setBusy(false);
  }
}

async function uploadPhotos(files) {
  if (!files.length) {
    return [];
  }
  if (files.length > 10) {
    throw new Error(t("tooManyPhotos"));
  }
  setBusy(true, t("busyUploading"));
  setUploading(true);
  const prevPreviews = [...state.photoPreviews];
  let nextPreviews = [];
  try {
    nextPreviews = files.map((file, idx) => ({
      source: "local",
      url: URL.createObjectURL(file),
      label: `#${idx + 1}`,
    }));
    state.photoPreviews = nextPreviews;
    renderPhotoPreviews();
    return await uploadFilesSequentially(files);
  } catch (error) {
    nextPreviews.forEach((item) => {
      if (item?.source === "local") {
        URL.revokeObjectURL(item.url);
      }
    });
    state.photoPreviews = prevPreviews;
    renderPhotoPreviews();
    throw error;
  } finally {
    setUploading(false);
    setBusy(false);
  }
}

async function appendEditPhotos(files) {
  if (!files.length) {
    return;
  }
  if (state.editModal.photoFileIds.length + files.length > 10) {
    throw new Error(t("tooManyPhotos"));
  }
  setBusy(true, t("busyUploading"));
  setEditUploading(true);
  const prevPreviews = [...state.editModal.photoPreviews];
  const prevFileIds = [...state.editModal.photoFileIds];
  let newPreviews = [];
  try {
    const startIndex = state.editModal.photoPreviews.length;
    newPreviews = files.map((file, idx) => ({
      source: "local",
      url: URL.createObjectURL(file),
      label: `#${startIndex + idx + 1}`,
    }));
    state.editModal.photoPreviews = [...state.editModal.photoPreviews, ...newPreviews];
    renderEditPhotoPreviews();
    const newFileIds = await uploadFilesSequentially(files);
    state.editModal.photoFileIds = [...state.editModal.photoFileIds, ...newFileIds];
  } catch (error) {
    newPreviews.forEach((item) => {
      if (item?.source === "local") {
        URL.revokeObjectURL(item.url);
      }
    });
    state.editModal.photoPreviews = prevPreviews;
    state.editModal.photoFileIds = prevFileIds;
    renderEditPhotoPreviews();
    throw error;
  } finally {
    setEditUploading(false);
    setBusy(false);
  }
}

async function uploadEditPhotos(files) {
  if (!files.length) {
    return [];
  }
  if (files.length > 10) {
    throw new Error(t("tooManyPhotos"));
  }
  setBusy(true, t("busyUploading"));
  setEditUploading(true);
  const prevPreviews = [...state.editModal.photoPreviews];
  let nextPreviews = [];
  try {
    nextPreviews = files.map((file, idx) => ({
      source: "local",
      url: URL.createObjectURL(file),
      label: `#${idx + 1}`,
    }));
    state.editModal.photoPreviews = nextPreviews;
    renderEditPhotoPreviews();
    return await uploadFilesSequentially(files);
  } catch (error) {
    nextPreviews.forEach((item) => {
      if (item?.source === "local") {
        URL.revokeObjectURL(item.url);
      }
    });
    state.editModal.photoPreviews = prevPreviews;
    renderEditPhotoPreviews();
    throw error;
  } finally {
    setEditUploading(false);
    setBusy(false);
  }
}

function handlePhotoInput() {
  const files = Array.from(elements.photos.files || []);
  elements.photos.value = "";
  if (!files.length) return;
  const hasExisting = state.photoFileIds.length > 0;
  const uploader = hasExisting ? appendPhotos : uploadPhotos;
  uploader(files)
    .then((fileIds) => {
      if (!hasExisting) {
        state.photoFileIds = fileIds;
      }
      state.photoPreviews = state.photoPreviews.map((item, idx) => ({
        ...item,
        label: `#${idx + 1}`,
      }));
      renderPhotoPreviews();
    })
    .catch((err) => {
      console.error(err);
      tg?.showAlert?.(err.message || t("uploadFailed"));
      setUploading(false);
    });
}
