chrome.runtime.onMessage.addListener(function(msg, sender, sendResponse) {
	eval(msg)
});