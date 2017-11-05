
class Condition:
    def eval(self, *args):
        pass
        
class Action:
    async def __call__(self, *args, **kwargs):
        pass

class RuleBase:

    '''
    def __init__(self, condition, action):
        self.condition = condition
        self.action = action
    '''
    
    async def __call__(self, condargs, actargs):
        if self.condition.eval(*condargs):
            await self.action(*actargs)
            
        
class MessageCountCondition(Condition):

    def __init__(self, count):
        self.count = count

    def eval(self, count):
        print("Evaluating {} >= {} : {}".format(count, self.count, count >= self.count))
        return count >= self.count
        
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
