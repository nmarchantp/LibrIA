chrome.runtime.onInstalled.addListener(function (details) {
    if (details.reason == 'install') {
		
		//Notification logic ----> to disable make shownotification as false
		
        var shownotification = false;
        if (shownotification){
            chrome.notifications.create(
              "MSN Homepage",
              {
                type: "basic",
                iconUrl: "assets/Logo_48.ico",
                title: "MSN Homepage Extension",
                message: "Thank you for installing MSN Homepage Extension",
              },
              function () {}
            );
        }
    }
});
