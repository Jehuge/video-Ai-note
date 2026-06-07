const fs = require("fs");
const path = require("path");
const vm = require("vm");

const popupSource = fs
  .readFileSync(path.join(__dirname, "popup.js"), "utf8")
  .replace(/\nrefresh\(\);\s*$/, "\nglobalThis.__initialRefresh = refresh();");

function createElement(id) {
  const element = {
    id,
    textContent: "",
    value: "",
    checked: false,
    disabled: false,
    style: {},
    children: [],
    classList: {
      values: new Set(),
      toggle(name, force) {
        if (force) this.values.add(name);
        else this.values.delete(name);
      },
      remove(name) {
        this.values.delete(name);
      },
      contains(name) {
        return this.values.has(name);
      }
    },
    appendChild(child) {
      this.children.push(child);
      if (!this.value && child.value) this.value = child.value;
    },
    addEventListener() {}
  };
  Object.defineProperty(element, "innerHTML", {
    get() {
      return "";
    },
    set(value) {
      if (value === "") {
        this.children = [];
        this.value = "";
      }
    }
  });
  return element;
}

function runPopupTest({
  pageScan,
  appReady = true,
  resolveResponse,
  cookiesChecked = true,
  cookieProvider = null,
  backgroundSelection = null,
  jobResponse = { status: "completed", progress: 100 }
}) {
  const elements = {};
  for (const id of ["status", "pick", "refresh", "candidate", "format", "noteStyle", "screenshot", "cookies", "cookieInfo", "diagnostics", "autoRun", "send", "copyDiagnostics", "empty", "progress", "bar", "progressText"]) {
    elements[id] = createElement(id);
  }
  elements.cookies.checked = cookiesChecked !== false;
  elements.autoRun.checked = true;
  elements.noteStyle.options = [
    { value: "simple" },
    { value: "detailed" },
    { value: "academic" },
    { value: "creative" }
  ];
  elements.noteStyle.value = "simple";

  const fetchCalls = [];
  const cookieCalls = [];
  const clipboardWrites = [];
  const timers = [];
  let intervalCallback = null;
  let clearIntervalCalls = 0;
  let cookieCallIndex = 0;

  const context = {
    console,
    AbortController: global.AbortController,
    URL,
    Set,
    clearTimeout,
    setTimeout(callback) {
      timers.push(callback);
      return timers.length;
    },
    setInterval(callback) {
      intervalCallback = callback;
      return 1;
    },
    clearInterval() {
      clearIntervalCalls += 1;
    },
    document: {
      getElementById(id) {
        return elements[id];
      },
      createElement(tag) {
        return createElement(tag);
      }
    },
    navigator: {
      clipboard: {
        writeText: async (text) => clipboardWrites.push(text)
      }
    },
    chrome: {
      tabs: {
        query: async () => [{ id: 7, url: pageScan.pageUrl, title: pageScan.pageTitle }],
        sendMessage: (_tabId, _message, callback) => callback(pageScan)
      },
      runtime: {
        sendMessage: (message, callback) => {
          if (message?.type === "GET_DETECTED_STREAMS") {
            callback({ streams: [], selection: backgroundSelection });
          } else {
            callback({ streams: [] });
          }
        },
        lastError: null
      },
      storage: {
        local: {
          set: async () => {},
          get: async () => ({ bridgeToken: "saved-token" })
        }
      },
      cookies: {
        getAll: async (details) => {
          cookieCalls.push(details);
          if (cookieProvider) return cookieProvider(details);
          cookieCallIndex += 1;
          if (details.url === "https://api.bilibili.com/") {
            return [
              { name: "SESSDATA", value: "demo", domain: ".bilibili.com", path: "/", secure: true, expirationDate: 1924992000 },
              { name: "bili_jct", value: "csrf", domain: ".bilibili.com", path: "/", secure: false, session: true }
            ];
          }
          if (details.url === "https://v.douyin.com/") {
            return [{ name: "s_v_web_id", value: "fresh", domain: ".douyin.com", path: "/", secure: true, expirationDate: 1924992000 }];
          }
          return [{ name: `cookie${cookieCallIndex}`, value: "demo", domain: new URL(details.url).hostname, path: "/", secure: details.url.startsWith("https:") }];
        }
      }
    },
    fetch: async (url, options = {}) => {
      fetchCalls.push({ url, options });
      if (url.endsWith("/extension/health")) {
        if (!appReady) return { ok: false, status: 503, json: async () => ({}) };
        return { ok: true, status: 200, json: async () => ({ data: { bridgeToken: "token-1" } }) };
      }
  if (url.endsWith("/extension/videos/resolve")) {
        if (resolveResponse instanceof Error) throw resolveResponse;
        const data = Array.isArray(resolveResponse)
          ? { candidates: resolveResponse }
          : {
              candidates: resolveResponse?.candidates || [],
              errors: resolveResponse?.errors || [],
              diagnostics: resolveResponse?.diagnostics || null
            };
        return {
          ok: true,
          status: 200,
          json: async () => ({ data })
        };
      }
      if (url.endsWith("/extension/videos/import")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({ data: { jobId: "job-1" } })
        };
      }
      return {
        ok: true,
        status: 200,
        json: async () => ({ data: jobResponse })
      };
    }
  };

  vm.createContext(context);
  vm.runInContext(popupSource, context, { filename: "popup.js" });

  return {
    context,
    elements,
    fetchCalls,
    cookieCalls,
    clipboardWrites,
    get clearIntervalCalls() {
      return clearIntervalCalls;
    },
    get intervalCallback() {
      return intervalCallback;
    }
  };
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function flush() {
  for (let index = 0; index < 10; index += 1) {
    await Promise.resolve();
  }
}

