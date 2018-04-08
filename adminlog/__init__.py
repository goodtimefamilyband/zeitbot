import time
from datetime import datetime
from logbot import Logger, Logbot, DiscreteLogbot
from logbot.utils import naive_utc_to_unix
from .classes import RuleRepo
from .schema import Config

adminbot = DiscreteLogbot(command_prefix='a.')

@adminbot.logger
class AdminLogger(Logger):

    def __init__(self, db, confid):
        super().__init__()
        self.db = db
        self.conf = db.query(Config).filter_by(id=confid).first()

        self.repo = RuleRepo(db, adminbot)

    def process_message(self, msg):
        self.client.loop.create_task(self.repo.run_event("on_message", msg.server.id, msg))
        # self.update_after(time.mktime(msg.timestamp.timetuple()))
        # self.update_after(msg.timestamp.total_seconds())
        self.update_after(naive_utc_to_unix(msg.timestamp))
        
    def after_update(self):
        print("after_update")
        self.update_after(self.client.next_after)

    def update_after(self, after):
        if after > self.conf.init_time:
            print("Update after", datetime.fromtimestamp(after))
            self.conf.init_time = after
            # self.db.add(self.conf)
            self.db.commit()
        
    def register_commands(self):
        self.repo.register_commands()

        @self.client.listen()
        async def on_message(msg):
            self.update_after(naive_utc_to_unix(msg.timestamp))
