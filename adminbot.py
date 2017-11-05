#adminbot.py

import sys
if len(sys.argv) == 1:
    print("Usage: ipython {} token".format(sys.argv[0]))
    sys.exit()
    
token = sys.argv[1]

from adminlog import adminbot, AdminLogger
from adminlog.schema import Session
db_session = Session()

adminlogger = AdminLogger(db_session)
adminbot.run(token)
