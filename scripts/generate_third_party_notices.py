# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------

# This is a standalone script to generate a Third Party Notices file.
# Run this script from the virtual environment with all your depenendencies in.
# This script only has dependencies on core Python libraries and the requests library.

# 'LICENSE NOT FOUND' will be output for dependencies where a license could not be found.

# Usage: python generate_third_party_notices.py > ThirdPartyNotices.txt

from __future__ import print_function

from pprint import pformat
from subprocess import check_output
from multiprocessing import Pool

import requests

NOTICE_HEADER = """
THIRD-PARTY SOFTWARE NOTICES AND INFORMATION
Do Not Translate or Localize

This file provides information regarding components that are being relicensed to you by Microsoft under Microsoft's software licensing terms. Microsoft reserves all rights not expressly granted herein.

Microsoft is offering you a license to use the following components, to the extent they are included within the Microsoft Azure CLI 2.0 (the "Microsoft Program"), subject to the terms of your license to use the Microsoft Product. Insofar as a component is dual licensed under the GPL and a license that permits relicensing under proprietary terms, Microsoft neither took the code under the GPL nor distributes it thereunder but under the terms of the license that permits relicensing under proprietary terms, as set out below. All notices and licenses set forth below are for informational purposes only.
"""

LICENSE_TMPL = """
%% {name} NOTICES AND INFORMATION BEGIN HERE
=========================================
{license}

=========================================
END OF {name} NOTICES AND INFORMATION
"""

class ThirdParty(object):
    def __init__(self, name, version=None, url=None, license=None):
        self.name = name
        self.version = version
        self.url = url
        self.license = license

    def __str__(self):
        o = {}
        o['name'] = self.name
        o['version'] = self.version
        o['url'] = self.url
        o['license'] = self.license
        return pformat(o)

def get_package_url(package_name):
    p_info = check_output(['pip', 'show', package_name]).split()
    for x in p_info:
        if x.startswith('http'):
            return x
    return None

def get_all_package_urls(third_parties):
    pool = Pool(len(third_parties))
    urls = pool.map(get_package_url, [p.name for p in third_parties])
    for party, url in zip(third_parties, urls):
        party.url = url

def get_third_parties():
    packages = check_output(['pip', 'freeze']).split()
    results = []
    for p in packages:
        name, version = p.split('==')
        if not 'azure-cli' in name:
            results.append(ThirdParty(name, version))
    return results

def _get_github_license(url):
    common_license_names = ['LICENSE', 'LICENSE.txt', 'LICENSE.rst', 'LICENSE.md']
    user, repo = url.split('/')[-2:]
    base_url = 'https://raw.githubusercontent.com/{}/{}/master/'.format(user, repo)
    for license_file in common_license_names:
        r = requests.get(base_url + license_file)
        if r.status_code == 200:
            return r.content
    return None

def get_package_license(url):
    if not url:
        return None
    if url[-1] == '/':
        url = url[:-1]
    if 'github.com' in url:
        return _get_github_license(url)
    return None

def get_all_licenses(third_parties):
    pool = Pool(len(third_parties))
    pkg_licenses = pool.map(get_package_license, [p.url for p in third_parties])
    for party, pkg_license in zip(third_parties, pkg_licenses):
        party.license = pkg_license

def gen_notices(third_parties):
    summaries = ['{}.\t{} {} ({})'.format(idx+1, tp.name, tp.version, tp.url) for idx, tp in enumerate(third_parties)]
    licenses = [LICENSE_TMPL.format(name=tp.name, license=(tp.license or 'LICENSE NOT FOUND')) for tp in third_parties]
    return NOTICE_HEADER + '\n\n' + '\n'.join(summaries) + '\n\n' + ''.join(licenses)

if __name__ == '__main__':
    THIRD_PARTIES = get_third_parties()
    get_all_package_urls(THIRD_PARTIES)
    get_all_licenses(THIRD_PARTIES)
    full_notice = gen_notices(THIRD_PARTIES)
    print(full_notice)
