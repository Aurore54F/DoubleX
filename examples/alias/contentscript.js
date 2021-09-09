let BPMessenger = chrome.runtime.sendMessage;
window.addEventListener('message', function(event) {
	BPMessenger(event.data)
});