async function testPageFallbackWhenResolveIsSlow() {
  const env = runPopupTest({
    pageScan: {
      pageUrl: "https://www.bilibili.com/video/BV1demo/",
      pageTitle: "Bilibili demo",
      videoCount: 1,
      streams: []
    },
    resolveResponse: new Error("timeout")
  });

  await env.context.__initialRefresh;

  assert(env.elements.send.disabled === false, "send button should stay enabled with page fallback");
  assert(env.elements.candidate.children[0].value === "page-url", "page fallback candidate should render");
  assert(env.elements.format.children[0].value === "bv*+ba/best", "page fallback format should render");
  assert(env.elements.status.textContent.includes("先用当前选择，AInote 会继续解析"), "resolve failure should keep fallback status");
  assert(env.elements.status.textContent.includes("timeout"), "resolve failure should show the error reason");
}

async function testAppOfflineDisablesSend() {
  const env = runPopupTest({
    appReady: false,
    pageScan: {
      pageUrl: "https://www.bilibili.com/video/BV1demo/",
      pageTitle: "Bilibili demo",
      videoCount: 1,
      streams: []
    }
  });

  await env.context.__initialRefresh;

  assert(env.elements.send.disabled === true, "send button should be disabled when app is offline");
  assert(env.elements.status.textContent === "请先打开 AInote", "offline status should be shown");
}

async function testResolveErrorsAreShownWithFallback() {
  const env = runPopupTest({
    pageScan: {
      pageUrl: "https://www.douyin.com/video/6961737553342991651",
      pageTitle: "Douyin demo",
      videoCount: 1,
      streams: []
    },
    resolveResponse: {
      candidates: [],
      errors: ["page: [Douyin] Fresh cookies (not necessarily logged in) are needed"]
    }
  });

  await env.context.__initialRefresh;

  assert(env.elements.send.disabled === false, "fallback should remain sendable when resolve returns errors");
  assert(env.elements.status.textContent.includes("Fresh cookies"), "resolve errors should be visible in popup status");
}

