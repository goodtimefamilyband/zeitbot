#adminbot.py

import sys
if len(sys.argv) == 1:
    print("Usage: ipython {} token".format(sys.argv[0]))
    sys.exit()
    
token = sys.argv[1]

from adminlog import adminbot, AdminLogger
from adminlog.classes import RuleRepo
from adminlog.schema import listeners, Session

db = Session()
repo = RuleRepo(db, adminbot)
adminlogger = AdminLogger(db)
for listener in listeners:
    listener().register_listeners(adminbot, db)

adminbot.run(token)
