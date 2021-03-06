#
# test_config.py
#
# Copyright (C) 2016 Kano Computing Ltd.
# License: http://www.gnu.org/licenses/gpl-2.0.txt GNU General Public License v2
#
# This module tests boot_config.py
#
# TODO: This test class has been disabled since it requires sudo to run
#       and because the tests for it take over 2 minutes.


import os
import re
import sys
import copy
import random
import unittest

from kano.utils import is_number

from tests.tools import mock_file, require_rpi


print '''
***************************
******* Test Config *******
***************************

'''

random.seed(12345)  # test should be deterministic

dummy_config_data = """

### foo: bar
hdmi_ignore_edid_audio=1
# junk
"""
config_path = '/boot/config.txt'


class config_vals:
    # Class to hold config values for comparison
    def __init__(self, values, comment_values, comments, comment_keys):
        self.values = values   # for lines of the form foo=bar
        self.comment_values = comment_values  # for lines of the form ### foo: bar
        self.comments = comments  # All other lines
        self.comment_keys = comment_keys

    def copy(self):
        return config_vals(copy.copy(self.values),
                           copy.copy(self.comment_values),
                           copy.copy(self.comments),
                           copy.copy(self.comment_keys))


def read_config(path=config_path):
    # read a config file for comparison, into a config_vals object

    lines = open(path, "r").readlines()
    values = {}
    comment_values = {}
    comment_keys = {}
    comments = []
    commentRe = re.compile('### ([^:]+): (.*)')
    valRe = re.compile('([^=#]+)=(.*)')
    valCommentRe = re.compile('^\s*#\s*([^=#]+)=(.*)')

    for x in lines:
        m = commentRe.match(x)
        if m:
            comment_values[m.group(1)] = m.group(2)
            continue
        m = valRe.match(x)
        m2 = valCommentRe.match(x)
        if m or m2:
            if not m:
                m = m2
            values[m.group(1)] = m.group(2)
            if is_number(m.group(2)):
                values[m.group(1)] = int(m.group(2))
            if m2:
                comment_keys[m.group(1)] = True
            continue
        comments.append(x)
    return config_vals(values, comment_values, comments, comment_keys)


def compare(a, b):
    if set(a.comments) != set(b.comments):
        print "comment difference", a.comments, b.comments
        return False

    if set(a.comment_values.keys()) != set(b.comment_values.keys()):
        print " comment set different", a.comment_values.keys(), b.comment_values.keys()
        return False

    for k in a.comment_values.keys():
        if a.comment_values[k] != b.comment_values[k]:
            print "comment value difference", k, a.comment_values[k], b.comment_values[k]
            return False

    if set(a.values.keys()) != set(b.values.keys()):
        print " value set different", a.values.keys(), b.values.keys()
        return False

    for k in a.values.keys():
        if a.values[k] != b.values[k]:
            print "value difference", k, a.values[k], b.values[k], a, b
            return False
    return True


