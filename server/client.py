# -*- coding: utf-8 -*-

from pprint import pformat
import cgi
from zope.interface import implements
from urllib import urlencode
import twisted
from twisted.internet.defer import succeed, fail
from twisted.web.iweb import IBodyProducer
from twisted.web.client import Agent, ResponseDone
from twisted.web.http_headers import Headers
from twisted.internet.defer import Deferred
from twisted.internet.protocol import Protocol


#from parsers import parse_request_to_monitorserver
#from parsers import parse_generic_request
from parsers import GenericGeocodingRequest
from parsers import GenericGeocodingResult
from parsers import NominatimResponse
from parsers import MONSERV, NOMINATIM, GOOGLECODER


from errors import *

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
            print 'buffer: ', self.full_data

    def connectionLost(self, reason):
        print 'Finished receiving body:', reason.getErrorMessage()
        if reason.check(ResponseDone):
            self.finished.callback(''.join(self.full_data))
        else:
            self.finished.errback(reason)


class MonServBodyReceiver(BodyReceiver):
    def connectionLost(self, reason):
        # Monserv geocoder doesent close connection properly,
        # thus there are no way to say that data is ok
        # except actually trying to parse it.
        print 'Finished receiving body:', reason.getErrorMessage()
        self.finished.callback(''.join(self.full_data))


def request_inst_to_agent_request_list(request, new_url):
    data = request.content.read()
    method = request.method
    url = new_url
    headers = Headers({'Connection': ['Keep-Alive'],
                       'Proxy-Connection': ['Keep-Alive'],
                       'Content-Type': ['text/xml'],
                       'Content-length': [len(data), ]})
    body = StringProducer(data)
    lst = [method, url, headers, body]
    return lst


def get_xml_from_monitor_server(request, url='http://62.213.6.99/cgi-bin/geocoder'):
    from twisted.internet import reactor
    agent = Agent(reactor)
    d = agent.request(*request_inst_to_agent_request_list(request, url))

    def callback_request(response):
        print 'Response version:', response.version
        print 'Response code:', response.code
        print 'Response phrase:', response.phrase


        def cbRequestFinished(response_data, response, request):
            for header, value in response.headers.getAllRawHeaders():
                request.setHeader(header, value[0])
            request.write(response_data)
            request.finish()

        def ebRequestFailed(reason, response, request):
            print 'request failed - {}'.format(reason.getErrorMessage())
            request.setResponseCode('500')
            request.write('Data Retrival Failed')

        finished = Deferred()
        finished.addCallback(cbRequestFinished, response, request)
        finished.addErrback(ebRequestFailed, response, request)
        response.deliverBody(MonServBodyReceiver(finished))
        return finished

    d.addCallback(callback_request)

    def errback(err):
        print 'Err'
        raise err
    d.addErrback(errback)

    return d


def latlng_to_nominatem_request_url(lat, lng, format='json',
                                    zoom=18, addressdetails=1,
                                    accept_language='UA'):
    base_nominatim_url = 'http://nominatim.openstreetmap.org/reverse'
    req = '?'.join((base_nominatim_url, urlencode({'lat': lat,
                                          'lon': lng,
                                          'format': format,
                                          'zoom': 18,
                                          'addressdetails': addressdetails,
                                          'accept-language': accept_language})
                    ))
    return req




def get_json_from_nominatim(request, url='http://nominatim.openstreetmap.org/reverse'):
    from twisted.internet import reactor

    geo_req = GenericGeocodingRequest(request, server=NOMINATIM)
    deferred_response = NominatimResponse(geo_req)
    d = deferred_response

    def PARSE(a):
        return a

    def callback_request(response):
        print 'Response version:', response.version
        print 'Response code:', response.code
        print 'Response phrase:', response.phrase

        def cbRequestFinished(response_data, deferred):
            latlng = PARSE(response_data)
            deferred.callback(response_data)

        def ebRequestFailed(reason, deferred):
            deferred.errback('Data retrival failure')

        finished = Deferred()
        finished.addCallback(cbRequestFinished, response, request)
        finished.addErrback(ebRequestFailed, response, request)
        response.deliverBody(BodyReceiver(finished))
        return finished

    def errback_request(err, request):
        print 'request failed - {}'.format(err.getErrorMessage())
        request.setResponseCode(500)
        request.write('Data Retrival Failed')

    d.addCallback(callback_request, d)
    d.addErrback(errback_request, d)

    def errback(err):
        print 'Err'
        raise err
    d.addErrback(errback)

    return d
