# http://code.activestate.com/recipes/577551-trace-decorator-for-debugging/

######################################################################
#  Copyright (c) by Kevin L. Sitze on 2011-01-23.
#  This code may be used pursuant to the MIT License.
######################################################################

"""This package provides facilities to attach trace_decorator to classes or
modules (possibly recursively).  A tracing decorator is provided for
tracing function and method calls in your applications.

from trace_decorator import *

@trace
def function(...):
    '''Output goes to <TT>logging.getLogger(__module__)</TT>,
    where <TT>__module__</TT> is the name of the module in which
    the function is defined.  If the current module is '__main__'
    then the root logger will be used.
    '''
    pass

@trace(logger)
def function(...):
    '''Output goes to the specified logger instance.
    '''
    pass

@trace("Logger")
def function(...):
    '''Output goes to the named logger instance.
    '''

class ClassName(object):
    '''Output goes to the ClassName logger.  If ClassName is
    not in the '__main__' module then the name of its module
    will be prefixed to the classname (separated by a dot).
    All methods on the class will be traced.
    '''
    __logger__ = loggerOrLoggerName # optional
    __metaclass__ = trace_decorator.TraceMetaClass
    def method(...):
        pass

class PostDecorate(object):
    def method(...):
        pass
# attach a decorator to an existing class.
attach(trace(logger), PostDecorate)

You can also attach a decorator to an existing module.
"""

import inspect
import logging
import sys
import threading
import types

from functools import update_wrapper
from itertools import chain

FunctionTypes = tuple(set((
    types.BuiltinFunctionType,
    types.FunctionType
)))

class _C(object):
    @classmethod
    def classMethod(klass): pass
    classMethodType = type(classMethod)

    @staticmethod
    def staticMethod(): pass
    staticMethodType = type(staticMethod)

    @property
    def propertyMethod(self): pass

    def normalMethod(self): pass

ClassMethodType = _C.classMethodType
StaticMethodType = _C.staticMethodType
PropertyType = type(_C.propertyMethod)
# use this instead of types.UnboundMethodType, which got cut from python3
NormalMethodType = type(_C.normalMethod)

MethodTypes = tuple(set((
    types.BuiltinMethodType,
    types.MethodType,
    NormalMethodType
)))

CallableTypes = tuple(set((
    types.BuiltinFunctionType,
    types.FunctionType,
    types.BuiltinMethodType,
    types.MethodType,
    NormalMethodType,
    ClassMethodType
)))

__all__ = (
    'TraceMetaClass',
    'attach',
    'getFormatter',
    'setFormatter',
    'getLoggerFactory',
    'setLoggerFactory',
    'trace'
)

######################################################################
#  Utility functions
######################################################################

MAX_SIZE = 320
def chop(value):
    s = repr(value)
    if len(s) > MAX_SIZE:
        return s[:MAX_SIZE] + '...' + s[-1]
    else:
        return s

def loggable(obj):
    """Return "True" if the obj implements the minimum Logger API
    required by the 'trace' decorator.
    """
    if isinstance(obj, logging.getLoggerClass()):
        return True
    else:
        return ( inspect.isclass(obj) and
                 inspect.ismethod(getattr(obj, 'isEnabledFor', None)) and
                 inspect.ismethod(getattr(obj, 'setLevel', None)) )

######################################################################
#  LoggerFactory Property
######################################################################

# lower priority than DEBUG, which is normally 10
TRACE = 5 

def addTraceLevel(factory):
    """Add a TRACE level with even lower priority than DEBUG
    to the given logger factory object
    """
    factory.TRACE = TRACE
    factory.addLevelName(TRACE, "TRACE")

# function to be used as logger.trace()
def loggerTrace(self, message, *args):
    if self.isEnabledFor(TRACE):
            self._log(TRACE, message, args)

# make factory generate logger with trace() method
def addTraceMethod(factory):
    # rename original factory.getLogger()
    factory.getLoggerNoTrace = factory.getLogger
    # create new factory.getLogger() that creates logger with original getLogger,
    # but then adds logger.trace() method
    def getLoggerTrace(*args):
        logger = factory.getLoggerNoTrace(*args)
        # MethodType() makes 'self' work as expected for instance method 
        logger.trace = types.MethodType(loggerTrace, logger)
        return logger
    factory.getLogger = getLoggerTrace

_logger_factory = logging
addTraceLevel(_logger_factory)
addTraceMethod(_logger_factory)

def getLoggerFactory():
    """Retrieve the current factory object for creating loggers.
    """
    global _logger_factory
    return _logger_factory

