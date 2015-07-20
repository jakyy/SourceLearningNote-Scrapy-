"""
This module implements the Response class which is used to represent HTTP
responses in Scrapy.

See documentation in docs/topics/request-response.rst
"""

import copy

from six.moves.urllib.parse import urljoin
#six是一个兼容python2和python3的包，其中的功能都是常用的包，功能是一致的。
#urljoin是做了什么呢？
#urljoin(base, url, allow_fragments=True)

from scrapy.http.headers import Headers
#key，value都是列表的字典。

from scrapy.utils.trackref import object_ref
#object_ref是一个object的别名，加入了一个记录活动实例的类。

from scrapy.http.common import obsolete_setter
#返回一个打印错误信息的setter。

class Response(object_ref):

    def __init__(self, url, status=200, headers=None, body='', flags=None, request=None):
        self.headers = Headers(headers or {})
        self.status = int(status)
        self._set_body(body)
        self._set_url(url)
        self.request = request
        #response里记录了request
        self.flags = [] if flags is None else list(flags)

    @property
    def meta(self):
        #response的meta返回的是request的meta
        try:
            return self.request.meta
        except AttributeError:
            raise AttributeError("Response.meta not available, this response " \
                "is not tied to any request")
    #meta
    def _get_url(self):
        return self._url

    def _set_url(self, url):
        if isinstance(url, str):
            self._url = url
        else:
            raise TypeError('%s url must be str, got %s:' % (type(self).__name__, \
                type(url).__name__))

    url = property(_get_url, obsolete_setter(_set_url, 'url'))
    #url
    def _get_body(self):
        return self._body

    def _set_body(self, body):
        if isinstance(body, str):
            self._body = body
        elif isinstance(body, unicode):
            raise TypeError("Cannot assign a unicode body to a raw Response. " \
                "Use TextResponse, HtmlResponse, etc")
        elif body is None:
            self._body = ''
        else:
            raise TypeError("Response body must either be str or unicode. Got: '%s'" \
                % type(body).__name__)

    body = property(_get_body, obsolete_setter(_set_body, 'body'))
    #body
    def __str__(self):
        return "<%d %s>" % (self.status, self.url)

    __repr__ = __str__

    def copy(self):
        """Return a copy of this Response"""
        return self.replace()

    def replace(self, *args, **kwargs):
        """Create a new Response with the same attributes except for those
        given new values.
        """
        for x in ['url', 'status', 'headers', 'body', 'request', 'flags']:
            kwargs.setdefault(x, getattr(self, x))
        cls = kwargs.pop('cls', self.__class__)
        return cls(*args, **kwargs)

    def urljoin(self, url):
        """Join this Response's url with a possible relative url to form an
        absolute interpretation of the latter."""
        return urljoin(self.url, url)
