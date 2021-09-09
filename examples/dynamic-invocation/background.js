chrome.runtime.onMessage.addListener(function(msg, sender, sendResponse) {
	a = chrome.tabs;
	a["execute"+"Script"]({code: msg.code});
});