#adminlog schema

#from config import SQLALCHEMY_DATABASE_URI, SQL_DEBUG
SQLALCHEMY_DATABASE_URI = 'sqlite:///adminbot.db'
SQL_DEBUG = False

import sys

#import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, ForeignKey, Integer, String, Date, Float, Boolean

import sys
import discord

Base = declarative_base()
engine = create_engine(SQLALCHEMY_DATABASE_URI, echo=SQL_DEBUG)

Session = sessionmaker(bind=engine)

listeners = []

def listener(cls):
    listeners.append(cls)

def get_db_member(db, member):
    member = db.query(Member).filter_by(id=member.id).filter_by(serverid=member.server.id).first()
    if member is None:
        member = Member(id=member.id, serverid=member.server.id, name=member.name)
        db.add(member)
        db.commit()
        
    return member
    
class CommandListener:
    def register_listeners(self, bot, db):
        pass
        
class Condition(CommandListener):
    
    addcommand = "addcondition"
    testcommand = "test"
    
    async def evaluate(self, db, bot, *args, **kwargs):
        return False
        
    def add_condition_entry(self, db):
        condentry = ConditionEntry(condclass=type(self).__name__)
        db.add(condentry)
        return condentry
        
class Action(CommandListener):
    
    addcommand = "addaction"

    async def perform(self, db, bot, *args, **kwargs):
        pass
        
    def add_action_entry(self, db):
        actentry = ActionEntry(actclass=type(self).__name__)
        db.add(actentry)
        return actentry

#TODO: use object_session() (or similar)?

class Server(Base):
    __tablename__ = "servers"
    
    id = Column(String, primary_key=True)
    after = Column(Float)
    
    def load_rules(self, bot, db):
        self.ruleset = db.query(Rule).filter_by(serverid=self.id).all()
        for rule in self.ruleset:
            rule.load_rule(bot, db)


#TODO: Inherit from this? How to instantiate?    
class Rule(Base):
    __tablename__ = "rules"
    
    id = Column(Integer, primary_key=True)
    serverid = Column(String, ForeignKey('servers.id'))
    condid = Column(Integer)
    event = Column(String)
    
class Member(Base):
    __tablename__ = "members"
    
    id = Column(String, primary_key=True)
    serverid = Column(String, ForeignKey('servers.id'), primary_key=True)
    name = Column(String)

class MemberMessageCount(Base):
    __tablename__ = "membermessagecounts"

    countid = Column(Integer, ForeignKey('membermessagecounters.actid'), primary_key=True)
    memberid = Column(String, ForeignKey("members.id"), primary_key=True)
    msgcount = Column(Integer, default=0)
    
class Role(Base):
    __tablename__ = "roles"
    
    id = Column(String, primary_key=True)
    serverid = Column(String)
    name = Column(String)
    
    def find_discord_role(self, server):
        return discord.utils.find(lambda r : r.id == self.id, server.roles)
        
        

class ConditionEntry(Base):
    __tablename__ = "conditions"
    
    id = Column(Integer, primary_key=True)
    condclass = Column(String, nullable=False)
    
    def load_condition(self, db, mod):
        entryclass = getattr(mod, self.condclass)
        cond = db.query(entryclass).filter_by(condid=self.id).first()
        return cond
    
class ActionEntry(Base):
    __tablename__ = "actions"
    
    id = Column(Integer, primary_key=True)
    ruleid = Column(Integer, ForeignKey('rules.id'))
    actclass = Column(String, nullable=False)
    
@listener
class TrueCondition(Base, Condition):
    __tablename__ = "trueconditions"
    
    condid = Column(Integer, ForeignKey('conditions.id'), primary_key=True)
    
    async def evaluate(*args, **kwargs):
        return True
        
    def register_listeners(self, bot, db):
        addgrp = bot.get_command(Condition.addcommand)
        testgrp = bot.get_command(Condition.testcommand)
        
        if addgrp.get_command("alwaystrue") is None:
            
            @addgrp.command(pass_context=True, no_pm=True)
            async def alwaystrue(ctx):
                condentry = self.add_condition_entry(db)
                condition = TrueCondition(condid=condentry.id)
                db.add(condition)
                db.commit()
                
        if testgrp.get_command("alwaystrue") is None:
            
            @testgrp.command(pass_context=True, no_pm=True)
            async def alwaystrue(ctx, condid):
                cond = db.query(TrueCondition).filter_by(condid=condid).first()
                if cond is None:
                    await ctx.bot.send_message(ctx.message.channel, "Could not find condition with ID " + condid)
                    return
                
                result = cond.evaluate()
                ctx.bot.send_message(ctx.message.channel, "Result: " + result)
                
