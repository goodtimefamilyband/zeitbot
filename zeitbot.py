#sambot

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

react_regex = 'z/([ad])(/[ad])*'

reacts = defaultdict(dict)
react_res = {}

from app.schema import Session, ScoreTbl, ScoreItem, Reaction
db_session = Session()

def emojikey(e):
    return str(e)

localtz = pytz.timezone("America/New_York")
def formatMessage(m):
    global localtz
    
    mstr = '------\n**{}**\n'.format(m.author.display_name)
    content = m.content
    for u in m.mentions:
        content = content.replace(u.mention, '@' + u.display_name)
        
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

class Zeitbot(commands.Bot):
    
    async def on_message(self, msg):
        #print("Got message", msg.content)
        match = reacts[msg.server.name].reactre.search(msg.content)
        if match is not None:
            s,e = match.span()
            mstr = msg.content[s:e]
            print(mstr)
            mitems = mstr.split('/')
            emojis = []
            for mitem in mitems[1:]:
                print("Checking", mitem)
                #print(reacts)
                if mitem in ScoreCard.scoretbl[msg.server.name]:
                    for si in ScoreCard.scoretbl[msg.server.name][mitem].emojis.values():
                        emojis.append(getEmojiObj(msg.server, si.emoji))
                elif mitem in reacts[msg.server.name]:
                    print(mitem)
                    e = reacts[msg.server.name][mitem]
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
                await self.add_reaction(msg, emoji)
                
        await super().on_message(msg)
    
class Score:
    
    def __init__(self, srecord, client):
    
        self.lock = asyncio.Lock()
        self.srecord = srecord
        self.server = discord.utils.find(lambda s : s.name == srecord.server, client.servers)
        self.owner = discord.utils.find(lambda m : m.id == srecord.owner, self.server.members)
        
        self.emojis = {}
        for si in db_session.query(ScoreItem).filter_by(score=srecord.id):
            self.emojis[si.emoji] = si
    
    async def save(self):
        print("(Score) Saving")
        await self.lock
        try:
            print(db_session)
            db_session.query(ScoreItem).filter_by(score=self.srecord.id).delete()
            for si in self.emojis.values():
                db_session.add(si)
            db_session.add(self.srecord)
            db_session.commit()
        except Exception:
            print(ex)
        finally:
            self.lock.release()
            pass
        print("Saved")
        
    async def delete(self):
        await self.lock
        try:
            db_session.query(ScoreTbl).filter_by(id=self.srecord.id).delete()
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
            db_session.add(si)
            db_session.commit()
        finally:
            self.lock.release()
            
    
class ScoreCard:
    
    scoretbl = defaultdict(dict)
    
    def __init__(self, message):
        self.message = message
        self.scores = {}
        
        tbl = ScoreCard.scoretbl[message.server.name]
        for r in message.reactions:
            for name, score in tbl.items():
                k = emojikey(r.emoji)
                if k in score.emojis:
                    if not name in self.scores:
                        self.scores[name] = 0
                    self.scores[name] += r.count * score.emojis[k].val
                    

class ScoreCommands:
    @staticmethod
    async def create(ctx, name):
        if not name in ScoreCard.scoretbl[ctx.message.server.name]:
            stbl = ScoreTbl(name=name, owner=ctx.message.author.id, server=ctx.message.server.name)
            s = Score(stbl, ctx.bot)
            ScoreCard.scoretbl[ctx.message.server.name][stbl.name] = s
            print("Saving")
            #print(s.save)
            await s.save()
            reacts[ctx.message.server.name].addOther(name)
            return True
        
        return False
        
    @staticmethod
    async def delete(ctx, name):
        score = ScoreCard.scoretbl[ctx.message.server.name][name]
        is_admin = ctx.message.server.default_channel.permissions_for(ctx.message.author).administrator
        if not is_admin and ctx.message.author != score.owner:
            return False
        
        await score.delete()
        del ScoreCard.scoretbl[ctx.message.server.name][name]
        return True
        
    @staticmethod
    async def about(ctx, name):
        if not name in ScoreCard.scoretbl[ctx.message.server.name]:
            return False
            
        score = ScoreCard.scoretbl[ctx.message.server.name][name]
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

    prefix = 'r'
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
        
        

mentions_regex = '@[^ ]*'
mentions_re = re.compile(mentions_regex)
ival = 60*60*24*7

#bot = commands.Bot(command_prefix='z>')
bot = Zeitbot(command_prefix='z>')

leaderboards = defaultdict(dict)
glock = asyncio.Lock()
busy = True

async def set_busy(val):
    global glock
    global busy

    await glock
    busy = val
    glock.release()
    
async def get_busy():
    global glock
    global busy

    await glock
    val = busy
    glock.release()
    return busy

ws_lock = asyncio.Lock()
ws_event = asyncio.Event()
ws_status = discord.Status.dnd
ws_msg = "Starting up..."
async def get_status():
    global ws_status
    global ws_msg
    
    return ws_msg, ws_status
    
