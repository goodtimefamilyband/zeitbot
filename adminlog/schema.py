from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, aliased
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy import Column, ForeignKey, Integer, String, Date, Float, Boolean

import sys
import discord
from discord.ext import commands

SQLALCHEMY_DATABASE_URI = 'sqlite:///adminbot.db'
SQL_DEBUG = False

Base = declarative_base()
engine = create_engine(SQLALCHEMY_DATABASE_URI, echo=SQL_DEBUG)

Session = sessionmaker(bind=engine)

listeners = []


def listener(cls):
    listeners.append(cls)
    return cls


class Config(Base):
    __tablename__ = "config"

    id = Column(Integer, primary_key=True)
    init_time = Column(Integer)


class EntryFactory:

    def __init__(self, entrycls):
        self.cls = entrycls

    def __call__(self, cls, *args, **kwargs):
        class NewFactory(cls):
            def add_entry(this, db, event=None):
                entry = self.cls(entryclass=type(this).__name__, entrymod=this.__module__, event=event)
                db.add(entry)
                db.commit()
                return entry

        return NewFactory


def get_db_member(db, member):
    dbmember = db.query(Member).filter_by(id=member.id).filter_by(serverid=member.server.id).first()
    if dbmember is None:
        dbmember = Member(id=member.id, serverid=member.server.id, name=member.name)
        db.add(dbmember)
        db.commit()
        
    return dbmember


def get_db_roles(db, *roles):
    dbroles = []
    for role in roles:
        dbrole = db.query(Role).filter_by(id=role.id).filter_by(serverid=role.server.id).first()
        if dbrole is None:
            dbrole = Role(id=role.id, serverid=role.server.id, name=role.name)
            db.add(dbrole)
            db.commit()

        dbroles.append(dbrole)

    return dbroles


class EntryMixIn:

    @declared_attr
    def id(self):
        return Column(Integer, primary_key=True)

    @declared_attr
    def entryclass(self):
        return Column(String, nullable=False)

    @declared_attr
    def entrymod(self):
        return Column(String, nullable=False)

    @declared_attr
    def event(self):
        return Column(String)

    def load_instance(self, db):

        entrycls = getattr(sys.modules[self.entrymod], self.entryclass)

        # TODO: Make this not stupid
        if issubclass(entrycls, Condition):
            argkey = "condid"
        elif issubclass(entrycls, Action):
            argkey = "actid"

        kwargs = {}
        kwargs[argkey] = self.id
        inst = db.query(entrycls).filter_by(**kwargs).first()
        return inst


class ConditionEntry(Base, EntryMixIn):
    __tablename__ = "conditions"


class ActionEntry(Base, EntryMixIn):
    __tablename__ = "actions"

    ruleid = Column(Integer, ForeignKey('rules.id', onupdate="CASCADE", ondelete="SET NULL"))


class CondIdMixin:
    
    @declared_attr
    def condid(self):
        return Column(Integer, ForeignKey('conditions.id', onupdate="CASCADE", ondelete="CASCADE"), primary_key=True)


class ActIdMixin:

    @declared_attr
    def actid(self):
        return Column(Integer, ForeignKey('actions.id', onupdate="CASCADE", ondelete="CASCADE"), primary_key=True)


class ServerIdMixin:
    
    @declared_attr
    def serverid(self):
        return Column(String, ForeignKey('servers.id'))


class CommandListener:
    def register_listeners(self, bot, db, addgrp=None, testgrp=None, infogrp=None, checkfun=None):
        pass
        
    def __str__(self):
        return type(self).__name__


@EntryFactory(entrycls=ConditionEntry)
class Condition(CommandListener, CondIdMixin):
    
    addcommand = "addcondition"
    testcommand = "test"
    
    async def evaluate(self, db, bot, *args, **kwargs):
        return False

    async def testmsg(self, db, ctx, cls, condid):
        cond = db.query(cls).filter_by(condid=condid).first()
        if cond is None:
            await ctx.bot.send_message(ctx.message.channel, "Could not find condition with ID " + condid)
            return

        result = await cond.evaluate(db, ctx.bot, ctx.message)
        await ctx.bot.send_message(ctx.message.channel, "Result: " + str(result))


@EntryFactory(entrycls=ActionEntry)
class Action(CommandListener, ActIdMixin):
    
    addcommand = "addaction"

    async def perform(self, db, bot, *args, **kwargs):
        pass


