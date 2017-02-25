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
        
        async def test2(logger, ctx, *args, **kwargs):
            print(logger, ctx)
            print("test2")

print("instantiating")
sl = SimpleLogger("baz", "blee")
print("instance", sl)

@bot.event
async def on_ready():
    print('Logged in as', bot.user.name)        
        
bot.run(token)