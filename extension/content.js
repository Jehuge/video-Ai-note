const MEDIA_PATTERN = /\.(m3u8|mpd|mp4|webm|m4v|mov|mkv|flv|m4s|ts|aac|m4a)(\?|#|$)/i;
let pickerActive = false;
let pickerHighlight = null;
let pickerHint = null;

function collectVideoStreams() {
  const streams = [];
  const seen = new Set();
  let videoCount = 0;

  function add(url, extra = {}) {
    if (!url) return;
    try {
      url = new URL(url, location.href).href;
    } catch (_) {
      return;
    }
    if (seen.has(url)) return;
    seen.add(url);
    streams.push({
      url,
      source: extra.source || "dom",
      label: extra.label || "Page video",
      mimeType: extra.mimeType || "",
      height: extra.height,
      width: extra.width,
      isFragment: extra.isFragment || isFragmentUrl(url),
      isBlob: url.startsWith("blob:")
    });
  }

  for (const video of document.querySelectorAll("video")) {
    videoCount += 1;
    add(video.currentSrc || video.src, {
      label: video.videoHeight ? `${video.videoHeight}p page video` : "Page video",
      height: video.videoHeight || undefined,
      width: video.videoWidth || undefined
    });

    for (const source of video.querySelectorAll("source")) {
      add(source.src, {
        label: source.label || source.getAttribute("res") || "Video source",
        mimeType: source.type || "",
        height: Number.parseInt(source.getAttribute("height") || "", 10) || undefined
      });
    }
  }

  for (const audio of document.querySelectorAll("audio")) {
    add(audio.currentSrc || audio.src, {
      label: "Page audio",
      source: "dom-audio"
    });
  }

  for (const source of document.querySelectorAll("source[src]")) {
    add(source.src, {
      label: source.label || "Media source",
      mimeType: source.type || ""
    });
  }

  if (performance?.getEntriesByType) {
    for (const entry of performance.getEntriesByType("resource")) {
      const url = entry.name || "";
      if (!MEDIA_PATTERN.test(url)) continue;
      add(url, {
        label: labelFromUrl(url),
        source: "performance",
        isFragment: isFragmentUrl(url)
      });
    }
  }

  return { streams, videoCount };
}

function collectStreamsFromElement(element) {
  const streams = [];
  const seen = new Set();

  function add(url, extra = {}) {
    if (!url) return;
    try {
      url = new URL(url, location.href).href;
    } catch (_) {
      return;
    }
    if (seen.has(url)) return;
    seen.add(url);
    streams.push({
      url,
      source: extra.source || "selected",
      label: extra.label || "Selected video",
      mimeType: extra.mimeType || "",
      height: extra.height,
      width: extra.width,
      isFragment: extra.isFragment || isFragmentUrl(url),
      isBlob: url.startsWith("blob:")
    });
  }

  const mediaElements = [];
  if (element?.matches?.("video,audio")) {
    mediaElements.push(element);
  }
  for (const item of element?.querySelectorAll?.("video,audio") || []) {
    mediaElements.push(item);
  }

  for (const media of mediaElements) {
    add(media.currentSrc || media.src, {
      label: media.videoHeight ? `${media.videoHeight}p selected video` : "Selected video",
      height: media.videoHeight || undefined,
      width: media.videoWidth || undefined,
      source: "selected-dom"
    });

    for (const source of media.querySelectorAll("source[src]")) {
      add(source.src, {
        label: source.label || source.getAttribute("res") || "Selected source",
        mimeType: source.type || "",
        height: Number.parseInt(source.getAttribute("height") || "", 10) || undefined,
        source: "selected-source"
      });
    }
  }

  if (element?.matches?.("source[src]")) {
    add(element.src, {
      label: element.label || "Selected source",
      mimeType: element.type || "",
      source: "selected-source"
    });
  }

  if (element?.matches?.("iframe[src]")) {
    add(element.src, {
      label: "Selected embedded player",
      mimeType: "text/html",
      source: "selected-frame"
    });
  }

  return streams;
}

function selectedSourceUrl(target) {
  if (target?.matches?.("iframe[src]")) {
    try {
      return new URL(target.src, location.href).href;
    } catch (_) {
      return location.href;
    }
  }
  return location.href;
}

function findPickTarget(element) {
  if (!element || element === document.documentElement || element === document.body) {
    return document.querySelector("video,audio,iframe,canvas") || document.body;
  }
  const direct = element.closest?.("video,audio,iframe,canvas");
  if (direct) return direct;
  const nested = element.querySelector?.("video,audio,iframe,canvas");
  if (nested) return nested;
  return element;
}

function elementLabel(element) {
  if (!element) return "Selected video area";
  if (element.matches?.("video")) return "Selected video";
  if (element.matches?.("audio")) return "Selected audio";
  if (element.matches?.("iframe")) return "Selected embedded player";
  if (element.matches?.("canvas")) return "Selected canvas player";
  return "Selected video area";
}

function rectPayload(rect) {
  return {
    x: Math.round(rect.x),
    y: Math.round(rect.y),
    width: Math.round(rect.width),
    height: Math.round(rect.height)
  };
}

function ensurePickerUi() {
  if (!pickerHighlight) {
    pickerHighlight = document.createElement("div");
    pickerHighlight.style.cssText = [
      "position:fixed",
      "z-index:2147483647",
      "pointer-events:none",
      "border:3px solid #38bdf8",
      "box-shadow:0 0 0 9999px rgba(15,23,42,.28)",
      "border-radius:8px",
      "display:none"
    ].join(";");
    document.documentElement.appendChild(pickerHighlight);
  }

  if (!pickerHint) {
    pickerHint = document.createElement("div");
    pickerHint.textContent = "点击要解析的视频区域，按 Esc 取消";
    pickerHint.style.cssText = [
      "position:fixed",
      "z-index:2147483647",
      "pointer-events:none",
      "left:16px",
      "top:16px",
      "padding:8px 10px",
      "border-radius:6px",
      "background:#0f172a",
      "color:white",
      "font:13px/1.3 system-ui,-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif",
      "box-shadow:0 8px 24px rgba(15,23,42,.28)"
    ].join(";");
    document.documentElement.appendChild(pickerHint);
  }
}

function updatePickerHighlight(element) {
  ensurePickerUi();
  const target = findPickTarget(element);
  const rect = target.getBoundingClientRect();
  pickerHighlight.style.display = "block";
  pickerHighlight.style.left = `${Math.max(0, rect.left)}px`;
  pickerHighlight.style.top = `${Math.max(0, rect.top)}px`;
  pickerHighlight.style.width = `${Math.max(1, rect.width)}px`;
  pickerHighlight.style.height = `${Math.max(1, rect.height)}px`;
}

function cleanupPicker() {
  pickerActive = false;
  document.removeEventListener("mousemove", handlePickerMouseMove, true);
  document.removeEventListener("click", handlePickerClick, true);
  document.removeEventListener("keydown", handlePickerKeyDown, true);
  pickerHighlight?.remove();
  pickerHint?.remove();
  pickerHighlight = null;
  pickerHint = null;
}

function selectedPayload(element) {
  const target = findPickTarget(element);
  const rect = target.getBoundingClientRect();
  const streams = collectStreamsFromElement(target);
  const sourceUrl = selectedSourceUrl(target);
  return {
    pageTitle: document.title,
    pageUrl: sourceUrl,
    sourceUrl,
    label: elementLabel(target),
    rect: rectPayload(rect),
    streams,
    videoCount: target.matches?.("video,audio") || target.querySelector?.("video,audio") ? 1 : 0,
    selectedAt: Date.now()
  };
}

function handlePickerMouseMove(event) {
  if (!pickerActive) return;
  updatePickerHighlight(event.target);
}

function handlePickerKeyDown(event) {
  if (event.key === "Escape") {
    event.preventDefault();
    event.stopPropagation();
    cleanupPicker();
  }
}

function handlePickerClick(event) {
  if (!pickerActive) return;
  event.preventDefault();
  event.stopPropagation();
  const selection = selectedPayload(event.target);
  chrome.runtime.sendMessage({ type: "SET_SELECTED_VIDEO", selection });
  cleanupPicker();
}

function startVideoPicker() {
  cleanupPicker();
  pickerActive = true;
  ensurePickerUi();
  document.addEventListener("mousemove", handlePickerMouseMove, true);
  document.addEventListener("click", handlePickerClick, true);
  document.addEventListener("keydown", handlePickerKeyDown, true);
}

function labelFromUrl(url) {
  try {
    const path = new URL(url).pathname.toLowerCase();
    if (path.endsWith(".m3u8")) return "HLS stream";
    if (path.endsWith(".mpd")) return "DASH stream";
    if (path.endsWith(".m4s")) return "DASH media segment";
    if (path.endsWith(".ts")) return "HLS media segment";
    const ext = path.split(".").pop();
    if (ext && ext.length <= 5) return ext.toUpperCase();
  } catch (_) {
    // ignore URL parsing issues
  }
  return "Media stream";
}

function isFragmentUrl(url) {
  try {
    const path = new URL(url).pathname.toLowerCase();
    return path.endsWith(".m4s") || path.endsWith(".ts");
  } catch (_) {
    return false;
  }
}

function publishStreams() {
  const { streams } = collectVideoStreams();
  if (streams.length) {
    chrome.runtime.sendMessage({ type: "ADD_CONTENT_STREAMS", streams });
  }
  return streams;
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "SCAN_PAGE_VIDEOS") {
    const result = collectVideoStreams();
    if (result.streams.length) {
      chrome.runtime.sendMessage({ type: "ADD_CONTENT_STREAMS", streams: result.streams });
    }
    sendResponse({
      pageTitle: document.title,
      pageUrl: location.href,
      streams: result.streams,
      videoCount: result.videoCount
    });
    return true;
  }
  if (message?.type === "START_VIDEO_PICKER") {
    startVideoPicker();
    sendResponse({ ok: true });
    return true;
  }
  return false;
});

publishStreams();
setTimeout(publishStreams, 1500);
setTimeout(publishStreams, 5000);
