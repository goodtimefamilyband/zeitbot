#rcounter
import discord
from discord.ext import commands
import asyncio
import re
from datetime import datetime, tzinfo, timedelta
import time
import pytz
from collections import defaultdict
import logbot
from logbot.utils import ChannelContainer
from app import bot

@bot.logger
class ReactCounter(logbot.Logger):
        
    def __init__(self, show=10):
        self.servers = {}
        self.counts = defaultdict(list)
        self.show = show
        
    def before_server_update(self, server):
        self.servers[server.id] = defaultdict(int)
        self.counts[server.id] = []
    
    def process_message(self, msg):
        
        for r in msg.reactions:
            self.servers[msg.server.id][str(r.emoji)] += r.count
            
    def after_server_update(self, server):
        for r,c in self.servers[server.id].items():
            try:
                print(r)
            except UnicodeEncodeError:
                pass
            self.counts[server.id].append([r,c])
            
        self.counts[server.id].sort(key=lambda l: l[1], reverse=True)
        print("{} counts in {}".format(len(self.counts[server.id]), server.name))
        
    async def after_update(self):
        print("ReactCounter done")
    
        
    def register_commands(self):
    
        @self.client.command(pass_context=True, no_pm=True)
        async def reactcount(ctx, *args, **kwargs):
            """Display reaction counts for this server.
            """
            
            print(args)
            
            toshow = self.show
            if len(args) > 0:
                toshow = int(args[0])
            
            msg = "------\n"
            msg += "\n".join(["{} {}".format(r,c) for (r,c) in self.counts[ctx.message.server.id]][:toshow])
            
            await self.client.send_message(ctx.message.channel, msg)
