#sambot

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

from .schema import ScoreTbl, ScoreItem, Reaction

@bot.logger
class Zeitlog(logbot.Logger):

    def __init__(self, db):
        super().__init__()
    
        self.db = db
        #self.channelcontainer = ChannelContainer()
        self.scoretbl = defaultdict(dict)
        self.reacts = {}
        self.scorecards = ChannelContainer()
        self.leaderboards = ChannelContainer()
        
        self.busy = True
        self.busylock = asyncio.Lock()
        
        self.lbQ = asyncio.Queue()
        self.msgQ = asyncio.Queue()
        
    async def set_busy(self, val):
        await self.busylock
        self.busy = val
        self.busylock.release()
        
    async def get_busy(self):
        await self.busylock
        val = self.busy
        self.busylock.release()
        return val
        
    async def before_channel_update(self, channel):
        await self.client.set_status(channel.name, self.client.ws_status)
        self.scorecards[channel] = []
        
    def process_message(self, msg):
        self.scorecards[msg.channel].append(ScoreCard(msg, self.scoretbl[msg.server.id]))
        
    async def after_channel_update(self, channel):
        scorecards = self.scorecards[channel]
        
        print("Got {} scorecards for {}".format(len(scorecards), channel.name))
        tempboard = {}
        for score in self.scoretbl[channel.server.id].keys():
            await self.client.set_status(score, self.client.ws_status)
            slist = [sc for sc in scorecards if score in sc.scores]
            tempboard[score] = sorted(slist, key=lambda sc: sc.scores[score], reverse=True)[:10]
            
        await self.leaderboards[channel].setLB(tempboard)
        self.scorecards[channel] = None
        
    async def after_update(self):
        await self.set_busy(False)
        status = discord.Status.online
        await self.client.set_status("Use z>help", status)
        
    async def qLoop(self, q, qCons, waitTime=0):
        while not self.client.is_closed:
            nextItem = await q.get()
            await qCons(nextItem)
            
            if waitTime > 0:
                await asyncio.sleep(waitTime)
                
    async def enqueue_lb(self, scores, leaderboard, dstchannel, channame):
        await self.lbQ.put((scores, leaderboard, dstchannel, channame))
                
    async def process_lb_req(self, lb):
        (scores,leaderboard,channel,channame) = lb
        
        for score in scores:
            if score in leaderboard:
                # await self.client.send_message(ctx.message.channel, "**__{}__**".format(score))
                await self.enqueue_message(channel, "**__{}__**".format(score))
                if len(leaderboard[score]) == 0:
                    # await self.client.send_message(ctx.message.channel, "No messages for {} in {} :(".format(score, chan.name))
                    await self.enqueue_message(channel, "No messages for {} in {} :(".format(score, channame))
                for sc in leaderboard[score]:
                    e = None
                    if len(sc.message.attachments) != 0:
                        e = discord.Embed()
                        e.set_image(url=sc.message.attachments[0]['url'])
                    
                    # await self.client.send_message(ctx.message.channel, formatMessage(sc.message), embed=e)
                    await self.enqueue_message(channel, formatMessage(sc.message), embed=e)
                    
        # await self.client.send_message(ctx.message.channel, "======= That's all =======")
        await self.enqueue_message(channel, "======= That's all =======")
        
    async def enqueue_message(self, channel, msg, embed=None):
        await self.msgQ.put((channel, msg, embed))
        
    async def send_message(self, msgspec):
        (channel, message, embed) = msgspec
        await self.client.send_message(channel, message, embed=embed)
        
        
    def register_commands(self):
        print("Registering commands")
        
        self.client.loop.create_task(self.qLoop(self.msgQ, self.send_message, waitTime=1))
        self.client.loop.create_task(self.qLoop(self.lbQ, self.process_lb_req))
        
        @self.client.event
        async def on_ready():
            print('Logged in as', self.client.user.name)
            
            for s in self.client.servers:
                #react_res[s.name] = re.compile('z/')
            
                for score in self.db.query(ScoreTbl).filter_by(server=s.id):
                    self.scoretbl[s.id][score.name] = Score(score, self.client, self.db)
                    
                self.reacts[s.id] = Reactions(s.id, self.db, scores=list(self.scoretbl[s.id]))
                for channel in s.channels:
                    self.leaderboards[channel] = LeaderBoard()

        @self.client.listen()
        async def on_message(msg):
            #print("Got message", msg.content)
            
            if msg.author.id == self.client.user.id:
                return
            #print(self.reacts[msg.server.id].reactre)
            match = self.reacts[msg.server.id].reactre.search(msg.content)
            if match is not None:
                print("Got a match")
                s,e = match.span()
                mstr = msg.content[s:e]
                print(mstr)
                mitems = mstr.split('/')
                emojis = []
                for mitem in mitems[1:]:
                    print("Checking", mitem)
                    #print(reacts)
                    if mitem in self.scoretbl[msg.server.id]:
                        for si in self.scoretbl[msg.server.id][mitem].emojis.values():
                            emojis.append(getEmojiObj(msg.server, si.emoji))
                    elif mitem in self.reacts[msg.server.id]:
                        print(mitem)
                        e = self.reacts[msg.server.id][mitem]
                        em = getEmojiObj(msg.server, e)
                        '''
                        em = discord.utils.find(lambda emo: str(emo) == e, msg.server.emojis)
                        if em is None:
                            em = e
                        '''
                            
                        print("Adding", mitem)
                        #await self.add_reaction(msg, em)
                        emojis.append(em)
                
                for emoji in emojis:
                    await self.client.add_reaction(msg, emoji)
        
        @self.client.command(pass_context=True, no_pm=True)
        async def score(ctx, cmd, name):
            """Create, delete, or get info about a score
            
            cmd -- create, delete, or about
            name -- the name of the score to create or delete or about
            """
            res = await getattr(ScoreCommands, cmd)(ctx, name, self.db, self.scoretbl[ctx.message.server.id], self.reacts[ctx.message.server.id])
            
            if res is not None:
                if res:
                    await self.client.send_message(ctx.message.channel, "Score {} has been {}d".format(name, cmd))
                else:
                    await self.client.send_message(ctx.message.channel, "Can't {} {}".format(cmd, name))
            print(self.scoretbl)
            
        @self.client.command(pass_context=True, no_pm=True)
        async def set(ctx, name, emoji, count):
            """Set the value of an emoji in a score
            
            name -- the name of the score to modify
            emoji -- the emoji for which to set a value
            count -- the value to set for the emoji. 
            
            Messages possessing n emoji reactions will have n*count added to their score with the given name\n\n
            """
            
            score = self.scoretbl[ctx.message.server.id][name]
            is_admin = ctx.message.server.default_channel.permissions_for(ctx.message.author).administrator
            if not is_admin and ctx.message.author != score.owner:
                await self.client.send_message(ctx.message.channel, "You are not allowed to modify this score")
                return
            
            print(type(emoji), type(count))
            #await ScoreCard.scoretbl[ctx.message.server.name][name].setItem(emoji, count)
            await score.setItem(emoji, count)
            await self.client.send_message(ctx.message.channel, "{} has been set to {} in {}".format(emoji, count, name))
            
        @self.client.command(pass_context=True, no_pm=True)
        async def scores(ctx, *args, **kwargs):
            """Display a list of scores"""
            print(self.scoretbl)
            scores = self.scoretbl[ctx.message.server.id].keys()
            print(ctx.message.server.name, scores)
            print("\n".join([score for score in scores]))
            msg = "No scores yet"
            if len(scores) != 0:
                msg = "Available scores: ```\n{}```".format("\n".join([score for score in scores]))
                
            await self.client.send_message(ctx.message.channel, msg)
                
        @self.client.command(pass_context=True, no_pm=True)
        async def zeitgeist(ctx, *args, **kwargs):
            """Display the top 10 highest scoring messages for a score or list of scores
            
            Use with z>zeitgeist score1 score2 ...
            Optionally include a channel mention to see zeitgeist for a specific channel.
            """
            
            if await self.get_busy():
                await self.client.send_message(ctx.message.channel, "I'm a little busy now, try again later?")
                return
            
            print(args, len(args))
            print(kwargs)
            
            chan = ctx.message.channel
            if len(ctx.message.channel_mentions) != 0:
                chan = ctx.message.channel_mentions[0]
            serv = ctx.message.server
            
            if not chan.permissions_for(ctx.message.author).read_messages:
                await self.client.send_message(ctx.message.channel, "Sorry, you're not allowed to see messages in {}...".format(chan.name))
                return
            
            if not chan in self.leaderboards:
                await self.client.send_message(ctx.message.channel, "I can't see {}.".format(chan.name))
                return
            
            leaderboard = await self.leaderboards[chan].getLB()
            print("leaderboard", leaderboard)
            scores = None
            if len(args) == 0:
                await self.client.send_message(ctx.message.channel, "Please specify at least one score. Type z>scores to see a list")
            else:
                scores = args
                
            dstchannel = discord.utils.find(lambda c: c.name == "zeitgeist", serv.channels)
            if dstchannel is None:
                await self.client.send_message(ctx.message.channel, "No channel named zeitgeist. Please create one.")
                return
            
            await self.enqueue_lb(scores, leaderboard, dstchannel, chan.name)
            await self.client.send_message(ctx.message.channel, "Messages sent to {}".format(dstchannel.mention))
            '''
            for score in scores:
                if score in leaderboard:
                    await self.client.send_message(ctx.message.channel, "**__{}__**".format(score))
                    if len(leaderboard[score]) == 0:
                        await self.client.send_message(ctx.message.channel, "No messages for {} in {} :(".format(score, chan.name))
                    for sc in leaderboard[score]:
                        e = None
                        if len(sc.message.attachments) != 0:
                            e = discord.Embed()
                            e.set_image(url=sc.message.attachments[0]['url'])
                        
                        await self.client.send_message(ctx.message.channel, formatMessage(sc.message), embed=e)

            await self.client.send_message(ctx.message.channel, "======= That's all =======")
            '''

        @self.client.command(pass_context=True, no_pm=True)
        async def react(ctx, str, emoji):
            is_admin = ctx.message.server.default_channel.permissions_for(ctx.message.author).administrator
            if not is_admin:
                await self.client.send_message(ctx.message.channel, "Sorry, you're not allowed to use this command")
                return
            
            self.reacts[ctx.message.server.id][str] = emoji
            self.reacts[ctx.message.server.id].save()
            '''
            reacts_group = "|".join(reacts[ctx.message.server.name].keys())
            reacts_regex = "r/({})(/({}))*".format(reacts_group, reacts_group)
            '''
            print(self.reacts[ctx.message.server.id].reactre)
            #react_res[ctx.message.server.name] = re.compile(reacts_regex)
            await self.client.send_message(ctx.message.channel, "Reaction added")

        @self.client.command(pass_context=True, no_pm=False)
        async def reactions(ctx):
            '''View a list of auto-reactions.
            
            To use auto reactions, include the string r/react1/react2/.../reactn anywhere in your message, where react1, react2, ..., reactn are the strings on the right in the response to this command.
            You can also use the names of scores. If you do, all the emojis in that score will be used in auto-reactions to your message.
            '''
            msg = "\n".join(["{} {}".format(r.emoji, str) for (str, r) in self.reacts[ctx.message.server.id].reactdict.items()])
            await self.client.send_message(ctx.message.channel, "-------\n" + msg)



