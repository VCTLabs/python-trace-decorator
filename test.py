#!/usr/bin/python

import test_module
import trace_decorator

# testing with attach()
trace_decorator.attach(trace_decorator.trace("This is a test"), test_module)

testme = test_module.SomeClass()
testme.static_method_am_i(1)
testme.instance_method_am_i(2)

test_module.some_func(42)

# testing with @trace
