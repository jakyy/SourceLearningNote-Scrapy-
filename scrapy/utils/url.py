"""
This module contains general purpose URL functions not found in the standard
library.

Some of the functions that used to be imported from this module have been moved
to the w3lib.url module. Always import those from there instead.
"""
import posixpath
from six.moves.urllib.parse import (ParseResult, urlunparse, urldefrag,
                                    urlparse, parse_qsl, urlencode,
                                    unquote)
#这里使用括弧应当是利用其换行吧。应该没有其他意思。

# scrapy.utils.url was moved to w3lib.url and import * ensures this move doesn't break old code
from w3lib.url import *
from scrapy.utils.python import unicode_to_str

#url的域名是否在domains列表中。
def url_is_from_any_domain(url, domains):
#>>> urlparse('http://www.baidu.com/index:8080')
#ParseResult(scheme='http'
           #, netloc='www.baidu.com'
           #, path='/index:8080'
           #, params='', query='', fragment='')
    """Return True if the url belongs to any of the given domains"""
    host = parse_url(url).netloc.lower()
    #获取主机名小写。

    if host:
        return any( ( 
                      ( host == d.lower() ) or ( host.endswith('.%s' % d.lower() ) ) 
                      for d in domains
                    )
                  )
        #主机名判定：可能相等。也可能是少前缀。
        #any( ( (== ) or (endswith)  for d in domains) )
    else:
        return False

#url属于spider的allowed_domains？
def url_is_from_spider(url, spider):
    """Return True if the url belongs to the given spider"""
    return url_is_from_any_domain(url,
        [spider.name] + list(getattr(spider, 'allowed_domains', [])))

#判断url是否含有拓展符号：.html等等。
def url_has_any_extension(url, extensions):
    return posixpath.splitext(parse_url(url).path)[1].lower() in extensions
#>>>re = urlparse('http://www.baidu.com/file1/file2/index.html')
#ParseResult(scheme='http'
#	    ,netloc='www.baidu.com'
#           ,path='/file1/file2/index.html:8080'
#           ,params='', query='', fragment='')
#>>>posixpath.splitext(re.path)
#('/file1/file2/index', '.html')
#[1]提取元组的第二位。



def canonicalize_url(url, keep_blank_values=True, keep_fragments=False,
        encoding=None):
    """Canonicalize the given url by applying the following procedures:

    - sort query arguments, first by key, then by value
    - percent encode paths and query arguments. non-ASCII characters are
      percent-encoded using UTF-8 (RFC-3986)
    - normalize all spaces (in query arguments) '+' (plus symbol)
    - normalize percent encodings case (%2f -> %2F)
    - remove query arguments with blank values (unless keep_blank_values is True)
    - remove fragments (unless keep_fragments is True)

    The url passed can be a str or unicode, while the url returned is always a
    str.

    For examples see the tests in tests/test_utils_url.py
    """

    scheme, netloc, path, params, query, fragment = parse_url(url)
    #将url分拆成为留个元素。

    keyvals = parse_qsl(query, keep_blank_values)
    #parse_qsl函数是从six里面import过来的。
    #>> parse_qsl('q=1&n=2')
    #[('q', '1'), ('n', '2')]


    keyvals.sort()
    #[('n', '2'), ('q', '1')]

    query = urlencode(keyvals)
    #'n=2&q=1'
 
    path = safe_url_string(_unquotepath(path)) or '/'
    fragment = '' if not keep_fragments else fragment
    return urlunparse((scheme, netloc.lower(), path, params, query, fragment))


def _unquotepath(path):
    for reserved in ('2f', '2F', '3f', '3F'):
        path = path.replace('%' + reserved, '%25' + reserved.upper())
        #这里将path中的字符 %2f 替换为 %252F 3f 
    return unquote(path)
    #unquote对path进行编码

#该函数会返回一个ParseResult，如函数注释。
def parse_url(url, encoding=None):

    """Return urlparsed url from the given argument (which could be an already
    parsed url)
    """
    return url if isinstance(url, ParseResult) else \
        urlparse(unicode_to_str(url, encoding))
        #>>> urlparse('http://www.baidu.com/index:8080')
        #ParseResult(scheme='http'
                    #, netloc='www.baidu.com'
                    #, path='/index:8080'
                    #, params='', query='', fragment='')
        #unicode_to_str()中，如果encoding为None，则在函数内部会默认使用utf-8
        

def escape_ajax(url):
    """
    Return the crawleable url according to:
    http://code.google.com/web/ajaxcrawling/docs/getting-started.html

    >>> escape_ajax("www.example.com/ajax.html#!key=value")
    'www.example.com/ajax.html?_escaped_fragment_=key%3Dvalue'
    >>> escape_ajax("www.example.com/ajax.html?k1=v1&k2=v2#!key=value")
    'www.example.com/ajax.html?k1=v1&k2=v2&_escaped_fragment_=key%3Dvalue'
    >>> escape_ajax("www.example.com/ajax.html?#!key=value")
    'www.example.com/ajax.html?_escaped_fragment_=key%3Dvalue'
    >>> escape_ajax("www.example.com/ajax.html#!")
    'www.example.com/ajax.html?_escaped_fragment_='

    URLs that are not "AJAX crawlable" (according to Google) returned as-is:

    >>> escape_ajax("www.example.com/ajax.html#key=value")
    'www.example.com/ajax.html#key=value'
    >>> escape_ajax("www.example.com/ajax.html#")
    'www.example.com/ajax.html#'
    >>> escape_ajax("www.example.com/ajax.html")
    'www.example.com/ajax.html'
    """
    #>>>urlparse('http://www.example.com/ajax.html?k1=v1&k2=v2#!key=value')
    #ParseResult(scheme='http', netloc='www.example.com', path='/ajax.html'
    #           , params='', query='k1=v1&k2=v2', fragment='!key=value')

    defrag, frag = urldefrag(url)
    #这个函数就是将fragment单独抽取出来的。以上面的url为例
    #('http://www.example.com/ajax.html?k1=v1&k2=v2', '!key=value')

    #如果不是以！开头就直接返回。
    #如果是则对url进行操作。
    if not frag.startswith('!'):
        return url
    return add_or_replace_parameter(defrag, '_escaped_fragment_', frag[1:])#[1:]去感叹号。
    #add_or_replace_parameter这个函数应该是从from w3lib.url import * 导入的。
    #这个函数应该就是把原本的frag进行编码（=->%3D）
    #,然后接上_escaped_frament_,再链接defrag
    #因为我对于web不是很熟悉，所以我不知道这个转移是做什么用的。
    #但是docstring中有提到的文档中应该有详细描写。

