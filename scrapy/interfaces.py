from zope.interface import Interface
#这个类应当就是给出了一个接口。
#为什么会特意使用zope.interface作为接口，它有什么优点？
class ISpiderLoader(Interface):

    def from_settings(settings):
        """Return an instance of the class for the given settings"""

    def load(spider_name):
        """Return the Spider class for the given spider name. If the spider
        name is not found, it must raise a KeyError."""

    def list():
        """Return a list with the names of all spiders available in the
        project"""

    def find_by_request(request):
        """Return the list of spiders names that can handle the given request"""


# ISpiderManager is deprecated, don't use it!
# An alias is kept for backwards compatibility.
ISpiderManager = ISpiderLoader
