const CHANNEL = 'Channel';
const MACHINE_ID = 'MachineID';
const DPC = 'DPC';
const MARKET = 'Market';
const PARTNER_CODE = 'PartnerCode';
const BLOCKING_URL_BPK = "*://www.msn.com/*?pc=BG04&osmkt=*";
const QSPC = 'qspc';
var bingUrl = "https://www.bing.com/";
var browserDefaultsUrl = "https://browserdefaults.microsoft.com/";
var chromeWS = "https://chrome.google.com/";
var feedbackFwlink = "https://go.microsoft.com/fwlink/?linkid=2138838";
var defaultPC = "BG04";
var manifestData = chrome.runtime.getManifest();
var ExtensionVersion = manifestData.version;		
									

var market = "";
try {
    market = chrome.i18n.getMessage("ExtnMarket");
}
catch (exception) {
    market = navigator.language.toLocaleLowerCase();
}
var extensionId = chrome.runtime.id;

var DAILY_PING_ALARM = "DAILYPINGALARM"
var dailyPingAlarmPeriodInMins = 1440; // 24 hours

var PING_ALARM = "BPK_PINGALARM";
let getPingAlarm = chrome.alarms.get(PING_ALARM);
getPingAlarm.then(dailyPingAlarm);

function dailyPingAlarm(alarm) {
    if (!alarm) {
        chrome.alarms.create(PING_ALARM, {
            delayInMinutes: 1
        });
    }
    else {
        console.log("Existing Ping Alarm: " + alarm.name);
    }
}

chrome.alarms.onAlarm.addListener((alarm) => {
    if (alarm.name === PING_ALARM) {
        chrome.storage.local.get([MACHINE_ID, "ExtensionUpdated", "updatePingSent", DPC, PARTNER_CODE], (items) => {
            //Sets '_NTPC' session cookies in bing.com domain whenever background.js gets executed
            chrome.cookies.set({
                url: bingUrl, domain: '.bing.com', name: '_NTPC', value: !items[PARTNER_CODE]? defaultPC : items[PARTNER_CODE], sameSite: 'no_restriction', secure: true
            }, function (cookie) {
        
            });

            var _dpc = items[DPC] ?items[DPC] : "organic";
            if (_dpc != undefined && _dpc != "" && _dpc != null) {
                chrome.cookies.set({ url: bingUrl, domain: '.bing.com', name: '_DPC', value: _dpc, sameSite: 'no_restriction', secure: true }, function (cookie) {
                });
            }
           
            if (items.ExtensionUpdated == "true" && items.updatePingSent == "false") {
                chrome.storage.local.set({
                    "updatePingSent": "true",
                    "ExtensionUpdated": "false"
                });
                console.log("Update ping");
                //Call for Update Ping
                SendPingDetails("3");
            }

            //To redirect feedback page while uninstalling the extension
            var uninstallUrl = feedbackFwlink + "&extnID=" + extensionId + "&mkt=" + market + "&mid=" + items[MACHINE_ID] + "&br=gc";
            chrome.runtime.setUninstallURL(uninstallUrl);

            //Redirect Homepage with dynamic PC
            addHomepageRedirectRule(1, items[PARTNER_CODE], defaultPC, BLOCKING_URL_BPK);
        });
    }
});

chrome.runtime.onInstalled.addListener(function (details) {

    if (details.reason == 'install') {
         console.log("install");

        //Sets the default pc of the extension in chrome storage
        var promise = new Promise((resolve, reject) => {
            chrome.storage.local.set({
                ["MigratedLocalStorage"]: true,
                ["ExtnVersion"]: ExtensionVersion
            });
            resolve("organic");
        });
        promise
        .then(getBrowserDefaultDetails)
        .then((detailsObj) => {
            chrome.alarms.clear(DAILY_PING_ALARM);
            chrome.alarms.create(DAILY_PING_ALARM, {
                delayInMinutes: 1,
                periodInMinutes: dailyPingAlarmPeriodInMins,
            });

            SendPingDetails("1");

            //To redirect Analytic redirection page while installing the extension
            var redirectionURL = "https://go.microsoft.com/fwlink/?linkid=2128904&trackingid=" + chrome.runtime.id + "&partnercode=" + detailsObj.pc + "&browser=gc" + "&mkt=" + market;

            if (detailsObj.channel) {
                redirectionURL += "&channel=" + detailsObj.channel;
            }
            
            if (detailsObj.machineId) {
                redirectionURL += "&machineid=" + detailsObj.machineId;
            }

            chrome.tabs.create({ url: redirectionURL });

            chrome.storage.local.get([PARTNER_CODE], (items) => {
                addHomepageRedirectRule(1, items[PARTNER_CODE], defaultPC, BLOCKING_URL_BPK);
            });
       
        });
    }
    else if (details.reason == 'update') {
        chrome.storage.local.set({
            "updatePingSent": "false",
            "ExtensionUpdated": "true"
        });

        chrome.storage.local.get(["ExtnVersion", "MigratedLocalStorage", "ExtensionUpdatepageshown",PARTNER_CODE], function (items) {
            if (!items.ExtnVersion || items.ExtnVersion != chrome.runtime.getManifest().version) {
                chrome.storage.local.set({ "ExtnVersion": ExtensionVersion });
                if (!items.MigratedLocalStorage && !items.ExtensionUpdatepageshown) {
                    console.log("Display Migration HTML");
                    showhtmlpage();
                }
                addHomepageRedirectRule(1, items[PARTNER_CODE], defaultPC, BLOCKING_URL_BPK);
            }
        });
        chrome.alarms.clear(DAILY_PING_ALARM);
        chrome.alarms.create(DAILY_PING_ALARM, {
            delayInMinutes: 1,
            periodInMinutes: dailyPingAlarmPeriodInMins,
        }); 
    }
});

