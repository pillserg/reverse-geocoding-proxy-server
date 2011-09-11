from twisted.internet.defer import Deferred as D
from twisted.web.server import NOT_DONE_YET, Site
from twisted.web.resource import Resource
import os


TEMPLATE_DIR = '../templates'
ERROR_503_MSG = '<h1>503</h1> something bad happend... contact administration please'
VERSION = '0.0.1'
HTTP_PORT = 8888

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

    def __init__(self, path):
        Resource.__init__(self)
        self.path = path

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
        return PageNotFound404(path)
    
    def render_GET(self, request):
        try:
            template = load_template(self.template_name)
        except NoTemplateError:
            request.setResponseCode(503)
            return ERROR_503_MSG
        return template.format(VERSION=VERSION)


def main():
    from twisted.internet import reactor
    root = GeoServer()
    http_factory = Site(root)
    reactor.listenTCP(HTTP_PORT, http_factory)
    print 'RGS v {} is listening on {} port'.format(VERSION, HTTP_PORT)
    reactor.run()
    
if __name__ == '__main__':
    main()