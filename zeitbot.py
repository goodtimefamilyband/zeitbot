#zeitbot.py

import sys
if len(sys.argv) == 1:
    print("Usage: ipython {} token".format(sys.argv[0]))
    sys.exit()
    
token = sys.argv[1]

from app import bot
from zeitlog import Zeitlog
from heartbeat import Graphlog
from rcounter import ReactCounter

from app.schema import Session
db_session = Session()

zlogger = Zeitlog(db_session)
glogger = Graphlog('graphs')
rlogger = ReactCounter()

bot.run(token)