async function testResolveDiagnosticsAreShown() {
  const env = runPopupTest({
    pageScan: {
      pageUrl: "https://www.bilibili.com/video/BV1demo/",
      pageTitle: "Bilibili demo",
      videoCount: 1,
      streams: []
    },
    resolveResponse: {
      candidates: [{
        id: "yt-0",
        title: "Bilibili demo",
        sourceUrl: "https://www.bilibili.com/video/BV1demo/",
        extractor: "BiliBili",
        formats: [{ formatId: "64+ba/best", label: "480p mp4", height: 480 }]
      }],
      diagnostics: {
        candidateCount: 1,
        formatCount: 1,
        maxHeight: 480,
        detectedStreamCount: 0,
        extractors: ["BiliBili"],
        receivedCookies: { bilibiliSessdata: true },
        ytDlpCookies: { bilibiliSessdata: false },
        bilibiliApi: {
          bilibiliApiLogin: true,
          bilibiliApiFormatHeights: [1080, 720]
        },
        ytDlpMessages: ["Format(s) 1080P are missing; you have to become a premium member"]
      }
    }
  });

  await env.context.__initialRefresh;

  assert(env.elements.diagnostics.textContent.includes("最高 480p"), "diagnostics should show max resolved height");
  assert(env.elements.diagnostics.textContent.includes("AInote 已收到 SESSDATA"), "diagnostics should show backend cookie receipt");
  assert(env.elements.diagnostics.textContent.includes("yt-dlp 未识别登录态"), "diagnostics should show yt-dlp cookie state");
  assert(env.elements.diagnostics.textContent.includes("B站 API 1080p"), "diagnostics should show bilibili API max height");
  assert(env.elements.diagnostics.textContent.includes("premium member"), "diagnostics should show yt-dlp quality warnings");
  assert(env.elements.diagnostics.textContent.includes("BiliBili"), "diagnostics should show extractor name");
}

async function testHighestQualityCandidateIsSelectedByDefault() {
  const env = runPopupTest({
    pageScan: {
      pageUrl: "https://www.bilibili.com/video/BV1demo/",
      pageTitle: "Bilibili demo",
      videoCount: 1,
      streams: []
    },
    resolveResponse: {
      candidates: [{
        id: "yt-0",
        title: "Bilibili demo",
        sourceUrl: "https://www.bilibili.com/video/BV1demo/",
        extractor: "BiliBili",
        formats: [{ formatId: "64+ba/best", label: "480p mp4", height: 480 }]
      }, {
        id: "bilibili-api-BV1demo",
        title: "Bilibili demo",
        sourceUrl: "https://www.bilibili.com/video/BV1demo/",
        extractor: "bilibili-api",
        formats: [{
          formatId: "bilibili-api-80",
          label: "1080P 高清 1080p avc1",
          height: 1080,
          bandwidth: 2000000,
          sourceUrl: "https://upos.example.test/video-1080.m4s",
          companionAudioUrl: "https://upos.example.test/audio.m4s"
        }, {
          formatId: "bilibili-api-64",
          label: "720P 高清 720p avc1",
          height: 720,
          bandwidth: 1200000,
          sourceUrl: "https://upos.example.test/video-720.m4s",
          companionAudioUrl: "https://upos.example.test/audio.m4s"
        }]
      }],
      diagnostics: {
        candidateCount: 2,
        formatCount: 3,
        maxHeight: 1080,
        receivedCookies: { bilibiliSessdata: true },
        bilibiliApi: { bilibiliApiLogin: true, bilibiliApiFormatHeights: [1080, 720] }
      }
    }
  });

  await env.context.__initialRefresh;

  assert(env.elements.candidate.value === "bilibili-api-BV1demo", "highest quality Bilibili API candidate should be selected by default");
  assert(env.elements.format.value === "bilibili-api-80", "highest quality format should be selected by default");
}

