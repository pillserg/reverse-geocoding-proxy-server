# -*- coding: utf-8 -*-
"""
Bunch of primitive request, response parsers
for different geoservers
"""
from xml.dom import minidom
import cgi
import simplejson
import time
from zope.interface import implements
from urllib import urlencode

from twisted.internet.defer import succeed, fail
from twisted.web.client import Agent, ResponseDone
from twisted.web.http_headers import Headers
from twisted.web.iweb import IBodyProducer
from twisted.internet.defer import Deferred
from twisted.internet.protocol import Protocol

from errors import *
import settings

#server's marks
NOMINATIM, MONSERV, GOOGLECODER = range(1, 4)
SERVERS = (NOMINATIM, MONSERV, GOOGLECODER)

from utils import sentinel


def conver_Nominatem_response_to_MonServ(data):
    return data

def simpleErrBack(err):
    err.printTraceback()

class AlreadyParsedError(Exception):
    pass

class UnknownServerError(Exception):
    pass


class StringProducer(object):
    implements(IBodyProducer)

    def __init__(self, body):
        self.body = body
        self.length = len(self.body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass


class BodyReceiver(Protocol):
    def __init__(self, finished):
        self.finished = finished
        self.remaining = 1024 * 10
        self.full_data = []

    def dataReceived(self, bytes):
        if self.remaining:
            data = bytes[:self.remaining]
            self.remaining -= len(data)
            self.full_data.append(data)

    def connectionLost(self, reason):
        if reason.check(ResponseDone):
            self.finished.callback(''.join(self.full_data))
        else:
            self.finished.errback(reason)


class MonServBodyReceiver(BodyReceiver):
    def connectionLost(self, reason):
        # Monserv geocoder doesent close connection properly,
        # thus there are no way to say that data is ok
        # except actually trying to parse it.

        self.finished.callback(''.join(self.full_data))


class GenericGeocodingRequest(object):
    """
    Basic georequest representation suitable for use with any geoserver
    """

    def __init__(self, request, format='json', MOCK=False):
        """
        request must be original twisted request object
        or may be dict like:
        {
        lat: 50,
        lon: 29,
        }
        in this case MOCK flag must raised. Then parsing will be omitted
        """

        self.processed = False
        self.lat = None
        self.lon = None
        self.format = format


        if MOCK:
            self.request = None
            self.lat = request.get('lat')
            self.lon = request.get('lon')
            self.raw_data = None
        else:
            self.request = request
            self.raw_data = request.content.read()
            self._parse_request(request)

    def get_format(self):
        return self.format

    def get_latlon(self):
        return self.lat, self.lon

    def get_raw_data(self):
        return self.raw_data

    def _parse_request(self, request):
        if self.processed:
            raise AlreadyParsedError('I can be called only once')
        try:
            lat = cgi.escape(request.args['lat'][0])
            lon = cgi.escape(request.args['lon'][0])
        except:
            raise MalformedDataError('error parsing lat lon')
        self.lat = lat
        self.lon = lon
        self.processed = True


class MonitorServerGeocodingRequest(GenericGeocodingRequest):
    def _parse_request(self, request):
        """
        parses request (assumes xml) to monitorserver geocoder,
        """
        if self.processed:
            raise AlreadyParsedError('I can be called only once')
        data = self.raw_data
        if data:
            try:
                xml_data = minidom.parseString(data)
                latlng = xml_data.getElementsByTagName('latlng')[0].firstChild.data
                lat, lon = map(float, latlng.split(', '))
            except Exception, err:
                raise MalformedDataError(err)
        else:
            raise MalformedDataError('no data body')
        self.lat = lat
        self.lon = lon
        self.processed = True



class GoogleGeocoderRequest(GenericGeocodingRequest):
    def _parse_request(self, request):
        if self.processed:
            raise AlreadyParsedError('I can be called only once')
        raise NotImplementedError('google parser not implemented')


class NominatimGeocoderRequest(GenericGeocodingRequest):
    def _parse_request(self, request):
        if self.processed:
            raise AlreadyParsedError('I can be called only once')
        raise NotImplementedError('google parser not implemented')


class GenericGeocodingResponse(object):
    def __init__(self, geocoding_request, return_raw=False, convertor=None):
        """
        
        instantiate with georequest
        grab deferred using _.get_address()
        add nice callback to it.
        d will be fired with request result or err.
        
        > geocoding_request instance of GenericGeocodingRequest subclass
        > return_raw | Bool # dosent touch resulting ans return it in raw
        > convertor | explicit function for converting geoserver resp body
                      must take data as first arg, and original georeq inst
        
        """
        self.convertor = convertor
        self.return_raw = return_raw
        self.georequest = geocoding_request
        self.original_request = self.georequest.request
        self.lat, self.lon = geocoding_request.get_latlon()
        self.address_str = None
        self.format = geocoding_request.get_format()
        self.raw_data = self.georequest.get_raw_data()
        self.finished = Deferred()

    def get_display_address(self):
        return self.address_str

    def get_latlon(self):
        return self.lat, self.lon

    def get_raw_data(self):
        return self.raw_data

    def _parse_response(self, data):
        # process self.raw_data
        # must be implemented in subclasses
        raise NotImplementedError()

    def get_address(self):
        # returns deferred which will be fired with 
        # nice address string from server (or error :))
        return self._get_agent()

    def _make_args_for_agent(self):
        raise NotImplementedError()

    def _cb_process_response(self, response):

        def cb_request_finished(response_data):
            """data would be sent to recepient immedeatly
            so encode it"""
            resp = self._parse_response(response_data).encode('utf-8')
            if not self.return_raw:
                if self.format == 'json':
                    resp = simplejson.dumps({'address': resp})
                elif self.format == 'xml':
                    resp = self._parse_response(resp)
            self.finished.callback(resp)

        def eb_request_failed(reason):
            print 'ERR'
            raise

        d = Deferred()
        d.addCallback(cb_request_finished)
        d.addErrback(eb_request_failed)
        response.deliverBody(BodyReceiver(d))
        return d

    def _get_agent(self):
        from twisted.internet import reactor
        agent = Agent(reactor)
        args = self._make_args_for_agent()
        d = agent.request(*args)
        d.addCallback(self._cb_process_response)
        d.addErrback(simpleErrBack)
        return self.finished

class NominatimResponse(GenericGeocodingResponse):
    base_nominatim_url = settings.NOMINATIM_URL

    def _make_url_for_nominatim(self):
        req = '?'.join((self.base_nominatim_url,
                        urlencode({'lat': self.lat,
                                   'lon': self.lon,
                                   'format': self.format,
                                   'zoom': 18, # default zoom MAGIC NUM !!!
                                   'addressdetails': '',
                                   'accept-language': ''})
                      ))
        return req

    def _make_args_for_agent(self):
        method = 'GET'
        url = self._make_url_for_nominatim()
        headers = Headers({'Connection': ['Keep-Alive'],
                           'Proxy-Connection': ['Keep-Alive'],
                           'User-Agent': ['Twisted_app']
                           })
        body = None
        return [method, url, headers, body]

    def _parse_response(self, data):
        if self.convertor:
            return self.convertor(data, self.georequest)

        if self.format == 'json':
            try:
                json = simplejson.loads(data.decode('utf-8'))
            except:
                raise
            self.address_str = json['display_name']
        else:
            raise NotImplementedError('xml parsing from Nominatim not implemented')
        return self.address_str


class MonServerResponse(GenericGeocodingResponse):

    mon_serv_url = settings.MON_SERV_URL

    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)
        self.format = 'xml'
        self._make_body()

    def _make_body(self):
        xml_body = ('<?xml version="1.0" encoding="utf-8" ?><findNearbyPlaces>'
                    '<points><latlng>{lat}, {lon}</latlng></points>'
                    '</findNearbyPlaces>').format(lat=self.lat,
                                                  lon=self.lon)
        self.raw_data = xml_body
        return self.raw_data

    def _make_args_for_agent(self):
        """
        Prepare args for agent.request method.
        returns list
        server dependent
        """
