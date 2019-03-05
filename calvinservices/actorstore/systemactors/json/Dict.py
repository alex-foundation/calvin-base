# -*- coding: utf-8 -*-

# Copyright (c) 2015 Ericsson AB
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# encoding: utf-8

from calvin.actor.actor import Actor, manage, condition, stateguard
from calvin.runtime.north.calvin_token import EOSToken, ExceptionToken

class Dict(Actor):

    """
    documentation:
    - Create a dict
    - Consume 'n' key/value pairs to produce a dictionary. If 'n' is
      zero or negative, consume key/value pairs until EOS encountered on both input ports.
      If EOS is only encountered on one port, produce an execption.
    ports:
    - direction: in
      help: key must be string
      name: key
    - direction: in
      help: can be any token
      name: value
    - direction: out
      help: dictionary or Exception
      name: dict
    """


    @manage(['n', '_dict', 'done'])
    def init(self, n):
        self.n = n if n > 0 else 0
        self._dict = {}
        self.done = False

    def _bail(self):
        self._dict = ExceptionToken()
        self.done = True

    def exception_handler(self, action, args):
        if self.n or not (isinstance(args[0], EOSToken) and isinstance(args[1], EOSToken)):
            self._bail()
        self.done = True


    @stateguard(lambda self: not self.n and not self.done)
    @condition(['key', 'value'], [])
    def add_entry_EOS(self, key, value):
        if isinstance(key, str):
            self._dict[key] = value
        else:
            self._bail()


    @stateguard(lambda self: self.n and not self.done)
    @condition(['key', 'value'], [])
    def add_entry(self, key, value):
        if isinstance(key, str):
            self._dict[key]=value
            self.done = bool(len(self._dict) == self.n)
        else:
            self._bail()


    @stateguard(lambda self: self.done)
    @condition([], ['dict'])
    def produce_dict(self):
        res = self._dict
        self.done = False
        self._dict = {}
        return (res, )

    action_priority = (produce_dict, add_entry, add_entry_EOS)


    test_kwargs = {'n': 1}
    test_set = [
        {
            'inports': {'key': ["a", "b"], 'value': [1, 2]},
            'outports': {'dict': [{"a":1}, {"b":2}]},
        },
        {
            'setup':[lambda self: self.init(n=2)],
            'inports': {'key': ["a", "b"], 'value': [1, 2]},
            'outports': {'dict': [{"a":1, "b":2}]},
        },
        {
            'setup':[lambda self: self.init(n=0)],
            'inports': {'key': ["a", "b", EOSToken()], 'value': [1, 2, EOSToken()]},
            'outports': {'dict': [{"a":1, "b":2}]},
        },
        # Error conditions
        {
            'setup':[lambda self: self.init(n=0)],
            'inports': {'key': ["a", EOSToken()], 'value': [1, 2]},
            'outports': {'dict': ['Exception']},
        },
        {
            'setup':[lambda self: self.init(n=2)],
            'inports': {'key': ["a", 1, "b", "c"], 'value': [10, 20, 30, 40]},
            'outports': {'dict': ['Exception', {"b":30, "c":40}]},
        },

    ]