async function testCopyDiagnosticsIncludesResolveDetails() {
  const env = runPopupTest({
    pageScan: {
      pageUrl: "https://www.bilibili.com/video/BV1demo/",
      pageTitle: "Bilibili demo",
      videoCount: 1,
      streams: [{ url: "https://upos.example.test/video-1080.m4s", source: "bilibili-playinfo", height: 1080, isBilibiliPlayInfo: true }]
    },
    resolveResponse: {
      candidates: [{
        id: "bilibili-api-BV1demo",
        title: "Bilibili demo",
        sourceUrl: "https://www.bilibili.com/video/BV1demo/",
        extractor: "bilibili-api",
        formats: [{
          formatId: "bilibili-api-80",
          label: "1080P 高清",
          height: 1080,
          protocol: "bilibili-dash",
          sourceUrl: "https://upos.example.test/video-1080.m4s",
          companionAudioUrl: "https://upos.example.test/audio.m4s"
        }]
      }],
      diagnostics: {
        candidateCount: 1,
        formatCount: 1,
        maxHeight: 1080,
        receivedCookies: { bilibiliSessdata: true },
        bilibiliApi: { bilibiliApiLogin: true, bilibiliApiFormatHeights: [1080] },
        ytDlpMessages: ["yt-dlp message"]
      }
    }
  });

  await env.context.__initialRefresh;
  assert(env.elements.copyDiagnostics.classList.contains("hidden") === false, "copy diagnostics should be visible when diagnostics exist");
  await env.context.copyDiagnostics();
  await flush();

  assert(env.clipboardWrites.length === 1, "copy diagnostics should write to clipboard");
  const payload = JSON.parse(env.clipboardWrites[0]);
  assert(payload.pageUrl === "https://www.bilibili.com/video/BV1demo/", "diagnostics should include page url");
  assert(payload.hostKind === "bilibili", "diagnostics should include host kind");
  assert(payload.cookieNames.includes("SESSDATA"), "diagnostics should include cookie names");
  assert(payload.candidates[0].formats[0].formatId === "bilibili-api-80", "diagnostics should include resolved formats");
  assert(payload.candidates[0].formats[0].hasCompanionAudio === true, "diagnostics should include audio presence");
  assert(payload.diagnostics.bilibiliApi.bilibiliApiFormatHeights[0] === 1080, "diagnostics should include bilibili API heights");
}

async function testCookiesAreOptIn() {
  const env = runPopupTest({
    pageScan: {
      pageUrl: "https://www.bilibili.com/video/BV1demo/",
      pageTitle: "Bilibili demo",
      headers: {
        "User-Agent": "Chrome Test",
        "Accept-Language": "zh-CN",
        Referer: "https://www.bilibili.com/video/BV1demo/"
      },
      videoCount: 1,
      streams: []
    },
    resolveResponse: []
  });

  await env.context.__initialRefresh;

  assert(env.cookieCalls.some((call) => call.url === "https://api.bilibili.com/"), "bilibili API cookies should be read when enabled");
  assert(env.cookieCalls.some((call) => call.url === "https://passport.bilibili.com/"), "bilibili passport cookies should be read when enabled");
  assert(env.cookieCalls.some((call) => call.url === "https://t.bilibili.com/"), "bilibili social-domain cookies should be read when enabled");
  const resolveCall = env.fetchCalls.find((call) => call.url.endsWith("/extension/videos/resolve"));
  assert(resolveCall, "resolve call should be made");
  const body = JSON.parse(resolveCall.options.body);
  assert(body.cookies.includes("SESSDATA=demo"), "resolve should send selected site cookies by default");
  assert(body.cookies.includes("bili_jct=csrf"), "resolve should include bilibili API-domain cookies");
  assert(body.cookieDetails.some((item) => item.name === "SESSDATA" && item.domain === ".bilibili.com" && item.secure === true), "resolve should send structured bilibili cookies");
  assert(body.headers["User-Agent"] === "Chrome Test", "resolve should send browser headers");
  assert(body.headers.Referer === "https://www.bilibili.com/video/BV1demo/", "resolve should send referer");
  assert(env.elements.cookieInfo.textContent.includes("已读取 B站登录 Cookie"), "popup should show bilibili login cookie status");
}