def setLoggerFactory(factory):
    """Set a factory object for creating loggers.  This object must
    publish a method or class named 'getLogger' that takes a string
    parameter naming the logger instance to retrieve.  Logger objects
    returned by this factory must, at a minimum, expose the method
    'isEnabledFor' and setLevel.

    The logger factory is modified by adding TRACE logging level
    and making it generate loggers with a corresponding trace() 
    method for logging at TRACE level.
    """
    global _logger_factory
    _logger_factory = factory

    # add TRACE level 
    addTraceLevel(_logger_factory)
    # add logger.trace() method for logging at TRACE level
    addTraceMethod(_logger_factory)



######################################################################
#  class PrependLoggerFactory
######################################################################

class PrependLoggerFactory(object):
    """This is a convenience class for creating new loggers for the
    "trace" decorator.  All loggers created via this class will have a
    user specified prefix prepended to the name of the logger to
    instantiate.
    """
    def __init__(self, prefix = 'trace'):
        """Construct a new "PrependLoggerFactory" instance that
        prepends the value \var{prefix} to the name of each
        logger to be created by this class.
        """
        self.__prefix = prefix.strip('.')

    @property
    def prefix(self):
        """The value to prefix to each logger created by this factory.
        """
        return self.__prefix
    @prefix.setter
    def prefix(self, value):
        self.__prefix = value.strip('.')

    def getLogger(self, name):
        return logging.getLogger('.'.join((self.__prefix, name)))

######################################################################
#  Formatter functions
######################################################################

def _formatter_self(name, value):
    """Format the "self" variable and value on instance methods.
    """
    __mname = value.__module__
    if __mname != '__main__':
        return '%s = <%s.%s object at 0x%x>' % (name, __mname, value.__class__.__name__, id(value))
    else:
        return '%s = <%s object at 0x%x>' % (name, value.__class__.__name__, id(value))

def _formatter_class(name, value):
    """Format the "klass" variable and value on class methods.
    """
    __mname = value.__module__
    if __mname != '__main__':
        return "%s = <type '%s.%s'>" % (name, __mname, value.__class__.__name__)
    else:
        return "%s = <type '%s'>" % (name, value.__class__.__name__)

def _formatter_named(name, value):
    """Format a named parameter and its value.
    """
    return '%s = %s' % (name, chop(value))

def _formatter_defaults(name, value):
    return '[%s = %s]' % (name, chop(value))

af_self = _formatter_self
af_class = _formatter_class
af_named = _formatter_named
af_default = _formatter_defaults
af_unnamed = chop
af_keyword = _formatter_named

def getFormatter(name):
    """Return the named formatter function.  See the function
    "setFormatter" for details.
    """
    if name in ( 'self', 'instance', 'this' ):
        return af_self
    elif name == 'class':
        return af_class
    elif name in ( 'named', 'param', 'parameter' ):
        return af_named
    elif name in ( 'default', 'optional' ):
        return af_default
    elif name in ( 'anonymous', 'arbitrary', 'unnamed' ):
        return af_anonymous
    elif name in ( 'keyword', 'pair', 'pairs' ):
        return af_keyword
    else:
        raise ValueError('unknown trace formatter %r' % name)

def setFormatter(name, func):
    """Replace the formatter function used by the trace decorator to
    handle formatting a specific kind of argument.  There are several
    kinds of arguments that trace discriminates between:

    * instance argument - the object bound to an instance method.
    * class argument - the class object bound to a class method.
    * positional arguments (named) - values bound to distinct names.
    * positional arguments (default) - named positional arguments with
      default values specified in the function declaration.
    * positional arguments (anonymous) - an arbitrary number of values
      that are all bound to the '*' variable.
    * keyword arguments - zero or more name-value pairs that are
      placed in a dictionary and bound to the double-star variable.

    \var{name} - specifies the name of the formatter to be modified.

        * instance argument - "self", "instance" or "this"
        * class argument - "class"
        * named argument - "named", "param" or "parameter"
        * default argument - "default", "optional"
        * anonymous argument - "anonymous", "arbitrary" or "unnamed"
        * keyword argument - "keyword", "pair" or "pairs"

    \var{func} - a function to format an argument.
    * For all but anonymous formatters this function must accept two
      arguments: the variable name and the value to which it is bound.
    * The anonymous formatter function is passed only one argument
      corresponding to an anonymous value.
    * if \var{func} is "None" then the default formatter will be used.
    """
    if name in ( 'self', 'instance', 'this' ):
        global af_self
        af_self = _formatter_self if func is None else func
    elif name == 'class':
        global af_class
        af_class = _formatter_class if func is None else func
    elif name in ( 'named', 'param', 'parameter' ):
        global af_named
        af_named = _formatter_named if func is None else func
    elif name in ( 'default', 'optional' ):
        global af_default
        af_default = _formatter_defaults if func is None else func
    elif name in ( 'anonymous', 'arbitrary', 'unnamed' ):
        global af_anonymous
        af_anonymous = chop if func is None else func
    elif name in ( 'keyword', 'pair', 'pairs' ):
        global af_keyword
        af_keyword = _formatter_named if func is None else func
    else:
        raise ValueError('unknown trace formatter %r' % name)