#        user_agent_mimic = self.original_request.requestHeaders.getRawHeaders('User-Agent')
#        if user_agent_mimic:
#            user_agent_mimic = user_agent_mimic[0]
#        else:
#            user_agent_mimic = 'Twisted reverse geocoder v0.0.1'
        user_agent_mimic = 'Twisted reverse geocoder v0.0.1'
        method = 'POST'
        url = self.mon_serv_url
        headers = Headers({'Connection': ['Keep-Alive'],
                           'Proxy-Connection': ['Keep-Alive'],
                           'User-Agent': [user_agent_mimic],
                           'Content-Type': ['text/xml'],
                           'Content-length': [len(self.raw_data), ]
                           })
        body = StringProducer(self.raw_data)
        return [method, url, headers, body]

    def _parse_response(self, data):
        if self.format == 'json':
            try:
                json = simplejson.loads(data.decode('utf-8'))
            except:
                raise
            self.address_str = json['display_name']
        elif self.format == 'xml':
            return data
            #xml_data = minidom.parseString(data)
            #xml_data.getElementsByTagName('latlng')[0].firstChild.data
        return self.address_str

    def _cb_process_response(self, response):

        def cb_request_finished(response_data):
            """data would be sent to recepient immedeatly
            so encode it"""
            resp = self._parse_response(response_data)
            if not self.return_raw:
                if self.format == 'json':
                    resp = simplejson.dumps({'address': resp})
                elif self.format == 'xml':
                    resp = self._parse_response(resp)
            self.finished.callback(resp)

        def eb_request_failed(reason):
            print 'ERR'
            raise

        d = Deferred()
        d.addCallback(cb_request_finished)
        d.addErrback(eb_request_failed)
        response.deliverBody(BodyReceiver(d))
        return d

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


#<?xml version="1.0" encoding="utf-8" ?><findNearbyPlaces><points><latlng>50.427390, 30.453530</latlng></points></findNearbyPlaces>

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