def emojikey(e):
    return str(e)

localtz = pytz.timezone("America/New_York")
def formatMessage(m):
    global localtz
    
    mstr = '------\n**{}**\n'.format(m.author.display_name)
    content = m.content
    for u in m.mentions:
        content = content.replace(u.mention, '@' + u.display_name)
        
    content = content.replace('@everyone', 'everyone')
    content = content.replace('@here', 'here')
        
    if len(content) != 0:
        mstr += '{}\n'.format(content)
    
    aware_tz = pytz.utc.localize(m.timestamp)
    mstr += '*{}*\n'.format(aware_tz.astimezone(localtz).strftime('%b %d, %Y @ %I:%M%p'))
    mstr += ' '.join(['{}{}'.format(r.count, r.emoji) for r in m.reactions])
    return mstr
    
def formatLeaderboard(name, scorecards):
    msg = '**__{}__**\n'.format(name)
    msg += "\n------------\n".join([formatMessage(sc.message) for sc in scorecards])
    return msg        
    #await bot.send_message(ctx.message.channel, msg)

def getEmojiObj(server, emoji):
    e = discord.utils.find(lambda emo: str(emo) == emoji, server.emojis)
    if e is None:
        return emoji
    return e
    
class Score:
    
    def __init__(self, srecord, client, db):
    
        self.lock = asyncio.Lock()
        self.srecord = srecord
        self.server = discord.utils.find(lambda s : s.id == srecord.server, client.servers)
        self.owner = discord.utils.find(lambda m : m.id == srecord.owner, self.server.members)
        
        self.db = db
        
        self.emojis = {}
        for si in self.db.query(ScoreItem).filter_by(score=srecord.id):
            self.emojis[si.emoji] = si
    
    async def save(self):
        print("(Score) Saving")
        await self.lock
        try:
            print(self.db)
            self.db.query(ScoreItem).filter_by(score=self.srecord.id).delete()
            for si in self.emojis.values():
                self.db.add(si)
            self.db.add(self.srecord)
            self.db.commit()
        except Exception:
            print(ex)
        finally:
            self.lock.release()
            pass
        print("Saved")
        
    async def delete(self):
        await self.lock
        try:
            self.db.query(ScoreTbl).filter_by(id=self.srecord.id).delete()
        finally:
            self.lock.release()
            
    async def setItem(self, emoji, val):
        print("Setting emoji to", val)
        si = None
        if emoji in self.emojis:
            si = self.emojis[emoji]
        else:
            si = ScoreItem(score=self.srecord.id, emoji=emoji)
            
        si.val = val
        self.emojis[emoji] = si
        await self.lock
        try:
            self.db.add(si)
            self.db.commit()
        finally:
            self.lock.release()
            
    
