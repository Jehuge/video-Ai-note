const APP_BASE = "http://127.0.0.1:8483/api";
const TERMINAL_JOB_STATUSES = new Set(["completed", "failed", "canceled", "cancelled"]);
const NOTE_STYLE_STORAGE_KEY = "noteStyle";

const state = {
  tab: null,
  token: "",
  pageUrl: "",
  pageTitle: "",
  pageHeaders: {},
  detectedStreams: [],
  selectedVideo: null,
  candidates: [],
  resolveErrors: [],
  cookieHeader: "",
  cookieDetails: [],
  videoCount: 0,
  jobTimer: null
};

const els = {
  status: document.getElementById("status"),
  pick: document.getElementById("pick"),
  refresh: document.getElementById("refresh"),
  candidate: document.getElementById("candidate"),
  format: document.getElementById("format"),
  noteStyle: document.getElementById("noteStyle"),
  screenshot: document.getElementById("screenshot"),
  cookies: document.getElementById("cookies"),
  cookieInfo: document.getElementById("cookieInfo"),
  autoRun: document.getElementById("autoRun"),
  send: document.getElementById("send"),
  empty: document.getElementById("empty"),
  progress: document.getElementById("progress"),
  bar: document.getElementById("bar"),
  progressText: document.getElementById("progressText")
};

function setStatus(text, ok = false) {
  els.status.textContent = text;
  els.status.style.color = ok ? "#15803d" : "#64748b";
}

async function getCurrentTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

function sendMessage(tabId, message) {
  return new Promise((resolve) => {
    chrome.tabs.sendMessage(tabId, message, (response) => {
      resolve(chrome.runtime.lastError ? null : response);
    });
  });
}

function runtimeMessage(message) {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage(message, (response) => {
      resolve(chrome.runtime.lastError ? null : response);
    });
  });
}

async function restoreNoteStyle() {
  if (!els.noteStyle) return;
  const saved = await chrome.storage.local.get(NOTE_STYLE_STORAGE_KEY);
  if (saved.noteStyle && [...els.noteStyle.options].some((option) => option.value === saved.noteStyle)) {
    els.noteStyle.value = saved.noteStyle;
  }
}

async function saveNoteStyle() {
  if (!els.noteStyle) return;
  await chrome.storage.local.set({ [NOTE_STYLE_STORAGE_KEY]: els.noteStyle.value || "simple" });
}

function cookieProbeUrls(pageUrl) {
  const urls = [];
  try {
    const parsed = new URL(pageUrl);
    urls.push(parsed.href);
    const host = parsed.hostname.toLowerCase();
    if (host.endsWith("bilibili.com")) {
      urls.push("https://www.bilibili.com/", "https://api.bilibili.com/");
    }
    if (host.endsWith("douyin.com")) {
      urls.push("https://www.douyin.com/", "https://v.douyin.com/");
    }
    if (host.endsWith("iesdouyin.com")) {
      urls.push("https://www.iesdouyin.com/", "https://www.douyin.com/");
    }
  } catch (_) {
    return urls;
  }
  return [...new Set(urls)];
}

function cookieNames(cookieHeader) {
  return new Set(
    String(cookieHeader || "")
      .split(";")
      .map((item) => item.trim().split("=", 1)[0])
      .filter(Boolean)
  );
}

function updateCookieInfo(cookieHeader = "") {
  if (!els.cookieInfo) return;
  if (els.cookies && els.cookies.checked === false) {
    els.cookieInfo.textContent = "站点 Cookie 已关闭：可能只能解析公开清晰度。";
    els.cookieInfo.style.color = "#b45309";
    return;
  }
  const names = cookieNames(cookieHeader);
  let message = "站点 Cookie 已开启。";
  let ok = true;
  try {
    const host = new URL(state.pageUrl || "").hostname.toLowerCase();
    if (host.endsWith("bilibili.com")) {
      ok = names.has("SESSDATA");
      message = ok ? "已读取 B站登录 Cookie，可解析登录清晰度。" : "未读到 B站 SESSDATA，可能只能到 480p。";
    } else if (host.endsWith("douyin.com") || host.endsWith("iesdouyin.com")) {
      ok = names.has("s_v_web_id") || names.has("msToken") || names.has("ttwid");
      message = ok ? "已读取抖音 fresh Cookie，可继续解析。" : "未读到抖音 fresh Cookie，解析可能失败。";
    }
  } catch (_) {
    // Keep generic message.
  }
  els.cookieInfo.textContent = message;
  els.cookieInfo.style.color = ok ? "#15803d" : "#b45309";
}

