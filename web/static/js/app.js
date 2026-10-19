/**
 * Joy-Con(L) 設定UI クライアントスクリプト。
 * サーバーから現在の設定を取得して各ボタン/リング方向に表示し、
 * クリックで開くモーダルでキーボードのキーを記録してショートカットを割り当てる。
 */
(() => {
  "use strict";

  let settings = { buttons: {}, oshi_ring: {} };
  let displayNames = {};

  let modalSection = null;
  let modalSlot = null;
  let modalKeys = [];
  let recording = false;

  const modal = document.getElementById("modal");
  const modalTitle = document.getElementById("modal-title");
  const modalLabel = document.getElementById("modal-label");
  const modalTextEl = document.getElementById("modal-text");
  const modalKeysEl = document.getElementById("modal-keys");
  const recordBtn = document.getElementById("record-btn");
  const recordHint = document.getElementById("record-hint");
  const clearKeysBtn = document.getElementById("clear-keys-btn");
  const saveBtn = document.getElementById("save-btn");
  const cancelBtn = document.getElementById("cancel-btn");
  const toast = document.getElementById("toast");

  // ブラウザの KeyboardEvent を core/shortcut_executor.py の SPECIAL_KEYS と
  // 同じ命名規則の文字列に変換する。
  const KEY_NAME_MAP = {
    Control: "ctrl",
    Shift: "shift",
    Alt: "alt",
    Meta: "cmd",
    Enter: "enter",
    Escape: "esc",
    Tab: "tab",
    " ": "space",
    Backspace: "backspace",
    Delete: "delete",
    ArrowUp: "up",
    ArrowDown: "down",
    ArrowLeft: "left",
    ArrowRight: "right",
    Home: "home",
    End: "end",
    PageUp: "page_up",
    PageDown: "page_down",
    CapsLock: "caps_lock",
    Insert: "insert",
    PrintScreen: "print_screen",
  };

  function normalizeKey(event) {
    if (KEY_NAME_MAP[event.key]) return KEY_NAME_MAP[event.key];
    if (/^F([1-9]|1\d|2[0-4])$/.test(event.key)) return event.key.toLowerCase();
    if (event.key.length === 1) return event.key.toLowerCase();
    return null;
  }

  function showToast(message, isError) {
    toast.textContent = message;
    toast.classList.toggle("error", !!isError);
    toast.hidden = false;
    setTimeout(() => { toast.hidden = true; }, 2500);
  }

  function renderAssigned() {
    document.querySelectorAll("[data-target]").forEach((el) => {
      const [section, slot] = el.dataset.target.split(":");
      const action = (settings[section] && settings[section][slot]) || { keys: [], text: "" };
      const btn = el.closest(".jc-btn");
      if (btn) btn.classList.toggle("assigned", !!(action.text || (action.keys && action.keys.length)));
      if (action.text) {
        el.textContent = "貼付: " + (action.text.length > 20 ? action.text.slice(0, 20) + "…" : action.text);
      } else if (action.keys && action.keys.length) {
        el.textContent = action.keys.join(" + ");
      } else {
        el.textContent = "未設定";
      }
    });
  }

  async function loadSchema() {
    const res = await fetch("/api/schema");
    const data = await res.json();
    displayNames = data.display_names || {};
  }

  async function loadConfig() {
    const res = await fetch("/api/config");
    settings = await res.json();
    renderAssigned();
  }

  function renderModalKeys() {
    modalKeysEl.innerHTML = "";
    if (modalKeys.length === 0) {
      const empty = document.createElement("span");
      empty.className = "record-hint";
      empty.textContent = "（キー未記録）";
      modalKeysEl.appendChild(empty);
      return;
    }
    modalKeys.forEach((k) => {
      const chip = document.createElement("span");
      chip.className = "key-chip";
      chip.textContent = k;
      modalKeysEl.appendChild(chip);
    });
  }

  function onKeyDown(event) {
    if (!recording) return;
    if (event.key === "Escape") {
      event.preventDefault();
      stopRecording();
      return;
    }
    event.preventDefault();
    const name = normalizeKey(event);
    if (name && !modalKeys.includes(name)) {
      modalKeys.push(name);
      renderModalKeys();
    }
  }

  function onModalKeyDown(event) {
    if (event.key === "Escape" && !modal.hidden && !recording) {
      closeModal();
    }
  }

  function startRecording() {
    recording = true;
    modalKeys = [];
    renderModalKeys();
    recordBtn.textContent = "記録終了";
    recordBtn.classList.add("recording");
    recordHint.hidden = false;
    document.addEventListener("keydown", onKeyDown, true);
  }

  function stopRecording() {
    recording = false;
    recordBtn.textContent = "キーを記録";
    recordBtn.classList.remove("recording");
    recordHint.hidden = true;
    document.removeEventListener("keydown", onKeyDown, true);
  }

  function openModal(section, slot) {
    modalSection = section;
    modalSlot = slot;
    const action = (settings[section] && settings[section][slot]) || { label: "", keys: [], text: "" };
    modalKeys = [...(action.keys || [])];
    modalLabel.value = action.label || "";
    modalTextEl.value = action.text || "";
    modalTitle.textContent = displayNames[slot] || slot;
    renderModalKeys();
    modal.hidden = false;
  }

  function closeModal() {
    if (recording) stopRecording();
    modal.hidden = true;
    modalSection = null;
    modalSlot = null;
  }

  async function saveModal() {
    if (recording) stopRecording();

    const updated = JSON.parse(JSON.stringify(settings));
    updated[modalSection][modalSlot] = {
      label: modalLabel.value.trim(),
      keys: modalKeys,
      text: modalTextEl.value,
    };

    const res = await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updated),
    });
    const data = await res.json();

    if (!res.ok || !data.ok) {
      showToast(data.error || "保存に失敗しました", true);
      return;
    }

    settings = data.settings;
    renderAssigned();
    closeModal();
    showToast("保存しました");
  }

  document.querySelectorAll("[data-section][data-slot]").forEach((el) => {
    el.addEventListener("click", () => openModal(el.dataset.section, el.dataset.slot));
  });

  recordBtn.addEventListener("click", () => (recording ? stopRecording() : startRecording()));
  clearKeysBtn.addEventListener("click", () => { modalKeys = []; renderModalKeys(); });
  saveBtn.addEventListener("click", saveModal);
  cancelBtn.addEventListener("click", closeModal);
  modal.addEventListener("click", (e) => { if (e.target === modal) closeModal(); });
  document.addEventListener("keydown", onModalKeyDown);

  loadSchema().then(loadConfig).catch((err) => showToast("読み込みに失敗しました: " + err, true));
})();
