# -*- coding: utf-8 -*-

from xml.dom import minidom
import cgi
from errors import *


def parse_generic_request(request):
    print request.args
    try:
        lat = cgi.escape(request.args['lat'][0])
        lng = cgi.escape(request.args['lng'][0])
    except:
        print 'error parsing lat lng'
        raise MalformedDataError('error parsing lat lng')
    return lat, lng


def parse_request_to_monitorserver(request):
    """
    parses request (assumes xml) to monitorserver geocoder,
    returns lat, long tuple
    """
    data = request.content.read()
    if data:
        try:
            xml_data = minidom.parseString(data)
            latlng = xml_data.getElementsByTagName('latlng')[0].firstChild.data
            lat, lng = map(float, latlng.split(', '))

        except Exception, err:
            #raise MalformedDataError(err)
            raise

        return lat, lng


def parse_monitor_server_response(xml_data):
        try:
            xml_data = minidom.parseString(data)
            latlng = xml_data.getElementsByTagName('latlng')[0].firstChild.data
            lat, lng = map(float, latlng.split(', '))
        except Exception, err:
            raise MalformedDataError(err)

        return lat, lng


def parse_generic(request):
    pass


# monitorserver: 
#    xml-body
#    <?xml version="1.0" encoding="utf-8" ?>
#        <findNearbyPlaces>
#            <points>
#                <latlng>50.427390, 30.453530</latlng>
#            </points>
#        </findNearbyPlaces>
#    response:
#    <?xml version="1.0" encoding="utf-8" ?>
#    <nearbyPlaces>
#     <point>
#      <latlng>50.427390, 30.453530</latlng>
#      <neighbors>
#       <road>
#        <name>Очаківський провулок</name>
#        <street></street>
#        <distance>11.2480037721226</distance>
#       </road>
#       <polygon>
#        <name>Київ</name>
#        <street></street>
#        <housenumber></housenumber>
#        <distance>0</distance>
#       </polygon>
#       <poi>
#        <name>Минеральные Воды</name>
#        <street></street>
#        <housenumber></housenumber>
#        <distance>662.773161048974</distance>
#       </poi>
#      </neighbors>
#     </point>
#    </nearbyPlaces>
# nominatim e.g.: ?format=xml&lat=52.5487429714954&lon=-1.81602098644987&zoom=18&addressdetails=1
# gooogle example: ?q=40.714224,-73.961452&output=json&oe=utf8&sensor=true_or_false&key=your_api_key
