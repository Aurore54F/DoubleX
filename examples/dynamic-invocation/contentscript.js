var f = function(event) {
    chrome.runtime.sendMessage(event.data.foo);
  };
window.onmessage = f;