function compactResolveError(error) {
  const text = String(error || "").replace(/\s+/g, " ").trim();
  if (!text) return "";
  return text
    .replace(/^page:\s*/i, "")
    .replace(/^stream\s+\S+:\s*/i, "")
    .slice(0, 120);
}

function resolveErrorSummary() {
  const errors = (state.resolveErrors || []).map(compactResolveError).filter(Boolean);
  if (!errors.length) return "";
  return errors.slice(0, 2).join("；");
}

async function collectSiteCookies() {
  if (els.cookies && els.cookies.checked === false) {
    state.cookieHeader = "";
    state.cookieDetails = [];
    updateCookieInfo("");
    return "";
  }
  if (!/^https?:\/\//i.test(state.pageUrl || "")) {
    state.cookieHeader = "";
    state.cookieDetails = [];
    return "";
  }
  const cookieMap = new Map();
  const cookieDetails = new Map();
  try {
    for (const url of cookieProbeUrls(state.pageUrl)) {
      const cookies = await chrome.cookies.getAll({ url });
      for (const item of cookies) {
        if (item.name && typeof item.value === "string") {
          cookieMap.set(item.name, item.value);
          const key = `${item.domain || ""}|${item.path || "/"}|${item.name}`;
          cookieDetails.set(key, {
            name: item.name,
            value: item.value,
            domain: item.domain || "",
            path: item.path || "/",
            secure: Boolean(item.secure),
            expirationDate: item.expirationDate,
            session: Boolean(item.session)
          });
        }
      }
    }
  } catch (_) {
    state.cookieHeader = "";
    state.cookieDetails = [];
    updateCookieInfo("");
    return "";
  }
  const cookieHeader = [...cookieMap.entries()]
    .map(([name, value]) => `${name}=${value}`)
    .join("; ");
  state.cookieHeader = cookieHeader;
  state.cookieDetails = [...cookieDetails.values()];
  updateCookieInfo(cookieHeader);
  return cookieHeader;
}

async function appFetch(path, options = {}) {
  const { timeoutMs, ...fetchOptions } = options;
  const headers = {
    "Content-Type": "application/json",
    ...(fetchOptions.headers || {})
  };
  if (state.token) headers["X-AINOTE-BRIDGE-TOKEN"] = state.token;

  let timer = null;
  const controller = timeoutMs ? new AbortController() : null;
  if (controller) {
    timer = setTimeout(() => controller.abort(), timeoutMs);
  }

  try {
    return await fetch(`${APP_BASE}${path}`, {
      ...fetchOptions,
      headers,
      signal: controller?.signal || fetchOptions.signal
    });
  } finally {
    if (timer) clearTimeout(timer);
  }
}