######################################################################
#  Decorator: trace
######################################################################

__builtins = (
    '__import__(name,globals={},locals={},fromlist=[],level=-1)',
    'abs(number)',
    'all(iterable)',
    'any(iterable)',
    'apply(object,args=[],kwargs={})',
    'bin(number)',
    'callable(object)',
    'chr(i)',
    'cmp(x,y)',
    'coerce(x,y)',
    'compile(source,filename,mode,flags=0,dont_inherit=0)',
    'delattr(object,name)',
    'dir()',
    'divmod(x,y)',
    'eval(source,globals={},locals={})',
    'execfile(filename,globals={},locals={})',
    'filter(function,sequence)',
    'format(value,format_spec="")',
    'getattr(object,name)',
    'globals()',
    'hasattr(object,name)',
    'hash(object)',
    'hex(number)',
    'id(object)',
    'input(prompt=None)',
    'intern(string)',
    'isinstance(object,klass)',
    'issubclass(C,B)',
    'iter(collection)',
    'len(object)',
    'locals()',
    'map(function,sequence)',
    'max(iterable,key=None)',
    'min(iterable,key=None)',
    'next(iterator)',
    'oct(number)',
    'open(name,mode=0666,buffering=True)',
    'ord(c)',
    'pow(x,y,z=None)',
    'range()',
    'raw_input(prompt=None)',
    'reduce(function,sequence)',
    'reload(module)',
    'repr(object)',
    'round(number,ndigits=0)',
    'setattr(object,name,value)',
    'sorted(iterable,cmp=None,key=None,reverse=False)',
    'sum(sequence,start=0)',
    'unichr(i)',
    'vars()',
    'zip(sequence)'
)

__builtin_defaults = {
    '""': "",
    '-1': -1,
    '0' : 0,
    '0666': 0o666,
    'False': False,
    'None': None,
    'True': True,
    '[]': list(),
    '{}': dict()
}

__builtin_functions = None
def __lookup_builtin(name):
    """Lookup the parameter name and default parameter values for
    builtin functions.
    """
    global __builtin_functions
    if __builtin_functions is None:
        builtins = dict()
        for proto in __builtins:
            pos = proto.find('(')
            name, params, defaults = proto[:pos], list(), dict()
            for param in proto[pos+1:-1].split(','):
                pos = param.find('=')
                if not pos < 0:
                    param, value = param[:pos], param[pos+1:]
                    try:
                        defaults[param] = __builtin_defaults[value]
                    except KeyError:
                        raise ValueError( 'builtin function %s: parameter %s: unknown default %r' % ( name, param, value ) )
                params.append(param)
            builtins[name] = ( params, defaults )
        __builtin_functions = builtins

    try:
        params, defaults = __builtin_functions[name]
    except KeyError:
        params, defaults = tuple(), dict()
        __builtin_functions[name] = ( params, defaults )
        print >>sys.stderr, "Warning: builtin function %r is missing prototype" % name
    return ( len(params), params, defaults )

_ = threading.local()
_.value = False

