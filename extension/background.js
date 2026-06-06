const MEDIA_PATTERN = /\.(m3u8|mpd|mp4|webm|m4v|mov|mkv|flv|m4s|ts|aac|m4a)(\?|#|$)/i;
const STREAMS_BY_TAB = new Map();
const SELECTION_BY_TAB = new Map();
const MAX_STREAMS = 80;

function normalizeStream(details) {
  const responseHeaders = details.responseHeaders || [];
  const contentType = responseHeaders.find((h) => h.name && h.name.toLowerCase() === "content-type")?.value || "";
  const lowerType = contentType.toLowerCase();
  if (!MEDIA_PATTERN.test(details.url) && !lowerType.includes("video") && !lowerType.includes("audio") && !lowerType.includes("mpegurl") && !lowerType.includes("dash")) {
    return null;
  }

  return {
    url: details.url,
    mimeType: contentType,
    source: details.type || "network",
    label: labelFromUrl(details.url, contentType),
    isFragment: isFragmentUrl(details.url),
    detectedAt: Date.now()
  };
}

function labelFromUrl(url, mimeType = "") {
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
  return mimeType || "Media stream";
}

function isFragmentUrl(url) {
  try {
    const path = new URL(url).pathname.toLowerCase();
    return path.endsWith(".m4s") || path.endsWith(".ts");
  } catch (_) {
    return false;
  }
}

function rememberStream(tabId, stream) {
  if (!tabId || tabId < 0 || !stream) return;
  const list = STREAMS_BY_TAB.get(tabId) || [];
  if (list.some((item) => item.url === stream.url)) return;
  list.unshift(stream);
  STREAMS_BY_TAB.set(tabId, list.slice(0, MAX_STREAMS));
}

chrome.webRequest.onCompleted.addListener(
  (details) => rememberStream(details.tabId, normalizeStream(details)),
  { urls: ["<all_urls>"] },
  ["responseHeaders"]
);

chrome.tabs.onRemoved.addListener((tabId) => {
  STREAMS_BY_TAB.delete(tabId);
  SELECTION_BY_TAB.delete(tabId);
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "GET_DETECTED_STREAMS") {
    const tabId = message.tabId || sender.tab?.id;
    sendResponse({
      streams: STREAMS_BY_TAB.get(tabId) || [],
      selection: SELECTION_BY_TAB.get(tabId) || null
    });
    return true;
  }

  if (message?.type === "ADD_CONTENT_STREAMS") {
    const tabId = sender.tab?.id || message.tabId;
    for (const stream of message.streams || []) {
      rememberStream(tabId, stream);
    }
    sendResponse({ ok: true });
    return true;
  }

  if (message?.type === "SET_SELECTED_VIDEO") {
    const tabId = sender.tab?.id || message.tabId;
    if (tabId && message.selection) {
      SELECTION_BY_TAB.set(tabId, message.selection);
      for (const stream of message.selection.streams || []) {
        rememberStream(tabId, stream);
      }
    }
    sendResponse({ ok: true });
    return true;
  }

  if (message?.type === "CLEAR_SELECTED_VIDEO") {
    const tabId = message.tabId || sender.tab?.id;
    if (tabId) SELECTION_BY_TAB.delete(tabId);
    sendResponse({ ok: true });
    return true;
  }

  return false;
});
