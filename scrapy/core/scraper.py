"""This module implements the Scraper component which parses responses and
extracts information from them"""

import logging
#标准库logging，有多种配置方式。
#scrapy使用的是logging提供的高级方式。
#在每个需要日志的模块中，使用模块名作为logger的名称
#在记录日志的时候会自动记录日志产生的模块。
#另外logger需要handler，filter，formatter配合使用。
#在学习logging时，查看python的官方文档HowTos中关于logging的模块
#https://docs.python.org/2/howto/

from collections import deque
#容器deque
#append从右边加入队尾
#popleft从左边出队


from twisted.python.failure import Failure
from twisted.internet import defer
#-----------twisted架构 defer

from scrapy.utils.defer import defer_result, defer_succeed, parallel, iter_errback
#这个看过了，但是由于不太懂twisted，所以不明白运作细节。

from scrapy.utils.spider import iterate_spider_output
#这个函数将传入的参数变成可迭代的对象返回。
#传入result，如果result可迭代则直接返回，
#否则返回[result]

from scrapy.utils.misc import load_object
#输入一个path：scrapy.downloadermiddlewares.redirect.RedirectMiddleware
#将会import scrapy.downloadermiddlewares.redirect
#并且尝试返回RedirectMiddleware模块

from scrapy.utils.log import logformatter_adapter, failure_to_exc_info
#logformatter_adapter:从输入的参数中提取出level，message，args元组。参数是一个包含logging设置的字典。

#failure_to_exc_info:参数是一个twisted.python.Failure类实例。
#返回这个失败实例的type，value，etTracebackObject()

from scrapy.exceptions import CloseSpider, DropItem, IgnoreRequest
from scrapy import signals
#signals中就是一对object对象的实例，取了不同的名字而已。

from scrapy.http import Request, Response
#两个代表http请求和回复的类。包含url/body/encoding等等属性。

from scrapy.item import BaseItem
#BaseItem就是一个object_ref的子类，但是没有添加任何东西。

from scrapy.core.spidermw import SpiderMiddlewareManager
#SpiderMiddlewareManager：
#添加了scrape_response实例方法：
#方法内部，有process_spider_input调用处理方法
#process_spider_output调用callback
#process_spider_exception调用errorback

####################################################################
logger = logging.getLogger(__name__)


class Slot(object):
    """Scraper slot (one per running spider)"""
    #每一个spider 有一个slot
    MIN_RESPONSE_SIZE = 1024

    def __init__(self, max_active_size=5000000):#5000000是怎么来的。
        self.max_active_size = max_active_size
        self.queue = deque() #队列，这个队列是用来存放什么东西的？
        self.active = set()  #集合
        self.active_size = 0 
        self.itemproc_size = 0
        self.closing = None

    def add_response_request(self, response, request):
        deferred = defer.Deferred()
        self.queue.append((response, request, deferred))
        #队列存入了（response,request,defered）元组。

        if isinstance(response, Response):
            self.active_size += max(len(response.body), self.MIN_RESPONSE_SIZE)
        #response如果是一个Response对象，则活动size增加一个数字。

        else:
            self.active_size += self.MIN_RESPONSE_SIZE
        #如果不是Response对象，则添加最小值。

        return deferred

    def next_response_request_deferred(self):
        response, request, deferred = self.queue.popleft()
        #出列

        self.active.add(request)
        #集合添加request

        return response, request, deferred
        #返回元组。

    def finish_response(self, response, request):
        self.active.remove(request)
        #集合移除request

        if isinstance(response, Response):
            self.active_size -= max(len(response.body), self.MIN_RESPONSE_SIZE)
        else:
            self.active_size -= self.MIN_RESPONSE_SIZE
        #处理其他数据。

    #队列为空并且active为空，则表示空闲。
    def is_idle(self):
        return not (self.queue or self.active)

    def needs_backout(self):
        return self.active_size > self.max_active_size
    #如果活动

