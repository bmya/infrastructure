# Supported provider API types
#   data ID must match
GOOGLE_COMPUTE_ENGINE = 1
DIGITAL_OCEAN = 2

# Server status
#   data ID must match*
INITIAL_SETUP = 1
ACTIVE = 2
STOPPED = 3
WAITING_FOR_DEPLOYMENT = 4
WAITING_FOR_SCRIPT_ACTION = 5
WAITING_FOR_STOP = 6
WAITING_FOR_DELETE = 7
WAITING_FOR_REBOOT = 8
#   *alias
WAITING_FOR_START = 8
