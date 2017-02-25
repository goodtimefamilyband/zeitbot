#logbot.py

import sys
if len(sys.argv) == 1:
    print("Usage: ipython {} token".format(sys.argv[0]))
    sys.exit()
    
token = sys.argv[1]

import discord
from discord.ext import commands
import asyncio
import re
from datetime import datetime, tzinfo
import time
import pytz
from collections import defaultdict
import websockets
import aiohttp

class Logger:

    def before_update(self):
        pass

    def before_server_update(self, server):
        pass

    def before_channel_update(self, channel):
        pass

    def process_message(self, msg):
        pass
        
    def after_channel_update(self, channel):
        pass

    def after_server_update(self, server):
        pass
    
    def after_update(self):
        pass
        
    def set_client(self, client):
        self.client = client
        

class Logbot(commands.Bot):
    
    def __init__(self, *args, db=None, wait_interval=300, message_interval=604800, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.wait_ival = wait_interval
        self.msg_ival = message_interval
        
        self.ws_lock = asyncio.Lock()
        self.ws_event = asyncio.Event()
        self.ws_status = discord.Status.dnd
        self.ws_msg = "Starting up..."
        
        self.loop.create_task(self.ws_coro())
        
        self.loggers = []
        self.loop.create_task(self.bg_loop())
    
    # Enforces websocket rate limiting
    async def ws_coro(self):
        await self.wait_until_ready()
        while await self.ws_event.wait():
            await self.ws_lock
            try:
                await self.change_presence(game=discord.Game(name=self.ws_msg, url='', type=0), status=self.ws_status)
            except websockets.exceptions.ConnectionClosed as ex:
                print(ex)
                
            self.ws_event.clear()
            self.ws_lock.release()
            await asyncio.sleep(15)
    
    async def set_status(self, msg, status):
        await self.ws_lock
        self.ws_status = status
        self.ws_msg = msg
        self.ws_event.set()
        self.ws_lock.release()
        
    async def bg_loop(self):
        await self.wait_until_ready()        
        while not self.is_closed:
            try:
                for l in self.loggers:
                    l.before_update()
                    
                for server in self.servers:
                    
                    for l in self.loggers:
                        l.before_server_update(server)
                        
                    for channel in server.channels:
                        for l in self.loggers:
                            l.before_channel_update(channel)
                            
                        t = datetime.fromtimestamp(time.time() - self.msg_ival)
                        async for m in bot.logs_from(channel, after=t, limit=100000):
                            for l in self.loggers:
                                l.process_message(m)
                        
                        for l in self.loggers:
                            l.after_channel_update(channel)    
                            
                    for l in self.loggers:
                        l.after_server_update(server)
                        
                for l in self.loggers:
                    l.after_update()
                '''
                for sm in self.servermetas.items():
                    await sm.cycle()
                        
                await set_busy(False)
                status = discord.Status.online
                await set_status("Use z>help", status)
                '''
            except aiohttp.errors.ServerDisconnectedError as ex:
                print(ex)
            except aiohttp.errors.ClientResponseError as ex:
                print(ex)
            except discord.errors.HTTPException as ex:
                print(ex)
            
            await asyncio.sleep(self.wait_ival)

    def add_logger(self, loggerInstance):
        if not issubclass(type(loggerInstance), Logger):
            raise RuntimeError('Decorated class is not a Logger')
                
        loggerInstance.set_client(self)
        self.loggers.append(loggerInstance)
    
    def logger(self, loggerCls):
        '''Class decorator for loggers'''
        print("logger", type(loggerCls))
        
        def decorator(*args, **kwargs):
            print("decorator", args, kwargs)
            #print("loggerInstance", loggerInstance)
            loggerInstance = loggerCls(*args, **kwargs)
            self.add_logger(loggerInstance)
            return loggerInstance
            
        return decorator
        
bot = Logbot(command_prefix='z>')

@bot.logger
class SimpleLogger(Logger):

    def __init__(self, foo, bar):
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
        
    @bot.command(pass_context=True, no_pm=True)
    async def test(self, *args, **kwargs):
        print("test", args, kwargs)

print("instantiating")
sl = SimpleLogger("baz", "blee")
print("instance", sl)

@bot.event
async def on_ready():
    print('Logged in as', bot.user.name)        
        
bot.run(token)