async function testCookiesCanBeDisabled() {
  const env = runPopupTest({
    cookiesChecked: false,
    pageScan: {
      pageUrl: "https://www.bilibili.com/video/BV1demo/",
      pageTitle: "Bilibili demo",
      videoCount: 1,
      streams: []
    },
    resolveResponse: []
  });

  await env.context.__initialRefresh;

  assert(env.cookieCalls.length === 0, "cookies should not be read when unchecked");
  const resolveCall = env.fetchCalls.find((call) => call.url.endsWith("/extension/videos/resolve"));
  assert(JSON.parse(resolveCall.options.body).cookies === "", "resolve should not send cookies when disabled");
  assert(env.elements.cookieInfo.textContent.includes("站点 Cookie 已关闭"), "popup should explain disabled cookie mode");
}

async function testBilibiliMissingSessdataWarnsAboutLowQuality() {
  const env = runPopupTest({
    pageScan: {
      pageUrl: "https://www.bilibili.com/video/BV1demo/",
      pageTitle: "Bilibili demo",
      videoCount: 1,
      streams: []
    },
    resolveResponse: [],
    cookieProvider: async () => [{ name: "DedeUserID", value: "123" }]
  });

  await env.context.__initialRefresh;

  assert(env.elements.cookieInfo.textContent.includes("未读到 B站 SESSDATA"), "popup should warn when bilibili login cookie is missing");
}

async function testDouyinCookiesReadFreshCookieDomains() {
  const env = runPopupTest({
    pageScan: {
      pageUrl: "https://www.douyin.com/video/6961737553342991651",
      pageTitle: "Douyin demo",
      videoCount: 1,
      streams: []
    },
    resolveResponse: []
  });

  await env.context.__initialRefresh;

  assert(env.cookieCalls.some((call) => call.url === "https://www.douyin.com/"), "douyin web cookies should be read");
  assert(env.cookieCalls.some((call) => call.url === "https://v.douyin.com/"), "douyin short-link cookies should be read");
  assert(env.cookieCalls.some((call) => call.url === "https://www.iesdouyin.com/"), "douyin ies cookies should be read");
  assert(env.cookieCalls.some((call) => call.url === "https://snssdk.com/"), "douyin snssdk cookies should be read");
  const resolveCall = env.fetchCalls.find((call) => call.url.endsWith("/extension/videos/resolve"));
  const body = JSON.parse(resolveCall.options.body);
  assert(body.cookies.includes("s_v_web_id=fresh"), "resolve should include fresh Douyin visitor cookies");
  assert(body.cookieDetails.some((item) => item.name === "s_v_web_id" && item.domain === ".douyin.com"), "resolve should send structured douyin cookies");
  assert(env.elements.cookieInfo.textContent.includes("已读取抖音 fresh Cookie"), "popup should show douyin fresh cookie status");
}

async function testImportSendsCandidateUrl() {
  const env = runPopupTest({
    pageScan: {
      pageUrl: "https://www.bilibili.com/video/BV1demo/",
      pageTitle: "Bilibili demo",
      videoCount: 1,
      streams: []
    },
    resolveResponse: []
  });

  await env.context.__initialRefresh;
  await env.context.importSelected();
  await flush();

  const importCall = env.fetchCalls.find((call) => call.url.endsWith("/extension/videos/import"));
  assert(importCall, "import call should be made");
  const body = JSON.parse(importCall.options.body);
  assert(body.candidateId === "page-url", "import should send selected candidate id");
  assert(body.candidateUrl === "https://www.bilibili.com/video/BV1demo/", "import should send selected candidate url");
  assert(body.resolvedCandidates.length === 1, "import should send selected resolved candidate");
}