# TODO: use object_session() (or similar)?
class Server(Base):
    __tablename__ = "servers"
    
    id = Column(String, primary_key=True)
    after = Column(Float)


# TODO: Inherit from this? How to instantiate?
class Rule(Base, CondIdMixin):
    __tablename__ = "rules"
    
    id = Column(Integer, primary_key=True)
    serverid = Column(String, ForeignKey('servers.id'))
    condid = Column(Integer, ForeignKey('conditions.id', onupdate="CASCADE", ondelete="CASCADE"))

    def __str__(self):
        return "{} (Condition: {})".format(self.id, self.condid)


class Member(Base):
    __tablename__ = "members"
    
    id = Column(String, primary_key=True)
    serverid = Column(String, ForeignKey('servers.id'), primary_key=True)
    name = Column(String)


class Role(Base):
    __tablename__ = "roles"
    
    id = Column(String, primary_key=True)
    serverid = Column(String)
    name = Column(String)
    is_admin = Column(Boolean, default=False)
    
    def find_discord_role(self, server):
        return discord.utils.find(lambda r : r.id == self.id, server.roles)

    
@listener
class TrueCondition(Base, Condition):
    __tablename__ = "trueconditions"
    
    async def evaluate(*args, **kwargs):
        return True
        
    def register_listeners(self, bot, db, addgrp=None, testgrp=None, **kwargs):
        if addgrp is not None and addgrp.get_command("alwaystrue") is None:
            
            @addgrp.command(pass_context=True, no_pm=True)
            async def alwaystrue(ctx):
                condentry = self.add_entry(db)
                print(condentry.id, condentry.entryclass, type(TrueCondition))
                
                condition = TrueCondition(condid=condentry.id)
                db.add(condition)
                db.commit()
                
                await ctx.bot.send_message(ctx.message.channel, "Added condition ({})".format(condentry.id))
                
        if testgrp is not None and testgrp.get_command("alwaystrue") is None:
            
            @testgrp.command(pass_context=True, no_pm=True)
            async def alwaystrue(ctx, condid):
                cond = db.query(TrueCondition).filter_by(condid=condid).first()
                if cond is None:
                    await ctx.bot.send_message(ctx.message.channel, "Could not find condition with ID " + condid)
                    return
                
                result = await cond.evaluate()
                await ctx.bot.send_message(ctx.message.channel, "Result: " + str(result))
                

@listener
class ComplementCondition(Base, Condition):
    __tablename__ = 'complements'
    
    target = Column(Integer, ForeignKey('conditions.id', onupdate="CASCADE", ondelete="CASCADE"))
    
    async def evaluate(self, db, bot, *args, **kwargs):
        tgtentry = db.query(ConditionEntry).filter_by(id=self.target).first()
        tgt = tgtentry.load_instance(db)
        res = await tgt.evaluate(db, bot, *args, **kwargs)
        return not res
        
    def register_listeners(self, bot, db, addgrp=None, testgrp=None, **kwargs):
        if addgrp is not None and addgrp.get_command("opposite") is None:
            @addgrp.command(pass_context=True, no_pm=True)
            async def opposite(ctx, target):
                print("opposite", ctx, target)
                target = int(target)
                
                tgtentry = db.query(ConditionEntry).filter_by(id=target).first()
                if tgtentry is None:
                    ctx.bot.send_message(ctx.message.channel, "Target condition not found")
                    return
                    
                tgtcond = tgtentry.load_instance(db)
                
                condentry = self.add_entry(db, event=tgtentry.event)
                cond = ComplementCondition(condid=condentry.id, target=target)
                db.add(cond)
                db.commit()
                
                await ctx.bot.send_message(ctx.message.channel, "Added condition ({})".format(condentry.id))
                
        # TODO: This should probably handle other types of events
        if testgrp is not None and testgrp.get_command("opposite") is None:
            @testgrp.command(pass_context=True, no_pm=True)
            async def opposite(ctx, condid):
                cond = db.query(ComplementCondition).filter_by(condid=condid).first()
                if cond is None:
                    await ctx.bot.send_message(ctx.message.channel, "Could not find condition with ID " + condid)
                    return
                
                result = await cond.evaluate(db, ctx.bot, ctx.message)
                await ctx.bot.send_message(ctx.message.channel, "Result: " + str(result))
                
    def __str__(self):
        return "Opposite({})".format(self.target)


