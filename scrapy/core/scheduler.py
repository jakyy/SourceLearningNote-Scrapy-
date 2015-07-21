import os
import json
import logging
from os.path import join, exists

#queuelib.PriorityQueue()
#queuelib是scrapy项目自己开发的一个包。
#queuelib.queue包含内存LIFO，FIFO，硬盘：LIFO，FIFO，四种队列。
#queuelib.pqueue实现PriorityQueue()
#其中内存队列主要使用python自带的collection.deque结构实现。
#硬盘队列是自己实现的文件写入方式存储的队列。
from queuelib import PriorityQueue

#request读取到dict，或者通过dict构造request
from scrapy.utils.reqser import request_to_dict, request_from_dict
from scrapy.utils.misc import load_object
from scrapy.utils.job import job_dir

logger = logging.getLogger(__name__)


class Scheduler(object):
#Scheduler实例有三个主要的属性或者说是数据结构：
#1 self.dupefilter 去重功能实例。
#2 self.dqs 磁盘队列管理器，里面按优先级为关键字，每一个优先级对应一个request队列。
#4 self.mqs 内存队列管理器，同上。


    #__init__方法是通过类方法from_crawler来调用的，也就是一般都要一个crawler才方便实例化。
    def __init__(self, dupefilter, jobdir=None, dqclass=None, mqclass=None, logunser=False, stats=None):
        self.df = dupefilter
        self.dqdir = self._dqdir(jobdir)
        self.dqclass = dqclass
        self.mqclass = mqclass
        
        #这个东西是从setting读取出来的，用来干嘛呢？
        self.logunser = logunser 
        
        #crawler的stats，这个属性是做什么的呢？
        self.stats = stats 
    
    @classmethod
    def from_crawler(cls, crawler):
        settings = crawler.settings
        
        #DUPEFILTER_CLASS = 'scrapy.dupefilters.RFPDupeFilter'
        dupefilter_cls = load_object(settings['DUPEFILTER_CLASS'])
        dupefilter = dupefilter_cls.from_settings(settings)
        
        #SCHEDULER_DISK_QUEUE = 'scrapy.squeues.PickleLifoDiskQueue'
        dqclass = load_object(settings['SCHEDULER_DISK_QUEUE'])

        #SCHEDULER_MEMORY_QUEUE = 'scrapy.squeues.LifoMemoryQueue'
        mqclass = load_object(settings['SCHEDULER_MEMORY_QUEUE'])
         
        #LOG_UNSERIALIZABLE_REQUESTS：False
        logunser = settings.getbool('LOG_UNSERIALIZABLE_REQUESTS')

        return cls(dupefilter, job_dir(settings), dqclass, mqclass, logunser, crawler.stats)

    def has_pending_requests(self):
        #len(self)会调用该类中__len__方法。计量内存和硬盘队列的总长。
        return len(self) > 0

    def __len__(self):
        #如果self.dqs（diskqueue)不为空，则加上self.dqs,否则返回self.mqs
        return len(self.dqs) + len(self.mqs) if self.dqs else len(self.mqs)

    def open(self, spider):
        #打开调度器，绑定spider，实例化mqs，dqs。
        self.spider = spider

        #PriorityQueue见import部分。
        #mqs=memery_queues,queues使用的是自己实现的PriorityQueue。
        #队列中没一项都是一个memeryqueue-scrapy.squeues.LifoMemoryQueue
        self.mqs = PriorityQueue(self._newmq)

        #当指定了JOBDIR，self.dqdir是JOBDIR的子目录。
        #self.dqdir = setting['JOBDIR'] + '/request.queue'
        #在获取这个文件夹path同时，也创建了这个文件夹。
        #self._dq()：返回了一个diskqueue的PriorityQueue，会处理文件中的内容读入到内存。
        self.dqs = self._dq() if self.dqdir else None

        #返回dupefilter实例。
        #RFPDupeFilter没有实现open方法，
        #其基类BaseDupeFilter.open(),只有一句pass
        #所以这个scheduler.open(),在不改变调度器和去重类的情况下，直接返回的是None
        return self.df.open()

    def close(self, reason):
        if self.dqs:
            #PriorityQueue.close()方法，获取到每一个prios，并关闭dqs中的每一个队列。
            prios = self.dqs.close() 
            with open(join(self.dqdir, 'active.json'), 'w') as f:
                json.dump(prios, f)
        #mqs不做处理。

        #self.df.close():如果JOBDIR存在则将，则关闭指定的request.seen文件。否则不做任何操作。
        return self.df.close(reason)

    def enqueue_request(self, request):
        #去重标志为真，dupefilter中出现过当前request：
        #不做操作，记录日志。
        if not request.dont_filter and self.df.request_seen(request):
            self.df.log(request, self.spider)
            return False
        
        #如果进入disk队列，就不会进入内存队列。
        #入列先尝试disk，disk没有再尝试内存。
        dqok = self._dqpush(request)
        if dqok:
            #self.stats是干嘛用的。
            self.stats.inc_value('scheduler/enqueued/disk', spider=self.spider)
        else:
            self._mqpush(request)
            self.stats.inc_value('scheduler/enqueued/memory', spider=self.spider)
        self.stats.inc_value('scheduler/enqueued', spider=self.spider)
        return True

    def next_request(self):
    #出列先尝试从内存队列读取，内存队列没有，再从
        request = self.mqs.pop()
        if request:
            self.stats.inc_value('scheduler/dequeued/memory', spider=self.spider)
        else:
            request = self._dqpop()
            if request:
                self.stats.inc_value('scheduler/dequeued/disk', spider=self.spider)
        if request:
            self.stats.inc_value('scheduler/dequeued', spider=self.spider)
        return request

    #优先级队列入列，确定使用哪一个队列的标志是request中的priority属性。
    def _dqpush(self, request):
        #self.dqs为空，也就是磁盘队列没有实例化，直接返回。
        if self.dqs is None:
            return
        try:
            #把request请求放入到对应的优先级队列中。
            #request_to_dict方法可以把request实例，转换成一个字典：
            #d = {'url': request.url.decode('ascii'), # urls should be safe (safe_string_url)
            #'callback': cb,
            #'errback': eb,
            #'method': request.method,
            #'headers': dict(request.headers),
            #'body': request.body,
            #'cookies': request.cookies,
            #'meta': request.meta,
            #'_encoding': request._encoding,
            #'priority': request.priority,
            #'dont_filter': request.dont_filter,}
            reqd = request_to_dict(request, self.spider)
            #字典根据优先级入列。
            self.dqs.push(reqd, -request.priority)
        except ValueError as e: # non serializable request
            if self.logunser:
                logger.error("Unable to serialize request: %(request)s - reason: %(reason)s",
                             {'request': request, 'reason': e},
                             exc_info=True, extra={'spider': self.spider})
            return
        else:
            #如果没有错误，则返回真。
            return True

    def _mqpush(self, request):
        #内存队列，就直接入列，不转换成字典。
        self.mqs.push(request, -request.priority)

    def _dqpop(self):
        if self.dqs:
            d = self.dqs.pop()
            if d:
                return request_from_dict(d, self.spider)

    def _newmq(self, priority):
        return self.mqclass()

    def _newdq(self, priority):
        return self.dqclass(join(self.dqdir, 'p%s' % priority))

    #当self.dqdir有值的时候，才会调用该方法
    def _dq(self):
        #self.dqdir = setting['JOBDIR'] + '/request.queue'
        #activef = setting['JOBDIR'] + '/request.queue' +'/active.json'
        activef = join(self.dqdir, 'active.json')
        
        #如果这个文件存在，则打开，并将文件中的内容，读取进入prios（json结构）
        if exists(activef):
            with open(activef) as f:
                prios = json.load(f)

        #如果不存在这个文件，则prios为空集合。
        else:
            prios = ()
        
        q = PriorityQueue(self._newdq, startprios=prios)
        if q:
            logger.info("Resuming crawl (%(queuesize)d requests scheduled)",
                        {'queuesize': len(q)}, extra={'spider': self.spider})
        return q

    def _dqdir(self, jobdir):
        if jobdir:
            dqdir = join(jobdir, 'requests.queue')
            if not exists(dqdir):
                os.makedirs(dqdir)
            return dqdir
