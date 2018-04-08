from .schema import listeners, ConditionEntry, ActionEntry, Rule, Condition, Action, Role
from sqlalchemy import or_
from discord.ext import commands


class RuleRepo:
    def __init__(self, db, client):
        self.db = db
        self.bot = client

    def admin_check(self, ctx):
        perms = ctx.message.author.permissions_in(ctx.message.channel)
        if not perms.administrator:
            dbroles = self.db.query(Role).filter_by(is_admin=True).filter(Role.id.in_([r.id for r in ctx.message.author.roles])).all()
            if len(dbroles) == 0:
                return False

        return True

    async def run_message_event(self, msg):
        rules = self.db.query(Rule, ConditionEntry). \
            join(ConditionEntry, Rule.condid == ConditionEntry.id). \
            filter(Rule.serverid == msg.server.id). \
            filter(or_(ConditionEntry.event == "on_message", ConditionEntry.event == None))

        for (rule, condentry) in rules:
            print(rule, condentry)
            cond = condentry.load_instance(self.db)
            condresult = await cond.evaluate(self.db, self.bot, msg)

            if condresult:
                actentries = self.db.query(ActionEntry).filter_by(ruleid=rule.id)
                for actentry in actentries:
                    action = actentry.load_instance(self.db)

                    if actentry.event == "on_message":
                        self.bot.loop.create_task(action.perform(self.db, self.bot, msg))
                    elif actentry.event == "on_user":
                        self.bot.loop.create_task(action.perform(self.db, self.bot, msg.author))

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
                    action = actentry.load_instance(self.db)
                    self.bot.loop.create_task(action.perform(self.db, self.bot, *args, **kwargs))
                    
    def register_commands(self):

        @commands.check(self.admin_check)
        @self.bot.group(pass_context=True)
        async def addc(ctx):
            pass
            
        @self.bot.group(pass_context=True)
        async def test(ctx):
            print("test[ctx={}]".format(ctx))

        @commands.check(self.admin_check)
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

            listener().register_listeners(self.bot, self.db, addgrp=addgrp, testgrp=test, infogrp=info, checkfun=self.admin_check)
        
        @self.bot.event
        async def on_ready():
            pass

        async def send_entry_list(ctx, entries):
            lst = "\n".join(["{} {}".format(entry.id, str(entry.load_instance(self.db))) for entry in entries])
            msg = "```{}```".format(lst)
            await ctx.bot.send_message(ctx.message.channel, msg)

        @self.bot.command(pass_context=True, no_pm=True)
        async def conditions(ctx):
            entries = self.db.query(ConditionEntry)
            await send_entry_list(ctx, entries)

        @self.bot.command(pass_context=True, no_pm=True)
        async def actions(ctx):
            entries = self.db.query(ActionEntry).filter_by(ruleid=None)
            await send_entry_list(ctx, entries)

        @commands.check(self.admin_check)
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

        @commands.check(self.admin_check)
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

        @commands.check(self.admin_check)
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
            actions = ["{} {}".format(actentry.id, str(actentry.load_instance(self.db))) for actentry in actentries]

            msg = "RULE {}\n".format(rule.id)
            msg += "Condition: {}\n".format(cond)
            msg += "Actions:\n"
            msg += "\n".join(actions)

            await ctx.bot.send_message(ctx.message.channel, "```{}```".format(msg))

        @commands.check(self.admin_check)
        @self.bot.command(pass_context=True, no_pm=True)
        async def ruledel(ctx, ruleid):
            rule = self.db.query(Rule).filter_by(id=int(ruleid))
            if rule is not None:
                rule.delete()
                self.db.commit()

                await ctx.bot.send_message(ctx.message.channel, "Rule {} deleted".format(ruleid))

        @self.bot.listen()
        async def on_message(msg):
            if msg.server is None:
                return

            await self.run_message_event(msg)
