
class SomeClass(object):
    def __init__(self, prop="cleesh"):
        self._prop = prop

    @staticmethod
    def static_method_am_i(level):
        return { "name": "frotz", "level": level }

    @classmethod
    def class_method_am_i(cls, level):
        return ["nitfol", level]

    @property
    def property_am_i(self):
        print ("Go get that prop")
        return self._prop

    @property_am_i.setter
    def property_am_i(self, value):
        print ("Go set that prop")
        self._prop = value

    def instance_method_am_i(self, level):
        return ("rezrov", level)

def some_func(arg):
    return "blorb %d times" % arg
