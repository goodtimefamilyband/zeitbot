#adminbot.py

import sys
if len(sys.argv) == 1:
    print("Usage: ipython {} token".format(sys.argv[0]))
    sys.exit()
    
token = sys.argv[1]

from adminlog import adminbot, AdminLogger
from adminlog.classes import RuleRepo
from adminlog.schema import Session

db = Session()
repo = RuleRepo(db, adminbot)
repo.register_commands()
adminlogger = AdminLogger(db)

adminbot.run(token)