@listener
class AndCondition(Base, Condition):
    __tablename__ = 'andconditions'
    
    lhand = Column(Integer, ForeignKey('conditions.id'))
    rhand = Column(Integer, ForeignKey('conditions.id'))

    async def evaluate(self, db, bot, *args, **kwargs):
        lhandentry = db.query(ConditionEntry).filter_by(id=self.lhand).first()
        rhandentry = db.query(ConditionEntry).filter_by(id=self.rhand).first()
        
        lhandcond = lhandentry.load_instance(db)
        rhandcond = rhandentry.load_instance(db)
        
        return await lhandcond.evaluate(db, bot, *args, **kwargs) and await rhandcond.evaluate(db, bot, *args, **kwargs)
        
    def register_listeners(self, bot, db, addgrp=None, testgrp=None, **kwargs):
        if addgrp is not None and addgrp.get_command("andc") is None:
            
            @addgrp.command(pass_context=True, no_pm=True)
            async def andc(ctx, left, right):
                leftcond = db.query(ConditionEntry).filter_by(id=int(left)).first()
                if leftcond is None:
                    return
                
                rightcond = db.query(ConditionEntry).filter_by(id=int(right)).first()
                if rightcond is None:
                    return

                if leftcond.event != rightcond.event:
                    await ctx.bot.send_message("Condition event types do not match")
                    return
                
                entry = self.add_entry(db, event=leftcond.event)
                cond = AndCondition(condid=entry.id, lhand=int(left), rhand=int(right))
                db.add(cond)
                db.commit()
                
                await ctx.bot.send_message(ctx.message.channel, "Added condition ({})".format(cond.condid))
                
        if testgrp is not None and testgrp.get_command("andc") is None:
            
            @testgrp.command(pass_context=True, no_pm=True)
            async def andc(ctx, condid, *args):
                cond = db.query(AndCondition).filter_by(condid=condid).first()
                if cond is None:
                    await ctx.bot.send_message(ctx.message.channel, "Could not find condition with ID " + condid)
                    return
                
                result = await cond.evaluate(db, bot, ctx.message)
                await ctx.bot.send_message(ctx.message.channel, "Result: " + str(result))
        
    # TODO: object_session? what even is that?
    def __str__(self):
        # lentry = self.db.query(ConditionEntry).filter_by(id=self.lhand).first()
        # rentry = self.db.query(ConditionEntry).filter_by(id=self.rhand).first()
        
        # lhandcond = lentry.load_condition(db, sys.modules[__name__])
        # rhandcond = rentry.load_condition(db, sys.modules[__name__])
        
        return "({} AND {})".format(self.lhand, self.rhand)


class RoleChecker(Base, Condition):
    __tablename__ = "rolecheckers"
    
    roleid = Column(String, ForeignKey('roles.id'))
    
    async def evaluate(self, db, bot, msg):
        for role in msg.author.roles:
            if role.id == self.roleid:
                return True
                
        return False
        

class RoleAdderRole(Base):
    __tablename__ = 'roleadderroles'
    
    roleid = Column(String, ForeignKey('roles.id'), primary_key=True)
    actid = Column(Integer, ForeignKey('actions.id'), primary_key=True)
    

class RoleAdder(Base, Action):
    __tablename__ = "roleadders"
    
    async def perform(self, db, bot, member):
        rar_alias = aliased(RoleAdderRole)
    
        roles = db.query(Role).\
        join(rar_alias, Role.roleid == rar_alias.roleid).\
        filter(rar_alias.actid == self.actid)
        
        servers = {}
        for role in roles:
            servers[role.serverid] = discord.utils.find(lambda s : s.id == role.serverid, bot.servers)
            
        rolestoadd = [r.find_discord_role(servers[r.serverid]) for r in roles]
        if len(rolestoadd) > 0:
            await bot.add_roles(member, *rolestoadd)

    def register_listeners(self, bot, db, addgrp=None, testgrp=None, infogrp=None, checkfun=None):
        if addgrp is not None and addgrp.get_command("roleadd") is None:

            @commands.check(has_role_mentions)
            @addgrp.command(pass_context=True, no_pm=True)
            async def roleadd(ctx, *args):
                dbroles = get_db_roles(db, ctx.message.role_mentions)
                entry = self.add_entry(db, event="on_user")
                act = RoleAdder(actid=entry.id)
                db.add(act)

                for dbrole in dbroles:
                    db.add(RoleAdderRole(actid=entry.id, roleid=dbrole.id))

                db.commit()
                await ctx.bot.send_message("Action added ({})".format(entry.id))

        if infogrp is not None and infogrp.get_command("roleadd" is None):
            @infogrp.command(pass_context=True, no_pm=True)
            async def roleadd(ctx, actid):
                rars = db.query(RoleAdderRole, Role).\
                    join(Role, RoleAdderRole.roleid == Role.id).\
                    filter(RoleAdderRole.actid == int(actid))

                msg = "\n".join([r.name for rar, r in rars])
                await ctx.bot.send_message(ctx.message.channel, "``` {} ```".format(msg))


