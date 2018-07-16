import datetime
import logging

logger = logging.getLogger(__name__)


def sane_day(dt):
    '''Get sane (sun=1,...,sat=7) from isoweekday()

    Parameters
    ----------
    d: datetime.datetime
        the datetime to get the day for

    Returns
    -------
    int:
        the hebrew day num (1=sunday,...,7=sat)
    '''
    return sane_day_from_isoweekday(dt.isoweekday())


def sane_day_from_isoweekday(day):
    '''Convert iso day (1 is monday,..., 7 is sunday) to sane day (1=sunday,...7=saturaday)

    Parameters
    ----------
    day: int
        the isoweekday()

    Returns
    int:
        the hebrew day num (1=sunday,...,7=sat)
    '''
    day = day+1
    if day == 8:
        day = 1
    return day


def next_weekday(d, weekday):
    '''
    Find the closest occurence of weekday following date d.
    if the weekday is the same as the day in d, return d.
    :param d: datetime.datetime
        the start date from where to look for the next day occurance
    :param weekday: int
        the day to look for (1-sunday,....,7-saturday)
    :return:
    datetime.datetime
        The closest datetime to d which is day weekday
    '''
    days_ahead = weekday - sane_day(d)
    if days_ahead < 0:  # Target day already happened this week
        days_ahead += 7
    return d + datetime.timedelta(days_ahead)


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

    def should_be_open(self):
        '''
        Test if timer should be open or closed now

        :return: bool
            True if timer should be open now, False if not
        '''
        raise ValueError('Base class timer - not implemented')

    def should_remove(self):
        '''
        return True if timer should be deleted (i.e. single timer and past the time) otherwise False
        :return:
        '''
        return False


class WeeklyTimer(Timer):
    # Timer that repeats every week on same day/time
    def __init__(self, duration, cfaucet, start_day, start_time):
        '''

        :param duration: int
            duration (minutes)

        :param cfaucet: Faucet
            The Faucet the timer is associated with
        :param start_day: int
            The day to open in (1-sunday...7-saturday)
        :param start_time: datetime.time
            The time (hour:min) to open in
        '''
        super().__init__(duration=duration, cfaucet=cfaucet)
        self.timer_type = 'weekly'
        self.start_day = int(start_day)
        self.start_time = start_time
        # set the overnight flag if the faucet starts before midnight and ends after midnight
        self.overnight = False
        test_start = datetime.datetime.combine(datetime.date.today(), self.start_time)
        test_end = test_start + datetime.timedelta(minutes=self.duration)
        if test_end.day != test_start.day:
            logger.debug('timer %s is overnight' % self)
            self.overnight = True
        logger.debug('timer %s initialized' % self)

    def should_be_open(self):
        '''
        Test if timer should be open or closed now

        :return: bool
            True if timer should be open now, False if not
        '''
        now = datetime.datetime.now()
        if not self.overnight:
            # if not overnight timer, just check day and then time
            # is it the correct day now?
            if sane_day(now) != self.start_day:
                return False
            if not time_in_range(self.start_time.hour, self.start_time.minute, self.duration):
                return False
            return True
        else:
            # overnight timer, so check if current
            next_start = datetime.datetime.combine(next_weekday(now, self.start_day).date(), self.start_time)
            if now < next_start:
                return False
            next_end = next_start + datetime.timedelta(minutes=self.duration)
            if now > next_end:
                return False
            return True

    def should_remove(self):
        # since always there's another week, don't delete
        return False

    def time_to_close(self):
        '''How much time left until the timer ends

        Returns
        -------
        float - the time left to closing (in seconds)
        '''
        now = datetime.datetime.now()
        test_start = datetime.datetime.combine(datetime.date.today(), self.start_time)
        test_end = test_start + datetime.timedelta(minutes=self.duration)
        time_left = (test_end - now).total_seconds()
        return time_left


class SingleTimer(Timer):
    #
    def __init__(self, duration, cfaucet, start_datetime, is_manual=False):
        '''
        Create a single event timer

        :param duration: int
            irrigation duration (minutes)
        :param cfaucet: str
            the faucet name to open
        :param start_datetime: datetime.datetime or None
            the datetime when to open the faucet or None to open now
        :param is_manual: bool (optional)
            True to indicate timer is related to manual open command, False it is not
        '''
        super().__init__(duration=duration, cfaucet=cfaucet)
        print('creating timer')
        if start_datetime is None:
            start_datetime = datetime.datetime.now()
        self.start_datetime = start_datetime
        self.end_datetime = start_datetime + datetime.timedelta(minutes=int(duration))
        self.timer_type = 'single'
        self.is_manual = is_manual
        logger.debug('timer %s initialized' % self)

    def should_be_open(self):
        now = datetime.datetime.now()
        if now >= self.start_datetime:
            if now <= self.end_datetime:
                return True
        return False

    def should_remove(self):
        '''
        Return True if close time is less than the current time
        :return:
        '''
        now = datetime.datetime.now()
        if now <= self.end_datetime:
            return False
        logger.debug('Single timer %s should be deleted since past bedtime' % self)
        return True

    def time_to_close(self):
        '''How much time left until the timer ends

        Returns
        -------
        float - the time left to closing (in seconds)
        '''
        now = datetime.datetime.now()
        time_left = (self.end_datetime - now).total_seconds()
        return time_left
