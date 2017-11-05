#adminlog schema

#from config import SQLALCHEMY_DATABASE_URI, SQL_DEBUG
SQLALCHEMY_DATABASE_URI = 'sqlite:///adminbot.db'
SQL_DEBUG = False

#import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, ForeignKey, Integer, String, Date, Float, Boolean

import discord
from .classes import MessageCountCondition, AddRoleAction, RuleBase

Base = declarative_base()
engine = create_engine(SQLALCHEMY_DATABASE_URI, echo=SQL_DEBUG)

Session = sessionmaker(bind=engine)    

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
    
class Rule(Base, RuleBase):
    __tablename__ = "rules"
    
    id = Column(Integer, primary_key=True)
    serverid = Column(String, ForeignKey('servers.id'))
    mincount = Column(Integer, default=0)
    
    def load_rule(self, bot, db):
        self.condition = MessageCountCondition(self.mincount)
        server = discord.utils.find(lambda s : s.id == self.serverid, bot.servers)
        roles = [r.find_role(server) for r in db.query(Role).join(RuleRole, Role.id == RuleRole.roleid).filter(RuleRole.ruleid == self.id)]
        
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
        

class Role(Base):
    __tablename__ = "roles"
    
    id = Column(String, primary_key=True)
    
    def find_role(self, server):
        return discord.utils.find(lambda r : r.id == self.id, server.roles)
        
class RuleRole(Base):
    __tablename__ = "rule_role"
    
    ruleid = Column(Integer, ForeignKey('rules.id'), primary_key=True)
    roleid = Column(String, ForeignKey('roles.id'), primary_key=True)
    
class RoleException(Base):
    __tablename__ = "role_exceptions"
    
    ruleid = Column(Integer, ForeignKey('rules.id'), primary_key=True)
    roleid = Column(String, ForeignKey('roles.id'), primary_key=True)
    memberid = Column(String, ForeignKey('members.id'), primary_key=True)
    
    
Base.metadata.create_all(engine)