#utils.py

from collections import defaultdict
from datetime import timezone


def naive_utc_to_unix(naive_utc_dt):
    return naive_utc_dt.replace(tzinfo=timezone.utc).timestamp()


class ChannelContainer:

    def __init__(self):
        self.container = defaultdict(dict)
        
    # TODO: Use server ID instead
    def __getitem__(self, channel):
        return self.container[channel.server.name][channel.id]
        
    def __setitem__(self, channel, val):
        self.container[channel.server.name][channel.id] = val
    
    def __contains__(self, channel):
        return channel.id in self.container[channel.server.name]

