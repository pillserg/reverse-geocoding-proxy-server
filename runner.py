import server
import sys
from twisted.application import service, internet

application = service.Application("Track_Server")

print 'RGS v {} is listening on {} port'.format(server.VERSION, server.HTTP_PORT)
httpService = internet.TCPServer(server.HTTP_PORT, server.http_factory)



httpService.setServiceParent(application)
