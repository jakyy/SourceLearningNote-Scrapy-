"""
Helper functions for dealing with Twisted deferreds
"""

from twisted.internet import defer, reactor, task
#defer相关操作需要学习twisted教程,
#以了解twisted的基本模型。
#这里需要学习twisted框架，不然根本闹不明白在干什么。
#转头学习twisted框架去啦，可以直接看twisted官网的关于defered的主题。

from twisted.python import failure

from scrapy.exceptions import IgnoreRequest

def defer_fail(_failure):
    """Same as twisted.internet.defer.fail but delay calling errback until
    next reactor loop

    It delays by 100ms so reactor has a chance to go trough readers and writers
    before attending pending delayed calls, so do not set delay to zero.
    """
    d = defer.Deferred()
    #创建延迟对象
    reactor.callLater(0.1, d.errback, _failure)
    #这个应该是在reactor.run启动后，0.1s后调用错误回调。
    return d

def defer_succeed(result):
    """Same as twisted.internet.defer.succeed but delay calling callback until
    next reactor loop

    It delays by 100ms so reactor has a chance to go trough readers and writers
    before attending pending delayed calls, so do not set delay to zero.
    """
    d = defer.Deferred()
    reactor.callLater(0.1, d.callback, result)
    #0.1s后调用回调链。
    return d

def defer_result(result):
    if isinstance(result, defer.Deferred):
        return result
    #如果result是一个延迟对象，则直接返回
    elif isinstance(result, failure.Failure):
        return defer_fail(result)
    #如果是一个failure，则返回一个预备调用错误回调的延迟对象
    else:
        return defer_succeed(result)
    #其他，返回一个预备调用回调函数的延迟对象。

def mustbe_deferred(f, *args, **kw):
    """Same as twisted.internet.defer.maybeDeferred, but delay calling
    callback/errback to next reactor loop
    """
    try:
        result = f(*args, **kw)
    #调用f函数
    # FIXME: Hack to avoid introspecting tracebacks. This to speed up
    # processing of IgnoreRequest errors which are, by far, the most common
    # exception in Scrapy - see #125
    except IgnoreRequest as e:
        return defer_fail(failure.Failure(e))
    except:
        return defer_fail(failure.Failure())
    #如果执行发生异常，则返回调用错误回调的延迟对象。

    else:
        return defer_result(result)
    #如果不是，则对result创建延迟对象。

def parallel(iterable, count, callable, *args, **named):
    """Execute a callable over the objects in the given iterable, in parallel,
    using no more than ``count`` concurrent calls.

    Taken from: http://jcalderone.livejournal.com/24285.html
    """
    coop = task.Cooperator()
    work = (callable(elem, *args, **named) for elem in iterable)
    #work应该是执行结果吧。
    #这个callable不是内建函数，而是从形参传入的。

    return defer.DeferredList([coop.coiterate(work) for i in xrange(count)])

#将callback中的函数操作穿成链，然后调用回调链。
def process_chain(callbacks, input, *a, **kw):
    """Return a Deferred built by chaining the given callbacks"""
    d = defer.Deferred()
    for x in callbacks:
        d.addCallback(x, *a, **kw)
    #把callback加入到链中。
    d.callback(input)
    #调用回调链。
    return d

#判定input的类型，然后调用callback，或者errback
def process_chain_both(callbacks, errbacks, input, *a, **kw):
    """Return a Deferred built by chaining the given callbacks and errbacks"""
    d = defer.Deferred()
    for cb, eb in zip(callbacks, errbacks):
        d.addCallbacks(cb, eb, callbackArgs=a, callbackKeywords=kw,
            errbackArgs=a, errbackKeywords=kw)
    #将callback和errback对 分别加入到回调链和错误链。

    if isinstance(input, failure.Failure):
    #如果input是一个failure
    #就开始调用errorback链？
    #否则调用callback？
        d.errback(input)
    else:
        d.callback(input)
    return d

def process_parallel(callbacks, input, *a, **kw):
    """Return a Deferred with the output of all successful calls to the given
    callbacks
    """
    dfds = [defer.succeed(input).addCallback(x, *a, **kw) for x in callbacks]
    #将所有openspider方法添加到defer.succeed(input)中，这个延迟对象0.1s后就会
    #使用input作为参数，调用其内部的回调链（callback）
    #dfd是一个延迟对象列表，每一个对象被添加了一个callbacks中的函数当作回调函数。
    #0.1s之后，他们会被全部调用。
    
    
    d = defer.DeferredList(dfds, fireOnOneErrback=1, consumeErrors=1)
    #defer.DeferredList也是一个延迟对象，但是，在他之中要传入一个包含延迟对象的列表
    #[d1,d2,d3]
    #当d1,d2,d3他们的callback，或者errback调用完成，会将结果列表传入deferredList的回调。
    #然后调用deferredList的回调。
    
    
    d.addCallbacks(lambda r: [x[1] for x in r], lambda f: f.value.subFailure)
    #添加延迟列表的回调及错误回调。
    #这里相当于函数实体定义。
    #延迟对象回调链的结果：（success，value）。x[1]取结果的值。
    
    return d
    #返回这个延迟对象。

def iter_errback(iterable, errback, *a, **kw):
    """Wraps an iterable calling an errback if an error is caught while
    iterating it.
    """
    it = iter( iterable )
    while 1:
        try:
            yield next(it)
        except StopIteration:
            break
        #如果取尽了，就停止。
        except:
            errback(failure.Failure(), *a, **kw)
        #如果是其他错误，则调用errback

   
