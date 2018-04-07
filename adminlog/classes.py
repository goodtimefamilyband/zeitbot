import sys
import discord
from collections import defaultdict

from . import schema
from .schema import listeners, ConditionEntry, ActionEntry, Rule, Condition, Action
from sqlalchemy import or_

'''
class Condition:
    def eval(self, *args):
        pass
        
class Action:
    async def __call__(self, *args, **kwargs):
        pass
'''


class RuleRepo:
    def __init__(self, db, client):
        self.db = db
        self.bot = client
            
    async def run_event(self, eventtype, serverid, *args, **kwargs):
        rules = self.db.query(Rule, ConditionEntry).\
            join(ConditionEntry, Rule.condid == ConditionEntry.id).\
            filter(Rule.serverid == serverid).\
            filter(or_(ConditionEntry.event == eventtype, ConditionEntry.event == None))
        
        # TODO: Use a join instead
        for (rule, condentry) in rules:
            print(rule, condentry)
            cond = condentry.load_instance(self.db)
            condresult = await cond.evaluate(self.db, self.bot, *args, **kwargs)
            
            if condresult:
                actentries = self.db.query(ActionEntry).filter_by(ruleid=rule.id)
                for actentry in actentries:
                    # actclass = getattr(schema, actentry.actclass)
                    action = actentry.load_instance(self.db)
                    # self.db.query(actclass).filter_by(actionid=actentry.id).first()
                    self.bot.loop.create_task(action.perform(self.db, self.bot, *args, **kwargs))
                    
    def register_commands(self):
        
        @self.bot.group(pass_context=True)
        async def addc(ctx):
            pass
            
        @self.bot.group(pass_context=True)
        async def test(ctx):
            print("test[ctx={}]".format(ctx))

        @self.bot.group(pass_context=True)
        async def adda(ctx):
            pass

        @self.bot.group(pass_context=True)
        async def info(ctx):
            pass

        for listener in listeners:
            addgrp = None

            if issubclass(listener, Condition):
                addgrp = addc
            elif issubclass(listener, Action):
                addgrp = adda

            listener().register_listeners(self.bot, self.db, addgrp=addgrp, testgrp=test, infogrp=info)
        
        @self.bot.event
        async def on_ready():
            pass

        async def send_entry_list(ctx, entries):
            lst = "\n".join(["{} {}".format(entry.id, str(entry.load_instance(self.db))) for entry in entries])
            msg = "```{}```".format(lst)
            await ctx.bot.send_message(ctx.message.channel, msg)
        
        # TODO: Figure out condition server IDs
        @self.bot.command(pass_context=True, no_pm=True)
        async def conditions(ctx):
            entries = self.db.query(ConditionEntry)
            await send_entry_list(ctx, entries)

        @self.bot.command(pass_context=True, no_pm=True)
        async def actions(ctx):
            entries = self.db.query(ActionEntry)
            await send_entry_list(ctx, entries)
            
        @self.bot.command(pass_context=True, no_pm=True)
        async def delc(ctx, condid):
            entry = self.db.query(ConditionEntry).filter_by(id=int(condid))
            msg = ""
            if entry is None:
                msg = "No conditions with that ID"
            else:
                entry.delete()
                self.db.commit()
                msg = "Condition {} deleted".format(condid)
                
            await ctx.bot.send_message(ctx.message.channel, msg)

        @self.bot.command(pass_context=True, no_pm=True)
        async def rule(ctx, condid):
            centry = self.db.query(ConditionEntry).filter_by(id=int(condid))
            if centry is None:
                await ctx.bot.send_message(ctx.message.channel, "No condition with that ID")
                return
                
            r = Rule(condid=int(condid), serverid=ctx.message.server.id)
            self.db.add(r)
            self.db.commit()

            await ctx.bot.send_message(ctx.message.channel, "Rule added ({})".format(r.id))

        @self.bot.command(pass_context=True, no_pm=True)
        async def onrule(ctx, ruleid, actionid):
            rule = self.db.query(Rule).filter_by(id=int(ruleid)).first()
            if rule is None:
                return

            aentry = self.db.query(ActionEntry).filter_by(id=int(actionid)).first()
            if aentry is None:
                return

            aentry.ruleid = rule.id
            self.db.commit()

            await ctx.bot.send_message(ctx.message.channel, "Success")

        @self.bot.command(pass_context=True, no_pm=True)
        async def rules(ctx):
            rules = self.db.query(Rule).filter_by(serverid=ctx.message.server.id)
            rulestr = "\n".join([str(rule) for rule in rules])
            await ctx.bot.send_message(ctx.message.channel, "```{}```".format(rulestr))

        @self.bot.command(pass_context=True, no_pm=True)
        async def ruledesc(ctx, ruleid):
            rule = self.db.query(Rule).filter_by(id=int(ruleid)).first()
            if rule is None:
                await ctx.bot.send_message(ctx.message.channel, "No rule by that ID")

            condentry = self.db.query(ConditionEntry).filter_by(id=rule.condid).first()
            cond = str(condentry.load_instance(self.db))

            actentries = self.db.query(ActionEntry).filter_by(ruleid=rule.id)
            actions = [str(actentry.load_instance(self.db)) for actentry in actentries]

            msg = "RULE {}\n".format(rule.id)
            msg += "Condition: {}\n".format(cond)
            msg += "Actions:\n"
            msg += "\n".join(actions)

            await ctx.bot.send_message(ctx.message.channel, "```{}```".format(msg))

        @self.bot.listen()
        async def on_message(msg):
            if msg.server is None:
                return

            await self.run_event("on_message", msg.server.id, msg)
            

'''            
class MessageCountCondition(Condition):

    def __init__(self, count, bot, server):
        self.bot = bot
        self.server = server
        self.usercounts = defaultdict(int)
        self.count = count
        
        self.bot.loop.create_task(self.loop())
        
    def server_check(self, msg):
        return self.server.id == msg.server.id

    async def loop(self):
        while not self.bot.is_closed:
            msg = await self.bot.wait_for_message(check=self.server_check)
            self.bot.loop.create_task(self.update(message))
        
    async def update(self, message):
        self.increase_user_count(message.author, 1)
        
    # TODO: modify for use with DB
    def get_user_count(self, user):
        return self.usercounts[user.id]
        
    def increase_user_count(self, user, amt):
        self.usercounts[user.id] += amt
        
    def eval(self, user):
        print("Evaluating {} >= {} : {}".format(count, self.count, count >= self.count))
        return self.get_user_count(user) >= self.count
'''     
   
'''   
class ComplementCondition(Condition):
    def __init__(self, condition):
        self.condition = condition
        
    def eval(self, *args, **kwargs):
        return !condition.eval(*args, **kwargs)
        
class HasRoleCondition(Condition):
    def __init__(self, role):
        self.role = role
        
    def eval(self, member):
        mrole = discord.utils.find(lambda m : m.id == self.role.id, member.roles)
        return mrole is not None
        
        
class AddRoleAction(Action):
    def __init__(self, bot, *roles, dbcheck = lambda u,r : (r)):
        self.bot = bot
        self.roles = roles
        #self.dbcheck = dbcheck

    async def __call__(self, user):
        
        roles = [role for role in self.roles if not role in user.roles]
        print("AddRoleAction {} {} {}".format([role.name for role in roles], self.roles, user.roles))
        if len(roles) > 0:
            await self.bot.add_roles(user, *roles)
'''