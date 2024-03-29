# -*- coding: utf-8 -*-

import os
import cgi
import sys
import time
import simplejson

from twisted.internet.defer import Deferred as D
from twisted.internet.defer import CancelledError
from twisted.python.failure import Failure
from twisted.web.server import NOT_DONE_YET, Site
from twisted.web.resource import Resource

from parsers import GenericGeocodingRequest, MonitorServerGeocodingRequest
from parsers import GenericGeocodingResponse
from parsers import NominatimResponse
from parsers import MonServerResponse
from parsers import MONSERV, NOMINATIM, GOOGLECODER
from parsers import sentinel
from errors import *
import settings

TEMPLATE_DIR = settings.TEMPLATE_DIR
ERROR_503_MSG = '<h1>503</h1> something bad happend... contact administration please'
VERSION = '0.0.1'
HTTP_PORT = settings.PORT
GEOCODERS_URLS = {'monitorserver': 'http://62.76.178.190/cgi-bin/geocoder',
                  'google': 'http://maps.google.com/maps/geo',
                  'nominatim': ' http://nominatim.openstreetmap.org/reverse'}


class NoTemplateError(Exception):
    def __init__(self, path, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)
        self.message = 'could not open template "{}"'.format(path)


def load_template(filename):
    full_path = os.path.join(TEMPLATE_DIR, filename)
    try:
        with open(full_path) as f:
            data = f.read()
    except IOError:
        raise NoTemplateError(full_path)
    else:
        return data


class PageNotFound404(Resource):
    isLeaf = True
    template_name = '404.html'

    def render_GET(self, request):
        try:
            template = load_template(self.template_name)
        except NoTemplateError:
            request.setResponseCode(503)
            return ERROR_503_MSG
        return template.format(VERSION=VERSION)


class GeoServer(Resource):

    template_name = 'welcome.html'

    def getChild(self, path, request):
        if path == '':
            return self
        request.setResponseCode(404)
        return PageNotFound404()

    def render_GET(self, request):
        print '<<< {}'.format(request)
        try:
            template = load_template(self.template_name)
        except NoTemplateError:
            request.setResponseCode(503)
            return ERROR_503_MSG
        return template.format(VERSION=VERSION)

    def render_POST(self, request):
        """TEMP"""
        print '<<< {}'.format(request)
        print request.content.read()
        return 'No Post'


class MonServEmulator(Resource):

    def render_GET(self, request):
        return 'POST please'

    def render_POST(self, request):
        start_time = time.time()
        #print request.method
        #print '<<< {}... '.format(request)
        #lat, lng = parse_request_to_monitorserver(request)
        #d = get_xml_from_monitor_server(request)
        #def cc(resp):
        #    print 'Done'
        #d.addCallback(cc)
        #print 'OK in {}'.format(time.time() - start_time)
        return NOT_DONE_YET


class Nominatim(Resource):
    def render_GET(self, request):
        print 'incoming: {}'.format(request)
        d = get_json_from_nominatim(request)
        def cb(resp):
            print 'DONE'
        d.addCallback(cb)
        return NOT_DONE_YET


class CGI_bin_emul(Resource):
    """Havent fully grok Twisted url dispather thus this little spike"""
    def getChild(self, path, request):
        if path == 'geocoder':
            return MonServToNominatim()
        else:
            return PageNotFound404()


class GenericToNominatim(Resource):

    def print_request(self, request):
        print '{}: {} > {} ...'.format(time.time(), request.getClientIP(),
                                       request.__repr__()),

    def print_end_time(self, start_time):
        print 'OK: {} s'.format(time.time() - start_time)
    def render_GET(self, request):
        def cb_data_received_from_geoserver(response, request):
            request.setHeader('Content-type', 'application/json; charset=UTF-8')
            request.write(response)
            request.finish()

        def eb_something_went_wrong(reason, request):
            request.setResponseCode(500)
            request.write('<h2>500</h2> Something went wrong')
            request.finish()

        def finish_request(_, request, start_time):
            self.print_end_time(start_time)

        try:
            geocoder_request = GenericGeocodingRequest(request)
        except MalformedDataError, err:
            request.setHeader('Content-type', 'application/json; charset=UTF-8')
            return '{"failure": "bad params"}'

        req_start_time = time.time()
        self.print_request(request)

        d = NominatimResponse(geocoder_request).get_address()
        d.addCallback(cb_data_received_from_geoserver, request)
        d.addErrback(lambda err: err.trap(CancelledError))
        d.addErrback(eb_something_went_wrong, request)
        d.addBoth(finish_request, request, req_start_time)
        request.notifyFinish().addErrback(lambda _, d: d.cancel(), d)
        return NOT_DONE_YET


