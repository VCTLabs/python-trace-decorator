
class SomeClass(object):

    @staticmethod
    def static_method_am_i(level):
        return { "name": "frotz", "level": level }

    def instance_method_am_i(self, level):
        return ("rezrov", level)

def some_func(arg):
    return "blorb %d times" % arg