class ScoreCard:
    
    #scoretbl = defaultdict(dict)
    
    def __init__(self, message, tbl):
        self.message = message
        self.scores = {}
        
        #tbl = scoretbl[message.server.name]
        for r in message.reactions:
            for name, score in tbl.items():
                k = emojikey(r.emoji)
                if k in score.emojis:
                    if not name in self.scores:
                        self.scores[name] = 0
                    self.scores[name] += r.count * score.emojis[k].val
                    

class ScoreCommands:
    @staticmethod
    async def create(ctx, name, db, scoretbl, reacts):
        if not name in scoretbl:
            stbl = ScoreTbl(name=name, owner=ctx.message.author.id, server=ctx.message.server.id)
            s = Score(stbl, ctx.bot, db)
            scoretbl[stbl.name] = s
            print("Saving")
            #print(s.save)
            await s.save()
            reacts.addOther(name)
            return True
        
        return False
        
    @staticmethod
    async def delete(ctx, name, db, scoretbl, reacts):
        score = scoretbl[name]
        is_admin = ctx.message.server.default_channel.permissions_for(ctx.message.author).administrator
        if not is_admin and ctx.message.author != score.owner:
            return False
        
        await score.delete()
        del scoretbl[name]
        reacts.removeOther(name)
        return True
        
    @staticmethod
    async def about(ctx, name, db, scoretbl, reacts):
        if not name in scoretbl:
            return False
            
        score = scoretbl[name]
        owner = "no one" if score.owner is None else score.owner.display_name
        
        msg = " ".join(["{}{}".format(emoji, si.val) for (emoji, si) in score.emojis.items()])
        msg += "\nOwned by " + owner
        
        if len(msg) == 0:
            msg = "No emojis set for " + name
        await ctx.bot.send_message(ctx.message.channel, msg)
        return None
        
        
