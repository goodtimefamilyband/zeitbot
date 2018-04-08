import time
from logbot import Logger, Logbot, DiscreteLogbot
from .classes import RuleRepo
from .schema import Config

adminbot = DiscreteLogbot(command_prefix='a.')
# adminbot = commands.Bot(command_prefix='a.')


@adminbot.logger
class AdminLogger(Logger):

    def __init__(self, db, confid):
        super().__init__()
        self.db = db
        self.conf = db.query(Config).filter_by(id=confid)

        self.repo = RuleRepo(db, adminbot)

    def process_message(self, msg):
        self.client.loop.create_task(self.repo.run_event("on_message", msg.server.id, msg))
        
    def after_update(self):
        self.update_after(self.client.before)

    def update_after(self, after):
        self.conf.init_time = after
        self.db.commit()
        
    def register_commands(self):

        self.repo.register_commands()

        @self.client.listen()
        async def on_message(msg):
            # client.after = client.before once loop is done
            self.client.before = time.mktime(msg.timestamp.timetuple())
            self.update_after(self.client.before)
