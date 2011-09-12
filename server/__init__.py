# -*- coding: utf-8 -*-

import os
import cgi
import sys
import time

from twisted.internet.defer import Deferred as D
from twisted.web.server import NOT_DONE_YET, Site
from twisted.web.resource import Resource
from parsers import parse_request_to_monitorserver
from client import get_xml_from_monitor_server

TEMPLATE_DIR = '../templates'
ERROR_503_MSG = '<h1>503</h1> something bad happend... contact administration please'
VERSION = '0.0.1'
HTTP_PORT = 8888
GEOCODERS_URLS = {'monitorserver': 'http://62.76.178.190/cgi-bin/geocoder',
                  'google': 'http://maps.google.com/maps/geo',
                  'nominatim': ' http://nominatim.openstreetmap.org/reverse'}


class NoTemplateError(Exception):
    def __init__(self, path, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)
        self.message = 'could not open template "{}"'.format(path)

class MalformedDataError(Exception):
    pass


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


class BaseReverseGeocoder(Resource):
    """
        Base class for reverse geocoding requests
        gets data, parses it and sends to server
        returns server answer to client
    """

    def send_response(self, respone, request):
        request.write(response)
        request.finish()

    def render_GET(self, request):
        data = self._parse_request()

        return NOT_DONE_YET


class CGI_bin_emul(Resource):
    def getChild(self, path, request):
        if path == 'geocoder':
            return MonServEmulator()
        else:
            return PageNotFound404()


class MonServEmulator(Resource):

    def render_GET(self, request):
        return 'POST please'

    def render_POST(self, request):
        start_time = time.time()
        print request.method
        print '<<< {}... '.format(request)
        #lat, lng = parse_request_to_monitorserver(request)
        d = get_xml_from_monitor_server(request)
        def cc(resp):
            print 'Done'
        d.addCallback(cc)
        print 'OK in {}'.format(time.time() - start_time)
        return NOT_DONE_YET

def main():
    from twisted.internet import reactor
    root = GeoServer()
    root.putChild('cgi-bin', CGI_bin_emul())
    http_factory = Site(root)
    reactor.listenTCP(HTTP_PORT, http_factory)
    print 'RGS v {} is listening on {} port'.format(VERSION, HTTP_PORT)
    reactor.run()

if __name__ == '__main__':
    try:
        HTTP_PORT = int(sys.argv[1])
    except:
        pass
    main()
