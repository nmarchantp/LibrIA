var strBrowserName = "gc";
//global variable from default.js
var strExtnID = getQryStrParamValues('xid');
var market = getQryStrParamValues('bmkt');
var strExtnName = "";
var pageText1 = "";
var pageText2 = "";

if (!market) {  
    market = "en-us";
} 

//Loading the page
window.onload = onload();

function onload() {
    init(market);
    setLocalStorageParametersToChromeStorage();
}

//To get the parameter's value
function getQryStrParamValues(param) {
    var url = window.location.href.slice(window.location.href.indexOf('?') + 1).split('&');
    for (var i = 0; i < url.length; i++) {
        var urlparam = url[i].split('=');
        if (urlparam[0].toLowerCase() == param.toLowerCase()) {
            if (urlparam[1] == undefined)
                return undefined;
            else
                return urlparam[1].toLowerCase();
        }
    }
}

function init(market) {
    document.getElementById("marketId").value = market;
    document.body.className = market;

    var rtlMarkets = ["ar-sa", "fa-ir", "he-il", "ur-pk", "ug-cn"];

    if (rtlMarkets.indexOf(market) != -1) {
        document.body.dir = "rtl";
        document.dir = "rtl";
        document.documentElement.lang = market;
        var isRtl = true;
    }

    try {

        $.getJSON('assets/json/ExtnName/' + strExtnID + '/messages.json', function (extnresponse) {
            console.log(market);
            if (extnresponse[market]) {
                strExtnName = extnresponse[market];
            }
            else {
                strExtnName = extnresponse["en-us"];
            }
        });

        //setTimeout(function () {
            fetch('assets/json/Common/' + market.toLowerCase() + '/messages.json').then(response => {
                return response.json();
            }).then(data => {
                // Parse JSON string into object
                var actual_JSON = data;
                // need to pass EXTENSION ID to json file to get mapping text
                document.title = actual_JSON.Heading;
                pageText1 = actual_JSON.Step2a;
                pageText2 = actual_JSON.Step1a;

                //To load banner, logo and prompt screenshot
                $(function () {
                    $.getJSON("scripts/extnDetails.json", function (responseJSON) {

                        var bannerImg = document.getElementById("image2");
                        bannerImgSource = responseJSON[strBrowserName][strExtnID]["banner"];
                        var logoImg = document.getElementById("logo");
                        logoImageSource = responseJSON[strBrowserName][strExtnID]["logo"];
                        document.getElementById("Step2a").innerHTML = pageText1;
                        document.getElementById("Step1a").innerHTML = pageText2 + " " + strExtnName + ".";

                        if (bannerImgSource != "" && bannerImgSource != null && bannerImgSource != undefined) {
                            bannerImg.src = bannerImgSource;
                        }
                        else {
                            $("#image2").hide();
                        }

                        //Logo availability
                        if (logoImageSource != "" && logoImageSource != null && logoImageSource != undefined) {
                            logoImg.src = logoImageSource;
                        }
                        else {
                            $("#logo").hide();
                        }
                    });
                });
            }).catch(err => {
                // Do something for an error here
            });
        //}, 200);
    }
    catch (err) {
    }
}

//Showing page for valid xid
if (strExtnID != 0) {
    document.body.style.opacity = 1;
}

function setLocalStorageParametersToChromeStorage() {

    //If user is updated directly to version 10 from any older versions - for inactive users
    console.log("Set default values from json.js");
    ////Set Migration flag
    chrome.storage.local.set({ "MigratedLocalStorage": true });

    var defaultPC = "BG04";
    //pc
    if (localStorage["pc"]) {
        chrome.storage.local.set({ "PartnerCode": localStorage["pc"] });
    }
    else {
        chrome.storage.local.set({ "PartnerCode": defaultPC });
    }
    //machineID
    if (localStorage["MachineID"])
        chrome.storage.local.set({ "MachineID": localStorage["MachineID"] });
    else {
        chrome.storage.local.get(["MachineID"], (items) => {
            if (!items.MachineID) {
                chrome.storage.local.set({ "MachineID": guid() });
            }
        });
    }

    //channel
    if (localStorage["channel"])
        chrome.storage.local.set({ "Channel": localStorage["channel"] });
    else
        chrome.storage.local.set({ "Channel": "organic" });

    if (!localStorage["_dpc"]) {
        chrome.storage.local.set({ "DPC": localStorage["channel"] });
    }
    else {
        if (localStorage["_dpc"].indexOf('_') === -1 && localStorage["_dpc"] !== localStorage["channel"]) {
            chrome.storage.local.set({ "DPC": localStorage["_dpc"] + "_" + localStorage["channel"] });
        }
        else {
            chrome.storage.local.set({ "DPC": localStorage["_dpc"] });
        }
    }
}
/* Function to create an unique machine id */
function guid() {
    function s4() {
        return Math.floor((1 + Math.random()) * 0x10000)
            .toString(16)
            .substring(1);
    }
    var MachineGUID = s4() + s4() + s4() + s4() + s4() + s4() + s4() + s4();
    MachineGUID = MachineGUID.toLocaleUpperCase();
    console.log("Machine ID generated from welcome page: " + MachineGUID);
    chrome.storage.local.set({
        "MachineID": MachineGUID
    });
    return MachineGUID;
}
