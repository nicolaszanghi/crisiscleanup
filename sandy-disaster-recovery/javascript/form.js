/**
 * Copyright 2012 Jeremy Pack
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 **/
goog.require("goog.dom");

goog.require('goog.dom');
goog.require('goog.ui.ac.ArrayMatcher');
goog.require('goog.ui.ac.AutoComplete');
goog.require('goog.ui.ac.InputHandler');
goog.require('goog.ui.ac.Renderer');
goog.require('goog.ui.ac');

goog.require('goog.net.XhrIo');
goog.require('goog.events');
goog.require('goog.json');
goog.require('goog.net.cookies');

goog.require('sandy.util');
goog.require('sandy.sites');

goog.provide("sandy.form");


var map;

var geocoder;

var country = sandy.util.determineCountry();


var showSimilar = function(matches) {
    // show similarity matches 
    var div = goog.dom.getElement('similars');
    goog.dom.removeChildren(div);
    if (matches.length > 0) {
        var p = goog.dom.createDom('p', 'bold', 'Possible existing matches:');
        div.appendChild(p);
        var ul = goog.dom.createElement('ul');
        div.appendChild(ul);
        for (var i=0; i<matches.length && i<3; i++) {
            (function() {
                var match = matches[i];
                var url = "/edit?case=" + match.split(':')[0];
                ul.appendChild(
                    goog.dom.createDom('li', null, 
                        goog.dom.createDom('a', {href:url}, match))
                );
            })();
        }
    }
};

sandy.form.Initialize = function() {
    // setup google map
    var mapCenter = sandy.util.MAP_CENTER[country];
    var mapOptions = {
        zoom: 5,
        center: new google.maps.LatLng(mapCenter.lat, mapCenter.lon),
        mapTypeId: google.maps.MapTypeId.ROADMAP
    };
    map = new google.maps.Map(document.getElementById('map_canvas'), mapOptions);

    // load sites
    sandy.sites.tryBatchLoadSites("open", 0);

    // construct array matcher
    var am = new goog.ui.ac.ArrayMatcher(terms);

    // listen for keyup on primary fields
    var AC_FIELD_NAMES = ['name', 'address', 'zip_code'];
    for (var i=0; i<AC_FIELD_NAMES.length; i++) {
        (function() {
            var inputElement = goog.dom.getElement(AC_FIELD_NAMES[i]);
                goog.events.listen(
                    inputElement,
                    goog.events.EventType.KEYUP,
                    function(evt) {
                        if (inputElement.value.length > 3) {
                            showSimilar(am.getPrefixMatches(inputElement.value));
                        }
                    }
                );
        })();
    }

    // add event handlers
    sandy.form.SetUpValidation();
    sandy.form.SetUpAdditionalHandlers();

    // fire necessary change handlers immediately
    sandy.form.fireFormModificationHandlers();
};


sandy.form.SetUpValidation = function() {
    geocoder = new google.maps.Geocoder();

    // Set up validation events
    goog.dom.getElement('address').onblur = validate;
    goog.dom.getElement('zip_code').onblur = validate;
    goog.dom.getElement('state').onblur = validate;
    goog.dom.getElement('county').onblur = validate;
    goog.dom.getElement('city').onblur = validate;

};


var last_city = "";
var last_state = "";
var last_zip_code = "";
var last_geocode = "";
var geocoding = false;
var marker;


sandy.form.handleStatusChanged = function() {
  // show Assigned To field only if status is 'Open, unassigned'
  var status = goog.dom.getElement('status').value;
  var assigned_to_row = goog.dom.getElement('assigned_to_row');
  if (status == 'Open, unassigned') {
    assigned_to_row.style.display = 'none';
  } else {
    assigned_to_row.style.display = 'block';
  }
};


sandy.form.SetUpAdditionalHandlers = function() {
  // handle status changed
  goog.dom.getElement('status').onchange = sandy.form.handleStatusChanged;

  // disable return key
  document.onkeypress = function(e) {
    if (e.which == '13') {
      e.preventDefault();
    }
  };
};


sandy.form.fireFormModificationHandlers = function() {
    // fire handlers that setup initial appearance of the form
    sandy.form.handleStatusChanged();
};


