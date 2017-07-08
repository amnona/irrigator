import datetime
import logging

import faucet


logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)


def time_in_range(start_hour, start_minute, duration, test_time=None):
    '''Check whether the current_time is within the time window specified

    Parameters
    ----------
        start_hour : int
            the starting hour (24hr format)
        start_minute: int
            the starting minute (0-60)
        duration : int
            the duration of the time window (in minutes)
        test_time : datetime.datetime or None (optional)
            the time to test whether falls within the window
            None (default) to use the current date/time

    Returns
    -------
        bool
        True if test_time is within the time window, False if not
    '''
    if test_time is None:
        test_time = datetime.datetime.now()
        start_time = datetime.datetime(test_time.year, test_time.month, test_time.day, start_hour, start_minute)
        if start_time > test_time:
            return False
        if start_time + datetime.timedelta(minutes=duration) < test_time:
            return False
        return True

class Timer:
    def __init__(self, duration, cfaucet):
        self.duration = int(duration)
        self.faucet = cfaucet
        self.timer_type = 'generic'

    def __repr__(self):
        return "Timer: " + ', '.join("%s: %s" % item for item in vars(self).items())


class WeeklyTimer(Timer):
    def __init__(self, duration, cfaucet, start_day, start_time):
        super().__init__(duration=duration, cfaucet=cfaucet)
        self.timer_type = 'weekly'
        self.start_day = int(start_day)
        self.start_time = start_time
        logger.debug('timer %s initialized' % self)

    def should_be_open(self):
        now = datetime.datetime.now()
        # is it the correct day now?
        # BUG: should fix if switches to next day during...
        if now.isoweekday()+1 != self.start_day:
            return False
        if not time_in_range(self.start_time.hour, self.start_time.minute, self.duration):
            return False
        return True


class SingleTimer(Timer):
    def __init__(self, duration, cfaucet, start_datetime):
        super().__init__(duration=duration, cfaucet=cfaucet)
        self.start_datetime = start_datetime
        self.end_datetime = start_datetime + datetime.timedelta(minutes=duration)
        self.timer_type = 'single'
        logger.debug('timer %s initialized' % self)

    def should_be_open(self):
        now = datetime.datetime.now()
        if now >= self.start_datetime:
            if now <= self.end_datetime:
                return True
        return False
