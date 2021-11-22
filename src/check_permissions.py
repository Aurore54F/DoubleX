# Copyright (C) 2021 Aurore Fass
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


"""
    Checking the permissions of an extension.
    Generating a json file of relevant sensitive APIs to consider for this extension.
"""

import os
import logging
import json


def permission_check(manifest_path, permission_set):
    """ Checks and stores the relevant extension permissions. """

    try:
        manifest = json.load(open(manifest_path))
    except FileNotFoundError:
        logging.critical('No manifest file found in %s', manifest_path)
        return None

    if manifest['manifest_version'] == 3:  # Other checks for manifest v3
        return permission_check_v3(manifest, permission_set)

    # For manifest v2
    all_permissions = manifest.get('permissions', [])
    all_permissions.extend(manifest.get('optional_permissions', []))

    # Host permission checks
    for perm in all_permissions:
        if perm in ('http://*/*', 'https://*/*', '*://*/*', '<all_urls>',
                    'https://*/', 'http://*/'):
            permission_set.add('host')
            break

    # Other permission checks
    permissions2check = ['activeTab', 'bookmarks', 'cookies', 'downloads', 'history', 'topSites']
    for check in permissions2check:
        if check in all_permissions:
            permission_set.add(check)

    # Code execution in the BP CSP checks
    if 'content_security_policy' in manifest:
        if 'unsafe-eval' in manifest['content_security_policy']:
            permission_set.add('eval')

    return 2


def permission_check_v3(manifest, permission_set):
    """ Checks and stores the relevant extension permissions. """

    all_permissions = manifest.get('permissions', [])
    all_permissions.extend(manifest.get('optional_permissions', []))
    host_permissions = manifest.get('host_permissions', [])

    # Host permission checks
    for perm in host_permissions:
        if perm in ('http://*/*', 'https://*/*', '*://*/*', '<all_urls>',
                    'https://*/', 'http://*/'):
            permission_set.add('host')
            break

    # Other permission checks
    permissions2check = ['bookmarks', 'cookies', 'downloads', 'history', 'topSites']
    for check in permissions2check:
        if check in all_permissions:
            permission_set.add(check)

    # No more code execution in the BP with eval and friends
    # executeScript cannot be called on 'code' property, so not interesting anymore

    return 3


def generate_json_apis(extension, manifest_path, json_apis=None):
    """ Generates a json file for DoubleX to analyze only relevant sensitive APIs and only if the
    extension has the corresponding permissions. """

    # tabs.executeScript: activeTab or host
    # ['ajax', 'fetch', 'get', 'post', '$http.get', '$http.post', 'XMLHttpRequest.open']: host
    # ['bookmarks', 'cookies', 'downloads', 'history', 'topSites']: corresponding permission

    permission_set = set()
    version = permission_check(manifest_path, permission_set)  # collected extension permissions
    if version is None:  # if no manifest found
        return None  # this is different from no permission
    apis_dict = dict()

    apis_dict['_description'] = "Suspicious APIs considered by DoubleX for " + manifest_path

    cs_dict = apis_dict['cs'] = {}
    cs_dict['direct_dangers'] = {}
    cs_dict['indirect_dangers'] = {}
    cs_dict['exfiltration_dangers'] = {}

    # For manifest v3, the CS will be subject to the same rules as the page they are running within:
    # https://www.chromium.org/Home/chromium-security/extension-content-script-fetches
    cs_dict['direct_dangers']['execution'] = ['eval', 'setInterval', 'setTimeout']
    if 'host' in permission_set and version == 2:
        # For v3, in CS, XHRs are also governed by the CSP of the page, so the CS can only connect
        # to origins that are allowed by the page
        cs_dict['direct_dangers']['bypass_sop'] = ['XMLHttpRequest().open', 'XMLHttpRequest.open']
        cs_dict['indirect_dangers']['bypass_sop'] = ["fetch", "$.ajax", "jQuery.ajax", "$.get",
                                                     "jQuery.get", "$.post", "jQuery.post",
                                                     "$http.get", "$http.post"]

    bp_dict = apis_dict['bp'] = {}
    bp_dict['direct_dangers'] = {}
    bp_dict['indirect_dangers'] = {}
    bp_dict['exfiltration_dangers'] = {}

    if version == 2 and 'eval' in permission_set:  # Only for manifest v2 and if corresponding CSP
        bp_dict['direct_dangers']['execution'] = ['eval', 'setInterval', 'setTimeout']
    if version == 2 and ('host' in permission_set or 'activeTab' in permission_set):
        if 'execution' not in bp_dict['direct_dangers']:
            bp_dict['direct_dangers']['execution'] = []
        bp_dict['direct_dangers']['execution'].append('tabs.executeScript')  # Only for manifest v2
    if 'downloads' in permission_set:
        bp_dict['direct_dangers']['download'] = ['downloads.download']
    if 'host' in permission_set:
        if version == 2:  # XHR not defined in BP = service worker, for v3
            bp_dict['direct_dangers']['bypass_sop'] = ['XMLHttpRequest().open',
                                                       'XMLHttpRequest.open']
        bp_dict['indirect_dangers']['bypass_sop'] = ["fetch", "$.ajax", "jQuery.ajax", "$.get",
                                                     "jQuery.get", "$.post", "jQuery.post",
                                                     "$http.get", "$http.post"]
        # For v3, we should also check that the extension CSP does not forbid cross-origin requests
    if 'cookies' in permission_set:
        bp_dict['exfiltration_dangers']['cookies'] = ['cookies.getAll']
    bp_dict['exfiltration_dangers']['privacy'] = []
    if 'bookmarks' in permission_set:
        bp_dict['exfiltration_dangers']['privacy'].append('bookmarks.getTree')
    if 'history' in permission_set:
        bp_dict['exfiltration_dangers']['privacy'].append('history.search')
    if 'topSites' in permission_set:
        bp_dict['exfiltration_dangers']['privacy'].append('topSites.get')
    if not bp_dict['exfiltration_dangers']['privacy']:  # empty list
        bp_dict['exfiltration_dangers'].pop('privacy')  # can remove it

    if json_apis is None:
        json_apis = os.path.join(extension, 'extension_doublex_apis.json')
    with open(json_apis, 'w') as json_data:
        json.dump(apis_dict, json_data, indent=2, sort_keys=False)
    return json_apis
