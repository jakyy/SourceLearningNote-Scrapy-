#不是特别明白这个函数的作用是什么。
def obsolete_setter(setter, attrname):
    def newsetter(self, value):
        c = self.__class__.__name__
        msg = "%s.%s is not modifiable, use %s.replace() instead" % (c, attrname, c)
        raise AttributeError(msg)
        #这个setter没有做任何事情，只是提供了错误信息。
        #所以在对该属性赋值时，是不可用的。
    return newsetter



#其他地方调用的时候，setter中传入一个函数
#attrname传入字符串。

#class c:
#   def f():
#       pass

#c.f.__class__ -> <type 'instancemethod'>
#c.f.__class__.__name__-> instancemethod

#__class__指明当前对象属于哪一个类。
