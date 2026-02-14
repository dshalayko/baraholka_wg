function hexToRgb(hex) {
  if (!hex) return null;
  const value = hex.replace("#", "");
  if (value.length !== 6) return null;
  const r = parseInt(value.slice(0, 2), 16);
  const g = parseInt(value.slice(2, 4), 16);
  const b = parseInt(value.slice(4, 6), 16);
  return { r, g, b };
}

function isLightColor(hex) {
  const rgb = hexToRgb(hex);
  if (!rgb) return false;
  const { r, g, b } = rgb;
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.6;
}

function applyTelegramTheme() {
  if (!tg?.themeParams) return false;
  const p = tg.themeParams;
  const root = document.documentElement.style;
  const bg = p.bg_color || "#ffffff";
  const isLight = isLightColor(bg);
  const secondary = p.secondary_bg_color || (isLightColor(bg) ? "#ffffff" : "#1a1f2b");
  const text = p.text_color || (isLightColor(bg) ? "#101418" : "#f3f5f7");
  const hint = p.hint_color || (isLightColor(bg) ? "rgba(16,20,24,0.5)" : "rgba(243,245,247,0.62)");
  const link = p.link_color || (isLightColor(bg) ? "#1a73e8" : "#5aa7ff");
  const button = p.button_color || (isLightColor(bg) ? "#2481cc" : "#3f8cff");
  const buttonText = p.button_text_color || "#ffffff";
  const border = isLightColor(bg) ? "rgba(16,20,24,0.08)" : "rgba(255,255,255,0.12)";

  root.setProperty("--bg", bg);
  root.setProperty("--secondary-bg", secondary);
  root.setProperty("--ink", text);
  root.setProperty("--muted", hint);
  root.setProperty("--meta-text", isLight ? "#000000" : "rgba(243, 247, 252, 0.86)");
  root.setProperty("--link", link);
  root.setProperty("--button", button);
  root.setProperty("--button-text", buttonText);
  root.setProperty("--border", border);
  document.documentElement.dataset.theme = isLight ? "light" : "dark";
  return true;
}

function autoResizeTextarea(textarea) {
  if (!textarea) return;
  textarea.style.height = "auto";
  textarea.style.height = `${textarea.scrollHeight}px`;
}

function autoResizeDescription() {
  autoResizeTextarea(elements.description);
}

function wrapSelection(textarea, prefix, suffix = prefix) {
  if (!textarea) return;
  const start = textarea.selectionStart ?? 0;
  const end = textarea.selectionEnd ?? start;
  const value = textarea.value || "";
  const selected = value.slice(start, end);
  const left = value.slice(0, start);
  const right = value.slice(end);

  if (!selected) {
    textarea.value = `${left}${prefix}${suffix}${right}`;
    const caret = start + prefix.length;
    textarea.setSelectionRange(caret, caret);
  } else {
    textarea.value = `${left}${prefix}${selected}${suffix}${right}`;
    textarea.setSelectionRange(start + prefix.length, end + prefix.length);
  }

  textarea.focus();
  textarea.dispatchEvent(new Event("input", { bubbles: true }));
}

function renderStyledText(text) {
  const source = String(text || "");
  const escaped = source
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  return escaped
    .replace(/\*\*(.+?)\*\*/gs, "<strong>$1</strong>")
    .replace(/_(.+?)_/gs, "<em>$1</em>")
    .replace(/~~(.+?)~~/gs, "<s>$1</s>")
    .replace(/\n/g, "<br>");
}

function setFieldInvalid(input, isInvalid) {
  if (!input) return;
  input.classList.toggle("field-invalid", isInvalid);
  if (isInvalid) {
    input.setAttribute("aria-invalid", "true");
  } else {
    input.removeAttribute("aria-invalid");
  }
}

function applyContactFieldVisibility() {
  if (state.hasUsername) {
    if (elements.contactField) {
      elements.contactField.hidden = true;
      elements.contactField.style.display = "none";
    }
    if (elements.editContactField) {
      elements.editContactField.hidden = true;
      elements.editContactField.style.display = "none";
    }
    if (elements.contactInfo) {
      elements.contactInfo.value = "";
    }
    if (elements.editContactInfo) {
      elements.editContactInfo.value = "";
    }
  } else {
    if (elements.contactField) {
      elements.contactField.hidden = false;
      elements.contactField.style.display = "";
    }
    if (elements.editContactField) {
      elements.editContactField.hidden = false;
      elements.editContactField.style.display = "";
    }
  }
}

