#heartbeat.py

import pandas as pd

import discord
from discord.ext import commands
import asyncio
import re
from datetime import datetime, tzinfo
import time
import pytz
from collections import defaultdict
import logbot
from logbot.utils import ChannelContainer
from app import bot

import os

import matplotlib.pyplot as plt
import matplotlib.dates as mdates

localtz = pytz.timezone("America/New_York")

@bot.logger
class Graphlog(logbot.Logger):
    
    periods = 24*7
    
    def __init__(self, path):
        self.path = path
        
        if not os.path.isdir(self.path):
            os.makedirs(self.path)
        
        self.messages = ChannelContainer()
        self.starttimes = ChannelContainer()
        self.counts = ChannelContainer()
    
    async def before_channel_update(self, channel):
        self.messages[channel] = []
        
    def channel_update_starttime(self, channel, st):
        self.starttimes[channel] = st
        
    def process_message(self, msg):
        self.messages[msg.channel].append(msg)
        
    async def after_channel_update(self, channel):
        if len(self.messages[channel]) == 0:
            return
        
        messages = self.messages[channel]
        print(len(messages))
        starttime = self.starttimes[channel].timestamp()
        endtime = time.time()
        delta = endtime - starttime
        
        print(starttime, endtime)
        print(delta, int(delta))
        
        #r = pd.date_range(starttime, periods=24*7, freq='H')
        buckets = [0] * (int(delta/3600))
        print(len(buckets))
        for m in messages:
            aware_tz = pytz.utc.localize(m.timestamp)
            
            mdelta = aware_tz.timestamp() - starttime
            bucket = int(mdelta / 3600)
            buckets[bucket] += 1
        
        self.counts[channel] = (buckets, starttime, False)
        
    async def after_update(self):
        print("Heartbeat done")
    
    def get_plot(self, channel):
        
        buckets, starttime, drawn = self.counts[channel]
        ppath = os.path.join(self.path, channel.server.name, channel.name + '.png')
        if not drawn and not os.path.isfile(ppath):        
            dates = []
            for i in range(len(buckets)):
                tstamp = starttime + (3600 * i)
                dates.append(datetime.fromtimestamp(tstamp))
            
            plt.figure(figsize=(20,10))
            plt.plot_date(x=dates, y=buckets, fmt="r-")
            plt.savefig(ppath, bbox_inches='tight')
            
        return ppath
        
    def register_commands(self):
    
        @self.client.listen()
        async def on_ready():
            for server in self.client.servers:
                spath = os.path.join(self.path, server.name)
                print(spath)
                if not os.path.isdir(spath):
                    os.makedirs(spath)
    
        @self.client.command(pass_context=True, no_pm=True)
        async def heartbeat(ctx, *args, **kwargs):
            """Display a graph of user activity.
            """
            path = self.get_plot(ctx.message.channel)
            print(path)
            with open(path, 'rb') as f:
                await self.client.send_file(ctx.message.channel, f)
                