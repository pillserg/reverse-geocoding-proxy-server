import time

def sentinel(f):
    def inner_call(*args, **kwargs):
        print '\n!--- Entering {} -------'.format(f.__name__)
        print '\t--- args: {}; kwargs: {}'.format(args, kwargs)
        start_time = time.time()
        res = f(*args, **kwargs)
        end_time = time.time() - start_time
        print '\t--- Result: {}'.format(res)
        print '\t--- Exiting {} ---- time taken: {}---\n'.format(f.__name__,
                                                                 end_time)
        return res
    return inner_call
