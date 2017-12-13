# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------

import os
from pprint import pformat
from six.moves import configparser

from knack.log import get_logger
from knack.util import CLIError
from knack.config import get_config_parser

from msrestazure.azure_cloud import (CloudEndpoints as _CloudEndpoints,
                                     CloudSuffixes as _CloudSuffixes,
                                     Cloud,
                                     AZURE_PUBLIC_CLOUD,
                                     AZURE_CHINA_CLOUD,
                                     AZURE_US_GOV_CLOUD,
                                     AZURE_GERMAN_CLOUD)

from azure.cli.core.profiles import API_PROFILES
from azure.cli.core._config import GLOBAL_CONFIG_DIR


logger = get_logger(__name__)


CLOUD_CONFIG_FILE = os.path.join(GLOBAL_CONFIG_DIR, 'clouds.config')


class CloudNotRegisteredException(Exception):
    def __init__(self, cloud_name):
        super(CloudNotRegisteredException, self).__init__(cloud_name)
        self.cloud_name = cloud_name

    def __str__(self):
        return "The cloud '{}' is not registered.".format(self.cloud_name)


class CloudAlreadyRegisteredException(Exception):
    def __init__(self, cloud_name):
        super(CloudAlreadyRegisteredException, self).__init__(cloud_name)
        self.cloud_name = cloud_name

    def __str__(self):
        return "The cloud '{}' is already registered.".format(self.cloud_name)


class CannotUnregisterCloudException(Exception):
    pass


class CloudEndpointNotSetException(CLIError):
    pass


class CloudSuffixNotSetException(CLIError):
    pass


class CloudEndpoints(_CloudEndpoints):  # pylint: disable=too-few-public-methods,too-many-instance-attributes
    def __getattribute__(self, name):
        val = object.__getattribute__(self, name)
        if val is None:
            raise CloudEndpointNotSetException("The endpoint '{}' for this cloud "
                                               "is not set but is used.\n"
                                               "{} may be corrupt or invalid.\nResolve the error or delete this file "
                                               "and try again.".format(name, CLOUD_CONFIG_FILE))
        return val


class CloudSuffixes(_CloudSuffixes):  # pylint: disable=too-few-public-methods
    def __getattribute__(self, name):
        val = object.__getattribute__(self, name)
        if val is None:
            raise CloudSuffixNotSetException("The suffix '{}' for this cloud "
                                             "is not set but is used.\n"
                                             "{} may be corrupt or invalid.\nResolve the error or delete this file "
                                             "and try again.".format(name, CLOUD_CONFIG_FILE))
        return val


KNOWN_CLOUDS = [AZURE_PUBLIC_CLOUD, AZURE_CHINA_CLOUD, AZURE_US_GOV_CLOUD, AZURE_GERMAN_CLOUD]


def _set_active_cloud(cli_ctx, cloud_name):
    cli_ctx.config.set_value('cloud', 'name', cloud_name)


def get_active_cloud_name(cli_ctx):
    try:
        return cli_ctx.config.config_parser.get('cloud', 'name')
    except (configparser.NoOptionError, configparser.NoSectionError):
        _set_active_cloud(cli_ctx, AZURE_PUBLIC_CLOUD.name)
        return AZURE_PUBLIC_CLOUD.name


def _get_cloud(cli_ctx, cloud_name):
    return next((x for x in get_clouds(cli_ctx) if x.name == cloud_name), None)


def cloud_is_registered(cli_ctx, cloud_name):
    return bool(_get_cloud(cli_ctx, cloud_name))


def get_custom_clouds(cli_ctx):
    known_cloud_names = [c.name for c in KNOWN_CLOUDS]
    return [c for c in get_clouds(cli_ctx) if c.name not in known_cloud_names]


def get_clouds(cli_ctx):
    clouds = []
    config = get_config_parser()
    # Start off with known clouds and apply config file on top of current config
    for c in KNOWN_CLOUDS:
        _config_add_cloud(config, c)
    config.read(CLOUD_CONFIG_FILE)
    for section in config.sections():
        c = Cloud(section)
        for option in config.options(section):
            if option == 'profile':
                c.profile = config.get(section, option)
            if option.startswith('endpoint_'):
                setattr(c.endpoints, option.replace('endpoint_', ''), config.get(section, option))
            elif option.startswith('suffix_'):
                setattr(c.suffixes, option.replace('suffix_', ''), config.get(section, option))
        if c.profile is None:
            # If profile isn't set, use latest
            setattr(c, 'profile', 'latest')
        if c.profile not in API_PROFILES:
            raise CLIError('Profile {} does not exist or is not supported.'.format(c.profile))
        if not c.endpoints.has_endpoint_set('management') and \
                c.endpoints.has_endpoint_set('resource_manager'):
            # If management endpoint not set, use resource manager endpoint
            c.endpoints.management = c.endpoints.resource_manager
        clouds.append(c)
    active_cloud_name = get_active_cloud_name(cli_ctx)
    for c in clouds:
        if c.name == active_cloud_name:
            c.is_active = True
            break
    return clouds


def get_cloud(cli_ctx, cloud_name):
    cloud = _get_cloud(cli_ctx, cloud_name)
    if not cloud:
        raise CloudNotRegisteredException(cloud_name)
    return cloud