function validate() {
    var zip_code = goog.dom.getElement('zip_code').value;
    var city_value = goog.dom.getElement('city').value;
    var state_value = goog.dom.getElement('state').value;
    var street_address = goog.dom.getElement('address').value;
    if ((zip_code.length < 5 && city_value.length < 2 && state_value.length < 2) ||
        street_address.length < 5) return;
    var address = street_address;
    // If city was not automatically set, then use it.
    if (city_value != last_city) {
        address += " " + city_value;
    }
    if (state_value != last_state) {
        address += " " + state_value;
    }
    if (zip_code != last_zip_code) {
        address += " " + zip_code;
    }
    address += " " + sandy.util.COUNTRY_NAME[country];
    if (address == last_geocode) return;
    last_geocode = address;

    // call the geocoder
    geocoder.geocode({'address': address, 'region': country}, function(results, status) {

        if (status == google.maps.GeocoderStatus.OK) {
            // upon successful geocoding, add draggable marker and center the map
            map.setCenter(results[0].geometry.location);
            latlon = results[0].geometry.location;
            
            if (marker) marker.setMap(null);
            marker = new google.maps.Marker({
                map: map,
                position: latlon,
                draggable: true
            });

            google.maps.event.addListener(marker, 'dragend', function (event) {
                // update the form's latlon if the pin is dragged
                goog.dom.getElement('latitude').value = this.getPosition().lat();
                goog.dom.getElement('longitude').value = this.getPosition().lng();
            });

            var mapBounds = new google.maps.LatLngBounds(
                new google.maps.LatLng(latlon.lat() - 0.05, latlon.lng() - 0.02),
                new google.maps.LatLng(latlon.lat() + 0.05, latlon.lng() + 0.08)
            );
            map.setZoom(10);
            map.fitBounds(mapBounds);
            
            goog.dom.getElement('latitude').value = latlon.lat();
            goog.dom.getElement('longitude').value = latlon.lng();

            var comps = results[0].address_components;
            for (var i = 0; i < comps.length; ++i) {
                for (var t = 0; t < comps[i].types.length; ++t) {
                    if (comps[i].types[t] === "administrative_area_level_1") {
                        var state = goog.dom.getElement("state");
                        if (state.value === last_state) {
                            state.value = last_state = comps[i].short_name;
                            goog.dom.getElement("stateSuggestion").innerHTML = "";
                        } else if (state.value != comps[i].short_name) {
                            goog.dom.getElement("stateSuggestion").innerHTML = comps[i].short_name + "?";
                        } else {
                            goog.dom.getElement("stateSuggestion").innerHTML = "";
                        }
                    } else if (comps[i].types[t] === "locality") {
                        var city = goog.dom.getElement("city");
                        if (city.value === last_city) {
                            city.value = last_city = comps[i].long_name;
                            goog.dom.getElement("citySuggestion").innerHTML = "";
                        } else if (city.value !== comps[i].long_name) {
                            goog.dom.getElement("citySuggestion").innerHTML = comps[i].long_name + "?";
                        } else {
                            goog.dom.getElement("citySuggestion").innerHTML = "";
                        }
                    } else if (comps[i].types[t] === "postal_code") {
                        var zip_code = goog.dom.getElement("zip_code");
                        if (zip_code.value === last_zip_code) {
                            zip_code.value = last_zip_code = comps[i].long_name;
                            goog.dom.getElement("zipCodeSuggestion").innerHTML = "";
                        } else if (zip_code.value !== comps[i].long_name) {
                            goog.dom.getElement("zipCodeSuggestion").innerHTML = comps[i].long_name + "?";
                        } else {
                            goog.dom.getElement("zipCodeSuggestion").innerHTML = "";
                        }
                    } else if (comps[i].types[t] === "administrative_area_level_2") {
                        goog.dom.getElement("county").value = comps[i].long_name;
                    }
                }
            } // Before here, run a new script to run search (searchExisting(lat, lng). Run Ajax
            } else {
                //alert('Geocode was not successful for the following reason: ' + status);
            }
        });
    }
    
    function searchMatchingLatLng(latitude, longitude) {
        var request = new goog.net.XhrIo();
        goog.events.listen(request, 'complete', function(){
            if(request.isSuccess()){
              var data = request.getResponseJson();
              if (goog.isArray(data) && !goog.array.isEmpty(data)) {
                  showPopup(data);
              }
              
            } else {
                //error
            }
        });
        request.getWithCredentials();
        var str = '?latitude=' + latitude+'&longitude=' + longitude;
        var url = '/api/site_ajax' + str;
        request.send(url, 'GET');
    }
    
    function showPopup(data) {
        var map_element = document.getElementById('map_canvas').style.display;
        if(map_element == "none") {
            // This way, we never show more than one pop up box
            return;
        }
        var form = document.createElement("form", "report_form");
        form.id = "report_form";
        form.method = "post";
        form.action = "index.php?mode=post_comment";
        
        var reply_place = document.createElement("div");
        reply_place.id = "overlay";
        var inner_div = document.createElement("div"), button_close = document.createElement("button");
        button_close.id = "upprev_close";
        button_close.innerHTML = "x";
        button_close.onclick = function () {
            var element = document.getElementById('overlay');
            element.parentNode.removeChild(element);
            document.getElementById('map_canvas').style.display = '';
        };
        inner_div.appendChild(button_close);
        
        var legend = document.createElement("legend");
        legend.innerHTML = "There are other sites with this address already loaded. There is a list of them below. If you see an identical address, click on the address and hit submit.";
        form.appendChild(legend);
        
        for (var i = 0; i < data.length; i++) {
            obj = JSON.parse(data[i]);            
            var input1 = document.createElement("input");
            input1.type = "radio";
            input1.id = obj['id'];
            input1.value = obj['id'];
            input1.name = "options";
            var radio_label1 = document.createElement("label");
            radio_label1.htmlFor = obj['id'];
            radio_label1_text = obj['address'];
            radio_label1.appendChild(document.createTextNode(radio_label1_text));
            form.appendChild(input1);
            form.appendChild(radio_label1);
            
        }
        var submit_btn = document.createElement("input", "the_submit");
        submit_btn.type = "submit";
        submit_btn.className = "submit";
        submit_btn.value = "Report";
        form.appendChild(submit_btn);
        
        submit_btn.onclick = function () {
            var checked = false, formElems = this.parentNode.getElementsByTagName('input');
            for (var i = 0; i < formElems.length; i++) {
                if (formElems[i].type == 'radio' && formElems[i].checked == true) {
                    checked = true;
                    var el = formElems[i];
                    break;
                }
            }
            if (!checked) return false;
            var location_string = "/edit?id=" + el.value;
            window.location=location_string;
            return false;
        }
        
        inner_div.appendChild(form);
        reply_place.appendChild(inner_div);
        document.getElementById('map_canvas').style.display = 'none';
        
        var attach_to = document.getElementById("wrapper"), parentDiv = attach_to.parentNode;
        
        parentDiv.insertBefore(reply_place, attach_to);
    }
