function showAdsSkeleton() {
  elements.adsList.innerHTML = "";
  for (let i = 0; i < 3; i++) {
    const card = document.createElement("div");
    card.className = "skeleton-card";
    const photo = document.createElement("div");
    photo.className = "skeleton-photo";
    const body = document.createElement("div");
    body.className = "skeleton-body";
    body.innerHTML = `
      <div class="skeleton-line skeleton-line-full"></div>
      <div class="skeleton-line skeleton-line-mid"></div>
      <div class="skeleton-line skeleton-line-short"></div>
    `;
    card.append(photo, body);
    elements.adsList.appendChild(card);
  }
}

function moveTabIndicator(activeTab) {
  if (!elements.tabIndicator || !activeTab) return;
  elements.tabIndicator.style.width = `${activeTab.offsetWidth}px`;
  elements.tabIndicator.style.transform = `translateX(${activeTab.offsetLeft}px)`;
}

function showTab(tab) {
  const isList = tab === "list";
  const isForm = tab === "form";
  const isSettings = tab === "settings";
  elements.listPanel.hidden = !isList;
  elements.formPanel.hidden = !isForm;
  if (elements.settingsPanel) elements.settingsPanel.hidden = !isSettings;
  elements.tabMyAds.classList.toggle("active", isList);
  elements.tabCreate.classList.toggle("active", isForm);
  if (elements.tabSettings) elements.tabSettings.classList.toggle("active", isSettings);
  moveTabIndicator(isForm ? elements.tabCreate : isSettings ? elements.tabSettings : elements.tabMyAds);
  if (isForm) {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        autoResizeDescription();
      });
    });
  }
}

function setAdType(type) {
  state.adType = type;
  const isAuction = type === "auction";
  if (elements.adTypeFixedBtn) elements.adTypeFixedBtn.classList.toggle("active", !isAuction);
  if (elements.adTypeAuctionBtn) elements.adTypeAuctionBtn.classList.toggle("active", isAuction);
  if (elements.priceSectionWrap) elements.priceSectionWrap.hidden = isAuction;
  if (elements.auctionSection) elements.auctionSection.hidden = !isAuction;
  // Drafts can be saved for auctions too — the end time is set at publish.
  if (elements.saveAdBtn) elements.saveAdBtn.hidden = false;
}

function captureFormSnapshot() {
  return JSON.stringify({
    description: elements.description.value,
    contactInfo: elements.contactInfo.value,
    price: elements.price.value,
    priceInDescription: elements.priceInDescription.checked,
    adType: state.adType,
    photoFileIds: state.photoFileIds,
    auctionStartPrice: elements.auctionStartPrice?.value || "",
    auctionMinStep: elements.auctionMinStep?.value || "",
    auctionBuyout: elements.auctionBuyout?.value || "",
    auctionDuration: elements.auctionDuration?.value || "",
    auctionCurrency: state.auctionCurrency,
  });
}

function isFormDirty() {
  return !elements.formPanel.hidden && captureFormSnapshot() !== state.formSnapshot;
}

