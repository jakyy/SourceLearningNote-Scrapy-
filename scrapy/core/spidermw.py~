"""
Spider Middleware manager

See documentation in docs/topics/spider-middleware.rst
"""

from twisted.python.failure import Failure
#失败类

from scrapy.middleware import MiddlewareManager
#MiddlewareManager：该类定义了中间件管理的相关操作。
#self.methods是一个defaultdict类，其value值是list类型。
#其在初始化是对中间件的特定函数实例进行装载。
#类中还定义了对这些函数实例进行延迟调用的相关操作。这部分还不是特别明白。
#from_settings可以用来实例化。

from scrapy.utils.defer import mustbe_deferred
#传入一个函数对象，和参数
#获取该函数执行的结果。
#如果有IgnoreRequest，或者其他异常。则调用错误回调
#否则用结果调用回调链。

from scrapy.utils.conf import build_component_list
#这个函数做了三件事：
#接受base，custom，和update_classpath函数实例。
#利用函数update_classpath来替换base，custom中的不赞成使用的模块。
#检查配置的模块path有没有问题。
#注意几点（使用默认的update_classpath函数）：
#1custom中指定的class会覆盖base中同名的。
#2custom中value指定为None的模块，会被忽略。
#3字典中的value会被当作排序的依据。
#4如果custom中使用的不是字典，而是元组或者列表，则不会和base合并。
# 而是直接使用custom中的列表。

def _isiterable(possible_iterator):
    return hasattr(possible_iterator, '__iter__')
#hasattr(possible_iterator,'__iter__')

class SpiderMiddlewareManager(MiddlewareManager):

    component_name = 'spider middleware'

    #self.methods = defaultdict(list)
    #基类属性，value的类型为list

    #蜘蛛中间件管理器类方法。
    #在MiddlewareManager中，该方法没有被完成。
    #在from_setting方法中，需要使用这个方法来获取中间件列表。
    #将SETTINGS中SPIDER_MIDDLEWARES_BASE 和 SPIDER_MIDDLEWARES字典合并覆盖
    #并且将优先级排序，然后返回一个classpath列表。
    @classmethod
    def _get_mwlist_from_settings(cls, settings):
        return build_component_list(settings['SPIDER_MIDDLEWARES_BASE'], \
            settings['SPIDER_MIDDLEWARES'])
        
    #基类的初始化方法中会对实例化传入的所有中间件调用该方法。
    #基类的_add_middleware方法做了：
    #1将mw中，名为open_spider的方法添加到methods['open_spider']列尾。
    #2将mw中，名为close_spider的方法添加到methods['close_spider']列首。
    def _add_middleware(self, mw):
        super(SpiderMiddlewareManager, self)._add_middleware(mw)
        #mw.process_spider_input      列尾
        #mw.process_spider_output     列首
        #mw.process_spider_exception  列首
        #mw.process_start_requests    列首
        if hasattr(mw, 'process_spider_input'):
            self.methods['process_spider_input'].append(mw.process_spider_input)
        if hasattr(mw, 'process_spider_output'):
            self.methods['process_spider_output'].insert(0, mw.process_spider_output)
        if hasattr(mw, 'process_spider_exception'):
            self.methods['process_spider_exception'].insert(0, mw.process_spider_exception)
        if hasattr(mw, 'process_start_requests'):
            self.methods['process_start_requests'].insert(0, mw.process_start_requests)


    def scrape_response(self, scrape_func, response, request, spider):
        #scrapy_func是什么东西？？

        fname = lambda f:'%s.%s' % (f.im_self.__class__.__name__, f.im_func.__name__)
        #fname(f):传入f
        #返回f.im_self.__class__.__name__ 和f.im_func.__name__连接的字符串。


        def process_spider_input(response):
            #依次调用methods中存入的，所有中间件中的process_spider_input方法。
            for method in self.methods['process_spider_input']:
                try:
                    result = method(response=response, spider=spider)
                    #每一个中间件处理input完成的result没有记录或者处理
                    #process_spider_inpurt1,2,3,4,5,6...(response,spider)

                    assert result is None, \
                            'Middleware %s must returns None or ' \
                            'raise an exception, got %s ' \
                            % ( fname(method), type( result ) )
                    #如果result为None，则表示调用成功。
                    #猜测：可能repsonse在process中已经被修改了某些部分，
                    #所以没有必要记录返回的result。
                except:
                    return scrape_func(Failure(), request, spider)
                #猜测：如果有一个中间件执行错误。应该是调用错误回调。
                #猜测：Failure()实例作为input（或者result)返回到下一错误链。

            return scrape_func(response, request, spider)
            #猜测：如果执行正确，则以response为input（或者result）返回到回调链。


        def process_spider_exception(_failure):
            exception = _failure.value
            #exception
            for method in self.methods['process_spider_exception']:
                result = method(response=response, exception=exception, spider=spider)
                assert result is None or _isiterable(result), \
                    'Middleware %s must returns None, or an iterable object, got %s ' % \
                    (fname(method), type(result))

                #如果不是None，就从链中断开，直接返回result。
                #猜测：这个result会不会返回到callback？？
                if result is not None:
                    return result
            return _failure

        def process_spider_output(result):
            for method in self.methods['process_spider_output']:
                result = method(response=response, result=result, spider=spider)
                assert _isiterable(result), \
                    'Middleware %s must returns an iterable object, got %s ' % \
                    (fname(method), type(result))
            return result

        dfd = mustbe_deferred(process_spider_input, response)
        #mustbe_deffered:首先调用result = process_spider_input(response)
        #出错就一会调用errback
        #result没问题则调用下一轮处理result的延迟。

        dfd.addErrback(process_spider_exception)
        #添加errback


        dfd.addCallback(process_spider_output)
        #添加callback

        return dfd
        #返回这个延迟对象。

    def process_start_requests(self, start_requests, spider):
        return self._process_chain('process_start_requests', start_requests, spider)
        #scrapy.utils.defer.process_chain(self.methods['process_start_requests'], obj, *args)
        #将self.methods['process_start_requests']列表中的每一个实例添加到一个延迟defer.deferred()
        #然后调用d.callback(start_requests)