def trace(_name):
    """Function decorator that logs function entry and exit details.

    \var{_name} a string, an instance of logging.Logger or a function.

    Construct a function or method proxy to generate call traces.
    """
    def decorator(_func, func_type=None, class_obj=None):
        """This is the actual decorator function that wraps the
        \var{_func} function for detailed logging.
        """

        def positional(name, value):
            """Format one named positional argument.
            """
            if name is __self:
                return af_self(name, value)
            elif name is __klass:
                return af_class(name, value)
            else:
                return af_named(name, value)

        def wrapper(*__argv, **__kwds):
            if not logger.isEnabledFor(TRACE) or _.value:
                return _func(*__argv, **__kwds)

            try:
                _.value = True
                params = dict(co_defaults)
                params.update(__kwds)
                params.update(zip(co_varnames, __argv))

                position = [ positional(n, params.pop(n)) for n in co_varnames[:len(__argv)] ]
                defaults = [ af_default(n, params.pop(n)) for n in co_varnames[len(__argv):] ]
                nameless = ( af_unnamed(v) for v in __argv[co_argcount:] )
                keywords = ( af_keyword(n, params[n]) for n in sorted(params.keys()) )

                params = ', '.join(filter(None, chain(position, defaults, nameless, keywords)))
                # params = params.replace(', [', '[, ').replace('][, ', ', ')

                enter = [ pre_enter ]
                if params:
                    enter.append(' ')
                    enter.append(params)
                    enter.append(' ')
                enter.append(')')

                leave = [ pre_leave ]

                try:
                    logger.trace(''.join(enter))
                    try:
                        try:
                            _.value = False
                            result = _func(*__argv, **__kwds)
                        finally:
                            _.value = True
                    except:
                        type, value, traceback = sys.exc_info()
                        leave.append(' => exception thrown\n\traise ')
                        __mname = type.__module__
                        if __mname != '__main__':
                            leave.append(__mname)
                            leave.append('.')
                        leave.append(type.__name__)
                        if value.args:
                            leave.append('(')
                            leave.append(', '.join(chop(v) for v in value.args))
                            leave.append(')')
                        else:
                            leave.append('()')
                        raise
                    else:
                        if result is not None:
                            leave.append(' => ')
                            leave.append(chop(result))
                finally:
                    logger.trace(''.join(leave))
            finally:
                _.value = False

            return result

        ####
        #  decorator
        ####

        if not func_type:
            func_type = type(_func)

        __self  = False
        __klass = False
        if func_type == ClassMethodType:
            __klass = True
            __cname = class_obj.__name__
            _func = _func.__func__
        elif func_type == StaticMethodType:
            __cname = class_obj.__name__
        elif func_type in FunctionTypes:
            if class_obj:
                # python3 instance method
                __self = True
                __cname = class_obj.__name__
            else:
                # normal function
                __cname = None
        elif func_type in MethodTypes:
            # python2 instance method
            __self = True
            __cname = class_obj.__name__
        else:
            # other callables are not supported yet.
            return _func
        __module = _func.__module__
        __fname  = _func.__name__

        # Do not wrap initialization and conversion methods.
        if __fname in ('__init__', '__new__', '__repr__', '__str__'):
            return _func

        # Generate the Fully Qualified Function Name.

        __fqfn = list()
        if __module != '__main__':
            __fqfn.append(__module)
            __fqfn.append('.')
        if __cname is not None:
            __fqfn.append(__cname)
            __fqfn.append('.')
        __fqcn = ''.join(__fqfn)
        __fqfn.append(__fname)
        __fqfn = ''.join(__fqfn)

        if type(_name) in CallableTypes:
            logger = getLoggerFactory().getLogger(__fqfn)
        elif loggable(_name):
            logger = _name
        elif isinstance(_name, (bytes, str)):
            logger = getLoggerFactory().getLogger(_name)
        else:
            raise ValueError('invalid object %r: must be a function, a method, a string or an object that implements the Logger API' % _name)

        pre_enter = [ '>>> ' ]
        pre_enter.append(__fqfn)
        pre_enter.append('(')
        pre_enter = ''.join(pre_enter)

        pre_leave = [ '<<< ' ]
        pre_leave.append(__fqfn)
        pre_leave = ''.join(pre_leave)

        ####
        #  Here we are really mucking around in function internals.
        #  __code__ is the low level 'code' instance that describes
        #  the function arguments, variable and other stuff.
        #
        #  func.__code__.co_argcount - number of function arguments.
        #  func.__code__.co_varnames - function variables names, the
        #      first co_argcount values are the argument names.
        #  func.__defaults__ - contains default arguments

        try:
            code = _func.__code__
        except AttributeError:
            co_argcount , \
            co_varnames , \
            co_defaults = __lookup_builtin(_func.__name__)
        else:
            co_argcount = code.co_argcount
            co_varnames = code.co_varnames[:co_argcount]
            if _func.__defaults__:
                co_defaults = dict(zip(co_varnames[-len(_func.__defaults__):], _func.__defaults__))
            else:
                co_defaults = dict()
            if __klass:
                __klass = co_varnames[0]
            if __self:
                __self  = co_varnames[0]
        return update_wrapper(wrapper, _func)

    ####
    #  trace
    ####

    logging.basicConfig(level = TRACE)
    if type(_name) in CallableTypes:
        return decorator(_name)
    else:
        return decorator

