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
    textContent: "",
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

const messages = [];
const listeners = {};
const documentElement = createElement("html");
const body = createElement("body");
const iframe = createElement("iframe", { src: "https://player.example.test/embed/abc" });

const context = {
  URL,
  Date,
  setTimeout() {},
  navigator: {
    userAgent: "Chrome Test",
    languages: ["zh-CN", "en"],
    language: "zh-CN"
  },
  location: {
    href: "https://site.example.test/watch",
    origin: "https://site.example.test"
  },
  document: {
    title: "Picker demo",
    documentElement,
    body,
    scripts: [
      {
        textContent: 'window.__DATA__={"play_addr":{"url_list":["https:\\/\\/www.douyin.com\\/aweme\\/v1\\/play\\/?video_id=abc","https:\\/\\/www.douyin.com\\/aweme\\/v1\\/playwm\\/?video_id=wm","https:\\/\\/v3-dy-o.douyinvod.com\\/tos-cn-ve-15\\/abc\\/video"]},"video":{"bitrateInfo":[{"PlayAddr":{"UrlList":["https:\\u002F\\u002Fv3-dy-o.douyinvod.com\\u002Ftos-cn-ve-15\\u002Fabc\\u002Fbitrate-video?mime_type=video_mp4\\u0026a=b"]}}]}}'
      }
    ],
    createElement: (tag) => createElement(tag),
    querySelector: () => iframe,
    querySelectorAll: () => [],
    addEventListener(type, callback) {
      listeners[type] = callback;
    },
    removeEventListener(type) {
      delete listeners[type];
    }
  },
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

let response = null;
listeners.message({ type: "START_VIDEO_PICKER" }, null, (value) => {
  response = value;
});
assert(response?.ok === true, "picker should start");

listeners.click({
  target: iframe,
  preventDefault() {},
  stopPropagation() {}
});

const selected = messages.find((item) => item.type === "SET_SELECTED_VIDEO")?.selection;
assert(selected, "selected video message should be sent");
assert(selected.pageUrl === "https://player.example.test/embed/abc", "iframe src should become selected page url");
assert(selected.sourceUrl === "https://player.example.test/embed/abc", "iframe source url should be preserved");
assert(selected.streams[0].url === "https://player.example.test/embed/abc", "iframe src should be sent as selected stream");

let scanResponse = null;
listeners.message({ type: "SCAN_PAGE_VIDEOS" }, null, (value) => {
  scanResponse = value;
});
assert(scanResponse.headers["User-Agent"] === "Chrome Test", "scan should include browser user agent");
assert(scanResponse.headers.Referer === "https://site.example.test/watch", "scan should include referer");
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

console.log("extension content picker tests passed");
