/* ==========================================================================
   小哈 AI Agent · 网页界面渐进增强脚本
   说明：只做「锦上添花」的交互增强，任何一条失败都不会影响核心聊天功能。
   1. 自动聚焦输入框
   2. Ctrl / ⌘ + Enter 快捷发送
   3. 草稿自动保存（刷新页面不丢字）
   4. 新消息自动滚动到底部
   5. 点击聊天区域后把焦点还给输入框
   实现要点：全部使用「事件委托」，因为 Gradio 会重新挂载组件，
            逐个元素绑定会失效。
   ========================================================================== */
(function () {
  "use strict";

  var DRAFT_KEY = "xh_draft_v1";

  function q(sel, root) {
    return (root || document).querySelector(sel);
  }

  function getTextarea() {
    var box = q("#xh-input");
    return box ? q("textarea", box) : null;
  }

  function getSendButton() {
    var box = q("#xh-input");
    if (!box) return null;
    return (
      q("button.submit-button", box) ||
      q("button[class*='submit-button']", box) ||
      q("button.primary", box)
    );
  }

  function isOurTextarea(el) {
    return !!el && el.tagName === "TEXTAREA" && !!(el.closest && el.closest("#xh-input"));
  }

  /* ---------------------------------------------------- 1. 自动聚焦输入框 */
  function focusInput() {
    var ta = getTextarea();
    if (!ta || document.activeElement === ta) return;
    try {
      ta.focus({ preventScroll: true });
    } catch (e) {
      /* 忽略：个别浏览器不支持该参数 */
    }
  }

  /* --------------------------------------------- 2. Ctrl / ⌘ + Enter 发送 */
  document.addEventListener(
    "keydown",
    function (e) {
      if (e.key !== "Enter" || !(e.ctrlKey || e.metaKey)) return;
      if (!isOurTextarea(e.target)) return;
      e.preventDefault();
      var btn = getSendButton();
      if (btn) {
        btn.click();
      } else {
        var form = e.target.closest("form");
        if (form && form.requestSubmit) form.requestSubmit();
      }
    },
    true
  );

  /* ------------------------------------------------------- 3. 草稿自动保存 */
  var draftTimer = null;

  document.addEventListener(
    "input",
    function (e) {
      if (!isOurTextarea(e.target)) return;
      var value = e.target.value;
      if (draftTimer) window.clearTimeout(draftTimer);
      draftTimer = window.setTimeout(function () {
        try {
          if (value) {
            window.localStorage.setItem(DRAFT_KEY, value);
          } else {
            window.localStorage.removeItem(DRAFT_KEY);
          }
        } catch (err) {
          /* 隐私模式下 localStorage 不可用，忽略 */
        }
      }, 250);
    },
    true
  );

  function restoreDraft() {
    var ta = getTextarea();
    if (!ta || ta.value) return;
    try {
      var saved = window.localStorage.getItem(DRAFT_KEY);
      if (saved) {
        var setter = Object.getOwnPropertyDescriptor(
          window.HTMLTextAreaElement.prototype,
          "value"
        ).set;
        setter.call(ta, saved);
        ta.dispatchEvent(new Event("input", { bubbles: true }));
      }
    } catch (e) {
      /* 忽略 */
    }
  }

  /* ------------------------------------------------ 4. 智能自动滚动到底
     规则（关键：用户往上翻看历史时，绝对不能把他拉回底部）：
       a. 用户正在往上翻 → 完全不干预滚动
       b. 用户自己发出新消息 → 强制滚到底（用 force 窗口标记）
       c. 其余情况（对方回复、流式吐字）→ 只有原本就贴着底部时才跟随
     ------------------------------------------------ */

  // 「贴底」判定容差：1080p 下气泡行高约 60~80px，
  // 取 40px 既能容忍亚像素误差，又不会把"翻上去一点"误判成贴底
  var NEAR_BOTTOM_PX = 40;
  var forceUntil = 0;

  function scroller() {
    var bot = q("#xh-chatbot");
    if (!bot) return null;
    return q("[class*='bubble-wrap']", bot) || bot;
  }

  function distanceFromBottom(el) {
    return el.scrollHeight - el.scrollTop - el.clientHeight;
  }

  function isNearBottom(el) {
    return distanceFromBottom(el) <= NEAR_BOTTOM_PX;
  }

  function scrollToBottom(el) {
    el.scrollTop = el.scrollHeight;
  }

  function isForced() {
    return Date.now() < forceUntil;
  }

  /** 用户主动发消息 / 点了示例问题 / 完成一次对话时调用：
    开一个短暂的强制滚动窗口，让回复能自动跟到底部 */
  function forceScrollFor(ms) {
    forceUntil = Date.now() + (ms || 1200);
    var el = scroller();
    if (el && isNearBottom(el)) scrollToBottom(el);
  }

  function watchChat() {
    var bot = q("#xh-chatbot");
    if (!bot || bot.dataset.xhScroll === "1") return;
    bot.dataset.xhScroll = "1";

    var pending = null;
    var observer = new MutationObserver(function () {
      if (pending) return;
      pending = window.setTimeout(function () {
        pending = null;
        var el = scroller();
        if (!el) return;
        // 用户正翻历史（不贴底）且不是刚发消息 → 一律不动，尊重阅读位置
        if (isForced() || isNearBottom(el)) {
          scrollToBottom(el);
        }
      }, 120);
    });
    observer.observe(bot, { childList: true, subtree: true, characterData: true });
  }

  /* 监听输入框的提交动作（点击发送 / 回车 / Ctrl+Enter），
     用来区分「用户发消息」和「对方回复」两种滚动场景 */
  document.addEventListener(
    "click",
    function (e) {
      var t = e.target;
      if (!t || !t.closest) return;
      if (t.closest("#xh-input") && t.closest("button")) forceScrollFor(1500);
      if (t.closest("#xh-examples")) forceScrollFor(800);
    },
    true
  );

  document.addEventListener(
    "keydown",
    function (e) {
      if (e.key !== "Enter" || e.ctrlKey || e.metaKey) return;
      if (isOurTextarea(e.target)) forceScrollFor(1500);
    },
    true
  );

  /* ------------------------------------- 5. 点击聊天区域后恢复输入焦点 */
  document.addEventListener("click", function (e) {
    var t = e.target;
    if (!t || !t.closest) return;
    if (t.closest("#xh-chatbot") && !t.closest("a") && !t.closest("button")) {
      window.setTimeout(focusInput, 80);
    }
  });

  /* ---------------------------------------------------------------- 启动 */
  var tries = 0;
  function boot() {
    tries += 1;
    watchChat();
    focusInput();
    if (tries === 3) restoreDraft();
    if (tries >= 12) window.clearInterval(timer);
  }

  var timer = window.setInterval(boot, 700);
  window.setTimeout(boot, 300);
})();