class Scraper(object):

    def __init__(self, crawler):
        self.slot = None
        self.spidermw = SpiderMiddlewareManager.from_crawler(crawler)
        itemproc_cls = load_object(crawler.settings['ITEM_PROCESSOR'])
        #ITEM_PROCESSOR = 'scrapy.pipelines.ItemPipelineManager'
        #ItemPipelineManager是一个MiddlewareManager的派生类
        #加入了一个功能：将pipeline中process_item方法添加到回调链中。_add_middleware
        #然后以callback(spider)调用回调链。(pipelinemanager.process_item)

        self.itemproc = itemproc_cls.from_crawler(crawler)
        #管道管理器实例化。

        self.concurrent_items = crawler.settings.getint('CONCURRENT_ITEMS')
        #默认100

        self.crawler = crawler
        self.signals = crawler.signals
        self.logformatter = crawler.logformatter

    #装饰器：当yield中返回的defer对象的result可用时，生成器会重新开始。
    #？这个应该是意味着，当所有的open_spider返回result了，生成器就重置？
    @defer.inlineCallbacks
    def open_spider(self, spider):
        """Open the given spider for scraping and allocate resources for it"""
        self.slot = Slot()
        #实例化一个slot
        #这个slot如何与spider绑定呢？
        
        yield self.itemproc.open_spider(spider)
        #open_spider是MiddlewareManager的方法
        #将self.methods['open_spider'] 与 spider 作为参数
        #传入到_process_parallel:
        #对每一个open_spider函数生成延迟对象，并在轮询开始马上调用callback
        #当所有open_spider完成执行，返回一个执行结果列表（deferList的callback）。

    def close_spider(self, spider):
        """Close a spider being scraped and release its resources"""
        slot = self.slot
        slot.closing = defer.Deferred()
        slot.closing.addCallback(self.itemproc.close_spider)
        self._check_if_closing(spider, slot)
        return slot.closing
        #返回的是一个延迟对象。延迟对象有一个callback：close_spider。
        #close_spider与open_sipder是一个执行过程。
        #callback中添加的也是一个延迟对象。这种多层次的延迟对象以何种形式组织。

    def is_idle(self):
        """Return True if there isn't any more spiders to process"""
        return not self.slot

    def _check_if_closing(self, spider, slot):
        if slot.closing and slot.is_idle():
            slot.closing.callback(spider)
        #当closing延迟对象被实例化，并且is_idle，则开始关闭spider的回调

    def enqueue_scrape(self, response, request, spider):
        slot = self.slot
        dfd = slot.add_response_request(response, request)
        #response,request,以及一个deferred入列。
        #返回deferred

        def finish_scraping(_):
            slot.finish_response(response, request)
            
            self._check_if_closing(spider, slot)
            #如果closing，则立即启动关闭链。

            self._scrape_next(spider, slot)
            #爬取下一个
            return _

        dfd.addBoth(finish_scraping)
        dfd.addErrback(
            lambda f: logger.error('Scraper bug processing %(request)s',
                                   {'request': request},
                                   exc_info=failure_to_exc_info(f),
                                   extra={'spider': spider}))
        self._scrape_next(spider, slot)
        return dfd

    def _scrape_next(self, spider, slot):
        while slot.queue:
            response, request, deferred = slot.next_response_request_deferred()
            self._scrape(response, request, spider).chainDeferred(deferred)

    def _scrape(self, response, request, spider):
        """Handle the downloaded response or failure trough the spider
        callback/errback"""
        assert isinstance(response, (Response, Failure))

        dfd = self._scrape2(response, request, spider) # returns spiders processed output
        dfd.addErrback(self.handle_spider_error, request, response, spider)
        dfd.addCallback(self.handle_spider_output, request, response, spider)
        return dfd

    def _scrape2(self, request_result, request, spider):
        """Handle the different cases of request's result been a Response or a
        Failure"""
        if not isinstance(request_result, Failure):
            return self.spidermw.scrape_response(
                self.call_spider, request_result, request, spider)
        else:
            # FIXME: don't ignore errors in spider middleware
            dfd = self.call_spider(request_result, request, spider)
            return dfd.addErrback(
                self._log_download_errors, request_result, request, spider)

    def call_spider(self, result, request, spider):
        result.request = request
        dfd = defer_result(result)
        dfd.addCallbacks(request.callback or spider.parse, request.errback)
        return dfd.addCallback(iterate_spider_output)

    def handle_spider_error(self, _failure, request, response, spider):
        exc = _failure.value
        if isinstance(exc, CloseSpider):
            self.crawler.engine.close_spider(spider, exc.reason or 'cancelled')
            return
        referer = request.headers.get('Referer')
        logger.error(
            "Spider error processing %(request)s (referer: %(referer)s)",
            {'request': request, 'referer': referer},
            exc_info=failure_to_exc_info(_failure),
            extra={'spider': spider}
        )
        self.signals.send_catch_log(
            signal=signals.spider_error,
            failure=_failure, response=response,
            spider=spider
        )
        self.crawler.stats.inc_value(
            "spider_exceptions/%s" % _failure.value.__class__.__name__,
            spider=spider
        )

    def handle_spider_output(self, result, request, response, spider):
        if not result:
            return defer_succeed(None)
        it = iter_errback(result, self.handle_spider_error, request, response, spider)
        dfd = parallel(it, self.concurrent_items,
            self._process_spidermw_output, request, response, spider)
        return dfd

    def _process_spidermw_output(self, output, request, response, spider):
        """Process each Request/Item (given in the output parameter) returned
        from the given spider
        """
        if isinstance(output, Request):
            self.crawler.engine.crawl(request=output, spider=spider)
        elif isinstance(output, (BaseItem, dict)):
            self.slot.itemproc_size += 1
            dfd = self.itemproc.process_item(output, spider)
            dfd.addBoth(self._itemproc_finished, output, response, spider)
            return dfd
        elif output is None:
            pass
        else:
            typename = type(output).__name__
            logger.error('Spider must return Request, BaseItem, dict or None, '
                         'got %(typename)r in %(request)s',
                         {'request': request, 'typename': typename},
                         extra={'spider': spider})

    def _log_download_errors(self, spider_failure, download_failure, request, spider):
        """Log and silence errors that come from the engine (typically download
        errors that got propagated thru here)
        """
        if (isinstance(download_failure, Failure) and
                not download_failure.check(IgnoreRequest)):
            if download_failure.frames:
                logger.error('Error downloading %(request)s',
                             {'request': request},
                             exc_info=failure_to_exc_info(download_failure),
                             extra={'spider': spider})
            else:
                errmsg = download_failure.getErrorMessage()
                if errmsg:
                    logger.error('Error downloading %(request)s: %(errmsg)s',
                                 {'request': request, 'errmsg': errmsg},
                                 extra={'spider': spider})

        if spider_failure is not download_failure:
            return spider_failure

    def _itemproc_finished(self, output, item, response, spider):
        """ItemProcessor finished for the given ``item`` and returned ``output``
        """
        self.slot.itemproc_size -= 1
        if isinstance(output, Failure):
            ex = output.value
            if isinstance(ex, DropItem):
                logkws = self.logformatter.dropped(item, ex, response, spider)
                logger.log(*logformatter_adapter(logkws), extra={'spider': spider})
                return self.signals.send_catch_log_deferred(
                    signal=signals.item_dropped, item=item, response=response,
                    spider=spider, exception=output.value)
            else:
                logger.error('Error processing %(item)s', {'item': item},
                             exc_info=failure_to_exc_info(output),
                             extra={'spider': spider})
        else:
            logkws = self.logformatter.scraped(output, response, spider)
            logger.log(*logformatter_adapter(logkws), extra={'spider': spider})
            return self.signals.send_catch_log_deferred(
                signal=signals.item_scraped, item=output, response=response,
                spider=spider)

