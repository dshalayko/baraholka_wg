function showTab(tab) {
  const isList = tab === "list";
  elements.listPanel.hidden = !isList;
  elements.formPanel.hidden = isList;
  elements.tabMyAds.classList.toggle("active", isList);
  elements.tabCreate.classList.toggle("active", !isList);
  if (!isList) {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        autoResizeDescription();
      });
    });
  }
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

function formatCommentsCount(value) {
  const count = Number(value);
  if (!Number.isFinite(count) || count <= 0) return "0";
  if (count > 99) return "99+";
  return String(count);
}

function buildCommentsLink(postLink) {
  if (!postLink) return "";
  const separator = postLink.includes("?") ? "&" : "?";
  return `${postLink}${separator}comment=1`;
}

function getAdCommentsCount(ad) {
  const count = Number(ad?.comments_count);
  return Number.isFinite(count) && count > 0 ? count : 0;
}

function getAdsWithComments() {
  return (state.ads || [])
    .filter((ad) => ad?.is_published && ad?.post_link && getAdCommentsCount(ad) > 0)
    .sort((a, b) => {
      const byCount = getAdCommentsCount(b) - getAdCommentsCount(a);
      if (byCount !== 0) return byCount;
      return (b.id || 0) - (a.id || 0);
    });
}

function toShortDescription(value) {
  const raw = String(value || "")
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/_(.*?)_/g, "$1")
    .replace(/~~(.*?)~~/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
  if (!raw) return t("noAds");
  if (raw.length <= 78) return raw;
  return `${raw.slice(0, 75).trim()}...`;
}

function renderCommentsOverview() {
  const commentedAds = getAdsWithComments();
  const totalComments = commentedAds.reduce((sum, ad) => sum + getAdCommentsCount(ad), 0);

  elements.commentsTotalBadge.hidden = totalComments <= 0;
  elements.commentsTotalBadge.textContent = formatCommentsCount(totalComments);

  elements.commentsOverviewList.innerHTML = "";
  if (!commentedAds.length) {
    const empty = document.createElement("div");
    empty.className = "comments-overview-empty";
    empty.textContent = t("commentsOverviewEmpty");
    elements.commentsOverviewList.appendChild(empty);
    return;
  }

  commentedAds.forEach((ad) => {
    const commentsCount = getAdCommentsCount(ad);
    const row = document.createElement("div");
    row.className = "comments-overview-item";

    const textWrap = document.createElement("div");
    textWrap.className = "comments-overview-text";

    const desc = document.createElement("div");
    desc.className = "comments-overview-desc";
    desc.textContent = toShortDescription(ad.description);

    const meta = document.createElement("div");
    meta.className = "comments-overview-meta";
    meta.textContent = `${t("comments")}: ${commentsCount}`;
    textWrap.append(desc, meta);

    const viewBtn = document.createElement("button");
    viewBtn.className = "ghost comments-overview-open";
    viewBtn.type = "button";
    viewBtn.textContent = t("viewComments");
    viewBtn.setAttribute("data-comments-link", buildCommentsLink(ad.post_link) || ad.post_link);

    row.append(textWrap, viewBtn);
    elements.commentsOverviewList.appendChild(row);
  });
}