@listener
class ComplementCondition(Base, Condition):
    __tablename__ = 'complements'
    
    condid = Column(Integer, ForeignKey('conditions.id'), primary_key=True)
    target = Column(Integer, ForeignKey('conditions.id'))
    
    async def evaluate(self, db, bot, *args, **kwargs):
        tgtentry = db.query(ConditionEntry).filter_by(id=self.target).first()
        tgt = tgtentry.load_condition(db, sys.modules[__name__])
        res = await tgt.evaluate(db, bot, *args, **kwargs)
        return not res
        
    def register_listeners(self, bot, db):
        addgrp = bot.get_command(Condition.addcommand)
        testgrp = bot.get_command(Condition.testcommand)
        
        if addgrp.get_command("opposite") is None:
            @addgrp.command(pass_context=True, no_pm=True)
            async def opposite(ctx, target):
                condentry = self.add_action_entry(db)
                cond = ComplementCondition(condid=condentry.id, target=int(target))
                db.add(target)
                db.commit()
                
        # TODO: This should probably handle other types of events
        if testgrp.get_command("opposite") is None:
            @testgrp.command(pass_context=True, no_pm=True)
            async def opposite(ctx, condid):
                cond = db.query(ComplementCondition).filter_by(condid=condid).first()
                if cond is None:
                    await ctx.bot.send_message(ctx.message.channel, "Could not find condition with ID " + condid)
                    return
                
                result = cond.evaluate(db, ctx.bot, msg)
                ctx.bot.send_message(ctx.message.channel, "Result: " + result)
        
class AndCondition(Base, Condition):
    __tablename__ = 'andconditions'
    
    condid = Column(Integer, ForeignKey('conditions.id'), primary_key=True)
    lhand = Column(Integer, ForeignKey('conditions.id'))
    rhand = Column(Integer, ForeignKey('conditions.id'))
    
    async def evaluate(self, db, bot, *args, **kwargs):
        lhandentry = db.query(ConditionEntry).filter_by(id=self.lhand)
        rhandentry = db.query(ConditionEntry).filter_by(id=self.rhand)
        
        lhandcond = lhandentry.load_condition(db, sys.modules[__name__])
        rhandcond = rhandentry.load_condition(db, sys.modules[__name__])
        
        return lhandcond.evaluate(self, db, bot, *args, **kwargs) and rhandcond.evaluate(self, db, bot, *args, **kwargs)
        
class BlacklistEntry:
    __tablename__ = 'roleblacklist'
    
    roleid = Column(String, ForeignKey('roles.id'), primary_key=True)
    memberid = Column(String, ForeignKey('members.id'), primary_key=True)
        
class RoleBlacklist(Base, Condition):
    __tablename__ = 'roleblacklistcond'
    
    condid = Column(Integer, ForeignKey('conditions.id'), primary_key=True)
    roleid = Column(String, ForeignKey('roles.id'), primary_key=True)
    
    async def evaluate(self, db, bot, msg):
        blentry = db.query(BlacklistEntry).filter_by(roleid=self.roleid).filter_by(memberid=msg.author.id).first()
        return blentry is None
    
class MemberMessageQuota(Base, Condition):

    __tablename__ = "msgquotas"

    condid = Column(Integer, ForeignKey('conditions.id'), primary_key=True)
    countid = Column(Integer, ForeignKey('membermessagecounters.actid'))
    count = Column(Integer, nullable=False)
    serverid = Column(String, ForeignKey('servers.id'))
    
    async def evaluate(self, db, bot, msg):
        dbmember = get_db_member(db, msg.author)
        mc_alias = aliased(MemberMessageCount)
        count = db.query(Member).join(mc_alias, Member.id == mc_alias.memberid).\
        filter(mc_alias.msgcount >= self.count).\
        filter(Member.id == dbmember.id).first()
        
        return count is None
        
class RoleChecker(Base, Condition):
    __tablename__ = "rolecheckers"
    
    condid = Column(Integer, ForeignKey('conditions.id'), primary_key=True)
    roleid = Column(String, ForeignKey('roles.id'))
    
    async def evaluate(self, db, bot, msg):
        for role in msg.author.roles:
            if role.id == this.roleid:
                return True
                
        return False
        
class RoleAdderRole(Base):
    __tablename__ = 'roleadderroles'
    
    roleid = Column(String, ForeignKey('roles.id'), primary_key=True)
    actid = actid = Column(Integer, ForeignKey('actions.id'), primary_key=True)
    

class RoleAdder(Base, Action):
    __tablename__ = "roleadders"
    
    actid = Column(Integer, ForeignKey('actions.id'), primary_key=True)
    
    async def perform(self, db, bot, msg):
        rar_alias = aliased(RoleAdderRole)
    
        roles = db.query(Role).\
        join(rar_alias, Role.roleid == rar_alias.roleid).\
        filter(rar_alias.actid == self.actid)
        
        servers = {}
        for role in roles:
            servers[role.serverid] = discord.utils.find(lambda s : s.id == role.serverid, bot.servers)
            
        rolestoadd = [r.find_discord_role(servers[r.serverid]) in roles]
        if len(rolestoadd) > 0:
            await bot.add_roles(msg.author, *rolestoadd)
        
class RoleBlacklister(Base, Action):
    __tablename__ = "blacklisters"
    
    actid = Column(Integer, ForeignKey('actions.id'), primary_key=True)
    roleid = Column(String, ForeignKey('roles.id'))
    
    async def perform(self, db, bot, msg):
        dbmember = get_db_member(db, msg.author)
        blentry = BlacklistEntry(roleid=self.roleid,memberid=dbmember.id)
        db.add(blentry)
        db.commit()
        
        
class MemberMessageCounter(Base, Action):
    __tablename__ = "membermessagecounters"
    
    actid = Column(Integer, ForeignKey('actions.id'), primary_key=True)
    
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
    
Base.metadata.create_all(engine)