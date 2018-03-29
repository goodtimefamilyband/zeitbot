import sys
import discord
from collections import defaultdict

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
        rules = self.db.query(Rule).filter_by(serverid=serverid).filter_by(event=eventtype)
        
        #TODO: Use a join instead
        for rule in rules:
            condentry = self.db.query(ConditionEntry).filter_by(id=rule.condid).first()
            condclass = getattr(schema, condentry.condclass)
            cond = self.db.query(condclass).filter_by(condid=rule.condid).first()
            condresult = await cond.evaluate(self.db, self.bot, *args, **kwargs)
            
            if condresult:
                actentries = self.db.query(ActionEntry).filter_by(ruleid=rule.id)
                for actentry in actentries:
                    actclass = getattr(schema, actentry.actclass)
                    action = self.db.query(actclass).filter_by(actionid=actentry.id).first()
                    self.bot.loop.create_task(action.perform(self.db, self.bot, *args, **kwargs))

# TODO: Create initializer class/function, move to schema                    
# repo = RuleRepo(schema.Session(), __init__.adminbot)

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