function renderAds() {
  elements.adsList.innerHTML = "";
  if (!state.ads.length) {
    elements.adsList.appendChild(elements.emptyState);
    elements.emptyState.hidden = false;
    renderCommentsOverview();
    return;
  }
  elements.emptyState.hidden = true;
  state.ads.forEach((ad) => {
    const card = document.createElement("div");
    card.className = "ad-card";
    card.style.position = "relative";

    const photos = Array.isArray(ad.photo_file_ids) ? ad.photo_file_ids : [];
    if (photos.length) {
      card.classList.add("ad-card-media");
    }
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

    const body = document.createElement("div");
    body.className = "ad-body";
    if (!photos.length) {
      body.style.paddingTop = "44px";
    }

    const header = document.createElement("div");
    header.className = "ad-header";
    header.style.position = "absolute";
    header.style.top = "10px";
    header.style.right = "10px";
    header.style.zIndex = "4";
    header.style.pointerEvents = "none";

    const statusTag = document.createElement("span");
    statusTag.className = "ad-status-tag";
    if (!ad.is_published) {
      statusTag.textContent = t("statusDraft");
      statusTag.classList.add("is-draft");
    } else if (ad.is_updated) {
      statusTag.textContent = t("statusUpdated");
      statusTag.classList.add("is-updated");
    } else {
      statusTag.textContent = t("statusPublished");
      statusTag.classList.add("is-published");
    }
    header.appendChild(statusTag);

    const title = document.createElement("h3");
    title.className = "ad-description";
    title.innerHTML = renderStyledText(ad.description || t("noAds"));

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
    status.className = "ad-meta ad-timestamp";
    if (!ad.is_published) {
      status.textContent = t("draft");
    } else if (ad.is_updated) {
      status.textContent = `${t("editedAt")} ${formatPublishedAt(ad.published_at)}`.trim();
    } else {
      status.textContent = `${t("publishedAt")} ${formatPublishedAt(ad.published_at)}`.trim();
    }

    const actions = document.createElement("div");
    actions.className = "ad-actions";

    const editBtn = document.createElement("button");
    editBtn.className = "ghost ad-action ad-action-icon";
    editBtn.type = "button";
    editBtn.setAttribute("aria-label", t("edit"));
    editBtn.title = t("edit");
    editBtn.innerHTML = `
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M4 20h4l10.5-10.5a1.4 1.4 0 0 0 0-2L16.5 5.5a1.4 1.4 0 0 0-2 0L4 16v4zM13.8 7.2l3 3"></path>
      </svg>
    `;
    editBtn.onclick = () => {
      if (ad.is_published) {
        openEditModal(ad);
      } else {
        startEdit(ad);
      }
    };
    actions.appendChild(editBtn);

    if (!ad.is_published) {
      const publishBtn = document.createElement("button");
      publishBtn.className = "primary ad-action ad-action-main";
      publishBtn.type = "button";
      publishBtn.textContent = t("publish");
      publishBtn.onclick = () => publishAd(ad.id);
      actions.appendChild(publishBtn);
    }

    if (ad.post_link) {
      const openBtn = document.createElement("button");
      openBtn.className = "ad-open ad-action ad-action-main";
      openBtn.type = "button";
      openBtn.textContent = t("open");
      openBtn.onclick = () => tg?.openTelegramLink?.(ad.post_link);
      actions.appendChild(openBtn);
    }

    const commentsCount = Number(ad.comments_count) || 0;
    if (ad.is_published && ad.post_link && commentsCount > 0) {
      const commentsBtn = document.createElement("button");
      commentsBtn.className = "ghost ad-action ad-action-icon ad-action-comments";
      commentsBtn.type = "button";
      commentsBtn.setAttribute("aria-label", `${t("comments")} (${commentsCount})`);
      commentsBtn.title = `${t("comments")}: ${commentsCount}`;
      commentsBtn.innerHTML = `
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <path d="M6 18l-3 3V6a3 3 0 0 1 3-3h12a3 3 0 0 1 3 3v9a3 3 0 0 1-3 3H6z"></path>
          <path d="M8 9h8M8 13h6"></path>
        </svg>
        <span class="ad-action-badge">${formatCommentsCount(commentsCount)}</span>
      `;
      commentsBtn.onclick = () => {
        const commentsLink = buildCommentsLink(ad.post_link);
        void trackEvent("open_comments");
        tg?.openTelegramLink?.(commentsLink || ad.post_link);
      };
      actions.appendChild(commentsBtn);
    }

    const deleteBtn = document.createElement("button");
    deleteBtn.className = "danger ad-action ad-action-icon ad-action-delete";
    deleteBtn.type = "button";
    deleteBtn.setAttribute("aria-label", t("delete"));
    deleteBtn.title = t("delete");
    deleteBtn.innerHTML = `
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M9 4h6l1 2h4v2H4V6h4l1-2z"></path>
        <path d="M6 8h12l-1 12H7L6 8z"></path>
      </svg>
    `;
    deleteBtn.onclick = () => openDeleteConfirm(ad.id);
    actions.appendChild(deleteBtn);

    body.append(title, meta, status, actions);
    card.append(header, body);
    elements.adsList.appendChild(card);
  });
  renderCommentsOverview();
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
  renderPhotoPreviews();
  showTab("form");
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      autoResizeDescription();
    });
  });
  updateCounts();
}