class BlacklistEntry(Base):
    __tablename__ = 'roleblacklist'

    roleid = Column(String, ForeignKey('roles.id'), primary_key=True)
    memberid = Column(String, ForeignKey('members.id'), primary_key=True)


def has_role_mentions(ctx):
    return len(ctx.message.role_mentions) > 0


@listener
class RoleBlacklist(Base, Condition):
    __tablename__ = 'roleblacklistcond'

    roleid = Column(String, ForeignKey('roles.id'))

    async def evaluate(self, db, bot, msg):
        blentry = db.query(BlacklistEntry).filter_by(roleid=self.roleid).filter_by(memberid=msg.author.id).first()
        return blentry is None

    def register_listeners(self, bot, db, addgrp=None, testgrp=None, infogrp=None, **kwargs):
        if addgrp is not None and addgrp.get_command("rblc") is None:
            @commands.check(has_role_mentions)
            @addgrp.command(pass_context=True, no_pm=True)
            async def rblc(ctx, *roles):
                dbroles = get_db_roles(db, ctx.message.role_mentions[0])
                entry = self.add_entry(db, event="on_message")
                cond = RoleBlacklist(condid=entry.id, roleid=dbroles[0].id)
                db.add(cond)
                db.commit()

                await ctx.bot.send_message(ctx.message.channel, "Condition added ({})".format(entry.id))

        if testgrp is not None and testgrp.get_command("rblc") is None:
            @testgrp.command(pass_context=True, no_pm=True)
            async def rblc(ctx, condid):
                await self.testmsg(db, ctx, RoleBlacklist, condid)


@listener
class RoleBlacklister(Base, Action):
    __tablename__ = "blacklisters"
    
    roleid = Column(String, ForeignKey('roles.id'))
    
    async def perform(self, db, bot, msg):
        dbmember = get_db_member(db, msg.author)
        blentry = BlacklistEntry(roleid=self.roleid,memberid=dbmember.id)
        db.add(blentry)
        db.commit()

    def register_listeners(self, bot, db, addgrp=None, testgrp=None, infogrp=None, checkfun=None, **kwargs):
        if addgrp is not None and addgrp.get_command('rbla') is None:
            @addgrp.command(pass_context=True, no_pm=True)
            @commands.check(has_role_mentions)
            async def rbla(ctx, *roles):
                dbroles = get_db_roles(db, ctx.message.role_mentions[0])
                entry = self.add_entry(db, event="on_message")
                act = RoleBlacklister(actid=entry.id, roleid=dbroles[0].id)
                db.add(act)
                db.commit()

                await ctx.bot.send_message(ctx.message.channel, "Action added ({})".format(entry.id))

        if infogrp is not None and infogrp.get_command('rbla') is None:
            @infogrp.command(pass_context=True, no_pm=True)
            async def rbla(ctx, actid, *args):
                act = db.query(RoleBlacklister).filter_by(actid=int(actid)).first()

                members = ctx.message.mentions
                if len(members) == 0:
                    members = [ctx.message.author]

                bls = []
                for member in members:
                    bls.append((member, db.query(BlacklistEntry).filter_by(memberid=member.id).filter_by(roleid=act.roleid).first()))

                msg = "\n".join(["{}: {}".format(m.name, "N" if bl is None else "Y") for (m, bl) in bls])
                await ctx.bot.send_message(ctx.message.channel, "``` {} ```".format(msg))

        @commands.check(checkfun)
        @bot.command(pass_context=True, no_pm=True)
        async def bl(ctx, *args):
            """Add a user to a role condition blacklist
            """

            for member in ctx.message.mentions:
                dbmember = get_db_member(db, member)
                for role in get_db_roles(db, *ctx.message.role_mentions):
                    blentry = db.query(BlacklistEntry).filter_by(memberid=dbmember.id).filter_by(roleid=role.id).first()
                    if blentry is None:
                        db.add(BlacklistEntry(roleid=role.id, memberid=dbmember.id))

            db.commit()

        @commands.check(checkfun)
        @bot.command(pass_context=True, no_pm=True)
        async def unbl(ctx, *args):
            """Remove a user from a role condition blacklist
            """

            for member in ctx.message.mentions:
                dbmember = get_db_member(db, member)
                for role in get_db_roles(db, *ctx.message.role_mentions):
                    db.query(BlacklistEntry).filter_by(memberid=dbmember.id).filter_by(roleid=role.id).delete()

            db.commit()


