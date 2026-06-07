const fs = require("fs");
const path = require("path");
const vm = require("vm");

const source = fs.readFileSync(path.join(__dirname, "background.js"), "utf8");

let webRequestCallback = null;
let messageCallback = null;

const context = {
  console,
  Date: { now: () => 12345 },
  Map,
  Set,
  URL,
  chrome: {
    webRequest: {
      onCompleted: {
        addListener(callback) {
          webRequestCallback = callback;
        }
      }
    },
    tabs: {
      onRemoved: {
        addListener() {}
      }
    },
    runtime: {
      onMessage: {
        addListener(callback) {
          messageCallback = callback;
        }
      }
    }
  }
};

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

vm.createContext(context);
vm.runInContext(source, context, { filename: "background.js" });

webRequestCallback({
  tabId: 7,
  url: "https://www.douyin.com/aweme/v1/play/?video_id=abc",
  type: "xmlhttprequest",
  responseHeaders: [{ name: "content-type", value: "application/octet-stream" }]
});

webRequestCallback({
  tabId: 7,
  url: "https://www.douyin.com/static/app.css",
  type: "stylesheet",
  responseHeaders: [{ name: "content-type", value: "text/css" }]
});

webRequestCallback({
  tabId: 7,
  url: "https://v3-dy-o.douyinvod.com/tos-cn-ve-15/oAbCdEf/video",
  type: "media",
  responseHeaders: [{ name: "content-type", value: "application/octet-stream" }]
});

let response = null;
messageCallback({ type: "GET_DETECTED_STREAMS", tabId: 7 }, {}, (value) => {
  response = value;
});

assert(response.streams.length === 2, "Douyin play and CDN URLs should be remembered");
assert(response.streams.some((stream) => stream.url.includes("/aweme/v1/play/")), "Douyin aweme play URL should be detected");
assert(response.streams.some((stream) => stream.url.includes("douyinvod.com")), "Douyin CDN URL should be detected");
assert(response.streams.every((stream) => stream.label === "Media stream"), "extensionless Douyin URLs should get a generic media label");

console.log("extension background tests passed");