function applyPriceInDescriptionToggle(checkbox, input, field) {
  if (!checkbox || !input) return;
  input.disabled = checkbox.checked;
  if (field) {
    field.hidden = checkbox.checked;
    field.style.display = checkbox.checked ? "none" : "";
  }
  if (checkbox.checked) {
    input.value = "";
    setFieldInvalid(input, false);
  }
}

function validateAdForm({
  description,
  price,
  priceInDescription,
  contactInfo,
  requireContact,
  descriptionInput,
  priceInput,
  contactInput,
}) {
  const hasDescription = !!description.trim();
  const hasPrice = priceInDescription || !!price.trim();
  const hasContact = !requireContact || !!(contactInfo || "").trim();
  setFieldInvalid(descriptionInput, !hasDescription);
  setFieldInvalid(priceInput, !hasPrice && !priceInDescription);
  setFieldInvalid(contactInput, !hasContact);
  return hasDescription && hasPrice && hasContact;
}

function formatPublishedAt(value) {
  if (!value) return "";
  const match = String(value).match(/^(\d{2})\.(\d{2})\.(\d{4}) (\d{2}:\d{2})$/);
  if (!match) return value;
  return `${match[1]}.${match[2]}.${match[3]}, ${match[4]}`;
}

function showToast(message, variant = "info") {
  const toast = document.createElement("div");
  toast.className = `toast toast-${variant}`;
  toast.textContent = message;
  elements.toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.remove();
  }, 3000);
}

function setBusy(isBusy, text = "") {
  if (isBusy) {
    state.busyCount += 1;
  } else {
    state.busyCount = Math.max(0, state.busyCount - 1);
  }
  const active = state.busyCount > 0;
  elements.busyOverlay.hidden = !active;
  elements.busyOverlay.style.display = active ? "flex" : "none";
  if (text) {
    elements.busyText.textContent = text;
  }
  document.querySelectorAll("button, input, textarea, select").forEach((el) => {
    if (el === elements.settingsToggle) return;
    el.disabled = active;
  });
}

function setUnauthorizedMode(enabled) {
  state.unauthorized = !!enabled;
  if (elements.authorizedContent) {
    elements.authorizedContent.hidden = state.unauthorized;
  }
  if (elements.unauthorizedState) {
    elements.unauthorizedState.hidden = !state.unauthorized;
  }
  if (state.unauthorized) {
    closeDeleteConfirm();
    closeEditModal();
    closeErrorModal();
  }
}

function isDarkTheme() {
  return document.documentElement.dataset.theme === "dark";
}

function applyTheme(theme) {
  const root = document.documentElement.style;
  [
    "--bg",
    "--secondary-bg",
    "--ink",
    "--muted",
    "--meta-text",
    "--link",
    "--button",
    "--button-text",
    "--border",
  ].forEach((prop) => root.removeProperty(prop));
  document.documentElement.dataset.theme = theme;
  if (tg?.themeParams) {
    tg.setBackgroundColor?.(tg.themeParams.bg_color || (theme === "dark" ? "#0f1116" : "#f2f5f9"));
  }
  applyTranslations();
}

function toggleTheme() {
  const next = isDarkTheme() ? "light" : "dark";
  localStorage.setItem("theme", next);
  applyTheme(next);
}

function setTheme(theme) {
  if (theme !== "light" && theme !== "dark") return;
  localStorage.setItem("theme", theme);
  applyTheme(theme);
}

function initTheme() {
  const saved = localStorage.getItem("theme");
  if (saved === "light" || saved === "dark") {
    applyTheme(saved);
    return;
  }
  if (applyTelegramTheme()) {
    tg?.setBackgroundColor?.(tg.themeParams.bg_color || "#ffffff");
    tg?.onEvent?.("themeChanged", () => {
      if (localStorage.getItem("theme")) return;
      applyTelegramTheme();
      applyTranslations();
    });
    return;
  }
  if (tg?.colorScheme === "light") {
    applyTheme("light");
  } else {
    applyTheme("dark");
  }
}
