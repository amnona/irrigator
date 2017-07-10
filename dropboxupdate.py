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

import dropbox

def get_file(dbx, dir_name, file_name):
    '''
    read a file from dropbox to local directory
    '''
#    print(´getting file´)
    dbx.files_download_to_file(file_name, os.path.join(dir_name, file_name))
#    out = open(file_name, 'wb')
#    out.write(f.read())
#    out.close()
#    print(´got file´)


def synchronize_dropbox(dbx_key, dir_name, files):
    '''
    main loop to synchronize with dropbox

    :param dbx_key: str
        the key to use for dropbox or None to try from env. variable DROPBOXKEY
    :param dir_name: str
        the name of the app dropbox directory to check (i.e. '/pita')
    :param files: list of str
        list of files to check (i.e. 'timer-list.txt')
    :return:
    '''
    if dbx_key is None:
        try:
            dbx_key = os.environ['DROPBOXKEY']
        except:
            ValueError('no dropbox key supplied in env. variable DROPBOXKEY')
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
                properties = dbx.files_alpha_get_metadata(cname)
                if properties.client_modified > datetime.datetime.fromtimestamp(os.stat(cfile).st_mtime):
                    print('file %s is old' % cname)
                    print(properties)
                    need_to_pull = True
            if need_to_pull:
                print('pulling')
                get_file(dbx, dir_name, cfile)
        time.sleep(30)

parser = argparse.ArgumentParser()
parser.add_argument('--dbkey','-k',help='dropbox app token')
parser.add_argument('--dir','-d',help='dropbox dir for app', default='/pita')
parser.add_argument('--files','-f',help='file names', nargs='*',default=['timer-list.txt'])

ns = parser.parse_args()

synchronize_dropbox(dbx_key=ns.dbkey, dir_name=ns.dir, files=ns.files)

