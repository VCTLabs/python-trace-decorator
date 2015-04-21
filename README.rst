python-trace-decorator
----------------------

Python function-tracing module based on the recipe by Kevin L. Sitze

http://code.activestate.com/recipes/577551-trace-decorator-for-debugging/

but modified to work with python 3 (should work with 3.3 or greater). 
Still compatible with python 2.7, but not with older python versions.

Why do I find this module more convenient than the standard 'trace' module?

Because I like the interface better: 

* using @trace decorator or attach() to mark ahead of time what stuff 
  gets traced, rather than having to trace.Trace.run() code to be traced 
* nicely formatted trace output going to Logger, including own Logger
  subclass if desired, rather than going directly to stdout
* tracing can be turned on and off via logger configuration file
