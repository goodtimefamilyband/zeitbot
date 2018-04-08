# adminbot.py

import time
import sys
from adminlog import adminbot, AdminLogger
from adminlog.schema import Session, Config

if len(sys.argv) == 1:
    print("Usage: ipython {} token".format(sys.argv[0]))
    sys.exit()
    
token = sys.argv[1]

db = Session()
conf = db.query(Config).first()
if conf is None:
    conf = Config(init_time=time.time())
    db.add(conf)
    db.commit()

adminbot.after = conf.init_time
adminlogger = AdminLogger(db, conf.id)

adminbot.run(token)
