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

from logging.config import fileConfig

logger = logging.getLogger(__name__)

log = 'log.cfg'
# setting False allows other logger to print log.
fileConfig(log, disable_existing_loggers=False)


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
            ValueError('no dropbox key supplied in env. variable DROPBOXKEY')
    dbx = dropbox.dropbox.Dropbox(dbx_key)
    for cfile in files:
        print('uploading file %s' % cfile)
        with open(cfile,'rb') as fl:
            dat = fl.read()
            try:
                dbx.files_alpha_upload(dat, path=os.path.join(dir_name, cfile), mode=dropbox.dropbox.files.WriteMode('overwrite', None))
            except Exception as err:
                print('upload %s failed. error=%s' % (cfile, err))
        print('file %s uploaded' % cfile)


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
        the name of the app dropbox directory to check (i.e. '/pita')
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
        print('testing')
        for cfile in files:
            cname = os.path.join(dir_name, cfile)
            print('testing %s' % cname)
            need_to_pull = False
            if not os.path.isfile(cfile):
                print('file %s does not exist')
                need_to_pull = True
            else:
                try:
                    properties = dbx.files_alpha_get_metadata(cname)
                except Exception as err:
                    print('error getting properties for file %s. error=%s' % (cname, err))
                    continue
                print(properties)
                print('local file time stamp:')
                print(datetime.datetime.fromtimestamp(os.stat(cfile).st_mtime))
                if properties.client_modified > datetime.datetime.fromtimestamp(os.stat(cfile).st_mtime):
                    print('file %s is old' % cname)
                    print(properties)
                    need_to_pull = True
            if need_to_pull:
                print('pulling')
                get_file(dbx, dir_name, cfile)
        time.sleep(interval)

parser = argparse.ArgumentParser()
parser.add_argument('--dbkey','-k',help='dropbox app token')
parser.add_argument('--interval','-i', help='the time interval for upload/test (seconds)', default=30, type=int)
parser.add_argument('--dir','-d',help='dropbox dir for app', default='/pita')
parser.add_argument('--action','-a',help='action (sync or upload)', default='sync')
parser.add_argument('--files','-f',help='file names', nargs='*',default=['timer-list.txt'])
parser.add_argument('--debug-level','-l',help='debug level (DEBUG/INFO/WARNING)',default='DEBUG')

ns = parser.parse_args()

logger.setLevel(ns.debug_level)

if ns.action == 'upload':
    upload_file(dbx_key=ns.dbkey, dir_name=ns.dir, files=ns.files, interval=ns.interval)
elif ns.action == 'sync':
    synchronize_dropbox(dbx_key=ns.dbkey, dir_name=ns.dir, files=ns.files, interval=ns.interval)
else:
    print('action %s not supported - please use "upload" or "sync"' % ns.action)

