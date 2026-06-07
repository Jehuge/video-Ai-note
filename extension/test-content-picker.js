const fs = require("fs");
const path = require("path");
const vm = require("vm");

const source = fs.readFileSync(path.join(__dirname, "content.js"), "utf8");

function createElement(tag, props = {}) {
  return {
    tag,
    src: props.src || "",
    currentSrc: props.currentSrc || "",
    videoHeight: props.videoHeight || 0,
    videoWidth: props.videoWidth || 0,
    style: {},
    textContent: props.textContent || "",
    parent: null,
    remove() {},
    appendChild(child) {
      child.parent = this;
    },
    getBoundingClientRect() {
      return props.rect || { x: 10, y: 20, left: 10, top: 20, width: 640, height: 360 };
    },
    matches(selector) {
      return selector.split(",").map((item) => item.trim()).some((item) => {
        if (item === tag) return true;
        if (item === `${tag}[src]`) return Boolean(this.src);
        return false;
      });
    },
    closest(selector) {
      return this.matches(selector) ? this : null;
    },
    querySelector() {
      return null;
    },
    querySelectorAll() {
      return [];
    },
    getAttribute() {
      return "";
    }
  };
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function createDocument({ title = "Picker demo", scripts = [], elements = {} } = {}) {
  const documentElement = createElement("html");
  const body = createElement("body");
  const scriptElements = scripts.map((item) => {
    if (typeof item === "string") {
      return { textContent: item };
    }
    return item;
  });
  return {
    title,
    documentElement,
    body,
    scripts: scriptElements,
    createElement: (tag) => createElement(tag),
    getElementById(id) {
      return elements[id] || null;
    },
    querySelector: () => elements.querySelector || null,
    querySelectorAll: () => [],
    addEventListener(type, callback) {
      elements.listeners[type] = callback;
    },
    removeEventListener(type) {
      delete elements.listeners[type];
    }
  };
}

function runContentTest({ location, scripts = [], elements = {} }) {
  const messages = [];
  const listeners = {};
  elements.listeners = listeners;

  const context = {
    URL,
    Date,
    setTimeout() {},
    navigator: {
      userAgent: "Chrome Test",
      languages: ["zh-CN", "en"],
      language: "zh-CN"
    },
    location,
    document: createDocument({ scripts, elements }),
    performance: {
      getEntriesByType: () => []
    },
    chrome: {
      runtime: {
        sendMessage(message) {
          messages.push(message);
        },
        onMessage: {
          addListener(callback) {
            listeners.message = callback;
          }
        }
      }
    }
  };

  vm.createContext(context);
  vm.runInContext(source, context, { filename: "content.js" });
  return { context, messages, listeners };
}

function scanPage(listeners) {
  let scanResponse = null;
  listeners.message({ type: "SCAN_PAGE_VIDEOS" }, null, (value) => {
    scanResponse = value;
  });
  return scanResponse;
}

function testPickerAndBilibiliPlayInfo() {
  const iframe = createElement("iframe", { src: "https://player.example.test/embed/abc" });
  const env = runContentTest({
    location: {
      href: "https://www.bilibili.com/video/BV1demo/",
      origin: "https://www.bilibili.com",
      hostname: "www.bilibili.com"
    },
    elements: { querySelector: iframe },
    scripts: [
      'window.__DATA__={"play_addr":{"url_list":["https:\\/\\/www.douyin.com\\/aweme\\/v1\\/play\\/?video_id=abc","https:\\/\\/www.douyin.com\\/aweme\\/v1\\/playwm\\/?video_id=wm","https:\\/\\/v3-dy-o.douyinvod.com\\/tos-cn-ve-15\\/abc\\/video"]},"video":{"bitrateInfo":[{"PlayAddr":{"UrlList":["https:\\u002F\\u002Fv3-dy-o.douyinvod.com\\u002Ftos-cn-ve-15\\u002Fabc\\u002Fbitrate-video?mime_type=video_mp4\\u0026a=b"]}}]}}',
      'window.__playinfo__={"code":0,"data":{"dash":{"video":[{"baseUrl":"https://upos.example.test/video-1080.m4s","height":1080,"width":1920,"bandwidth":2000000,"codecs":"avc1.640028","mimeType":"video/mp4"},{"baseUrl":"https://upos.example.test/video-480.m4s","height":480,"width":852,"bandwidth":800000,"codecs":"avc1.64001f","mimeType":"video/mp4"}],"audio":[{"baseUrl":"https://upos.example.test/audio.m4s","bandwidth":128000,"codecs":"mp4a.40.2","mimeType":"audio/mp4"}]}}};'
    ]
  });

  let response = null;
  env.listeners.message({ type: "START_VIDEO_PICKER" }, null, (value) => {
    response = value;
  });
  assert(response?.ok === true, "picker should start");

  env.listeners.click({
    target: iframe,
    preventDefault() {},
    stopPropagation() {}
  });

  const selected = env.messages.find((item) => item.type === "SET_SELECTED_VIDEO")?.selection;
  assert(selected, "selected video message should be sent");
  assert(selected.pageUrl === "https://player.example.test/embed/abc", "iframe src should become selected page url");
  assert(selected.sourceUrl === "https://player.example.test/embed/abc", "iframe source url should be preserved");
  assert(selected.streams[0].url === "https://player.example.test/embed/abc", "iframe src should be sent as selected stream");

  const scanResponse = scanPage(env.listeners);
  assert(scanResponse.headers["User-Agent"] === "Chrome Test", "scan should include browser user agent");
  assert(scanResponse.headers.Referer === "https://www.bilibili.com/video/BV1demo/", "scan should include referer");
  assert(
    scanResponse.streams.some((stream) => stream.url.includes("/aweme/v1/play/?video_id=abc")),
    "scan should collect embedded Douyin play URLs"
  );
  assert(
    scanResponse.streams.some((stream) => stream.url.includes("/aweme/v1/playwm/?video_id=wm")),
    "scan should collect embedded Douyin playwm URLs"
  );
  assert(
    scanResponse.streams.some((stream) => stream.url.includes("douyinvod.com/tos-cn-ve-15/abc/video")),
    "scan should collect embedded Douyin CDN URLs"
  );
  assert(
    scanResponse.streams.some((stream) => stream.url.includes("douyinvod.com/tos-cn-ve-15/abc/bitrate-video")),
    "scan should collect escaped Douyin bitrate URLs"
  );
  const biliStream = scanResponse.streams.find((stream) => stream.url === "https://upos.example.test/video-1080.m4s");
  assert(biliStream, "scan should collect Bilibili page playinfo video track");
  assert(biliStream.source === "bilibili-playinfo", "Bilibili playinfo stream should be tagged");
  assert(biliStream.height === 1080, "Bilibili playinfo stream should keep height");
  assert(biliStream.companionAudioUrl === "https://upos.example.test/audio.m4s", "Bilibili playinfo stream should include companion audio");
}

function testDouyinUniversalPageData() {
  const universal = {
    __DEFAULT_SCOPE__: {
      "webapp.video-detail": {
        itemInfo: {
          itemStruct: {
            id: "7380000000000000000",
            desc: "Douyin demo",
            video: {
              height: 720,
              width: 1280,
              playAddr: [{ src: "https://v3-dy-o.douyinvod.com/tos-cn-ve-15/demo/playaddr?mime_type=video_mp4" }],
              downloadAddr: {
                url: "https://v3-dy-o.douyinvod.com/tos-cn-ve-15/demo/download?mime_type=video_mp4"
              },
              bitrateInfo: [{
                GearName: "normal_1080_0",
                PlayAddr: {
                  UrlList: ["https:\\u002F\\u002Fv3-dy-o.douyinvod.com\\u002Ftos-cn-ve-15\\u002Fdemo\\u002F1080p-video?mime_type=video_mp4"],
                  Height: 1080,
                  Width: 1920,
                  DataSize: 123456,
                  BitRate: 2000000,
                  CodecType: "h264"
                }
              }]
            }
          }
        }
      }
    }
  };
  const env = runContentTest({
    location: {
      href: "https://www.douyin.com/video/7380000000000000000",
      origin: "https://www.douyin.com",
      hostname: "www.douyin.com"
    },
    elements: {
      "__UNIVERSAL_DATA_FOR_REHYDRATION__": {
        textContent: JSON.stringify(universal)
      }
    }
  });

  const scanResponse = scanPage(env.listeners);
  const douyinStreams = scanResponse.streams.filter((stream) => stream.source === "douyin-page-data");

  assert(douyinStreams.length >= 3, "scan should collect Douyin page-data stream URLs");
  assert(douyinStreams.some((stream) => stream.height === 1080), "Douyin bitrate height should be preserved");
  assert(douyinStreams.every((stream) => stream.isDouyinPageData === true), "Douyin page-data marker should be sent");
  assert(
    douyinStreams.some((stream) => stream.url.includes("/1080p-video") && stream.filesize === 123456),
    "Douyin bitrate metadata should be preserved"
  );
}

function testDouyinAwemeListPageData() {
  const env = runContentTest({
    location: {
      href: "https://www.douyin.com/video/7380000000000000001",
      origin: "https://www.douyin.com",
      hostname: "www.douyin.com"
    },
    scripts: [
      'window.__INITIAL_STATE__={"awemeList":[{"aweme_id":"7380000000000000001","desc":"list demo","video":{"height":720,"width":1280,"play_addr":{"url_list":["https:\\/\\/v3-dy-o.douyinvod.com\\/tos-cn-ve-15\\/list-demo\\/play?mime_type=video_mp4"]}}}]}'
    ]
  });

  const scanResponse = scanPage(env.listeners);
  const stream = scanResponse.streams.find((item) => item.source === "douyin-page-data");
  assert(stream, "scan should collect Douyin awemeList page-data stream");
  assert(stream.url.includes("/list-demo/play"), "awemeList stream URL should be preserved");
  assert(stream.height === 720, "awemeList stream should preserve video height");
  assert(stream.isDouyinPageData === true, "awemeList stream should be marked as Douyin page data");
}

testPickerAndBilibiliPlayInfo();
testDouyinUniversalPageData();
testDouyinAwemeListPageData();

console.log("extension content picker tests passed");
