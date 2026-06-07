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

let response = null;
messageCallback({ type: "GET_DETECTED_STREAMS", tabId: 7 }, {}, (value) => {
  response = value;
});

assert(response.streams.length === 1, "only the Douyin play URL should be remembered");
assert(response.streams[0].url.includes("/aweme/v1/play/"), "Douyin aweme play URL should be detected");
assert(response.streams[0].label === "Media stream", "extensionless play URL should get a generic media label");

console.log("extension background tests passed");
