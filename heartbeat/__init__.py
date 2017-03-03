#heartbeat.py

import pandas as pd

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
        
        self.channellocks = ChannelContainer()
    
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
        starttime = self.starttimes[channel].timestamp()
        endtime = time.time()
        delta = endtime - starttime
        
        buckets = [0] * (int(delta/3600))
        for m in messages:
            aware_tz = pytz.utc.localize(m.timestamp)
            
            mdelta = aware_tz.timestamp() - starttime
            bucket = int(mdelta / 3600)
                
            try:
                buckets[bucket] += 1
            except IndexError:
                print("Tried to fill bucket {} when there are only {}".format(bucket, len(buckets)))
        
        await self.channellocks[channel]
        self.counts[channel] = (buckets, starttime, False)
        self.channellocks[channel].release()
        
    async def after_update(self):
        print("Heartbeat done")
    
    async def get_plot(self, channel):
        
        ppath = os.path.join(self.path, channel.server.name, channel.name + '.png')
        
        await self.channellocks[channel]
        if not drawn or not os.path.isfile(ppath):        
            dates = []
            for i in range(len(buckets)):
                tstamp = starttime + (3600 * i)
                dates.append(datetime.fromtimestamp(tstamp))
            
            plt.figure(figsize=(20,10))
            buckets, starttime, drawn = self.counts[channel]
            plt.plot_date(x=dates, y=buckets, fmt="-")
            plt.savefig(ppath, bbox_inches='tight')
            self.counts[channel] = (buckets, starttime, True)
        
        self.channellocks[channel].release()    
        return ppath
        
    async def get_plots(self, channels):
        
        channels.sort(key=lambda c : c.name)
        cnames = [c.name for c in channels]
        fname = '_'.join(cnames) + '.png'
        ppath = os.path.join(self.path, channels[0].server.name, fname)
        attribs = [self.counts[channel] for channel in channels]
        print("attribs", attribs)
        drawn = all([d for (buckets, starttime, d) in attribs])
        print(drawn)
        
        for channel in channels:
            await self.channellocks[channel]
        
        if not drawn or not os.path.isfile(ppath):

            #b0, st0, d0 = attribs[0]
            
            plt.figure(figsize=(20,10))
            for channel in channels:
                buckets, st0, drawn = self.counts[channel]
                dates = mdates.drange(datetime.fromtimestamp(st0), datetime.fromtimestamp(st0 + 3600*24*7), timedelta(hours=1))
                print("buckets", buckets)
                plt.plot_date(dates, buckets, fmt='-')
                self.counts[channel] = (buckets, st0, True)
                
            plt.legend(cnames, loc='upper right')
            plt.savefig(ppath, bbox_inches='tight')
            
        for channel in channels:
            self.channellocks[channel].release()
            
        return ppath
        
    def register_commands(self):
    
        @self.client.listen()
        async def on_ready():
            for server in self.client.servers:
                spath = os.path.join(self.path, server.name)
                print(spath)
                if not os.path.isdir(spath):
                    os.makedirs(spath)
                    
                for channel is server.channels:
                    self.channellocks[channel] = asyncio.Lock()
    
        @self.client.command(pass_context=True, no_pm=True)
        async def heartbeat(ctx, *args, **kwargs):
            """Display a graph of user activity.
            """
            if len(ctx.message.channel_mentions) == 0:
                path = await self.get_plot(ctx.message.channel)
            else:
                path = await self.get_plots(ctx.message.channel_mentions)
            print(path)
            with open(path, 'rb') as f:
                await self.client.send_file(ctx.message.channel, f)
                