function showhtmlpage() {
    chrome.tabs.create({ url: "../Welcomepage/index.html?xid=1400&bmkt=" + market });
    chrome.storage.local.set({ "ExtensionUpdatepageshown": "True" });
}

function getBrowserDefaultDetails(channelID) {
	return new Promise((resolve) => {
		var details = {
			pc: '',
			machineId: guid(),
			channel: channelID,
		    dpc: ''
		};
        chrome.cookies.get({ url: browserDefaultsUrl, name: chrome.runtime.id }, function (cookie) {
            if (cookie) {
                var cookieValue = String(cookie.value).split('&');
                for (var i = 0; i < cookieValue.length; i++) {

                    var cookieData = cookieValue[i].split('=');

                    if (cookieData[0].toLocaleUpperCase() == "MI") {
                        details.machineId = cookieData[1];
                    }
                    else if (cookieData[0].toLocaleUpperCase() == "CH") {
                        details.channel = cookieData[1];
                    }
                    else if (cookieData[0].toLocaleUpperCase() == "PC") {
                        details.pc = cookieData[1];
                    }
                    else if (cookieData[0].toLocaleUpperCase() == "BM") {
                        details.bmkt = cookieData[1];
                    }

                }
                chrome.cookies.remove({ url: browserDefaultsUrl, name: chrome.runtime.id });
              
            }

            if (details.channel == "organic") {
                // Fetching  __utmz cookie value from https://chrome.google.com/
                chrome.cookies.get({ url: chromeWS, name: '__utmz' }, function (cookie) {
    
                    if (cookie) {
                        var chromeWSChannel = getChromeWSChannel(cookie.value);
                        if (chromeWSChannel != "") {
                            details.channel = chromeWSChannel;
                        }
                        chrome.cookies.remove({ url: chromeWS, name: '__utmz' });
                    }
                });
            }
            
            details.pc = details.pc ? details.pc : defaultPC;
            details.dpc = details.pc && details.pc !== defaultPC
                ? details.pc + '_' + details.channel
                : details.channel;
            if (details.pc) {
                details.qspc = details.pc;
            }
            chrome.storage.local.set(
                {
                    [MACHINE_ID]: details.machineId,
                    [PARTNER_CODE]: details.pc,
                    [CHANNEL]: details.channel,
                    [MARKET]: details.bmkt,
                    [DPC]: details.dpc,
                    [QSPC]:details.qspc
                },
                () => {
                    resolve(details);
                },
            );
        });
	});
}
	
chrome.alarms.onAlarm.addListener((alarm) => {
    if (alarm.name === DAILY_PING_ALARM) {
        console.log("es2 ping - call getCookie")
        SendPingDetails("2");     
    }
});


/* Function to create an unique machine id */
function guid() {
    function s4() {
        return Math.floor((1 + Math.random()) * 0x10000)
            .toString(16)
            .substring(1);
    }
    var MachineGUID = s4() + s4() + s4() + s4() + s4() + s4() + s4() + s4();
    MachineGUID = MachineGUID.toLocaleUpperCase();
    chrome.storage.local.set({
        [MACHINE_ID]: MachineGUID
    });
    return MachineGUID;
}

