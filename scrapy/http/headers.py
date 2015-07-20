import six
from w3lib.http import headers_dict_to_raw
from scrapy.utils.datatypes import CaselessDict


class Headers(CaselessDict):
    """Case insensitive http headers dictionary"""
    #Headers是CaselessDict类的子类
    #CaselessDict是一个大小写不敏感的字典。
    #其所有操作方法均吧键改为小写。
    #headers在此基础之上，将所有的元素都改为了列表元素。

    def __init__(self, seq=None, encoding='utf-8'):
        self.encoding = encoding
        #获取到一个编码的字符串utf-8

        super(Headers, self).__init__(seq)
        #调用父类初始化函数
        
    def normkey(self, key):
    #覆盖父类的方法，父类该方法是return key.lower()
        """Normalize key to bytes"""
        return self._tobytes(key.title())
        #_tobytes()进行了什么样的错做？
        #为什么key有title方法，title方法返回了什么。

    def normvalue(self, value):
        """Normalize values to bytes"""
        #byte类型和str类型，在python3中有明确定
        #python2中好像没有明确区分。

        if value is None:
            value = []
        #如果value为空，就返回空列表。

        elif isinstance(value, (six.text_type, bytes)):
            value = [value]
        #如果value是six.text_type或者bytes
        #将value放入列表。

        elif not hasattr(value, '__iter__'):
            value = [value]
        #如果不是可迭代的类型，也放入list
        
        #如果value是可迭代的类型，比如列表，则直接到return

        return [self._tobytes(x) for x in value]
        #将value中的每一个元素，都执行_tobytes()

    def _tobytes(self, x):
        if isinstance(x, bytes):
            return x
        #是bytes对像就直接返回。

        elif isinstance(x, six.text_type):
            return x.encode(self.encoding)
        #是text_type就对x encode()
        #备注：encode unicode to str
        #decode str to unicode

        elif isinstance(x, int):
            return six.text_type(x).encode(self.encoding)
        #如果是数字，则先转换陈text_type，再encode。

        else:
            raise TypeError('Unsupported value type: {}'.format(type(x)))

    def __getitem__(self, key):
        try:
            return super(Headers, self).__getitem__(key)[-1]
            #dict.__getitem__(self, self.normkey(key))
            #返回get到的最后一个。
        except IndexError:
            return None

    def get(self, key, def_val=None):
        try:
            return super(Headers, self).get(key, def_val)[-1]
            #返回最后一个。
        except IndexError:
            return None

    def getlist(self, key, def_val=None):
        try:
            return super(Headers, self).__getitem__(key)
            #返回整个列表。
        except KeyError:
            if def_val is not None:
                return self.normvalue(def_val)
            return []

    def setlist(self, key, list_):
        self[key] = list_
        #设置{key:list_}

    def setlistdefault(self, key, default_list=()):
        return self.setdefault(key, default_list)
    
    def appendlist(self, key, value):
        lst = self.getlist(key)
        lst.extend(self.normvalue(value))
        self[key] = lst

    def items(self):
        return list(self.iteritems())

    def iteritems(self):
        return ((k, self.getlist(k)) for k in self.keys())

    def values(self):
        return [self[k] for k in self.keys()]

    def to_string(self):
        return headers_dict_to_raw(self)

    def __copy__(self):
        return self.__class__(self)
    copy = __copy__


