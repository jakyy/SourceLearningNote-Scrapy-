import logging
from collections import defaultdict
#defaultdict是一个dict的子类。
#它加入了一个属性default_factory
#在初始化是传入这个default_factory这个参数，
#字典的value将会变成这个类型。
#例如，d = defaultdict(list)
#d中的value值就是list类型。

from scrapy.exceptions import NotConfigured
#异常类。

from scrapy.utils.misc import load_object
#输入'scrapy.spider.middle'
#该函数会执行a = import_module('scrapy.spider')
#return getattr(a,'middle')
#也就是返回scrapy.spider.middle这个模块。

from scrapy.utils.defer import process_parallel, process_chain, process_chain_both
#这个不是特别熟悉，这个应该是用来组织多个程序如何进行连续作业的。


logger = logging.getLogger(__name__)
#

class MiddlewareManager(object):
    """Base class for implementing middleware managers"""

    component_name = 'foo middleware'
    #组件名称。

    def __init__(self, *middlewares):
        self.middlewares = middlewares
        #记录middlewares，也是一个列表。
        #这里实际上会传入from_setting中的获取到的
        #中间件的实例列表。

        self.methods = defaultdict(list)
        #methods是一个defaultdict，每一个value是一个列表。

        for mw in middlewares:
            self._add_middleware(mw)
        #_add_middleware：进行了两种抽取工作。
        #将每一个中间件中，open_spider方法加入到methods['open_spider']列尾
        #将每一个中间件中，close_spider方法加入到methods['close_spider']列首

    @classmethod
    def _get_mwlist_from_settings(cls, settings):
        raise NotImplementedError
    #该方法还没有被实现

    #类方法可以被类或者实力调用
    #但是不能访问__init__函数里面初始化的实例变量。
    #如果是实例调用的类方法，能不能访问实例变量呢？
    #因为实例变量第一参数传入的class，而不是self。
    #from_setting/from_crawler。都是用来创建实例的。
    @classmethod
    def from_settings(cls, settings, crawler=None):
        mwlist = cls._get_mwlist_from_settings(settings)
        #这个cls就是类本身
        #这里的_get_mwlist_from_settings没有任何意义。
        #需要在继承类中实现了该方法才可以。
        #mwlist获取到的应该是scrapy.conribute.xxmiddleware这种格式
        #字符串列表的列表。

        middlewares = []
        
        for clspath in mwlist:
            try:

                mwcls = load_object(clspath)
                #从path获取到类

                if crawler and hasattr(mwcls, 'from_crawler'):
                    mw = mwcls.from_crawler(crawler)
                #如果指定crawler，并且类中有from_crawler这个方法
                #则使用from_crawler进行实例化。

                elif hasattr(mwcls, 'from_settings'):
                    mw = mwcls.from_settings(settings)
                #如果没有from_crawler不能用，就用from_settings
                #来实例化
                 
                else:
                    mw = mwcls()
                #以上两个都没有，就直接实例化。

                middlewares.append(mw)
                #获取到中间件的实例，加入到列表尾。

            except NotConfigured as e:
                if e.args:
                    clsname = clspath.split('.')[-1]
                    logger.warning("Disabled %(clsname)s: %(eargs)s",
                                   {'clsname': clsname, 'eargs': e.args[0]},
                                   extra={'crawler': crawler})

        enabled = [x.__class__.__name__ for x in middlewares]
        #middlewares里是中间件的实例列表。
        #enabled中哦呢包含所有获取到的中间件的类名。

        logger.info("Enabled %(componentname)ss: %(enabledlist)s",
                    {'componentname': cls.component_name,
                     'enabledlist': ', '.join(enabled)},
                    extra={'crawler': crawler})

        return cls(*middlewares)
        #这里返回一个本类的实例。可以通过这个方法进行实例化。
        #这个return中的参数是怎么回事？？
        #做了个实验，a=[1,2,3,4,5,6]
        #pprint(a)是可以的
        #pprint(*a)会报错，说pprint只接受5个参数，但是这样调用提供了6个参数。
        #也就是说*a将a中的每一个元素当作一个 参数传递过去了。


    @classmethod
    def from_crawler(cls, crawler):
        return cls.from_settings(crawler.settings, crawler)

    #本类的from_crawler也是调用from_setting来实现的。
    #其他的是不是也是这样一个逻辑结构。



    #这个函数做了什么：
    #如果中间件有名为open_spider的方法，则加入到method['open_spider']队列尾。
    #如果有close_spider的方法，加入到method['close_spider']队列头。
    #因为先打开的要后关闭么？？
    def _add_middleware(self, mw):
        if hasattr(mw, 'open_spider'):
            self.methods['open_spider'].append(mw.open_spider)
        if hasattr(mw, 'close_spider'):
            self.methods['close_spider'].insert(0, mw.close_spider)
        #list.append方法将加入列表最后
        #list.insert(index,element)。
        #index=0插入到列表第一位的前面
        #index=-1插入到最后以为之前

    def _process_parallel(self, methodname, obj, *args):
        return process_parallel(self.methods[methodname], obj, *args)
    #给self.methods[methodname]中的每一个函数都创建一个延迟对象，
    #这个延迟对象在事件轮询开始之后的0.1s调用回调（链或者没有链）
    #这些延迟对象组成deferredList：callback是返回所有methodname执行的结果
    #errback则是subfailure。
    #然后返回了这个deferredList。当所有的延迟对象的call/errback执行完毕
    #再执行deferredList的call/errback

    def _process_chain( self, methodname, obj, *args ):
        return process_chain(self.methods[methodname], obj, *args)
    #将methodS['methodname']加入到回调链。
    #调用回调链，并返回deferred实例。

    def _process_chain_both(self, cb_methodname, eb_methodname, obj, *args):
        return process_chain_both(self.methods[cb_methodname], \
            self.methods[eb_methodname], obj, *args)
    #将回调和错误回调对，分别加入回调链。然后根据obj的类型调用回调，或者错误回调。
    #*args是回调的其他参数。

    def open_spider(self, spider):
        return self._process_parallel( 'open_spider', spider )
    #将名为字典中，名为open_spider的函数实例列表传入_process_parallel。

    def close_spider(self, spider):
        return self._process_parallel( 'close_spider', spider )
    #同上。
