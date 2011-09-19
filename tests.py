from server.parsers import NominatimResponse, GenericGeocodingRequest

mock_geo_request = GenericGeocodingRequest(request={'lat': 50,
                                                    'lon': 29},
                                           format='json',
                                           MOCK=True)
from server.utils import sentinel


COUNTER = 0
GLOB = []
F = open('C:/TEMP/log_test.txt', 'w')



def printer(res):
    print '.',
    F.write(res + '\n')


def play():
    response = NominatimResponse(mock_geo_request)
    d = response.get_address()
    d.addCallback(printer)

    from twisted.internet import reactor
    reactor.callLater(0.1, play)

    return d

def stop_reactor():
    from twisted.internet import reactor
    reactor.stop()
    F.close()

d = play()
from twisted.internet import reactor
reactor.callLater(1000, stop_reactor)
print 'starting reactor-----'
print 'requesting:'
reactor.run()
print 'reactor done'