async def set_status(msg, status):
    global ws_lock
    global ws_status
    global ws_msg
    global ws_event

    await ws_lock
    ws_status = status
    ws_msg = msg
    ws_event.set()
    ws_lock.release()

ws_state = True
async def compute_leaderboard():
    global ws_event
    
    await bot.wait_until_ready()
    status = discord.Status.dnd
    await set_status("Starting up...", status)
    # await bot.change_presence(game=discord.Game(name="Starting up...", url='', type=0), status=status)
    for server in bot.servers:
        for channel in server.channels:
            leaderboards[server][channel] = LeaderBoard()
            
    while not bot.is_closed:
        try:
            t = datetime.fromtimestamp(time.time() - ival)
            for server in bot.servers:
                for channel in server.channels:
                    try:
                        scorecards = []
                        
                        #await bot.change_presence(game=discord.Game(name=channel.name, url='', type=0), status=status)
                        await set_status(channel.name, status)
                        async for m in bot.logs_from(channel, after=t, limit=100000):
                            scorecards.append(ScoreCard(m))
                        
                        print("Got {} scorecards for {}".format(len(scorecards), channel.name))
                        tempboard = {}
                        for score in ScoreCard.scoretbl[server.name].keys():
                            #await bot.change_presence(game=discord.Game(name=score, url='', type=0), status=status)
                            await set_status(score, status)
                            slist = [sc for sc in scorecards if score in sc.scores]
                            tempboard[score] = sorted(slist, key=lambda sc: sc.scores[score], reverse=True)[:10]
                            
                        await leaderboards[server][channel].setLB(tempboard)
                    except discord.errors.Forbidden as ex:
                        print("{}: Can't access {} on {}".format(ex, channel.name, server.name))
                    
            await set_busy(False)
            status = discord.Status.online
            #await bot.change_presence(game=discord.Game(name="Use z>help", url='', type=0), status=status)
            await set_status("Use z>help", status)
            
            # Do it again to update status text?
            # await bot.change_presence(game=discord.Game(name="Use z>help", url='', type=0), status=status)
            
            
        except aiohttp.errors.ServerDisconnectedError as ex:
            print(ex)
        except aiohttp.errors.ClientResponseError as ex:
            print(ex)
        
        #ws_event.clear()
        await asyncio.sleep(300)


async def ws_coro():
    global ws_event
    global ws_lock
    
    await bot.wait_until_ready()
    while await ws_event.wait():
        await ws_lock
        try:
            msg, status = await get_status()
            await bot.change_presence(game=discord.Game(name=msg, url='', type=0), status=status)
        except websockets.exceptions.ConnectionClosed as ex:
            print(ex)
            
        ws_event.clear()
        ws_lock.release()
        await asyncio.sleep(15)
        
@bot.event
async def on_ready():
    print('Logged in as', bot.user.name)
    
    for s in bot.servers:
        #react_res[s.name] = re.compile('z/')
    
        for score in db_session.query(ScoreTbl).filter_by(server=s.name):
            ScoreCard.scoretbl[s.name][score.name] = Score(score, bot)
            
        reacts[s.name] = Reactions(s.name, db_session, scores=list(ScoreCard.scoretbl[s.name]))
                    
    
@bot.command(pass_context=True, no_pm=True)
async def score(ctx, cmd, name):
    """Create, delete, or get info about a score
    
    cmd -- create, delete, or about
    name -- the name of the score to create or delete or about
    """
    res = await getattr(ScoreCommands, cmd)(ctx, name)
    
    if res is not None:
        if res:
            await bot.send_message(ctx.message.channel, "Score {} has been {}d".format(name, cmd))
        else:
            await bot.send_message(ctx.message.channel, "Can't {} {}".format(cmd, name))
    print(ScoreCard.scoretbl)
    
@bot.command(pass_context=True, no_pm=True)
async def set(ctx, name, emoji, count):
    """Set the value of an emoji in a score
    
    name -- the name of the score to modify
    emoji -- the emoji for which to set a value
    count -- the value to set for the emoji. 
    
    Messages possessing n emoji reactions will have n*count added to their score with the given name\n\n
    """
    
    score = ScoreCard.scoretbl[ctx.message.server.name][name]
    is_admin = ctx.message.server.default_channel.permissions_for(ctx.message.author).administrator
    if not is_admin and ctx.message.author != score.owner:
        await bot.send_message(ctx.message.channel, "You are not allowed to modify this score")
        return
    
    print(type(emoji), type(count))
    #await ScoreCard.scoretbl[ctx.message.server.name][name].setItem(emoji, count)
    await score.setItem(emoji, count)
    await bot.send_message(ctx.message.channel, "{} has been set to {} in {}".format(emoji, count, name))
    
