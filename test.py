#!/usr/bin/python

import test_module
import trace_decorator

#import pdb ; pdb.set_trace()

# testing with attach()
trace_decorator.attach(trace_decorator.trace("This is a test"), test_module)

testme = test_module.SomeClass()
testme.static_method_am_i(1)
testme.class_method_am_i(2)
testme.instance_method_am_i(3)
p = testme.property_am_i
testme.property_am_i = p * 2

test_module.some_func(42)