function SendPingDetails(status) {

    var manifestData = chrome.runtime.getManifest();
    var extensionVersion = manifestData.version;
    var startIndex = navigator.userAgent.indexOf("(");
    var endIndex = navigator.userAgent.indexOf(")");
    var OS = navigator.userAgent.substring(startIndex + 1, endIndex).replace(/\s/g, '');
    var extensionName = manifestData.name.replace(/ /g, "").replace(/&/g, 'and');

    var browserVersion = navigator.userAgent.substr(navigator.userAgent.indexOf("Chrome")).split(" ")[0].replace("/", "");

    chrome.storage.local.get([PARTNER_CODE, CHANNEL, MACHINE_ID, DPC, MARKET], (items) => {
        var browserLanguage = (items[MARKET]) ? items[MARKET]: navigator.language;
        var pc = !items[PARTNER_CODE] ? "BG04" : items[PARTNER_CODE];
        var pingURL = 'https://go.microsoft.com/fwlink/?linkid=2243942&';
        var tVData = 'TV=is' + pc + '|pk' + extensionName + '|tm' + browserLanguage + '|bv' + browserVersion + '|ex' + extensionId + '|es' + status;
        if (items[CHANNEL])
            tVData = tVData + "|ch" + items[CHANNEL];
        if (items[DPC])
            tVData = tVData + "|dp" + items[DPC];
        var UD = 'MI=' + items[MACHINE_ID] + '&LV=' + extensionVersion + '&OS=' + OS + '&TE=37&' + tVData;
        UD = btoa(encodeURI(UD));
        pingURL = pingURL + 'UD=' + UD + '&ver=2';
        pingURL = encodeURI(pingURL);  // For HTML Encoding
        fetch(pingURL);
    });
};

function getChromeWSChannel(cookieValue) {

    // Sample Chrome Webstore PaidAds cookie Value: 73091649.1608191832.10.6.utmcsr=bgads|utmccn=rwdsus|utmcmd=(not%20set)
    //Cookie value: 73091649.1614306380.141.5.utmcsr=bgads|utmccn=rwdsus|utmcmd=rwdmed|utmcct=rwdcon
    //DPC: source_medium_campaign_content (bgads_rwdmed_rwdsus_rwdcon)
    var strSource = "";
    var strCampaign = "";
    var strMedium = "";
    var strContent = "";
    var strWSChannel = "";
    var splitStr = cookieValue.split(".");

    if (splitStr[splitStr.length - 1] != "") {
        var utmValues = splitStr[splitStr.length - 1].split("|");

        for (i = 0; i < utmValues.length; i++) {
            var utmValue = utmValues[i].split("=");
            if (utmValue[0] == "utmcsr") {
                strSource = utmValue[1];
            }
            else if (utmValue[0] == "utmccn") {
                strCampaign = utmValue[1];
            }
            else if (utmValue[0] == "utmcmd") {
                strMedium = utmValue[1];
            }
            else if (utmValue[0] == "utmcct") {
                strContent = utmValue[1];
            }
        }

        if (strSource == "bgads") {

            strWSChannel = strSource;

            if (strMedium != "(not%20set)" && strMedium != "(direct)" && strMedium != "(organic)") {
                strWSChannel = strWSChannel + "_" + strMedium;
            }

            if (strCampaign != "(not%20set)" && strCampaign != "(direct)" && strCampaign != "(organic)") {
                strWSChannel = strWSChannel + "_" + strCampaign;
            }

            if (strContent != "(not%20set)" && strContent != "(direct)" && strContent != "(organic)" && strContent != "") {
                strWSChannel = strWSChannel + "_" + strContent;
            }
        }

        return strWSChannel;
    }
}

function extractQueryString(param, url) {
    var p = (new RegExp("[\\?&]" + param + "=([^&#]*)")).exec(url);
    return (p === null) ? "" : p[1];
}

chrome.action.onClicked.addListener(function (tab) {
    var redirectURL = "https://www.msn.com/?pc=" + defaultPC + "&ocid=MSNHP_" + defaultPC;
    chrome.storage.local.get([PARTNER_CODE], (items) => {
        if (items[PARTNER_CODE]) {
            redirectURL = "https://www.msn.com/?pc=" + items[PARTNER_CODE] + "&ocid=MSNHP_" + items[PARTNER_CODE];
        }
        chrome.tabs.create({ url: redirectURL });
    });
});

function addHomepageRedirectRule(redirectRuleId, partnerCode, defaultPartnerCode, blockingURL) {
    if (partnerCode || defaultPartnerCode) {
        var rulesToAdd = [];

        var searchRedirectRule =
        {
            id: redirectRuleId,
            priority: 1,
            action: {
                type: "redirect",
                redirect: {
                    transform: {
                        queryTransform: {
                            addOrReplaceParams: [
                                {
                                    key: "ocid",
                                    value: partnerCode  ? "MSNHP_" + partnerCode : "MSNHP_" + defaultPartnerCode
                                },
                                {
                                    key: "pc",
                                    value: partnerCode ? partnerCode : defaultPartnerCode
                                }
                            ],
                            removeParams: [
                                "osmkt"
                            ]
                        }
                    }
                }
            },
            condition: {
                urlFilter: blockingURL,
                resourceTypes: ["main_frame", "xmlhttprequest"]
            }
        };
        rulesToAdd.push(searchRedirectRule);

        chrome.declarativeNetRequest.updateDynamicRules({
            addRules: rulesToAdd,
            removeRuleIds: [1]
        }, () => {
            if (chrome.runtime.lastError)
                console.log(chrome.runtime.lastError);
        });
    }
}
