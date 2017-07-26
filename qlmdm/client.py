# Quantopian, Inc. licenses this file to you under the Apache License, Version
# 2.0 (the "License"); you may not use this file except in compliance with the
# License. You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.

from functools import partial
import json
import os
import requests
import sys
from tempfile import NamedTemporaryFile

from qlmdm import (
    load_settings,
    get_setting as main_get_setting,
    set_setting as main_set_setting,
    get_logger as main_get_logger,
    save_settings as main_save_settings,
    get_selectors as main_get_selectors,
    encrypt_document as main_encrypt_document,
    client_gpg_version,
    gpg_command as main_gpg_command,
    top_dir,
)

gpg_command = partial(main_gpg_command, minimum_version=client_gpg_version)


def get_setting(setting, default=None, check_defaults=True):
    """Fetch a setting from `client/settings.xml`

    `setting` is a colon-separated list of keys and to transit to fetch the
    desired setting. For example, `logging:handler` fetches the type Logbook
    handler configured on the client.

    `default` is the value to return if the setting does not exist.

    `check_defaults` indicates whether `client/default-settings.yml` should be
    checked if the specified setting isn't in `client/settings.xml`.

    Returns None if the setting does not exist.
    """

    return main_get_setting(load_settings('client'), setting, default,
                            check_defaults)


def set_setting(setting, value):
    return main_set_setting(load_settings('client'), setting, value)


def save_settings():
    main_save_settings('client')


def get_logger(name):
    return main_get_logger(get_setting, name, fail_to_local=True)


def get_selectors():
    return main_get_selectors(get_setting)


def encrypt_document(*args, **kwargs):
    return main_encrypt_document(get_setting, *args, **kwargs)


def server_request(cmd, data=None, data_path=None,
                   exit_on_connection_error=False):
    server_url = get_setting('server_url')
    if data and data_path:
        raise Exception('Both data and data_path specified')
    with NamedTemporaryFile('w+') as temp_data_file, \
            NamedTemporaryFile('w+') as signature_file:
        if data:
            data = json.dumps(data)
            temp_data_file.write(data)
            temp_data_file.flush()
            data_path = temp_data_file.name
        else:
            data = open(data_path).read()
        gpg_command('--armor', '--detach-sign', '-o', signature_file.name,
                    data_path)
        signature_file.seek(0)
        post_data = {
            'data': data,
            'signature': signature_file.read(),
        }

    kwargs = {
        'data': post_data,
        'timeout': 30,
    }
    ca_path = get_setting('ssl:ca_path')
    if ca_path:
        if not ca_path.startswith('/'):
            ca_path = os.path.join(top_dir, ca_path)
        kwargs['verify'] = ca_path
    try:
        response = requests.post('{}{}'.format(server_url, cmd), **kwargs)
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        if exit_on_connection_error:
            sys.exit('Connection error posting to {}'.format(server_url))
        raise

    return response
