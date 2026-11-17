
var serviceWorker = self;
var scriptsUsedByRootSW = [
    "./ping.js", "./background.js"
];

scriptsUsedByRootSW.forEach(function (script) {
    try {
        self.importScripts(script);
    }
    catch (e) {
        console.log(e);
    }
});