def get_active_cloud(cli_ctx):
    try:
        return get_cloud(cli_ctx, get_active_cloud_name(cli_ctx))
    except CloudNotRegisteredException as err:
        logger.warning(err)
        logger.warning("Resetting active cloud to'%s'.", AZURE_PUBLIC_CLOUD.name)
        _set_active_cloud(cli_ctx, AZURE_PUBLIC_CLOUD.name)
        return get_cloud(cli_ctx, AZURE_PUBLIC_CLOUD.name)


def get_cloud_subscription(cloud_name):
    config = get_config_parser()
    config.read(CLOUD_CONFIG_FILE)
    try:
        return config.get(cloud_name, 'subscription')
    except (configparser.NoOptionError, configparser.NoSectionError):
        return None


def set_cloud_subscription(cli_ctx, cloud_name, subscription):
    if not _get_cloud(cli_ctx, cloud_name):
        raise CloudNotRegisteredException(cloud_name)
    config = get_config_parser()
    config.read(CLOUD_CONFIG_FILE)
    if subscription:
        try:
            config.add_section(cloud_name)
        except configparser.DuplicateSectionError:
            pass
        config.set(cloud_name, 'subscription', subscription)
    else:
        try:
            config.remove_option(cloud_name, 'subscription')
        except configparser.NoSectionError:
            pass
    if not os.path.isdir(GLOBAL_CONFIG_DIR):
        os.makedirs(GLOBAL_CONFIG_DIR)
    with open(CLOUD_CONFIG_FILE, 'w') as configfile:
        config.write(configfile)


def _set_active_subscription(cli_ctx, cloud_name):
    from azure.cli.core._profile import (Profile, _ENVIRONMENT_NAME, _SUBSCRIPTION_ID,
                                         _STATE, _SUBSCRIPTION_NAME)
    profile = Profile(cli_ctx)
    subscription_to_use = get_cloud_subscription(cloud_name) or \
                          next((s[_SUBSCRIPTION_ID] for s in profile.load_cached_subscriptions()  # noqa
                                if s[_STATE] == 'Enabled'),
                               None)
    if subscription_to_use:
        try:
            profile.set_active_subscription(subscription_to_use)
            sub = profile.get_subscription(subscription_to_use)
            logger.warning("Active subscription switched to '%s (%s)'.",
                           sub[_SUBSCRIPTION_NAME], sub[_SUBSCRIPTION_ID])
        except CLIError as e:
            logger.warning(e)
            logger.warning("Unable to automatically switch the active subscription. "
                           "Use 'az account set'.")
    else:
        logger.warning("Use 'az login' to log in to this cloud.")
        logger.warning("Use 'az account set' to set the active subscription.")


def switch_active_cloud(cli_ctx, cloud_name):
    if cli_ctx.cloud.name == cloud_name:
        return
    if not _get_cloud(cli_ctx, cloud_name):
        raise CloudNotRegisteredException(cloud_name)
    _set_active_cloud(cli_ctx, cloud_name)
    logger.warning("Switched active cloud to '%s'.", cloud_name)
    _set_active_subscription(cli_ctx, cloud_name)


def _config_add_cloud(config, cloud, overwrite=False):
    """ Add a cloud to a config object """
    try:
        config.add_section(cloud.name)
    except configparser.DuplicateSectionError:
        if not overwrite:
            raise CloudAlreadyRegisteredException(cloud.name)
    if cloud.profile:
        config.set(cloud.name, 'profile', cloud.profile)
    for k, v in cloud.endpoints.__dict__.items():
        if v is not None:
            config.set(cloud.name, 'endpoint_{}'.format(k), v)
    for k, v in cloud.suffixes.__dict__.items():
        if v is not None:
            config.set(cloud.name, 'suffix_{}'.format(k), v)


def _save_cloud(cloud, overwrite=False):
    config = get_config_parser()
    config.read(CLOUD_CONFIG_FILE)
    _config_add_cloud(config, cloud, overwrite=overwrite)
    if not os.path.isdir(GLOBAL_CONFIG_DIR):
        os.makedirs(GLOBAL_CONFIG_DIR)
    with open(CLOUD_CONFIG_FILE, 'w') as configfile:
        config.write(configfile)


def add_cloud(cli_ctx, cloud):
    if _get_cloud(cli_ctx, cloud.name):
        raise CloudAlreadyRegisteredException(cloud.name)
    _save_cloud(cloud)


def update_cloud(cli_ctx, cloud):
    if not _get_cloud(cli_ctx, cloud.name):
        raise CloudNotRegisteredException(cloud.name)
    _save_cloud(cloud, overwrite=True)


def remove_cloud(cli_ctx, cloud_name):
    if not _get_cloud(cli_ctx, cloud_name):
        raise CloudNotRegisteredException(cloud_name)
    if cloud_name == cli_ctx.cloud.name:
        raise CannotUnregisterCloudException("The cloud '{}' cannot be unregistered "
                                             "as it's currently active.".format(cloud_name))
    is_known_cloud = next((x for x in KNOWN_CLOUDS if x.name == cloud_name), None)
    if is_known_cloud:
        raise CannotUnregisterCloudException("The cloud '{}' cannot be unregistered "
                                             "as it's not a custom cloud.".format(cloud_name))
    config = get_config_parser()
    config.read(CLOUD_CONFIG_FILE)
    config.remove_section(cloud_name)
    with open(CLOUD_CONFIG_FILE, 'w') as configfile:
        config.write(configfile)
