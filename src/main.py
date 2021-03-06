#!/usr/bin/env python3
# Copyright 2017 Google Inc.
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

"""Run a recognizer using the Google Assistant Library with button support.

The Google Assistant Library has direct access to the audio API, so this Python
code doesn't need to record audio. Hot word detection "OK, Google" is supported.

It is available for Raspberry Pi 2/3 only; Pi Zero is not supported.
"""

import logging
import platform
import sys
import threading
import requests
import re

import aiy.assistant.auth_helpers
from aiy.assistant.library import Assistant
import aiy.voicehat
from google.assistant.library.event import EventType

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s:%(name)s:%(message)s"
)


class MyAssistant(object):
    """An assistant that runs in the background.

    The Google Assistant Library event loop blocks the running thread entirely.
    To support the button trigger, we need to run the event loop in a separate
    thread. Otherwise, the on_button_pressed() method will never get a chance to
    be invoked.
    """

    def __init__(self):
        self._task = threading.Thread(target=self._run_task)
        self._can_start_conversation = False
        self._assistant = None

    def start(self):
        """Starts the assistant.

        Starts the assistant event loop and begin processing events.
        """
        self._task.start()

    def _run_task(self):
        credentials = aiy.assistant.auth_helpers.get_assistant_credentials()
        with Assistant(credentials) as assistant:
            self._assistant = assistant
            for event in assistant.start():
                self._process_event(event)


    def power_off_pi(self):
        aiy.audio.say('Good bye!')
        subprocess.call('sudo shutdown now', shell=True)


    def reboot_pi(self):
        aiy.audio.say('See you in a bit!')
        subprocess.call('sudo reboot', shell=True)


    def say_ip(self):
        ip_address = subprocess.check_output("hostname -I | cut -d' ' -f1", shell=True)
        aiy.audio.say('My IP address is %s' % ip_address.decode('utf-8'))

    def light(self, active):
        cmd = 'On' if active else 'Off'
        url = "http://localhost:8080/json.htm?type=command&param=switchlight&idx=1&switchcmd="+cmd
        print(url)
        r = requests.get(url)

    def light_level(self, level):
        url = "http://localhost:8080/json.htm?type=command&param=switchlight&idx=1&switchcmd=Set%20Level&level="+str(level)
        print(url)
        r = requests.get(url)
        aiy.audio.say('Yes sir!', pitch=150, volume=10)
    
    def _process_event(self, event):
        status_ui = aiy.voicehat.get_status_ui()
        status_ui.set_trigger_sound_wave('src/googlestart.wav') 
        if event.type == EventType.ON_START_FINISHED:
            status_ui.status('ready')
            self._can_start_conversation = True
            # Start the voicehat button trigger.
            aiy.voicehat.get_button().on_press(self._on_button_pressed)
            if sys.stdout.isatty():
                print('Say "OK, Google" or press the button, then speak. '
                      'Press Ctrl+C to quit...')

        elif event.type == EventType.ON_CONVERSATION_TURN_STARTED:
            self._can_start_conversation = False
            status_ui.status('listening')

        elif event.type == EventType.ON_RECOGNIZING_SPEECH_FINISHED and event.args:
            print('You said:', event.args['text'])
            text = event.args['text'].lower()
            if text == 'power off':
                self._assistant.stop_conversation()
                self.power_off_pi()
            elif text == 'reboot':
                self._assistant.stop_conversation()
                self.reboot_pi()
            elif text == 'ip address':
                self._assistant.stop_conversation()
                self.say_ip()
            elif 'light' in text and '%' in text:
                m = re.search('[0-9]+%', text)
                if m:
                    try:
                        level = int(m.group()[:-1])
                        level = max(0, min(level, 100))
                        self._assistant.stop_conversation()
                        self.light_level(level)
                    except ValueError:
                        print('Unknown value ' + m.group())
            elif  'light' in text and 'on' in text:
                self._assistant.stop_conversation()
                self.light(True)
            elif 'light'in text and 'off' in text:
                self._assistant.stop_conversation()
                self.light(False)
                
        elif event.type == EventType.ON_END_OF_UTTERANCE:
            status_ui.status('thinking')

        elif (event.type == EventType.ON_CONVERSATION_TURN_FINISHED
              or event.type == EventType.ON_CONVERSATION_TURN_TIMEOUT
              or event.type == EventType.ON_NO_RESPONSE):
            status_ui.status('ready')
            self._can_start_conversation = True

        elif event.type == EventType.ON_ASSISTANT_ERROR and event.args and event.args['is_fatal']:
            sys.exit(1)

    def _on_button_pressed(self):
        # Check if we can start a conversation. 'self._can_start_conversation'
        # is False when either:
        # 1. The assistant library is not yet ready; OR
        # 2. The assistant library is already in a conversation.
        if self._can_start_conversation:
            self._assistant.start_conversation()


def main():
    if platform.machine() == 'armv6l':
        print('Cannot run hotword demo on Pi Zero!')
        exit(-1)
    MyAssistant().start()


if __name__ == '__main__':
    main()

