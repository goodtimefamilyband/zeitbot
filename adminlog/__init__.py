#logbot_example.py
import time

from logbot import Logger, Logbot, DiscreteLogbot
#from app import bot
from collections import defaultdict
from .schema import Server, Member, Role, Rule, RuleRole, RoleException

from discord.ext import commands
           
adminbot = DiscreteLogbot(command_prefix='a.')

@adminbot.logger
class AdminLogger(Logger):

    def __init__(self, db):
        super().__init__()
        self.db = db
        self.servertable = {}

    def before_update(self):
        print("before_update")

    def before_server_update(self, server):
        
        self.member_count_table = defaultdict(int)
        self.membertable = {}
        if not server.id in self.servertable:
            dbserv = self.db.query(Server).filter_by(id=server.id).first()
            if dbserv is None:
                dbserv = Server(id=server.id, after=time.time())
                self.db.add(dbserv)
                self.db.commit()
                
            dbserv.load_rules(self.client, self.db)
            self.servertable[server.id] = dbserv
            
            
        self.client.after = self.servertable[server.id].after
        self.client.before = time.time()

    def before_channel_update(self, channel):
        print("before_channel_update")

    def process_message(self, msg):
        self.member_count_table[msg.author.id] += 1
        self.membertable[msg.author.id] = msg.author
        t = time.mktime(msg.timestamp.timetuple())
        if t > self.servertable[msg.server.id].after:
            self.servertable[msg.server.id].after = t
            self.db.commit()
        
        
    def after_channel_update(self, channel):
        print("after_channel_update")
        
    def after_server_update(self, server):
        dbserv = self.servertable[server.id]
        
        for memberid, count in self.member_count_table.items():
            member = self.db.query(Member).filter_by(id=memberid, serverid=server.id).first()
            if member is None:
                member = Member(id=memberid, serverid=server.id,msgcount=0)
                self.db.add(member)
                
            member.msgcount += count
            for rule in dbserv.ruleset:
                self.client.loop.create_task(rule([member.msgcount], [self.membertable[memberid]]))
            
        self.db.commit()
        
    def after_update(self):
        print("after_update")
        
    def register_commands(self):
        
        def admin_check(ctx):
            print("***admin_check***", ctx.message.content, ctx.message.channel.permissions_for(ctx.message.author).administrator)
            return ctx.message.channel.permissions_for(ctx.message.author).administrator
        
        @self.client.event
        async def on_ready():
            print('Logged in as', self.client.user.name)
            
            print(self.client.servers)
            for server in self.client.servers:
                if not server.id in self.servertable:
                    dbserv = self.db.query(Server).filter_by(id=server.id).first()
                    if dbserv is None:
                        dbserv = Server(id=server.id, after=time.time())
                        self.db.add(dbserv)
                        self.db.commit()
                    
                    print("Loading server", server.id, server.name)
                    dbserv.load_rules(self.client, self.db)
                    self.servertable[dbserv.id] = dbserv
            
            
        @commands.check(admin_check)
        @self.client.command(pass_context=True, no_pm=True)
        async def roleadd(ctx, *args, **kwargs):
            print(self, ctx)
            print("roleadd", args, kwargs)
            
            dbrule = Rule(serverid=ctx.message.server.id, mincount=int(args[0]))
            self.db.add(dbrule)
            self.db.commit()
            
            for role in ctx.message.role_mentions:
                dbrole = self.db.query(Role).filter_by(id=role.id).first()
                if dbrole is None:
                    dbrole = Role(id=role.id)
                    self.db.add(dbrole)
                    self.db.commit()
                    
                rr = RuleRole(ruleid=dbrule.id, roleid=dbrole.id)
                self.db.add(rr)
                
            self.db.commit()
            
            dbrule.load_rule(self.client, self.db)
            self.servertable[ctx.message.server.id].ruleset.append(dbrule)
            await self.client.send_message(ctx.message.channel, "Rule {} created".format(dbrule.id))
            
        @self.client.command(pass_context=True, no_pm=True)
        async def rulelist(ctx):
            dbserv = self.servertable[ctx.message.server.id]
            
            msg = "Server rules: ```{}```".format("\n".join([str(rule) for rule in dbserv.ruleset]))
            await self.client.send_message(ctx.message.channel, msg)
            
        @commands.check(admin_check)
        @self.client.command(pass_context=True, no_pm=True)
        async def ruledel(ctx, ruleid):
            ruleid = int(ruleid)
            print("**************RULEDEL******************")
            dbserver = self.servertable[ctx.message.server.id]
            for i in range(len(dbserver.ruleset)):
                print(ruleid, dbserver.ruleset[i].id)
                if dbserver.ruleset[i].id == ruleid:
                    print("Deleting rule")
                    del dbserver.ruleset[i]
                    self.db.query(RuleRole).filter_by(ruleid=ruleid).delete()
                    self.db.query(Rule).filter_by(id=ruleid).delete()
                    self.db.commit()
                    await self.client.send_message(ctx.message.channel, "Rule {} deleted".format(ruleid))
                    return
            
        @self.client.listen()
        async def on_message(msg):
            await self.client.wait_until_ready() # Does this work?
        
            if msg.author.bot or msg.server is None:
                return
        
            dbmember = self.db.query(Member).filter_by(id=msg.author.id, serverid=msg.server.id).first()
            if dbmember is None:
                dbmember = Member(id=msg.author.id, serverid=msg.server.id, msgcount=0)
                self.db.add(dbmember)
                
            dbmember.msgcount += 1
            server = msg.server
            if not server.id in self.servertable:
                dbserv = self.db.query(Server).filter_by(id=server.id).first()
                if dbserv is None:
                    dbserv = Server(id=server.id, after=time.time())
                    self.db.add(dbserv)
                    self.db.commit()
                    
                dbserv.load_rules(self.client, self.db)
                self.servertable[server.id] = dbserv            
            
            dbserver = self.servertable[msg.server.id]
            print(dbserver.after)
            t = time.mktime(msg.timestamp.timetuple())
            if t > dbserver.after:
                dbserver.after = t
            
            self.db.commit()
            
            for rule in self.servertable[msg.server.id].ruleset:
                self.client.loop.create_task(rule([dbmember.msgcount], [msg.author]))
        
        '''
        @self.client.event
        async def on_member_update(before, after):
            removed_roles = [role for role in before.roles if role not in after.roles]
            ids = [role.id for role in removed_roles]
            affected_rules = self.db.query(RuleRole).filter(RuleRole.ruleid.in_(ids))
            for rule in affected_rules:
                rexcept = RoleException(ruleid=rule.ruleid, roleid=rule.roleid, memberid=after.id)
                self.db.add(rexcept)
                
            self.db.commit()
        '''
'''                
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
'''