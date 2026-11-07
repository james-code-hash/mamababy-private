// 《帕帕貝貝家》鏡頭動畫軌跡：用假的 GSAP 跑每鏡 composition 的 <script>，記下每一個 tween 呼叫。
// 輸入（stdin）：[{id, html}]；輸出（stdout）：{id: [[method, target, vars..., position], ...]}。
// 兩版 engine 對同一份分鏡產生的軌跡一樣＝畫面一樣（tween 參數、時間、順序都相同），不用開瀏覽器。
"use strict";
const vm = require("vm");

function recorder(calls, name) {
  const rec = (method) => (...args) => {
    calls.push([name, method, ...args.map((a) => (a && a.__tl ? `tl:${a.__tl}` : a))]);
    return self;
  };
  const self = { __tl: name };
  for (const m of ["to", "from", "fromTo", "set", "add", "call"]) self[m] = rec(m);
  return self;
}

function trace(html) {
  const m = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
  const code = m.length ? m[m.length - 1][1] : "";
  const calls = [];
  let n = 0;
  const gsap = { timeline: () => recorder(calls, n++ === 0 ? "root" : `t${n - 1}`) };
  const document = { querySelector: (sel) => (html.includes(`id="${sel.split(" ")[0].slice(1)}"`) ? {} : null) };
  const window = {};
  vm.runInNewContext(code, { gsap, document, window, Math, JSON });
  return JSON.parse(JSON.stringify(calls));
}

let input = "";
process.stdin.on("data", (d) => (input += d));
process.stdin.on("end", () => {
  const out = {};
  for (const s of JSON.parse(input)) out[s.id] = trace(s.html);
  process.stdout.write(JSON.stringify(out));
});