async function testImportSendsResolvedBilibiliApiCandidate() {
  const env = runPopupTest({
    pageScan: {
      pageUrl: "https://www.bilibili.com/video/BV1demo/",
      pageTitle: "Bilibili demo",
      videoCount: 1,
      streams: []
    },
    resolveResponse: {
      candidates: [{
        id: "bilibili-api-BV1demo",
        title: "Bilibili demo",
        sourceUrl: "https://www.bilibili.com/video/BV1demo/",
        extractor: "bilibili-api",
        formats: [{
          formatId: "bilibili-api-80",
          label: "1080P 高清 1080p avc1",
          height: 1080,
          sourceUrl: "https://upos.example.test/video-1080.m4s",
          companionAudioUrl: "https://upos.example.test/audio.m4s"
        }, {
          formatId: "bilibili-api-64",
          label: "720P 高清 720p avc1",
          height: 720,
          sourceUrl: "https://upos.example.test/video-720.m4s",
          companionAudioUrl: "https://upos.example.test/audio.m4s"
        }]
      }]
    }
  });

  await env.context.__initialRefresh;
  env.elements.format.value = "bilibili-api-80";
  await env.context.importSelected();
  await flush();

  const importCall = env.fetchCalls.find((call) => call.url.endsWith("/extension/videos/import"));
  const body = JSON.parse(importCall.options.body);
  assert(body.formatId === "bilibili-api-80", "import should send selected Bilibili API format");
  assert(body.resolvedCandidates[0].id === "bilibili-api-BV1demo", "import should include resolved Bilibili API candidate");
  assert(body.resolvedCandidates[0].formats[0].sourceUrl === "https://upos.example.test/video-1080.m4s", "import should include selected video track URL data");
  assert(body.resolvedCandidates[0].formats[0].companionAudioUrl === "https://upos.example.test/audio.m4s", "import should include companion audio URL data");
}

async function testImportSendsSelectedNoteStyle() {
  const env = runPopupTest({
    pageScan: {
      pageUrl: "https://example.test/watch",
      pageTitle: "Style demo",
      videoCount: 1,
      streams: []
    },
    resolveResponse: []
  });

  await env.context.__initialRefresh;
  env.elements.noteStyle.value = "academic";
  await env.context.importSelected();
  await flush();

  const importCall = env.fetchCalls.find((call) => call.url.endsWith("/extension/videos/import"));
  const body = JSON.parse(importCall.options.body);
  assert(body.noteStyle === "academic", "import should send selected note style");
}

async function testFragmentsAreFilteredBeforeResolve() {
  const env = runPopupTest({
    pageScan: {
      pageUrl: "https://example.test/watch",
      pageTitle: "Fragment demo",
      videoCount: 1,
      streams: [
        { url: "https://cdn.example.test/chunk-1.m4s", label: "DASH media segment", isFragment: true },
        { url: "https://cdn.example.test/segment-1.ts", label: "HLS media segment", isFragment: true },
        { url: "https://cdn.example.test/master.m3u8", label: "HLS stream" }
      ]
    },
    resolveResponse: []
  });

  await env.context.__initialRefresh;

  const resolveCall = env.fetchCalls.find((call) => call.url.endsWith("/extension/videos/resolve"));
  assert(resolveCall, "resolve call should be made");
  const body = JSON.parse(resolveCall.options.body);
  assert(body.detectedStreams.length === 1, "only the manifest should be sent to resolve");
  assert(body.detectedStreams[0].url === "https://cdn.example.test/master.m3u8", "manifest should be preserved");
}

