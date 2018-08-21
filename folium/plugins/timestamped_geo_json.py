# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division, print_function)

import json

from branca.element import CssLink, Figure, JavascriptLink, MacroElement
from branca.utilities import iter_points, none_max, none_min

from jinja2 import Template


class TimestampedGeoJson(MacroElement):
    """
    Creates a TimestampedGeoJson plugin from timestamped GeoJSONs to append
    into a map with Map.add_child.

    A geo-json is timestamped if:
    * it contains only features of types LineString, MultiPoint, MultiLineString,
      Polygon and MultiPolygon.
    * each feature has a 'times' property with the same length as the
      coordinates array.
    * each element of each 'times' property is a timestamp in ms since epoch,
      or in ISO string.

    Eventually, you may have Point features with a 'times' property being an
    array of length 1.

    Parameters
    ----------
    data: file, dict or str.
        The timestamped geo-json data you want to plot.
        * If file, then data will be read in the file and fully embedded in
          Leaflet's javascript.
        * If dict, then data will be converted to json and embedded in the
          javascript.
        * If str, then data will be passed to the javascript as-is.
    transition_time: int, default 200.
        The duration in ms of a transition from between timestamps.
    loop: bool, default True
        Whether the animation shall loop.
    auto_play: bool, default True
        Whether the animation shall start automatically at startup.
    add_last_point: bool, default True
        Whether a point is added at the last valid coordinate of a LineString.
    period: str, default "P1D"
        Used to construct the array of available times starting
        from the first available time. Format: ISO8601 Duration
        ex: 'P1M' 1/month, 'P1D' 1/day, 'PT1H' 1/hour, and 'PT1M' 1/minute
    duration: str, default None
        Period of time which the features will be shown on the map after their
        time has passed. If None, all previous times will be shown.
        Format: ISO8601 Duration
        ex: 'P1M' 1/month, 'P1D' 1/day, 'PT1H' 1/hour, and 'PT1M' 1/minute

    Examples
    --------
    >>> TimestampedGeoJson({
    ...     'type': 'FeatureCollection',
    ...     'features': [
    ...       {
    ...         'type': 'Feature',
    ...         'geometry': {
    ...           'type': 'LineString',
    ...           'coordinates': [[-70,-25],[-70,35],[70,35]],
    ...           },
    ...         'properties': {
    ...           'times': [1435708800000, 1435795200000, 1435881600000]
    ...           }
    ...         }
    ...       ]
    ...     })

    See https://github.com/socib/Leaflet.TimeDimension for more information.

    """
    _template = Template("""
        {% macro script(this, kwargs) %}
            L.Control.TimeDimensionCustom = L.Control.TimeDimension.extend({
                _getDisplayDateFormat: function(date){
                    var newdate = new moment(date);
                    return newdate.format("{{this.date_options}}");
                },
                _update: function() {
                  if (!this._timeDimension) {
                      return; 
                  }
                  var time = this._timeDimension.getCurrentTime();
                    var date = new Date(time);
                      if (this._displayDate) {
                        L.DomUtil.removeClass(this._displayDate, 'loading');
                        this._displayDate.innerHTML = this._getDisplayDateFormat(date);
                    }
                    if (this._sliderTime && !this._slidingTimeSlider) {
                        this._sliderTime.setValue(this._timeDimension.getCurrentTimeIndex());
                    }
            }
            });
            L.TimeDimension.Layer.GeoJsonCustom = L.TimeDimension.Layer.GeoJson.extend({
                _getFeatureTimes: function(feature) {
                    if (!feature.featureTimes) {
                        if (!feature.properties) {
                            feature.featureTimes = [];
                        } else if (feature.properties.hasOwnProperty('coordTimes')) {
                            feature.featureTimes = feature.properties.coordTimes;
                        } else if (feature.properties.hasOwnProperty('times')) {
                            feature.featureTimes = feature.properties.times;
                        } else if (feature.properties.hasOwnProperty('linestringTimestamps')) {
                            feature.featureTimes = feature.properties.linestringTimestamps;
                        } else if (feature.properties.hasOwnProperty('time')) {
                            feature.featureTimes = [feature.properties.time];
                        } else {
                            feature.featureTimes = [];
                        }
                        // String dates to ms
                        for (var i = 0, l = feature.featureTimes.length; i < l; i++) {
                            var time = feature.featureTimes[i];
                            if (typeof time == 'string' || time instanceof String) {
                                time = Date.parse(time.trim());
                                feature.featureTimes[i] = time;
                            }
                        }
                    }
                    return feature.featureTimes;
                },
                _getFeatureBetweenDates: function(feature, minTime, maxTime) {
                    //change min value to allow for dates before 01/01/1970
                    if (minTime == 0) {
                        minTime = -999999999999;
                    }
                    var featureTimes = this._getFeatureTimes(feature);
                    if (featureTimes.length == 0) {
                        return feature;
                    }

                    var index_min = null,
                        index_max = null,
                        l = featureTimes.length;

                    if (featureTimes[0] > maxTime || featureTimes[l - 1] < minTime) {
                        return null;
                    }

                    if (featureTimes[l - 1] > minTime) {
                        for (var i = 0; i < l; i++) {
                            if (index_min === null && featureTimes[i] > minTime) {
                                // set index_min the first time that current time is greater the minTime
                                index_min = i;
                            }
                            if (featureTimes[i] > maxTime) {
                                index_max = i;
                                break;
                            }
                        }
                    }
                    if (index_min === null) {
                        index_min = 0;
                    }
                    if (index_max === null) {
                        index_max = l;
                    }
                    var new_coordinates = [];
                    if (feature.geometry.coordinates[0].length) {
                        new_coordinates = feature.geometry.coordinates.slice(index_min, index_max);
                    } else {
                        new_coordinates = feature.geometry.coordinates;
                    }
                    return {
                        type: 'Feature',
                        properties: feature.properties,
                        geometry: {
                            type: feature.geometry.type,
                            coordinates: new_coordinates
                        }
                    };
                }

            });
            {{this._parent.get_name()}}.timeDimension = L.timeDimension({period:"{{this.period}}"});
            var timeDimensionControl = new L.Control.TimeDimensionCustom({{ this.options }});
            {{this._parent.get_name()}}.addControl(this.timeDimensionControl);

            var geoJsonLayer = L.geoJson({{this.data}}, {
                    pointToLayer: function (feature, latLng) {
                        if (feature.properties.icon == 'marker') {
                            if(feature.properties.iconstyle){
                                return new L.Marker(latLng, {
                                    icon: L.icon(feature.properties.iconstyle)});
                            }
                            //else
                            return new L.Marker(latLng);
                        }
                        if (feature.properties.icon == 'circle') {
                            if (feature.properties.iconstyle) {
                                return new L.circleMarker(latLng, feature.properties.iconstyle)
                                };
                            //else
                            return new L.circleMarker(latLng);
                        }
                        //else

                        return new L.Marker(latLng);
                    },
                    style: function (feature) {
                        return feature.properties.style;
                    },
                    onEachFeature: function(feature, layer) {
                        if (feature.properties.popup) {
                        layer.bindPopup(feature.properties.popup);
                        }
                    }
                })

            var {{this.get_name()}} = new L.TimeDimension.Layer.GeoJsonCustom(geoJsonLayer,
                {updateTimeDimension: true,
                 addlastPoint: {{'true' if this.add_last_point else 'false'}},
                 duration: {{ this.duration }},
                }).addTo({{this._parent.get_name()}});
        {% endmacro %}
        """)  # noqa

    def __init__(self, data, transition_time=200, loop=True, auto_play=True,
                 add_last_point=True, period='P1D', min_speed=0.1, max_speed=10,
                 loop_button=False, date_options='YYYY-MM-DD HH:mm:ss',
                 time_slider_drag_update=False, duration=None):
        super(TimestampedGeoJson, self).__init__()
        self._name = 'TimestampedGeoJson'

        if 'read' in dir(data):
            self.embed = True
            self.data = data.read()
        elif type(data) is dict:
            self.embed = True
            self.data = json.dumps(data)
        else:
            self.embed = False
            self.data = data
        self.add_last_point = bool(add_last_point)
        self.period = period
        self.date_options = date_options
        self.duration = 'undefined' if duration is None else "\""+duration+"\""

        options = {
            'position': 'bottomleft',
            'minSpeed': min_speed,
            'maxSpeed': max_speed,
            'autoPlay': auto_play,
            'loopButton': loop_button,
            'timeSliderDragUpdate': time_slider_drag_update,
            'playerOptions': {
                'transitionTime': int(transition_time),
                'loop': loop,
                'startOver': True
            }
        }
        self.options = json.dumps(options, sort_keys=True, indent=2)

    def render(self, **kwargs):
        super(TimestampedGeoJson, self).render()

        figure = self.get_root()
        assert isinstance(figure, Figure), ('You cannot render this Element '
                                            'if it is not in a Figure.')

        figure.header.add_child(
            JavascriptLink('https://cdnjs.cloudflare.com/ajax/libs/jquery/2.0.0/jquery.min.js'),  # noqa
            name='jquery2.0.0')

        figure.header.add_child(
            JavascriptLink('https://cdnjs.cloudflare.com/ajax/libs/jqueryui/1.10.2/jquery-ui.min.js'),  # noqa
            name='jqueryui1.10.2')

        figure.header.add_child(
            JavascriptLink('https://rawgit.com/nezasa/iso8601-js-period/master/iso8601.min.js'),  # noqa
            name='iso8601')

        figure.header.add_child(
            JavascriptLink('https://rawgit.com/socib/Leaflet.TimeDimension/master/dist/leaflet.timedimension.min.js'),  # noqa
            name='leaflet.timedimension')

        figure.header.add_child(
            CssLink('https://cdnjs.cloudflare.com/ajax/libs/highlight.js/8.4/styles/default.min.css'),  # noqa
            name='highlight.js_css')

        figure.header.add_child(
            CssLink("http://apps.socib.es/Leaflet.TimeDimension/dist/leaflet.timedimension.control.min.css"),  # noqa
            name='leaflet.timedimension_css')

        figure.header.add_child(
            JavascriptLink('https://cdnjs.cloudflare.com/ajax/libs/moment.js/2.18.1/moment.min.js'),
            name='moment')

    def _get_self_bounds(self):
        """
        Computes the bounds of the object itself (not including it's children)
        in the form [[lat_min, lon_min], [lat_max, lon_max]].

        """
        if not self.embed:
            raise ValueError('Cannot compute bounds of non-embedded GeoJSON.')

        data = json.loads(self.data)
        if 'features' not in data.keys():
            # Catch case when GeoJSON is just a single Feature or a geometry.
            if not (isinstance(data, dict) and 'geometry' in data.keys()):
                # Catch case when GeoJSON is just a geometry.
                data = {'type': 'Feature', 'geometry': data}
            data = {'type': 'FeatureCollection', 'features': [data]}

        bounds = [[None, None], [None, None]]
        for feature in data['features']:
            for point in iter_points(feature.get('geometry', {}).get('coordinates', {})):  # noqa
                bounds = [
                    [
                        none_min(bounds[0][0], point[1]),
                        none_min(bounds[0][1], point[0]),
                        ],
                    [
                        none_max(bounds[1][0], point[1]),
                        none_max(bounds[1][1], point[0]),
                        ],
                    ]
        return bounds
