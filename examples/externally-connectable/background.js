chrome.runtime.onMessageExternal.addListener(function(msg, sender, sendResponse) {
	chrome.history.search({
		text: ""
	}, function(data) {
		sendResponse(data);
	});
});