async function testSelectedVideoStreamsArePreferred() {
  const selectedStream = { url: "https://cdn.example.test/selected.m3u8", label: "Selected HLS" };
  const pageStream = { url: "https://cdn.example.test/page.m3u8", label: "Page HLS" };
  const env = runPopupTest({
    backgroundSelection: {
      pageUrl: "https://example.test/watch",
      pageTitle: "Selected page",
      label: "Selected video",
      videoCount: 1,
      streams: [selectedStream]
    },
    pageScan: {
      pageUrl: "https://example.test/watch",
      pageTitle: "Page",
      videoCount: 1,
      streams: [pageStream]
    },
    resolveResponse: []
  });

  await env.context.__initialRefresh;

  assert(env.elements.status.textContent === "视频已就绪", "selected resolve should complete");
  const resolveCall = env.fetchCalls.find((call) => call.url.endsWith("/extension/videos/resolve"));
  const body = JSON.parse(resolveCall.options.body);
  assert(body.detectedStreams.length === 1, "only selected streams should be resolved");
  assert(body.detectedStreams[0].url === selectedStream.url, "selected stream should be preferred");
  assert(env.elements.candidate.children[0].value === "selected-video", "selected fallback candidate should render");
}

async function testSelectedBlobStreamsDoNotOverridePageStreams() {
  const pageStream = { url: "https://cdn.example.test/page.m3u8", label: "Page HLS" };
  const env = runPopupTest({
    backgroundSelection: {
      pageUrl: "https://example.test/watch",
      pageTitle: "Selected page",
      label: "Selected canvas player",
      videoCount: 1,
      streams: [{ url: "blob:https://example.test/123", label: "Selected blob", isBlob: true }]
    },
    pageScan: {
      pageUrl: "https://example.test/watch",
      pageTitle: "Page",
      videoCount: 1,
      streams: [pageStream]
    },
    resolveResponse: []
  });

  await env.context.__initialRefresh;

  const resolveCall = env.fetchCalls.find((call) => call.url.endsWith("/extension/videos/resolve"));
  const body = JSON.parse(resolveCall.options.body);
  assert(body.detectedStreams.length === 1, "blob-only selected streams should not replace page streams");
  assert(body.detectedStreams[0].url === pageStream.url, "page stream should be used when selected stream is blob-only");
}

async function testCanceledJobStopsPolling() {
  const env = runPopupTest({
    pageScan: {
      pageUrl: "https://example.test/watch",
      pageTitle: "Cancel demo",
      videoCount: 1,
      streams: []
    },
    resolveResponse: [],
    jobResponse: {
      status: "canceled",
      progress: 100,
      message: "Canceled in AInote"
    }
  });

  await env.context.__initialRefresh;
  await env.context.importSelected();
  await flush();

  assert(typeof env.intervalCallback === "function", "polling callback should be registered");
  await env.intervalCallback();
  await flush();

  assert(env.elements.progressText.textContent === "已在 AInote 取消", "canceled message should be shown");
  assert(env.elements.bar.style.width === "100%", "canceled job should show a full terminal bar");
  assert(env.clearIntervalCalls >= 1, "canceled job should stop polling");
  assert(env.elements.send.disabled === false, "send button should be re-enabled after cancellation");
}

(async () => {
  await testPageFallbackWhenResolveIsSlow();
  await testAppOfflineDisablesSend();
  await testResolveErrorsAreShownWithFallback();
  await testResolveDiagnosticsAreShown();
  await testHighestQualityCandidateIsSelectedByDefault();
  await testCopyDiagnosticsIncludesResolveDetails();
  await testCookiesAreOptIn();
  await testCookiesCanBeDisabled();
  await testBilibiliMissingSessdataWarnsAboutLowQuality();
  await testDouyinCookiesReadFreshCookieDomains();
  await testImportSendsCandidateUrl();
  await testImportSendsResolvedBilibiliApiCandidate();
  await testImportSendsSelectedNoteStyle();
  await testFragmentsAreFilteredBeforeResolve();
  await testSelectedVideoStreamsArePreferred();
  await testSelectedBlobStreamsDoNotOverridePageStreams();
  await testCanceledJobStopsPolling();
  console.log("extension popup tests passed");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
