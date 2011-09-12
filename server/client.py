# -*- coding: utf-8 -*-

from pprint import pformat

from zope.interface import implements
import twisted

from twisted.internet.defer import succeed
from twisted.web.iweb import IBodyProducer
from twisted.web.client import Agent, ResponseDone
from twisted.web.http_headers import Headers
from twisted.internet.defer import Deferred
from twisted.internet.protocol import Protocol

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


def get_xml_from_monitor_server(request, url='http://62.76.178.190/cgi-bin/geocoder'):
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
