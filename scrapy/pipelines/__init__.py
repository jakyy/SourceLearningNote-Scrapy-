"""
Item pipeline

See documentation in docs/item-pipeline.rst
"""

from scrapy.middleware import MiddlewareManager
from scrapy.utils.conf import build_component_list

class ItemPipelineManager(MiddlewareManager):
#管道管理器，也是中间件管理器的派生类。

    component_name = 'item pipeline'

    @classmethod
    def _get_mwlist_from_settings(cls, settings):
        item_pipelines = settings['ITEM_PIPELINES']
        #获取ITEM_PIPELINES中定义的字典，列表。
        if isinstance(item_pipelines, (tuple, list, set, frozenset)):
            from scrapy.exceptions import ScrapyDeprecationWarning
            import warnings
            warnings.warn('ITEM_PIPELINES defined as a list or a set is deprecated, switch to a dict',
                category=ScrapyDeprecationWarning, stacklevel=1)
            # convert old ITEM_PIPELINE list to a dict with order 500
            item_pipelines = dict(zip(item_pipelines, range(500, 500+len(item_pipelines))))
        #如果不是字典，则改造成为字典。
        #根据先后顺序，为pipeline赋值为500之后的优先级。

        return build_component_list(settings['ITEM_PIPELINES_BASE'], item_pipelines)
        #这个函数进行了一些列的操作。
        #包括检查用户定义的pipeline，是否有重复，有不推荐使用的模块。
        #如果itepipeline没有改造成为字典，那么这个函数会直接返回用户定义的列表。
        #字典就会和系统默认的BASE合并。
        #优先级为None会被忽略。

    def _add_middleware(self, pipe):
        super(ItemPipelineManager, self)._add_middleware(pipe)
        if hasattr(pipe, 'process_item'):
            self.methods['process_item'].append(pipe.process_item)
    #基类的方法添加了pipe.open_spider/close_spider到self.methods

    #基类没有这个方法。
    def process_item(self, item, spider):
        return self._process_chain('process_item', item, spider)
    #生成一个defered对象，将self.process_item加入到回调链。
    #并调用callback(spider)