@bot.command(pass_context=True, no_pm=True)
async def scores(ctx, *args, **kwargs):
    """Display a list of scores"""
    
    scores = ScoreCard.scoretbl[ctx.message.server.name].keys()
    print(ctx.message.server.name, scores)
    print("\n".join([score for score in scores]))
    msg = "No scores yet"
    if len(scores) != 0:
        msg = "Available scores: ```\n{}```".format("\n".join([score for score in scores]))
        
    await bot.send_message(ctx.message.channel, msg)
        
@bot.command(pass_context=True, no_pm=True)
async def zeitgeist(ctx, *args, **kwargs):
    """Display the top 10 highest scoring messages for a score or list of scores
    
    Use with z>zeitgeist score1 score2 ...
    Optionally include a channel mention to see zeitgeist for a specific channel.
    """
    
    if await get_busy():
        await bot.send_message(ctx.message.channel, "I'm a little busy now, try again later?")
        return
    
    #print(type(ctx.message.channel_mentions[0]))
    print(args, len(args))
    #print(*)
    print(kwargs)
    t = datetime.fromtimestamp(time.time() - ival)
    
    chan = ctx.message.channel
    if len(ctx.message.channel_mentions) != 0:
        chan = ctx.message.channel_mentions[0]
    serv = ctx.message.server
    
    if not chan.permissions_for(ctx.message.author).read_messages:
        await bot.send_message(ctx.message.channel, "Sorry, you're not allowed to see messages in {}...".format(chan.name))
        return
    
    if not chan in leaderboards[serv]:
        await bot.send_message(ctx.message.channel, "I can't see {}.".format(chan.name))
        return
    
    leaderboard = await leaderboards[serv][chan].getLB()
    print("leaderboard", leaderboard)
    scores = None
    if len(args) == 0:
        #scores = leaderboard.keys()
        await bot.send_message(ctx.message.channel, "Please specify at least one score. Type z>scores to see a list")
    else:
        scores = args
    
    for score in scores:
        if score in leaderboard:
            await bot.send_message(ctx.message.channel, "**__{}__**".format(score))
            if len(leaderboard[score]) == 0:
                await bot.send_message(ctx.message.channel, "No messages for {} in {} :(".format(score, chan.name))
            for sc in leaderboard[score]:
                e = None
                if len(sc.message.attachments) != 0:
                    e = discord.Embed()
                    e.set_image(url=sc.message.attachments[0]['url'])
                
                await bot.send_message(ctx.message.channel, formatMessage(sc.message), embed=e)

    await bot.send_message(ctx.message.channel, "======= That's all =======")

@bot.command(pass_context=True, no_pm=True)
async def react(ctx, str, emoji):
    global reacts
    global react_res
    '''
    em = discord.utils.find(lambda e: str(e) == emoji, ctx.message.server.emojis)
    if em is None:
        await bot.send_message(ctx.message.channel, "Can't find {} on server {}...".format())
    '''
    is_admin = ctx.message.server.default_channel.permissions_for(ctx.message.author).administrator
    if not is_admin:
        await bot.send_message(ctx.message.channel, "Sorry, you're not allowed to use this command")
    
    reacts[ctx.message.server.name][str] = emoji
    reacts[ctx.message.server.name].save()
    '''
    reacts_group = "|".join(reacts[ctx.message.server.name].keys())
    reacts_regex = "r/({})(/({}))*".format(reacts_group, reacts_group)
    '''
    print(reacts[ctx.message.server.name].reactre)
    #react_res[ctx.message.server.name] = re.compile(reacts_regex)
    await bot.send_message(ctx.message.channel, "Reaction added")

@bot.command(pass_context=True, no_pm=False)
async def reactions(ctx):
    '''View a list of auto-reactions.
    
    To use auto reactions, include the string r/react1/react2/.../reactn anywhere in your message, where react1, react2, ..., reactn are the strings on the right in the response to this command.
    You can also use the names of scores. If you do, all the emojis in that score will be used in auto-reactions to your message.
    '''
    global reacts
    
    msg = "\n".join(["{} {}".format(r.emoji, str) for (str, r) in reacts[ctx.message.server.name].reactdict.items()])
    await bot.send_message(ctx.message.channel, "-------\n" + msg)
'''
@bot.command(pass_context=True, no_pm=True)
async def help(ctx, *args, **kwargs):
    h = "```\n"
    h += "z>score create [name]\n"
    h += "Create a score with the given name\n\n"
    
    h += "z>score delete [name]\n"
    h += "Delete the score with the given name\n\n"
    
    h += "z>set [score-name] [emoji] [value]\n"
    h += "Messages containing n [emoji]s will have n*[value] added to their [score-name] score\n\n"
    
    h += "z>zeitgeist [score-name] #[channel]\n"
    h += "View the top 10 scoring messages in #[channel], or the channel from which the command was sent (if #[channel] is missing\n\n"
    
    h += "z>help\n"
    h += "View this help (duh) "
    
    h += "```"
    
    await bot.send_message(ctx.message.author, h)
'''                
bot.loop.create_task(compute_leaderboard())
bot.loop.create_task(ws_coro())
bot.run(token)