class GenericToMonServer(Resource):

    def print_request(self, request):
        print '{}: {} > {} ...'.format(time.time(), request.getClientIP(),
                                       request.__repr__()),

    def print_end_time(self, start_time):
        print 'OK: {} s'.format(time.time() - start_time)

    def render_GET(self, request):
        def cb_data_received_from_geoserver(response, request):
            request.setHeader('Content-type', 'application/json; charset=UTF-8')
            request.write(response)
            request.finish()

        def eb_something_went_wrong(reason, request):
            request.setResponseCode(500)
            request.write('<h2>500</h2> Something went wrong')
            request.finish()

        def finish_request(_, request, start_time):
            self.print_end_time(start_time)
        #---------------------------------------------------------------------
        try:
            geocoder_request = GenericGeocodingRequest(request)
        except MalformedDataError, err:
            request.setHeader('Content-type', 'application/json; charset=UTF-8')
            return '{"failure": "bad params"}'

        req_start_time = time.time()
        self.print_request(request)

        d = MonServerResponse(geocoder_request).get_address()
        d.addCallback(cb_data_received_from_geoserver, request)
        d.addErrback(lambda err: err.trap(CancelledError))
        d.addErrback(eb_something_went_wrong, request)
        d.addBoth(finish_request, request, req_start_time)
        request.notifyFinish().addErrback(lambda _, d: d.cancel(), d)
        return NOT_DONE_YET


class MonServToNominatim(Resource):

    def print_request(self, request):
        print '{}: {} > {} ...'.format(time.time(), request.getClientIP(),
                                       request.__repr__()),

    def print_end_time(self, start_time):
        print 'OK: {} s'.format(time.time() - start_time)

    def render_GET(self, request):
        self.print_request(request)
        return 'only POST request are allowed'


    def render_POST(self, request):
        def cb_data_received_from_geoserver(response, request):
            request.setHeader('Content-type', 'application/xml; charset=UTF-8')
            request.write(response)
            request.finish()

        def eb_something_went_wrong(reason, request):
            request.setResponseCode(500)
            request.write('<h2>500</h2> Something went wrong')
            request.finish()

        def finish_request(_, request, start_time):
            self.print_end_time(start_time)

        def convertor(data, georequest):
            lat, lon = georequest.get_latlon()
            json = simplejson.loads(data.decode('utf-8'))
            address = 'display_name'
            test_data = ('<?xml version="1.0" encoding="utf-8" ?>'
                         '<nearbyPlaces>'
                         '<point>'
                         '<latlng>{lat}, {lng}</latlng>'
                         '<neighbors>'
                         '<poi>'
                         '<name>{name}</name>'
                         '<street></street>'
                         '<housenumber></housenumber>'
                         '<distance>0</distance>'
                         '</poi>'
                         '</neighbors>'
                         '</point>'
                         '</nearbyPlaces>').format(lat=lat,
                                                   lng=lon,
                                                   name=address)
            return test_data

        # -----------------------------------------------------------
        try:
            geocoder_request = MonitorServerGeocodingRequest(request)
        except MalformedDataError, err:
            request.setHeader('Content-type', 'application/json; charset=UTF-8')
            return '{"failure": "bad params"}'

        req_start_time = time.time()
        self.print_request(request)

        d = NominatimResponse(geocoder_request, convertor=convertor).get_address()
        d.addCallback(cb_data_received_from_geoserver, request)
        d.addErrback(lambda err: err.trap(CancelledError))
        d.addErrback(eb_something_went_wrong, request)
        d.addBoth(finish_request, request, req_start_time)
        request.notifyFinish().addErrback(lambda _, d: d.cancel(), d)
        return NOT_DONE_YET


root = GeoServer()
root.putChild('nominatim', Nominatim())
root.putChild('cgi-bin', CGI_bin_emul())
root.putChild('geocoder', GenericToNominatim())
root.putChild('monserv', GenericToMonServer())
http_factory = Site(root)

def main():
    from twisted.internet import reactor
    reactor.listenTCP(HTTP_PORT, http_factory)
    print 'RGS v {} is listening on {} port'.format(VERSION, HTTP_PORT)
    reactor.run()

if __name__ == '__main__':
    try:
        HTTP_PORT = int(sys.argv[1])
    except:
        pass
    main()