class MemberMessageCount(Base):
    __tablename__ = "membermessagecounts"

    countid = Column(Integer, ForeignKey('membermessagecounters.actid'), primary_key=True)
    memberid = Column(String, ForeignKey("members.id"), primary_key=True)
    msgcount = Column(Integer, default=0)


@listener
class MemberMessageCounter(Base, Action):
    __tablename__ = "membermessagecounters"

    async def perform(self, db, bot, msg):
        dbmember = get_db_member(db, msg.author)
        
        msgcount = db.query(MemberMessageCount).\
        filter_by(countid=self.actid).\
        filter_by(memberid=dbmember.id).\
        first()
        
        if msgcount is None:
            msgcount = MemberMessageCount(countid=self.actid, memberid=dbmember.id, msgcount=0)
            db.add(msgcount)
            
        msgcount.msgcount += 1
        db.commit()

    def register_listeners(self, bot, db, addgrp=None, testgrp=None, infogrp=None, **kwargs):

        if addgrp is not None and addgrp.get_command('mmc') is None:

            @addgrp.command(pass_context=True, no_pm=True)
            async def mmc(ctx):
                entry = self.add_entry(db, event="on_message")
                action = MemberMessageCounter(actid=entry.id)
                db.add(action)
                db.commit()

                await ctx.bot.send_message(ctx.message.channel, "Action added ({})".format(entry.id))

        if infogrp is not None and infogrp.get_command('mmc') is None:

            @infogrp.command(pass_context=True, no_pm=True)
            async def mmc(ctx, countid):
                memberlist = ctx.message.mentions
                if len(memberlist) == 0:
                    memberlist = [ctx.message.author]

                memberdict = {}
                for member in memberlist:
                    memberdict[member.id] = member

                # TODO: Use WHERE memberid IN(...)
                inst = db.query(MemberMessageCounter).filter_by(actid=int(countid)).first()
                membercounts = [db.query(MemberMessageCount).
                                filter_by(countid=inst.actid).
                                filter_by(memberid=member.id).first() for member in memberlist]

                msg = "\n".join(['{} {}'.format(memberdict[count.memberid].name, count.msgcount) for count in membercounts if count is not None])
                await ctx.bot.send_message(ctx.message.channel, "```{}```".format(msg))


@listener
class MemberMessageQuota(Base, Condition):
    __tablename__ = "msgquotas"

    countid = Column(Integer, ForeignKey('membermessagecounters.actid'))
    count = Column(Integer, nullable=False)

    async def evaluate(self, db, bot, msg):
        dbmember = get_db_member(db, msg.author)
        mc_alias = aliased(MemberMessageCount)
        count = db.query(Member).join(mc_alias, Member.id == mc_alias.memberid). \
            filter(mc_alias.msgcount >= self.count). \
            filter(Member.id == dbmember.id). \
            filter(Member.serverid == dbmember.serverid). \
            first()

        return count is not None

    def register_listeners(self, bot, db, addgrp=None, testgrp=None, infogrp=None, **kwargs):
        if addgrp is not None and addgrp.get_command('mmq') is None:
            @addgrp.command(pass_context=True, no_pm=True)
            async def mmq(ctx, countid, count):
                entry = self.add_entry(db, event='on_message')
                cond = MemberMessageQuota(condid=entry.id, countid=int(countid), count=int(count))
                db.add(cond)
                db.commit()

                await ctx.bot.send_message(ctx.message.channel, "Condition added ({})".format(entry.id))

        if testgrp is not None and testgrp.get_command('mmq') is None:
            @testgrp.command(pass_context=True, no_pm=True)
            async def mmq(ctx, condid):
                await self.testmsg(db, ctx, MemberMessageQuota, condid)


Base.metadata.create_all(engine)