function resetForm() {
  state.editingId = null;
  state.adType = "fixed";
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
  if (elements.descToolbar) elements.descToolbar.hidden = true;
  if (elements.formatToggleBtn) elements.formatToggleBtn.classList.remove("active");
  if (elements.auctionStartPrice) elements.auctionStartPrice.value = "";
  if (elements.auctionMinStep) elements.auctionMinStep.value = "";
  if (elements.auctionBuyout) elements.auctionBuyout.value = "";
  if (elements.auctionDuration) elements.auctionDuration.value = "24";
  if (typeof setAuctionCurrency === "function") setAuctionCurrency("RSD");
  setAdType("fixed");
  updateCounts();
  autoResizeDescription();
  updateCharCounter(elements.description, elements.descCounter, 800);
  state.formSnapshot = captureFormSnapshot();
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

function isOlderThanDays(value, days) {
  if (!value || !Number.isFinite(days) || days <= 0) return false;
  const match = String(value).trim().match(/^(\d{2})\.(\d{2})\.(\d{4})/);
  if (!match) return false;
  const day = Number(match[1]);
  const month = Number(match[2]);
  const year = Number(match[3]);
  const published = new Date(year, month - 1, day);
  if (Number.isNaN(published.getTime())) return false;
  const now = new Date();
  const threshold = new Date(now.getFullYear(), now.getMonth(), now.getDate() - days);
  return published < threshold;
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
  elements.adsList.classList.toggle("single-ad", state.ads.length === 1);
  if (!state.ads.length) {
    elements.adsList.appendChild(elements.emptyState);
    elements.emptyState.hidden = false;
    renderCommentsOverview();
    return;
  }
  elements.emptyState.hidden = true;
  state.ads.forEach((ad) => {
    const isExpiredFromChannel = !!ad.is_published && isOlderThanDays(ad.published_at, 30);
    const isAuction = ad.ad_type === "auction";
    // Everything is editable except a closed auction: /api/auctions/{id}/edit
    // rejects anything that isn't active, and republishing a finished lot would
    // put it back in the channel as if it were still up for bids.
    const canEdit = !ad.is_published || !isAuction || ad.auction_status === "active";
    const card = document.createElement("div");
    card.className = "ad-card";
    card.style.position = "relative";
    if (isExpiredFromChannel) {
      card.classList.add("ad-card-expired");
    }

    const openAdEdit = () => {
      haptic("light");
      if (ad.is_published) {
        openEditModal(ad);
      } else {
        startEdit(ad);
      }
    };

    // Tapping a photo is a shortcut to the edit screen; on a card that can't be
    // edited it just opens the photo full-size instead of a doomed edit.
    const onPhotoTap = (fileId) => () => {
      if (canEdit) {
        openAdEdit();
        return;
      }
      haptic("light");
      openAuthedPhotoViewer(`/api/announcements/${ad.id}/photo?file_id=${encodeURIComponent(fileId)}`);
    };

    const photos = Array.isArray(ad.photo_file_ids) ? ad.photo_file_ids : [];
    if (photos.length) {
      card.classList.add("ad-card-media");
    }
    if (photos.length) {
      const gallery = document.createElement("div");
      // Cards show small previews, so ask the server for lightweight thumbnails.
      const thumbUrl = (fileId) => `/api/announcements/${ad.id}/photo?file_id=${encodeURIComponent(fileId)}&size=thumb`;
      const total = photos.length;

      gallery.style.cursor = "pointer";
      if (total === 1) {
        const img = document.createElement("img");
        img.className = "ad-photo";
        img.style.cursor = "pointer";
        img.loading = "lazy";
        setAuthedImage(img, thumbUrl(photos[0]));
        img.alt = ad.description || "photo";
        img.addEventListener("click", onPhotoTap(photos[0]));
        card.appendChild(img);
      } else if (total === 2) {
        gallery.className = "ad-gallery ad-gallery-two";
        photos.slice(0, 2).forEach((fileId) => {
          const img = document.createElement("img");
          img.className = "ad-gallery-img";
          img.loading = "lazy";
          setAuthedImage(img, thumbUrl(fileId));
          img.alt = ad.description || "photo";
          img.addEventListener("click", onPhotoTap(fileId));
          gallery.appendChild(img);
        });
        card.appendChild(gallery);
      } else {
        gallery.className = "ad-gallery ad-gallery-three";
        const top = document.createElement("img");
        top.className = "ad-gallery-img ad-gallery-top";
        top.loading = "lazy";
        setAuthedImage(top, thumbUrl(photos[0]));
        top.alt = ad.description || "photo";
        top.addEventListener("click", onPhotoTap(photos[0]));

        const bottom = document.createElement("div");
        bottom.className = "ad-gallery-bottom";

        photos.slice(1, 3).forEach((fileId) => {
          const img = document.createElement("img");
          img.className = "ad-gallery-img";
          img.loading = "lazy";
          setAuthedImage(img, thumbUrl(fileId));
          img.alt = ad.description || "photo";
          img.addEventListener("click", onPhotoTap(fileId));
          bottom.appendChild(img);
        });

        if (total > 3) {
          const badge = document.createElement("div");
          badge.className = "ad-gallery-count-badge";
          badge.textContent = `+${total - 3}`;
          bottom.appendChild(badge);
        }

        gallery.appendChild(top);
        gallery.appendChild(bottom);
        card.appendChild(gallery);
      }
    }

    const body = document.createElement("div");
    body.className = "ad-body";

    const header = document.createElement("div");
    header.className = "ad-header";
    if (ad.is_published && ad.published_at) {
      const dateTag = document.createElement("span");
      dateTag.className = "ad-date-tag";
      dateTag.textContent = formatPublishedAt(ad.published_at);
      header.appendChild(dateTag);
    }

    const statusTag = document.createElement("span");
    statusTag.className = "ad-status-tag";
    if (isExpiredFromChannel) {
      statusTag.textContent = t("statusRemoved");
      statusTag.classList.add("is-removed");
    } else if (!ad.is_published) {
      statusTag.textContent = t("statusDraft");
      statusTag.classList.add("is-draft");
    } else if (isAuction && ad.auction_status === "finished") {
      statusTag.textContent = t("statusAuctionFinished");
      statusTag.classList.add("is-auction-finished");
    } else if (isAuction && ad.auction_status === "active") {
      statusTag.textContent = t("statusAuctionActive");
      statusTag.classList.add("is-auction-active");
    } else if (ad.is_reserved) {
      statusTag.textContent = t("statusReserved");
      statusTag.classList.add("is-reserved");
    } else if (ad.is_updated) {
      statusTag.textContent = t("statusUpdated");
      statusTag.classList.add("is-updated");
    } else {
      statusTag.textContent = t("statusPublished");
      statusTag.classList.add("is-published");
    }
    header.appendChild(statusTag);

    const title = document.createElement("h3");
    title.className = "ad-description ad-description-clamped";
    title.innerHTML = renderStyledText(ad.description || t("noAds"));

    let meta;
    if (isAuction) {
      meta = document.createElement("div");
      meta.className = "ad-auction-info";

      const addBidRow = (label, value, valueClass) => {
        const row = document.createElement("div");
        row.className = "ad-auction-row";
        const lbl = document.createElement("span");
        lbl.className = "ad-auction-label";
        lbl.textContent = label;
        const val = document.createElement("span");
        val.className = "ad-auction-value" + (valueClass ? ` ${valueClass}` : "");
        val.textContent = value;
        row.append(lbl, val);
        meta.appendChild(row);
      };

      const adCur = ad.currency || "RSD";
      if (ad.auction_status === "finished") {
        if (ad.current_price != null) {
          addBidRow(`${t("auctionCurrentBid")}:`, formatMoney(ad.current_price, adCur));
        }
        if (ad.winner_username) {
          addBidRow(`${t("auctionWinner")}:`, ad.winner_username);
        } else {
          addBidRow("", t("auctionNoBids"), "ad-auction-no-bids");
        }
      } else {
        if (ad.current_price != null) {
          addBidRow(`${t("auctionCurrentBid")}:`, formatMoney(ad.current_price, adCur), "ad-auction-current");
        } else {
          addBidRow(`${t("auctionStartPrice") || "Старт"}:`, ad.start_price != null ? formatMoney(ad.start_price, adCur) : "—");
          const noBids = document.createElement("div");
          noBids.className = "ad-auction-nobids";
          noBids.textContent = t("auctionNoBids");
          meta.appendChild(noBids);
        }
        if (ad.buyout_price != null) {
          addBidRow(`${t("auctionBuyoutRow")}:`, formatMoney(ad.buyout_price, adCur));
        }
        if (ad.bids_count > 0) {
          addBidRow(`${t("auctionBidsCount")}:`, String(ad.bids_count));
        }
        if (ad.auction_end_at) {
          addBidRow(`${t("auctionEndAt")}:`, formatAuctionEnd(ad.auction_end_at));
        }
      }
    } else if (ad.price_in_description || (ad.price || "").trim()) {
      meta = document.createElement("div");
      meta.className = "ad-meta ad-price";

      const priceLabel = document.createElement("span");
      priceLabel.className = "ad-price-label";
      priceLabel.textContent = t("price");

      const priceValue = document.createElement("span");
      priceValue.className = "ad-price-value";
      priceValue.textContent = ad.price_in_description ? t("priceInDescriptionValue") : ad.price;

      meta.append(priceLabel, priceValue);
    } else {
      // Draft without a price yet — don't render an empty price block.
      meta = null;
    }

    const removedNote = document.createElement("div");
    removedNote.className = "ad-removed-note";
    removedNote.textContent = t("removedFromChannel");

    // Consistent action layout on every card: one row with text actions
    // stretching on the left and fixed-size icon buttons pinned to the
    // right; the icon bar wraps below only when the row runs out of room.
    // Per-type button sets: drafts keep publish/edit/delete; published ads and
    // running auctions get the pencil too, since tapping the photo is a
    // shortcut nobody discovers on its own.
    const actions = document.createElement("div");
    actions.className = "ad-actions";
    const actionsMain = document.createElement("div");
    actionsMain.className = "ad-actions-main";
    const actionsBar = document.createElement("div");
    actionsBar.className = "ad-actions-bar";

    if (canEdit) {
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
      editBtn.onclick = openAdEdit;
      actionsBar.appendChild(editBtn);
    }

    if (!ad.is_published) {
      const publishBtn = document.createElement("button");
      publishBtn.className = "primary ad-action ad-action-main";
      publishBtn.type = "button";
      publishBtn.textContent = t("publish");
      publishBtn.onclick = () => { haptic("medium"); void publishAd(ad.id); };
      actionsMain.appendChild(publishBtn);
    }

    if (ad.is_published && !isExpiredFromChannel && !isAuction) {
      const reserveBtn = document.createElement("button");
      reserveBtn.className = "ghost ad-action ad-action-main ad-action-reserve";
      reserveBtn.type = "button";
      reserveBtn.textContent = t(ad.is_reserved ? "unreserve" : "reserve");
      reserveBtn.onclick = () => { haptic("light"); reserveAd(ad.id, !!ad.is_reserved); };
      actionsMain.appendChild(reserveBtn);
    }

    if (ad.is_published && isAuction) {
      const bidsBtn = document.createElement("button");
      bidsBtn.className = "ghost ad-action ad-action-main";
      bidsBtn.type = "button";
      bidsBtn.textContent = t("viewBids");
      bidsBtn.onclick = () => { haptic("light"); void openBidsScreen(ad.id); };
      actionsMain.appendChild(bidsBtn);
    }

    if (ad.is_published && isAuction && ad.auction_status === "active") {
      const stopBtn = document.createElement("button");
      stopBtn.className = "ghost ad-action ad-action-main ad-action-stop";
      stopBtn.type = "button";
      stopBtn.textContent = t("stopAuction");
      stopBtn.onclick = () => {
        haptic("light");
        const doStop = async () => {
          setBusy(true, t("busyStoppingAuction"));
          try {
            await stopAuction(ad.id);
            showToast(t("auctionStoppedToast"), "success");
            await refreshAds();
          } catch (err) {
            openErrorModal(err?.message || t("loadFailed"));
          } finally {
            setBusy(false);
          }
        };
        if (tg?.showConfirm) {
          tg.showConfirm(t("stopAuctionConfirm"), (ok) => { if (ok) void doStop(); });
        } else if (window.confirm(t("stopAuctionConfirm"))) {
          void doStop();
        }
      };
      actionsMain.appendChild(stopBtn);
    }

    const commentsCount = Number(ad.comments_count) || 0;
    if (ad.is_published && !isAuction && ad.post_link && commentsCount > 0 && !isExpiredFromChannel) {
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
      actionsBar.appendChild(commentsBtn);
    }

    // Active auctions can't be deleted — the trash icon appears only once
    // the auction is over (or the post has already left the channel).
    const canDelete =
      !ad.is_published ||
      !isAuction ||
      ad.auction_status === "finished" ||
      isExpiredFromChannel;
    if (canDelete) {
      const deleteBtn = document.createElement("button");
      deleteBtn.className = "ghost ad-action ad-action-icon ad-action-delete";
      deleteBtn.type = "button";
      deleteBtn.setAttribute("aria-label", t("delete"));
      deleteBtn.title = t("delete");
      deleteBtn.innerHTML = `
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <path d="M9 4h6l1 2h4v2H4V6h4l1-2z"></path>
          <path d="M6 8h12l-1 12H7L6 8z"></path>
        </svg>
      `;
      deleteBtn.onclick = () => { haptic("light"); openDeleteConfirm(ad.id); };
      actionsBar.appendChild(deleteBtn);
    }

    if (actionsMain.childElementCount) {
      actions.appendChild(actionsMain);
    }
    if (actionsBar.childElementCount) {
      actions.appendChild(actionsBar);
    }

    const readMoreBtn = document.createElement("button");
    readMoreBtn.className = "ad-read-more-btn";
    readMoreBtn.type = "button";
    readMoreBtn.textContent = t("readMore");
    readMoreBtn.hidden = true;
    readMoreBtn.onclick = () => {
      const nowClamped = !title.classList.contains("ad-description-clamped");
      title.classList.toggle("ad-description-clamped", nowClamped);
      card.classList.toggle("ad-card-desc-expanded", !nowClamped);
      readMoreBtn.textContent = nowClamped ? t("readMore") : t("readLess");
    };

    if (isExpiredFromChannel) {
      body.append(...[title, readMoreBtn, meta, removedNote, actions].filter(Boolean));
    } else {
      body.append(...[title, readMoreBtn, meta, actions].filter(Boolean));
    }
    card.append(header, body);
    elements.adsList.appendChild(card);

    // Reveal "read more" only once we know the clamp actually truncates this text.
    if (title.scrollHeight > title.clientHeight + 1) {
      readMoreBtn.hidden = false;
    }
  });
  renderCommentsOverview();
}

function startEdit(ad) {
  state.editingId = ad.id;
  state.photoFileIds = ad.photo_file_ids || [];
  state.photoPreviews = (ad.photo_file_ids || []).map((fileId, idx) => {
    const base = `/api/announcements/${ad.id}/photo?file_id=${encodeURIComponent(fileId)}`;
    return {
      source: "remote",
      url: `${base}&size=thumb`,
      fullUrl: base,
      label: `#${idx + 1}`,
    };
  });
  elements.description.value = ad.description || "";
  elements.contactInfo.value = ad.contact_info || "";

  const isAuction = ad.ad_type === "auction";
  setAdType(isAuction ? "auction" : "fixed");

  if (isAuction) {
    if (elements.auctionStartPrice) elements.auctionStartPrice.value = ad.start_price || "";
    if (elements.auctionMinStep) elements.auctionMinStep.value = ad.min_step || "";
    if (elements.auctionBuyout) elements.auctionBuyout.value = ad.buyout_price || "";
    if (elements.auctionDuration && ad.auction_duration_hours) {
      elements.auctionDuration.value = String(ad.auction_duration_hours);
    }
    if (typeof setAuctionCurrency === "function") setAuctionCurrency(ad.currency || "RSD");
  } else {
    elements.price.value = ad.price || "";
    elements.priceInDescription.checked = !!ad.price_in_description;
    applyPriceInDescriptionToggle(elements.priceInDescription, elements.price, elements.priceField);
  }

  elements.saveAdBtn.hidden = !!ad.is_published;
  renderPhotoPreviews();
  updateCharCounter(elements.description, elements.descCounter, 800);
  showTab("form");
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      autoResizeDescription();
    });
  });
  updateCounts();
  state.formSnapshot = captureFormSnapshot();
}