class LeaderBoard:
    
    def __init__(self):
        self.lock = asyncio.Lock()
        self.leaderboard = {}
        
    async def setLB(self, lb):
        await self.lock
        self.leaderboard = lb
        self.lock.release()
        
    async def getLB(self):
        await self.lock
        lb = self.leaderboard
        self.lock.release()
        return lb
        
class Reactions:

    prefix = '(^| )r'
    sep = '/'
    addtl = 'scores'

    def __init__(self, servername, dbsesh, **kwargs):
        self.dbsesh = dbsesh
        self.server = servername
        self.reactdict = {}
        for r in self.dbsesh.query(Reaction).filter_by(server=servername):
            self.reactdict[r.shortcut] = r
            
        self.other_shortcuts = []
        if Reactions.addtl in kwargs:
            self.other_shortcuts = list(kwargs[Reactions.addtl])
            
        self.setRe()
            
    def setRe(self):
        reacts_group = "|".join(list(self.reactdict) + self.other_shortcuts)
        reacts_regex = Reactions.prefix + Reactions.sep + "({})({}({}))*".format(reacts_group, Reactions.sep, reacts_group)
        self.reactre = re.compile(reacts_regex)
        
    def addOther(self, other):
        self.other_shortcuts.append(other)
        self.setRe()
        
    def removeOther(self, other):
        self.other_shortcuts.remove(other)
        self.setRe()
            
    def __getitem__(self, i):
        return self.reactdict[i].emoji
        
    def __setitem__(self, i, x):
        if not i in self.reactdict:
            self.reactdict[i] = Reaction(shortcut=i, server=self.server)
    
        self.reactdict[i].emoji = x
        self.setRe()
        
    def __iter__(self):
        return iter(list(self.reactdict) + self.other_shortcuts)
        
    '''
    def __next__(self):
        print('__next__')
        return next(self.reactdict)
    '''
        
    def items(self):
        return [(s,r.emoji) for s,r in self.reactdict.items()]
        
    def save(self, *args):
        keys = args
        if len(keys) == 0:
            keys = self.reactdict.keys()
            
        for k in keys:
            self.dbsesh.add(self.reactdict[k])
            
        self.dbsesh.commit()
