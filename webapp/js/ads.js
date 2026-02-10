function showTab(tab) {
  const isList = tab === "list";
  elements.listPanel.hidden = !isList;
  elements.formPanel.hidden = isList;
  elements.tabMyAds.classList.toggle("active", isList);
  elements.tabCreate.classList.toggle("active", !isList);
}

function resetForm() {
  state.editingId = null;
  state.photoFileIds = [];
  state.photoPreviews.forEach((item) => {
    if (item.source === "local") {
      URL.revokeObjectURL(item.url);
    }
  });
  state.photoPreviews = [];
  elements.description.value = "";
  elements.contactInfo.value = "";
  elements.price.value = "";
  elements.priceInDescription.checked = false;
  applyPriceInDescriptionToggle(elements.priceInDescription, elements.price, elements.priceField);
  elements.photos.value = "";
  elements.photoChips.innerHTML = "";
  elements.photoGrid.innerHTML = "";
  elements.saveAdBtn.hidden = false;
  updateCounts();
  autoResizeDescription();
}

function updatePreview() {}

function renderAds() {
  elements.adsList.innerHTML = "";
  if (!state.ads.length) {
    elements.adsList.appendChild(elements.emptyState);
    elements.emptyState.hidden = false;
    return;
  }
  elements.emptyState.hidden = true;
  state.ads.forEach((ad) => {
    const card = document.createElement("div");
    card.className = "ad-card";

    const photos = Array.isArray(ad.photo_file_ids) ? ad.photo_file_ids : [];
    if (photos.length && tg?.initData) {
      const gallery = document.createElement("div");
      const initData = encodeURIComponent(tg.initData);
      const total = photos.length;

      if (total === 1) {
        const img = document.createElement("img");
        img.className = "ad-photo";
        const fileId = photos[0];
        img.src = `/api/announcements/${ad.id}/photo?file_id=${encodeURIComponent(fileId)}&initData=${initData}`;
        img.alt = ad.description || "photo";
        card.appendChild(img);
      } else if (total === 2) {
        gallery.className = "ad-gallery ad-gallery-two";
        photos.slice(0, 2).forEach((fileId) => {
          const img = document.createElement("img");
          img.className = "ad-gallery-img";
          img.src = `/api/announcements/${ad.id}/photo?file_id=${encodeURIComponent(fileId)}&initData=${initData}`;
          img.alt = ad.description || "photo";
          gallery.appendChild(img);
        });
        card.appendChild(gallery);
      } else {
        gallery.className = "ad-gallery ad-gallery-three";
        const top = document.createElement("img");
        top.className = "ad-gallery-img ad-gallery-top";
        top.src = `/api/announcements/${ad.id}/photo?file_id=${encodeURIComponent(photos[0])}&initData=${initData}`;
        top.alt = ad.description || "photo";

        const bottom = document.createElement("div");
        bottom.className = "ad-gallery-bottom";

        photos.slice(1, 3).forEach((fileId) => {
          const img = document.createElement("img");
          img.className = "ad-gallery-img";
          img.src = `/api/announcements/${ad.id}/photo?file_id=${encodeURIComponent(fileId)}&initData=${initData}`;
          img.alt = ad.description || "photo";
          bottom.appendChild(img);
        });

        gallery.appendChild(top);
        gallery.appendChild(bottom);
        card.appendChild(gallery);
      }
    }

    const title = document.createElement("h3");
    title.className = "ad-description";
    title.textContent = ad.description || "(no description)";

    const meta = document.createElement("div");
    meta.className = "ad-meta ad-price";

    const priceLabel = document.createElement("span");
    priceLabel.className = "ad-price-label";
    priceLabel.textContent = t("price");

    const priceValue = document.createElement("span");
    priceValue.className = "ad-price-value";
    priceValue.textContent = ad.price_in_description ? t("priceInDescriptionValue") : (ad.price || "");

    meta.append(priceLabel, priceValue);

    const status = document.createElement("div");
    status.className = "ad-meta";
    if (!ad.is_published) {
      status.textContent = t("draft");
    } else if (ad.is_updated) {
      status.textContent = `${t("editedAt")} ${formatPublishedAt(ad.published_at)}`.trim();
    } else {
      status.textContent = `${t("publishedAt")} ${formatPublishedAt(ad.published_at)}`.trim();
    }

    if (!ad.is_published) {
      const publishBtn = document.createElement("button");
      publishBtn.className = "primary ad-center";
      publishBtn.textContent = t("publish");
      publishBtn.onclick = () => publishAd(ad.id);
      card.append(publishBtn);
    }

    if (ad.post_link) {
      const openBtn = document.createElement("button");
      openBtn.className = "ad-open ad-center";
      openBtn.textContent = t("open");
      openBtn.onclick = () => tg?.openTelegramLink?.(ad.post_link);
      card.append(openBtn);
    }

    const deleteBtn = document.createElement("button");
    deleteBtn.className = "ad-delete";
    deleteBtn.type = "button";
    deleteBtn.setAttribute("aria-label", t("delete"));
    deleteBtn.innerHTML = `
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M9 3h6l1 2h4v2H4V5h4l1-2zm1 7h2v8h-2v-8zm4 0h2v8h-2v-8zM7 8h10l-1 12H8L7 8z"></path>
      </svg>
    `;
    deleteBtn.onclick = () => openDeleteConfirm(ad.id);

    const editBtn = document.createElement("button");
    editBtn.className = "ad-edit";
    editBtn.type = "button";
    editBtn.setAttribute("aria-label", t("edit"));
    editBtn.innerHTML = `
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M3 17.25V21h3.75l11-11-3.75-3.75-11 11zM20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"></path>
      </svg>
    `;
    editBtn.onclick = () => {
      if (ad.is_published) {
        openEditModal(ad);
      } else {
        startEdit(ad);
      }
    };

    card.append(title, meta, status, editBtn, deleteBtn);
    elements.adsList.appendChild(card);
  });
}

function startEdit(ad) {
  state.editingId = ad.id;
  state.photoFileIds = ad.photo_file_ids || [];
  state.photoPreviews = (ad.photo_file_ids || []).map((fileId, idx) => {
    const initData = encodeURIComponent(tg?.initData || "");
    return {
      source: "remote",
      url: `/api/announcements/${ad.id}/photo?file_id=${encodeURIComponent(fileId)}&initData=${initData}`,
      label: `#${idx + 1}`,
    };
  });
  elements.description.value = ad.description || "";
  elements.contactInfo.value = ad.contact_info || "";
  elements.price.value = ad.price || "";
  elements.priceInDescription.checked = !!ad.price_in_description;
  applyPriceInDescriptionToggle(elements.priceInDescription, elements.price, elements.priceField);
  elements.saveAdBtn.hidden = !!ad.is_published;
  autoResizeDescription();
  renderPhotoPreviews();
  showTab("form");
  updateCounts();
}
