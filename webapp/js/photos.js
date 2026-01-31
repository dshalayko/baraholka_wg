function updateCounts() {
  // Counters removed from UI; keep placeholder for future metrics if needed.
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
  try {
    const startIndex = state.photoPreviews.length;
    const newPreviews = files.map((file, idx) => ({
      source: "local",
      url: URL.createObjectURL(file),
      label: `#${startIndex + idx + 1}`,
    }));
    state.photoPreviews = [...state.photoPreviews, ...newPreviews];
    renderPhotoPreviews();
    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));
    const headers = {};
    headers["ngrok-skip-browser-warning"] = "1";
    if (tg?.initData) {
      headers["X-Telegram-Init-Data"] = tg.initData;
    }
    const response = await fetch("/api/uploads", {
      method: "POST",
      headers,
      body: formData,
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `HTTP ${response.status}`);
    }
    const data = await response.json();
    const newFileIds = data.file_ids || [];
    state.photoFileIds = [...state.photoFileIds, ...newFileIds];
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
  try {
    state.photoPreviews = files.map((file, idx) => ({
      source: "local",
      url: URL.createObjectURL(file),
      label: `#${idx + 1}`,
    }));
    renderPhotoPreviews();
    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));
    const headers = {};
    headers["ngrok-skip-browser-warning"] = "1";
    if (tg?.initData) {
      headers["X-Telegram-Init-Data"] = tg.initData;
    }
    const response = await fetch("/api/uploads", {
      method: "POST",
      headers,
      body: formData,
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `HTTP ${response.status}`);
    }
    const data = await response.json();
    return data.file_ids || [];
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
  try {
    const startIndex = state.editModal.photoPreviews.length;
    const newPreviews = files.map((file, idx) => ({
      source: "local",
      url: URL.createObjectURL(file),
      label: `#${startIndex + idx + 1}`,
    }));
    state.editModal.photoPreviews = [...state.editModal.photoPreviews, ...newPreviews];
    renderEditPhotoPreviews();
    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));
    const headers = {};
    headers["ngrok-skip-browser-warning"] = "1";
    if (tg?.initData) {
      headers["X-Telegram-Init-Data"] = tg.initData;
    }
    const response = await fetch("/api/uploads", {
      method: "POST",
      headers,
      body: formData,
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `HTTP ${response.status}`);
    }
    const data = await response.json();
    const newFileIds = data.file_ids || [];
    state.editModal.photoFileIds = [...state.editModal.photoFileIds, ...newFileIds];
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
  try {
    state.editModal.photoPreviews = files.map((file, idx) => ({
      source: "local",
      url: URL.createObjectURL(file),
      label: `#${idx + 1}`,
    }));
    renderEditPhotoPreviews();
    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));
    const headers = {};
    headers["ngrok-skip-browser-warning"] = "1";
    if (tg?.initData) {
      headers["X-Telegram-Init-Data"] = tg.initData;
    }
    const response = await fetch("/api/uploads", {
      method: "POST",
      headers,
      body: formData,
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `HTTP ${response.status}`);
    }
    const data = await response.json();
    return data.file_ids || [];
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
