#logbot_example.py

import sys
if len(sys.argv) == 1:
    print("Usage: ipython {} token".format(sys.argv[0]))
    sys.exit()
    
token = sys.argv[1]

from logbot import Logger, Logbot
        
bot = Logbot(command_prefix='z>')

@bot.logger
class SimpleLogger(Logger):

    def __init__(self, foo, bar):
        super().__init__()
        print("__init__", foo, bar)

    def before_update(self):
        print("before_update")

    def before_server_update(self, server):
        print("before_server_update")

    def before_channel_update(self, channel):
        print("before_channel_update")

    def process_message(self, msg):
        print("process_message")
        
    def after_channel_update(self, channel):
        print("after_channel_update")
        
    def after_server_update(self, server):
        print("after_server_update")
        
    def after_update(self):
        print("after_update")
        
    def register_commands(self):
        
        @self.client.command(pass_context=True, no_pm=True)
        async def test(ctx, *args, **kwargs):
            print(self, ctx)
            print("test", args, kwargs)
        
        
            
    def command(self, *args, **kwargs):
        def decorator(func):
            self.client.command(*args, name=func.__name__, **kwargs)(async_partial(func, self, *args, **kwargs))
            
        return decorator
            
def async_partial(f, *oargs, **okwargs):
    async def inner(*args, **kwargs):
        newkwargs = okwargs.copy()
        newkwargs.update(kwargs)
        return await f(*oargs, *args, **kwargs)
        
    inner.func = f
    inner.args = oargs
    inner.keywords = okwargs
    return inner

print("instantiating")
sl = SimpleLogger("baz", "blee")
print("instance", sl)

@sl.command(pass_context=True, no_pm=True)
async def test2(logger, ctx, *args, **kwargs):
    print(logger, ctx)
    print("test2", args, kwargs)

@bot.event
async def on_ready():
    print('Logged in as', bot.user.name)        
        
bot.run(token)