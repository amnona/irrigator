#!/usr/bin/env python

'''
Synchronize dropbox files from a remote directory to local
Runs as a loop, synchronizing every 30 seconds

*** NOTE: requires the dropbox key in env. variable DROPBOXKEY
'''

# amnonscript

import os
import argparse
import time
import datetime

import logging

import dropbox
import dateutil.tz

from logging.config import fileConfig

logger = logging.getLogger(__name__)

log = 'log.cfg'
# setting False allows other logger to print log.
fileConfig(log, disable_existing_loggers=False)


def get_gmt_time(tm):
    '''get the GMT time for the local event.
    used since dropbox stores the GMT time instead of local time

    Parameters
    ----------
    tm : datetime to get the GMT when it happened

    Returns
    -------
    datetime
        the GMT time when tm happened
    '''
    localtz = dateutil.tz.tzlocal()
    delta = localtz.utcoffset(datetime.datetime.now(localtz))
    gmt_tm = tm - delta
    return gmt_tm


def watch_files(dbx_key, dir_name, files, interval=2):
    '''Watch a list of files for changes, and upload if changed

    Parameters
    ----------
    dbx_key: str or None
        the dropbox application token, or None to get from env var. DROPBOXKEY
    dir_name: str
        the dropbox app directory
    files : list of str
        list of files to watch
    interval: float
        the interval between file tests (seconds)
    '''
    file_times = {}
    for cfile in files:
        try:
            file_times[cfile] = datetime.datetime.fromtimestamp(os.stat(cfile).st_mtime)
        except:
            logger.warning('file %s does not exist' % cfile)

    while True:
        for cfile, watched_time in file_times.items():
            current_file_time = datetime.datetime.fromtimestamp(os.stat(cfile).st_mtime)
            if current_file_time > watched_time:
                logger.info('file %s changed. uploading' % cfile)
                if upload_file(dbx_key, dir_name, [cfile]):
                    file_times[cfile] = datetime.datetime.fromtimestamp(os.stat(cfile).st_mtime)
        time.sleep(interval)

def upload_file(dbx_key, dir_name, files):
    '''
    Upload a local file (file_name) to dropbox server
    :param dbx:
    :param dir_name:
    :param file_name:
    :return:
    '''
    if dbx_key is None:
        try:
            dbx_key = os.environ['DROPBOXKEY']
        except:
            raise ValueError('no dropbox key supplied in env. variable DROPBOXKEY')
    dbx = dropbox.dropbox.Dropbox(dbx_key)
    for cfile in files:
        logger.debug('uploading file %s' % cfile)
        with open(cfile,'rb') as fl:
            dat = fl.read()
            try:
                dbx.files_alpha_upload(dat, path=os.path.join(dir_name, cfile), mode=dropbox.dropbox.files.WriteMode('overwrite', None))
            except Exception as err:
                logger.warning('upload %s failed. error=%s' % (cfile, err))
                return False
        logger.info('file %s uploaded' % cfile)
        return True

def get_file(dbx, dir_name, file_name):
    '''
    read a file from dropbox to local directory
    '''
    print('getting file %s' % file_name)
    try:
        dbx.files_download_to_file(file_name, os.path.join(dir_name, file_name))
    except Exception as err:
        print('error getting file %s. error=%s' % (file_name, err))
    print('got file %s' % file_name)


def synchronize_dropbox(dbx_key, dir_name, files, interval=30):
    '''
    main loop to synchronize with dropbox

    :param dbx_key: str
        the key to use for dropbox or None to try from env. variable DROPBOXKEY
    :param dir_name: str
        the name of the app dropbox directory to check (i.e. '/irrigator2')
    :param files: list of str
        list of files to check (i.e. 'timer-list.txt')
    :param interval: int
        the interval (seconds) for sleeping between tests
    :return:
    '''
    logger.debug('synchronize')
    if dbx_key is None:
        try:
            logger.debug('no dropbox key supplied. trying env')
            dbx_key = os.environ['DROPBOXKEY']
            logger.debug('got dropbox key in environment')
        except:
            raise ValueError('no dropbox key supplied in env. variable DROPBOXKEY')
    else:
        logger.debug('dbkey is: %s' % dbx_key)
    dbx = dropbox.dropbox.Dropbox(dbx_key)

    while True:
        logger.debug('testing files')
        for cfile in files:
            cname = os.path.join(dir_name, cfile)
            logger.debug('testing file %s' % cname)
            need_to_pull = False
            if not os.path.isfile(cfile):
                logger.info('file %s does not exist')
                need_to_pull = True
            else:
                try:
                    properties = dbx.files_alpha_get_metadata(cname)
                except Exception as err:
                    logger.warning('error getting properties for file %s. error=%s' % (cname, err))
                    continue
                logger.debug('file %s' % cfile)
                logger.debug(properties)
                logger.debug('local file time stamp:')
                logger.debug(datetime.datetime.fromtimestamp(os.stat(cfile).st_mtime))
                logger.debug('gmt time when modified:')
                logger.debug(get_gmt_time(datetime.datetime.fromtimestamp(os.stat(cfile).st_mtime)))
                if properties.client_modified > get_gmt_time(datetime.datetime.fromtimestamp(os.stat(cfile).st_mtime)):
                    logger.info('file %s is old' % cname)
                    logger.debug(properties)
                    need_to_pull = True
            if need_to_pull:
                logger.info('pulling file %s' % cfile)
                try:
                    get_file(dbx, dir_name, cfile)
                    logger.debug('got file %s' % cfile)
                except Exception as err:
                    logger.warning('error gettting file %s. Error: %s' % (cfile, err))
        time.sleep(interval)

parser = argparse.ArgumentParser()
parser.add_argument('--dbkey','-k',help='dropbox app token')
parser.add_argument('--interval','-i', help='the time interval for upload/test (seconds)', default=30, type=int)
parser.add_argument('--dir','-d',help='dropbox dir for app', default='/irrigator2')
parser.add_argument('--action','-a',help='action (sync / upload / watch)', default='sync')
parser.add_argument('--files','-f',help='file names', nargs='*',default=['timer-list.txt'])
parser.add_argument('--debug-level','-l',help='debug level (DEBUG/INFO/WARNING)',default='DEBUG')

ns = parser.parse_args()

logger.setLevel(ns.debug_level)

if ns.action == 'upload':
    upload_file(dbx_key=ns.dbkey, dir_name=ns.dir, files=ns.files)
elif ns.action == 'sync':
    synchronize_dropbox(dbx_key=ns.dbkey, dir_name=ns.dir, files=ns.files, interval=ns.interval)
elif ns.action == 'watch':
    watch_files(dbx_key=ns.dbkey, dir_name=ns.dir, files=ns.files, interval=ns.interval)
else:
    print('action %s not supported - please use "upload" or "sync"' % ns.action)

