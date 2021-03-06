# -*- encoding: utf-8 -*-
#
# Copyright © 2013 eNovance <licensing@enovance.com>
#
# Author: Mehdi Abaakouk <mehdi.abaakouk@enovance.com>
#         Angus Salkeld <asalkeld@redhat.com>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
'''Tests alarm operation
'''

import logging
import uuid
import testscenarios

from .base import FunctionalTest

from ceilometer.storage.models import Alarm
from ceilometer.tests import db as tests_db

load_tests = testscenarios.load_tests_apply_scenarios

LOG = logging.getLogger(__name__)


class TestListEmptyAlarms(FunctionalTest,
                          tests_db.MixinTestsWithBackendScenarios):

    def test_empty(self):
        data = self.get_json('/alarms')
        self.assertEqual([], data)


class TestAlarms(FunctionalTest,
                 tests_db.MixinTestsWithBackendScenarios):

    def setUp(self):
        super(TestAlarms, self).setUp()

        self.auth_headers = {'X-User-Id': str(uuid.uuid1()),
                             'X-Project-Id': str(uuid.uuid1())}
        for alarm in [Alarm(name='name1',
                            counter_name='meter.test',
                            comparison_operator='gt', threshold=2.0,
                            statistic='avg',
                            repeat_actions=True,
                            user_id=self.auth_headers['X-User-Id'],
                            project_id=self.auth_headers['X-Project-Id']),
                      Alarm(name='name2',
                            counter_name='meter.mine',
                            comparison_operator='gt', threshold=2.0,
                            statistic='avg',
                            user_id=self.auth_headers['X-User-Id'],
                            project_id=self.auth_headers['X-Project-Id']),
                      Alarm(name='name3',
                            counter_name='meter.test',
                            comparison_operator='gt', threshold=2.0,
                            statistic='avg',
                            user_id=self.auth_headers['X-User-Id'],
                            project_id=self.auth_headers['X-Project-Id'])]:
            self.conn.update_alarm(alarm)

    def test_list_alarms(self):
        data = self.get_json('/alarms')
        self.assertEqual(3, len(data))
        self.assertEqual(set(r['name'] for r in data),
                         set(['name1', 'name2', 'name3']))
        self.assertEqual(set(r['counter_name'] for r in data),
                         set(['meter.test', 'meter.mine']))

    def test_get_alarm(self):
        alarms = self.get_json('/alarms',
                               q=[{'field': 'name',
                                   'value': 'name1',
                                   }])
        for a in alarms:
            print('%s: %s' % (a['name'], a['alarm_id']))
        self.assertEqual(alarms[0]['name'], 'name1')
        self.assertEqual(alarms[0]['counter_name'], 'meter.test')

        one = self.get_json('/alarms/%s' % alarms[0]['alarm_id'])
        self.assertEqual(one['name'], 'name1')
        self.assertEqual(one['counter_name'], 'meter.test')
        self.assertEqual(one['alarm_id'], alarms[0]['alarm_id'])
        self.assertEqual(one['repeat_actions'], alarms[0]['repeat_actions'])

    def test_post_invalid_alarm(self):
        json = {
            'name': 'added_alarm',
            'counter_name': 'ameter',
            'comparison_operator': 'gt',
            'threshold': 2.0,
            'statistic': 'magic',
        }
        self.post_json('/alarms', params=json, expect_errors=True, status=400,
                       headers=self.auth_headers)
        alarms = list(self.conn.get_alarms())
        self.assertEqual(3, len(alarms))

    def test_post_alarm(self):
        json = {
            'name': 'added_alarm',
            'counter_name': 'ameter',
            'comparison_operator': 'gt',
            'threshold': 2.0,
            'statistic': 'avg',
            'repeat_actions': True,
        }
        self.post_json('/alarms', params=json, status=200,
                       headers=self.auth_headers)
        alarms = list(self.conn.get_alarms())
        self.assertEqual(4, len(alarms))
        for alarm in alarms:
            if alarm.name == 'added_alarm':
                self.assertEqual(alarm.repeat_actions, True)
                break
        else:
            self.fail("Alarm not found")

    def test_put_alarm(self):
        json = {
            'name': 'renamed_alarm',
            'repeat_actions': True,
        }
        data = self.get_json('/alarms',
                             q=[{'field': 'name',
                                 'value': 'name1',
                                 }])
        self.assertEqual(1, len(data))
        alarm_id = data[0]['alarm_id']

        self.put_json('/alarms/%s' % alarm_id,
                      params=json,
                      headers=self.auth_headers)
        alarm = list(self.conn.get_alarms(alarm_id=alarm_id))[0]
        self.assertEqual(alarm.name, json['name'])
        self.assertEqual(alarm.repeat_actions, json['repeat_actions'])

    def test_put_alarm_wrong_field(self):
        # Note: wsme will ignore unknown fields so will just not appear in
        # the Alarm.
        json = {
            'name': 'renamed_alarm',
            'this_can_not_be_correct': 'ha',
        }
        data = self.get_json('/alarms',
                             q=[{'field': 'name',
                                 'value': 'name1',
                                 }],
                             headers=self.auth_headers)
        self.assertEqual(1, len(data))

        resp = self.put_json('/alarms/%s' % data[0]['alarm_id'],
                             params=json,
                             expect_errors=True,
                             headers=self.auth_headers)
        self.assertEqual(resp.status_code, 200)

    def test_delete_alarm(self):
        data = self.get_json('/alarms')
        self.assertEqual(3, len(data))

        self.delete('/alarms/%s' % data[0]['alarm_id'],
                    status=200)
        alarms = list(self.conn.get_alarms())
        self.assertEqual(2, len(alarms))

    def test_get_alarm_history(self):
        data = self.get_json('/alarms')
        history = self.get_json('/alarms/%s/history' % data[0]['alarm_id'])
        self.assertEqual([], history)

    def test_get_nonexistent_alarm_history(self):
        response = self.get_json('/alarms/%s/history' % 'foobar',
                                 expect_errors=True)
        self.assertEqual(response.status_int, 400)
