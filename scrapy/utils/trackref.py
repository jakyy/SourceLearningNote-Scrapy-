"""This module provides some functions and classes to record and report
references to live object instances.

If you want live objects for a particular class to be tracked, you only have to
subclass from object_ref (instead of object).

About performance: This library has a minimal performance impact when enabled,
and no performance penalty at all when disabled (as object_ref becomes just an
alias to object in that case).
"""
#这个模块提供一些函数和类来记录/报道，活动对象实例的引用。
#如果你希望特定类的活动对象被跟踪，你需要从object_ref继承，而不是object。
#这个苦在启用时只有极小的影响，当关闭时，就像object的别名一样。

from __future__ import print_function
import weakref, os, six
from collections import defaultdict
from time import time
from operator import itemgetter

NoneType = type(None)

live_refs = defaultdict(weakref.WeakKeyDictionary)
#通过全局变量来记录产生的对象，以及对应的类。还有开始的时间。
#其他地方可以应用这个字典。下面定义了一些，基本的访问该字典的方法。

class object_ref(object):
    """Inherit from this class (instead of object) to a keep a record of live
    instances"""

    __slots__ = ()

    def __new__(cls, *args, **kwargs):
        obj = object.__new__(cls)
        #这是创建一个类对象的根本方式么？

        live_refs[cls][obj] = time()
        #记录了这个。
        return obj

def format_live_refs(ignore=NoneType):
    s = "Live References" + os.linesep + os.linesep
    now = time()
    for cls, wdict in six.iteritems(live_refs):
        if not wdict:
            continue
        if issubclass(cls, ignore):
            continue
        oldest = min(wdict.itervalues())
        s += "%-30s %6d   oldest: %ds ago" % (cls.__name__, len(wdict), \
            now-oldest) + os.linesep
    return s
#活动的引用，打印出，每个类，活动的应用有几个，最早的活动了多久。


def print_live_refs(*a, **kw):
    print(format_live_refs(*a, **kw))

def get_oldest(class_name):
    for cls, wdict in six.iteritems(live_refs):
        if cls.__name__ == class_name:
            if wdict:
                return min(six.iteritems(wdict), key=itemgetter(1))[0]

def iter_all(class_name):
    for cls, wdict in six.iteritems(live_refs):
        if cls.__name__ == class_name:
            return six.iterkeys(wdict)
