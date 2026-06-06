const fs = require("fs");
const path = require("path");
const vm = require("vm");

const popupSource = fs
  .readFileSync(path.join(__dirname, "popup.js"), "utf8")
  .replace(/\nrefresh\(\);\s*$/, "\nglobalThis.__initialRefresh = refresh();");

function createElement(id) {
  return {
    id,
    textContent: "",
    value: "",
    checked: false,
    disabled: false,
    innerHTML: "",
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
}

function runPopupTest({
  pageScan,
  appReady = true,
  resolveResponse,
  cookiesChecked = false,
  backgroundSelection = null,
  jobResponse = { status: "completed", progress: 100 }
}) {
  const elements = {};
  for (const id of ["status", "pick", "refresh", "candidate", "format", "noteStyle", "screenshot", "cookies", "autoRun", "send", "empty", "progress", "bar", "progressText"]) {
    elements[id] = createElement(id);
  }
  elements.cookies.checked = cookiesChecked;
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
  const timers = [];
  let intervalCallback = null;
  let clearIntervalCalls = 0;

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
          return [{ name: "SESSDATA", value: "demo" }];
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
        return {
          ok: true,
          status: 200,
          json: async () => ({ data: { candidates: resolveResponse || [] } })
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
  assert(env.elements.status.textContent === "先用当前选择，AInote 会继续解析", "resolve failure should keep fallback status");
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

async function testCookiesAreOptIn() {
  const env = runPopupTest({
    cookiesChecked: true,
    pageScan: {
      pageUrl: "https://www.bilibili.com/video/BV1demo/",
      pageTitle: "Bilibili demo",
      videoCount: 1,
      streams: []
    },
    resolveResponse: []
  });

  await env.context.__initialRefresh;

  assert(env.cookieCalls.length === 1, "cookies should be read during resolve only when checked");
  const resolveCall = env.fetchCalls.find((call) => call.url.endsWith("/extension/videos/resolve"));
  assert(resolveCall, "resolve call should be made");
  assert(JSON.parse(resolveCall.options.body).cookies === "SESSDATA=demo", "resolve should send selected site cookies");
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
  await testCookiesAreOptIn();
  await testImportSendsCandidateUrl();
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