######################################################################
#  attach: apply decorator to a class or module
######################################################################

def attachToProperty(decorator, klass, k, prop_attr, prop_decorator):
    if prop_attr is not None:
        setattr(klass, k, prop_attr)
        # pass in the class to decorator, but func_type=None means let 
        # decorator determine method type
        value = decorator(getattr(klass, k), None, klass)
    else:
        value = None
    # Passing "None" to the property decorator causes the new property
    # to assume the original value of the associated attribute.
    return prop_decorator(value)

def attachToClass(decorator, klass, recursive = True):
    for k, v in klass.__dict__.items():
        t = type(v)
        if t is types.FunctionType:
            setattr(klass, k, decorator(getattr(klass, k), t, klass))
        elif t is ClassMethodType:
            setattr(klass, k, decorator(getattr(klass, k), t, klass))
        elif t is StaticMethodType:
            setattr(klass, k, staticmethod(decorator(getattr(klass, k), t, klass)))
        elif t is PropertyType:
            value = getattr(klass, k)
            value = attachToProperty(decorator, klass, k, value.fget, value.getter)
            value = attachToProperty(decorator, klass, k, value.fset, value.setter)
            value = attachToProperty(decorator, klass, k, value.fdel, value.deleter)
            setattr(klass, k, value)
        elif recursive and inspect.isclass(v):
            attachToClass(decorator, v, recursive)

def attach(decorator, obj, recursive = True):
    """attach(decorator, class_or_module[, recursive = True])

    Utility to attach a \val{decorator} to the \val{obj} instance.

    If \val{obj} is a module, the decorator will be attached to every
    function and class in the module.

    If \val{obj} is a class, the decorator will be attached to every
    method and subclass of the class.

    if \val{recursive} is "True" then subclasses will be decorated.
    """
    if inspect.ismodule(obj):
        for name, fn in inspect.getmembers(obj, inspect.isfunction):
            setattr(obj, name, decorator(fn))
        for name, klass in inspect.getmembers(obj, inspect.isclass):
            attachToClass(decorator, klass, recursive)
    elif inspect.isclass(obj):
        attachToClass(decorator, obj, recursive)

######################################################################
#  class TraceMetaClass
######################################################################

class TraceMetaClass(type):
    """Metaclass to automatically attach the 'trace' decorator to all
    methods, static method and class methods of the class.
    """
    def __new__(meta, className, bases, classDict):
        klass = super(TraceMetaClass, meta).__new__(meta, className, bases, classDict)
        if classDict.has_key('__logger__'):
            hook = trace(classDict['__logger__'])
        else:
            hook = trace
        attachToClass(hook, klass, False)
        return klass

if __name__ == '__main__':
    logging.basicConfig(level = TRACE)
    logger = logging.root

    class Test(object):
        __logger__ = logger
        __metaclass__ = TraceMetaClass

        @classmethod
        def classMethod(klass):
            pass

        @staticmethod
        def staticMethod():
            pass

        __test = None
        @property
        def test(self):
            return self.__test
        @test.setter
        def test(self, value):
            self.__test = value

        def method(self):
            pass

    Test.classMethod()
    Test.staticMethod()
    test = Test()
    test.test = 1
    assert 1 == test.test
    test.method()

    class Test(object):
        @classmethod
        def classMethod(klass):
            pass

        @staticmethod
        def staticMethod():
            pass

        __test = None
        @property
        def test(self):
            return self.__test
        @test.setter
        def test(self, value):
            self.__test = value

        def method(self):
            pass

        def __str__(self):
            return 'Test(' + str(self.test) + ')'

    attach(trace(logger), Test)
    Test.classMethod()
    Test.staticMethod()
    test = Test()
    test.test = 1
    assert 1 == test.test
    test.method()
    print(str(test))

    @trace(logger)
    def test(x, y, z = True):
        a = x + y
        b = x * y
        if z: return a
        else: return b

    test(5, 5)
    test(5, 5, False)

    setLoggerFactory(PrependLoggerFactory())

    @trace('main')
    def test(x, *argv, **kwds):
        """Simple test
        """
        return x + sum(argv)

    test(5)
    test(5, 5)
    test(5, 5, False)
    test(5, 5, False, name = 10)

    test( *xrange(50) )

    assert test.__doc__ == 'Simple test\n        '
    assert test.__name__ == 'test'

    myzip = trace('main')(zip)
    for i, j in myzip(xrange(5), xrange(5, 10)):
        print(i, j)