class configSetTest(unittest.TestCase):
    # The main test.
    # We want to test  the following:
    #    All read methods read correct value
    #    all read methods cause lock
    #    all write methods cause lock
    #    all write methods don't write back until writeback
    #    all writes are copied back after writeback
    #    locking is blocking
    #    All methods maintain the state invariants defined by valid_state()

    # To do this, we maintain three sets of configs:
    # 'current' (the current value of /boot/config.txt
    # 'written' (The value that will be written back at the end of the transaction)
    # 'backup' (The value of the safe mode backup config)

    def __init__(self, x):
        # can only test restoring after a backup
        self.backup_config_exists = False

        unittest.TestCase.__init__(self, x)

    @require_rpi
    @unittest.skipIf('-fast' in sys.argv, 'Skipping because tests are in fast mode')
    def test_set_config(self):
        from kano_settings import boot_config

        def choose_key(present, data):
            # Choose either  a key of a dictionary, or a key not present
            if present:
                key = random.choice(data.keys())
            else:
                # choose a key that is not present
                key = str(random.randint(0, 10000000))
                while key in data.keys():
                    key = str(random.randint(0, 10000000))
            return key

        def is_locked():
            # Check whether the lock is effective. Return true if the lock is held

            import os
            py = os.path.join(os.path.dirname(__file__), 'try_lock.py')
            return os.system('python ' + py) != 0

        def test_read(configs):
            # Test all read methods
            # Check the result of the read against the 'written' config set.

            which = random.randint(0, 3)
            present = random.randint(0, 1) == 1
            if which == 0:
                # test get_config_value

                key = choose_key(present, configs['written'].values)

                # test case when key is present and not present

                v = boot_config.get_config_value(key)
                print "testing get_config_value({}) => {}".format(key, v)

                if present:
                    self.assertEqual(v, configs['written'].values[key])
                else:
                    self.assertEqual(v, 0)

            elif which == 1:
                # test get_config_comment

                # test case when key is present and not present
                key = choose_key(present, configs['written'].comment_values)
                if present:
                    correct = random.randint(0, 1)
                    value = configs['written'].comment_values[key]
                    if not correct:
                        value = value + '_wrong'
                else:
                    correct = False
                    value = str(random.randint(0, 10))

                v = boot_config.get_config_comment(key, value)
                print "testing get_config_comment({},{}) => {}".format(key, value, v)

                # get_config comment
                self.assertTrue(v == (present and correct))

            elif which == 2:
                # test has_config_comment

                # test case when key is present and not present
                key = choose_key(present, configs['written'].comment_values)

                v = boot_config.has_config_comment(key)
                print "testing has_config_comment({}) => {}".format(key, v)

                self.assertTrue(v == present)

            elif which == 3:
                # test copy_to

                print "testing safe_mode_config_backup"
                boot_config.safe_mode_backup_config()

                # enable testing of restore
                self.backup_config_exists = True

                configs['backup'] = read_config(boot_config.boot_config_safemode_backup_path)

                self.assertTrue(compare(configs['backup'], configs['written']))

            # after a read, state should be at least locked.
            self.assertTrue(boot_config._trans().state >= 1)

            # after a read, config should be unmodified
            after_read = read_config()

            self.assertTrue(compare(configs['current'], after_read))
            self.assertTrue(is_locked())

        def test_write(configs):

            if self.backup_config_exists:
                which = random.randint(0, 2)
            else:
                which = random.randint(0, 1)

            present = random.randint(0, 1) == 1

            before_write = configs['current'].copy()

            if which == 0:
                # test set_config_value

                key = choose_key(present, configs['current'].values)
                if random.randint(0, 1):
                    value = None

                    print "testing set_config_value({},{})".format(key, value)
                    boot_config.set_config_value(key, value)
                    configs['written'].values[key] = 0
                    configs['written'].comment_keys[key] = True
                else:
                    value = random.randint(0, 1000)
                    print "testing set_config_value({},{})".format(key, value)
                    boot_config.set_config_value(key, value)
                    configs['written'].values[key] = value
                    configs['written'].comment_keys[key] = False

            elif which == 1:
                # test set_config_comment
                key = choose_key(present, configs['current'].comment_values)
                value = str(random.randint(0, 1000))

                print "testing set_config_comment({},{})".format(key, value)
                boot_config.set_config_comment(key, value)
                configs['written'].comment_values[key] = value

            elif which == 2:
                # test restore_backup

                self.assertTrue(self.backup_config_exists)  # bug in test if triggered

                print "testing safe_mode_restore_backup"
                boot_config.safe_mode_restore_config()
                configs['written'] = read_config(boot_config._trans().temp_path)

                self.backup_config_exists = False

                self.assertTrue(compare(configs['backup'], configs['written']))

            after_write = read_config()

            self.assertTrue(compare(before_write, after_write))
            self.assertTrue(boot_config._trans().state == 2)
            self.assertTrue(is_locked())

        def test_remove_noobs(configs):
            # FIXME this is not properly tested yet
            before_write = configs['current'].copy()
            present = boot_config.noobs_line in before_write.comments
            # test remove_noobs_defaults
            boot_config.remove_noobs_defaults()
            print "testing remove_noobs_defaults"

            after_write = read_config()

            self.assertTrue(compare(before_write, after_write))
            if present:
                self.assertTrue(boot_config._trans().state == 2)
            else:
                self.assertTrue(boot_config._trans().state >= 1)
            self.assertTrue(is_locked())

        def test_close(configs):
            boot_config.end_config_transaction()
            configs['current'] = read_config()

            print "testing close"

            # all written items should now be present
            self.assertTrue(compare(configs['current'], configs['written']))
            self.assertTrue(boot_config._trans().state == 0)
            self.assertTrue(not is_locked())

        with mock_file(config_path, dummy_config_data):

            self.assertTrue(not is_locked())

            orig = read_config()

            self.assertTrue(boot_config._trans().valid_state())
            self.assertTrue(boot_config._trans().state == 0)

            numtests = random.randint(0, 1000)

            configs = {}
            configs['current'] = orig
            configs['written'] = orig.copy()

            for trial in range(numtests):
                print "test number ", trial
                # os.system('cat /boot/config.txt')
                # print "___"
                # os.system('cat '+boot_config._trans().temp_config.path)
                # print "___"

                rwc = random.randint(0, 3)

                if rwc == 0:
                    test_read(configs)
                elif rwc == 1:
                    test_write(configs)
                elif rwc == 2:
                    test_remove_noobs(configs)
                else:
                    test_close(configs)

                # after each operation, state shuold be valid
                self.assertTrue(boot_config._trans().valid_state())

            # Sanity check - did we actually test anything?
            os.system('cat /boot/config.txt')
