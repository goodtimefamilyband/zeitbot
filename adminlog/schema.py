#adminlog schema

#from config import SQLALCHEMY_DATABASE_URI, SQL_DEBUG
SQLALCHEMY_DATABASE_URI = 'sqlite:///adminbot.db'
SQL_DEBUG = False

#import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, ForeignKey, Integer, String, Date, Float, Boolean

import sys

import discord
from .classes import Condition, Action, RuleBase

Base = declarative_base()
engine = create_engine(SQLALCHEMY_DATABASE_URI, echo=SQL_DEBUG)

Session = sessionmaker(bind=engine) 

#TODO: use object_session() (or similar)?

class Server(Base):
    __tablename__ = "servers"
    
    id = Column(String, primary_key=True)
    after = Column(Float)
    
    def load_rules(self, bot, db):
        self.ruleset = db.query(Rule).filter_by(serverid=self.id).all()
        for rule in self.ruleset:
            rule.load_rule(bot, db)
    
class Member(Base):
    __tablename__ = "members"
    
    id = Column(String, primary_key=True)
    serverid = Column(String, ForeignKey('servers.id'), primary_key=True)
    msgcount = Column(Integer, default=0)

class Role(Base):
    __tablename__ = "roles"
    
    id = Column(String, primary_key=True)
    
    def find_discord_role(self, server):
        return discord.utils.find(lambda r : r.id == self.id, server.roles)
        

class RuleRole(Base):
    __tablename__ = "rule_role"
    
    ruleid = Column(Integer, ForeignKey('rules.id'), primary_key=True)
    roleid = Column(String, ForeignKey('roles.id'), primary_key=True)

    
class DBClass(Base):
    __tablename__ = "classes"
    
    id = Column(Integer, primary_key=True)
    classname = Column(String)
#    datatbl = Column(String)
    
class ConditionBase(Condition):
    id = Column(Integer, primary_key=True)
    
class ActionBase(Action)
    id = Column(Integer, primary_key=True)
    
class MessageCountCondition(ConditionBase):

    __tablename__ = "msgcounts"

    count = Column(Integer, default=0)
    serverid = Column(Integer, ForeignKey('servers.id'))

    '''
    def __init__(self, count, bot, server):
        self.bot = bot
        self.server = server
        self.usercounts = defaultdict(int)
        self.count = count
        
        self.bot.loop.create_task(self.loop())
    '''
        
    def server_check(self, msg):
        return self.server.id == msg.server.id

    '''
    async def loop(self):
        while not self.bot.is_closed:
            msg = await self.bot.wait_for_message(check=self.server_check)
            self.bot.loop.create_task(self.update(message))
        
    async def update(self, message):
        self.increase_user_count(message.author, 1)
    '''
    
    # TODO: modify for use with DB
    def get_user_count(self, user, db):
        m = db.query(Member).filter_by(id=user.id)
        return m.msgcount
        
    def increase_user_count(self, user, amt, db):
        #self.usercounts[user.id] += amt
        m = db.query(Member).filter_by(id=user.id)
        m.msgcount += amt
        db.add(m)
        db.commit()
        
    def eval(self, user):
        print("Evaluating {} >= {} : {}".format(count, self.count, count >= self.count))
        return self.get_user_count(user) >= self.count
    

class AddRoleAction(ActionBase):
    #def __init__(self, bot, *roles, dbcheck = lambda u,r : (r)):
    serverid = Column(Integer, ForeignKey('servers.id'))
    
    def get_roles(self, db, server):
        return [r.find_discord_role(server) for r in db.query(Role).join(RuleRole, Role.id == RuleRole.roleid).filter(RuleRole.ruleid == self.id)]
    
    async def __call__(self, dmember, db, client):
        roles = [role for role in self.get_roles(db, dmember.server) if not role in dmember.roles]
        #print("AddRoleAction {} {} {}".format([role.name for role in roles], self.roles, user.roles))
        if len(roles) > 0:
            await client.add_roles(user, *roles)

class DBRule(Base):
    __tablename__ = "rules"
    
    id = Column(Integer, primary_key=True)
    serverid = Column(String, ForeignKey('servers.id'))
    classname = Column(String)
    
    def get_rule(self, db):
        return db.query(getattr(sys.modules[__name__], classname)).filter_by(id=self.id).first())

class MessageCountRoleAddRule(Base, RuleBase):
    __tablename__ = "messagecountrolerules":
    
    id = Column(Integer, ForeignKey('rules.id'), primary_key = True)
    condid = Column(Integer)
    actid = Column(Integer)
    
    def register(self, db):
        
    
#TODO: Inherit from this? How to instantiate?    
class Rule(Base, RuleBase):
    __tablename__ = "rules"
    
    id = Column(Integer, primary_key=True)
    serverid = Column(String, ForeignKey('servers.id'))
    condtype = Column(String)
    condid = Column(Integer)
    acttype = Column(String)
    actid = Column(Integer)
    event = Column(String)
    
    def get_condition(self, db):
        #return db.query(getattr(sys.modules[__name__], self.condtype)).filter_by(id=self.condid).first()
        return self.get_instance(db, self.condtype, self.condid)
        
    def get_action(self, db):
        #return db.query(getattr(sys.modules[__name__], self.condtype)).filter_by(id=self.condid).first()
        return self.get_instance(db, self.acttype, self.actid)
        
    def get_instance(self, db, classname, id):
        return db.query(getattr(sys.modules[__name__], classname)).filter_by(id=id).first()
    
    
    '''
    def load_rule(self, bot, db):
        self.condition = MessageCountCondition(self.mincount)
        server = discord.utils.find(lambda s : s.id == self.serverid, bot.servers)
        roles = [r.find_discord_role(server) for r in db.query(Role).join(RuleRole, Role.id == RuleRole.roleid).filter(RuleRole.ruleid == self.id)]
        
        print(roles)
        self.action = AddRoleAction(bot, *roles)
        
    def dbcheckfun(self, db):
        
        def check(u,r):
            newroles = {}
            for role in r:
                newroles[role.id] = role
            for rexcept in db.query(RoleException).filter_by(ruleid=self.id, memberid=u.id):
                del newroles[rexcept.roleid]
                
            return newroles.values()
            
        return check
        
    def __str__(self):
        try:
            return "({}) Roles added after {} messages: {}".format(self.id, self.mincount, ",".join([r.name for r in self.action.roles]))
        except AttributeError:
            return ""
    '''    


'''    
class RoleException(Base):
    __tablename__ = "role_exceptions"
    
    ruleid = Column(Integer, ForeignKey('rules.id'), primary_key=True)
    roleid = Column(String, ForeignKey('roles.id'), primary_key=True)
    memberid = Column(String, ForeignKey('members.id'), primary_key=True)
'''    
    
Base.metadata.create_all(engine)