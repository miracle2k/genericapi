from dispatch import Dispatcher
from response import APIResponse

__all__ = (
    'XmlRpcDispatcher',
    'XmlRpcResponse',
)

class XmlRpcResponse(APIResponse):
    def format(self, data):
        if isinstance(data, APIError):
            # convert to fault xmlrpc message
            pass
        else:
            # convert standard
            pass

class XmlRpcDispatcher(Dispatcher):
    """
    Accepts the regular XML-RPC method call via POST. Fails on GET, or if
    called with a (sub-)url. Uses a dot  "." for separating namespaces.

    POST /
    <?xml version="1.0"?>
    <methodCall>
      <methodName>comments.add</methodName>
      <params>
        <param><value><string>great post!</string></value></param>
      </params>
    </methodCall>
    ==> api.comments.add("great post!")

    Note that keyword arguments are not supported.
    """
    # TODO: support automatic introspection, multicall

    default_response_class = XmlRpcResponse

    def parse_url(self, request):
        pass