async function checkApp() {
  try {
    const response = await fetch(`${APP_BASE}/extension/health`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const json = await response.json();
    state.token = json.data?.bridgeToken || "";
    if (state.token) {
      await chrome.storage.local.set({ bridgeToken: state.token });
    }
    setStatus("AInote 已连接", true);
    return true;
  } catch (error) {
    const saved = await chrome.storage.local.get("bridgeToken");
    state.token = saved.bridgeToken || "";
    setStatus("请先打开 AInote");
    return false;
  }
}

function uniqueStreams(streams) {
  const seen = new Set();
  return streams.filter((stream) => {
    if (!stream?.url || seen.has(stream.url)) return false;
    if (stream.isBlob || String(stream.url).startsWith("blob:")) return false;
    if (stream.isFragment || isFragmentUrl(stream.url)) return false;
    seen.add(stream.url);
    return true;
  });
}

function isFragmentUrl(url) {
  try {
    const path = new URL(url).pathname.toLowerCase();
    return path.endsWith(".m4s") || path.endsWith(".ts");
  } catch (_) {
    return false;
  }
}

async function collectPageStreams() {
  state.tab = await getCurrentTab();
  state.pageUrl = state.tab?.url || "";
  state.pageTitle = state.tab?.title || "";

  const pageScan = await sendMessage(state.tab.id, { type: "SCAN_PAGE_VIDEOS" });
  const background = await runtimeMessage({ type: "GET_DETECTED_STREAMS", tabId: state.tab.id });
  state.selectedVideo = background?.selection || null;
  const selectedStreams = state.selectedVideo?.streams || [];
  state.detectedStreams = uniqueStreams([...selectedStreams, ...(pageScan?.streams || []), ...(background?.streams || [])]);
  state.videoCount = Math.max(pageScan?.videoCount || 0, state.selectedVideo?.videoCount || 0);
  state.pageTitle = state.selectedVideo?.pageTitle || pageScan?.pageTitle || state.pageTitle;
  state.pageUrl = state.selectedVideo?.pageUrl || pageScan?.pageUrl || state.pageUrl;
  state.pageHeaders = {
    ...(pageScan?.headers || {}),
    Referer: state.pageUrl
  };
}

function canUsePageResolver() {
  if (!/^https?:\/\//i.test(state.pageUrl || "")) return false;
  return state.videoCount > 0 || state.detectedStreams.length > 0 || /\/video\/|watch|play|live|episode/i.test(state.pageUrl || "");
}

function pageResolverCandidate() {
  if (!canUsePageResolver()) return null;
  return {
    id: "page-url",
    title: state.pageTitle || "当前页面视频",
    sourceUrl: state.pageUrl,
    extractor: "page-url",
    formats: [{
      formatId: "bv*+ba/best",
      label: "最佳清晰度（由 AInote 解析）",
      protocol: "yt-dlp"
    }]
  };
}

function selectedVideoCandidate() {
  if (!state.selectedVideo) return null;
  return {
    id: "selected-video",
    title: state.selectedVideo.label || state.pageTitle || "选中视频",
    sourceUrl: state.pageUrl,
    extractor: "selected-area",
    formats: [{
      formatId: "bv*+ba/best",
      label: "最佳清晰度（选中区域）",
      protocol: "yt-dlp"
    }]
  };
}

function mergeCandidates(primary, fallback) {
  const merged = [];
  const seen = new Set();
  for (const item of [...(primary || []), ...(fallback ? [fallback] : [])]) {
    const key = `${item.extractor || ""}:${item.sourceUrl || ""}:${item.id || ""}`;
    if (seen.has(key)) continue;
    seen.add(key);
    merged.push(item);
  }
  return merged;
}

async function resolveVideos() {
  const cookies = await collectSiteCookies();
  const selectedStreams = uniqueStreams(state.selectedVideo?.streams || []);
  const streamsToResolve = selectedStreams.length ? selectedStreams : state.detectedStreams;
  const response = await appFetch("/extension/videos/resolve", {
    method: "POST",
    timeoutMs: 30000,
    body: JSON.stringify({
      pageUrl: state.pageUrl,
      pageTitle: state.pageTitle,
      detectedStreams: streamsToResolve,
      headers: state.pageHeaders,
      cookies,
      cookieDetails: state.cookieDetails
    })
  });
  if (!response.ok) throw new Error(`Resolve failed: HTTP ${response.status}`);
  const json = await response.json();
  state.resolveErrors = json.data?.errors || [];
  state.candidates = (json.data?.candidates || []).filter((candidate) => !isFragmentUrl(candidate.sourceUrl || ""));
}

function renderCandidates() {
  els.candidate.innerHTML = "";
  els.format.innerHTML = "";
  els.empty.classList.toggle("hidden", state.candidates.length > 0);
  els.send.disabled = state.candidates.length === 0;

  for (const candidate of state.candidates) {
    const option = document.createElement("option");
    option.value = candidate.id;
    const source = candidate.extractor ? ` [${candidate.extractor}]` : "";
    option.textContent = `${candidate.title || candidate.sourceUrl || "检测到的视频"}${source}`;
    els.candidate.appendChild(option);
  }
  renderFormats();
}

function renderFormats() {
  const candidate = selectedCandidate();
  els.format.innerHTML = "";
  for (const format of candidate?.formats || []) {
    const option = document.createElement("option");
    option.value = format.formatId;
    const size = format.filesize ? ` / ${formatSize(format.filesize)}` : "";
    option.textContent = `${format.label || format.formatId}${size}`;
    els.format.appendChild(option);
  }
}

function selectedCandidate() {
  return state.candidates.find((item) => item.id === els.candidate.value) || state.candidates[0];
}

function formatSize(bytes) {
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let index = 0;
  while (value > 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  return `${value.toFixed(index ? 1 : 0)} ${units[index]}`;
}

async function importSelected() {
  const candidate = selectedCandidate();
  if (!candidate) return;
  await saveNoteStyle();

  els.send.disabled = true;
  els.progress.classList.remove("hidden");
  updateProgress({ progress: 0, message: "排队中" });
  const cookies = await collectSiteCookies();
  const selectedStreams = uniqueStreams(state.selectedVideo?.streams || []);

  const response = await appFetch("/extension/videos/import", {
    method: "POST",
    body: JSON.stringify({
      pageUrl: state.pageUrl,
      pageTitle: state.pageTitle,
      detectedStreams: selectedStreams.length ? selectedStreams : state.detectedStreams,
      headers: state.pageHeaders,
      candidateId: candidate.id,
      candidateUrl: candidate.sourceUrl,
      formatId: els.format.value,
      noteStyle: els.noteStyle?.value || "simple",
      autoRun: els.autoRun.checked,
      screenshot: els.screenshot.checked,
      cookies,
      cookieDetails: state.cookieDetails
    })
  });
  if (!response.ok) throw new Error(`Import failed: HTTP ${response.status}`);
  const json = await response.json();
  pollJob(json.data.jobId);
}

function updateProgress(job) {
  els.bar.style.width = `${job.progress || 0}%`;
  if (job.status === "canceled" || job.status === "cancelled") {
    els.progressText.textContent = "已在 AInote 取消";
    return;
  }
  if (job.status === "completed") {
    els.progressText.textContent = job.message || "已完成";
    return;
  }
  if (job.status === "failed") {
    els.progressText.textContent = job.error || job.message || "处理失败";
    return;
  }
  els.progressText.textContent = job.message || job.status || "处理中";
}

function pollJob(jobId) {
  clearInterval(state.jobTimer);
  state.jobTimer = setInterval(async () => {
    try {
      const response = await appFetch(`/extension/jobs/${jobId}`);
      const json = await response.json();
      const job = json.data || {};
      updateProgress(job);
      if (TERMINAL_JOB_STATUSES.has(job.status)) {
        clearInterval(state.jobTimer);
        els.send.disabled = state.candidates.length === 0;
      }
    } catch (error) {
      updateProgress({ progress: 0, error: error.message });
      clearInterval(state.jobTimer);
      els.send.disabled = state.candidates.length === 0;
    }
  }, 1200);
}

async function refresh() {
  els.send.disabled = true;
  setStatus("正在扫描页面...");
  await restoreNoteStyle();
  const appReady = await checkApp();
  await collectPageStreams();
  const selectedFallback = selectedVideoCandidate();
  const fallback = selectedFallback || pageResolverCandidate();
  if (fallback) {
    state.candidates = [fallback];
    renderCandidates();
    setStatus(selectedFallback ? "已选中视频区域" : "当前页面可发送到 AInote", true);
  }
  if (!appReady) {
    els.send.disabled = true;
    setStatus("请先打开 AInote");
    return;
  }
  try {
    setStatus("正在解析清晰度...");
    await resolveVideos();
    state.candidates = mergeCandidates(state.candidates, fallback);
    renderCandidates();
    const errorSummary = resolveErrorSummary();
    if (state.candidates.length) {
      setStatus(errorSummary ? `视频已就绪；解析提示：${errorSummary}` : "视频已就绪", true);
    } else {
      setStatus(errorSummary ? `未找到支持的视频：${errorSummary}` : "未找到支持的视频", false);
    }
  } catch (error) {
    if (fallback) {
      state.candidates = [fallback];
      setStatus(`先用当前选择，AInote 会继续解析：${error.message}`);
    } else {
      setStatus(error.message);
      state.candidates = [];
    }
    renderCandidates();
  }
}

async function startPicker() {
  state.tab = await getCurrentTab();
  if (!state.tab?.id) return;
  const response = await sendMessage(state.tab.id, { type: "START_VIDEO_PICKER" });
  if (response?.ok) {
    setStatus("回到网页点击视频区域");
    window.close();
  } else {
    setStatus("当前页面无法启动选择器");
  }
}

els.pick.addEventListener("click", () => {
  startPicker().catch((error) => setStatus(error.message));
});
els.refresh.addEventListener("click", refresh);
els.candidate.addEventListener("change", renderFormats);
els.noteStyle?.addEventListener("change", () => {
  saveNoteStyle().catch(() => {});
});
els.cookies?.addEventListener("change", () => {
  updateCookieInfo("");
});
els.send.addEventListener("click", () => {
  importSelected().catch((error) => {
    updateProgress({ progress: 0, error: error.message });
    els.progress.classList.remove("hidden");
    els.send.disabled = state.candidates.length === 0;
  });
});

refresh();
