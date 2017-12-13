#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import os
import sys
import random
import string
import re
import xml.etree.ElementTree as ElementTree
from subprocess import CalledProcessError, check_output
from webbreaker.webbreakerlogger import Logger
from webbreaker.webbreakerhelper import WebBreakerHelper
from webbreaker.confighelper import Config

try:
    import ConfigParser as configparser

    config = configparser.SafeConfigParser()
except ImportError:  # Python3
    import configparser

    config = configparser.ConfigParser()

runenv = WebBreakerHelper.check_run_env()


class WebInspectEndpoint(object):
    def __init__(self, uri, size):
        self.uri = uri
        self.size = size


class WebInspectSize(object):
    def __init__(self, size, max_scans):
        self.size = size
        self.max_scans = max_scans


class WebInspectConfig(object):
    def __init__(self):
        Logger.app.debug("Starting webinspect config initialization")
        try:
            webinspect_dict = self.__get_webinspect_settings__()
            self.endpoints = webinspect_dict['endpoints']
            self.sizing = webinspect_dict['size_list']
            self.default_size = webinspect_dict['default_size']
            self.webinspect_git = webinspect_dict['git']
            self.webinspect_dir = webinspect_dict['dir']
            self.mapped_policies = webinspect_dict['mapped_policies']
        except KeyError as e:
            Logger.console.error(
                "Your configurations file or scan setting is incorrect see log: {}!!!".format(Logger.app_logfile))
            Logger.app.error("Your configurations file or scan setting is incorrect : {}!!!".format(e))
        Logger.app.debug("Completed webinspect config initialization")

    # TODO: Move to webbreakerconfig
    def __get_webinspect_settings__(self):
        Logger.app.debug("Getting webinspect settings from config file")
        webinspect_dict = {}
        webinspect_setting = Config().config

        try:
            config.read(webinspect_setting)
            webinspect_dict['git'] = config.get("webinspect_repo", "git")
            webinspect_dict['dir'] = config.get("webinspect_repo", "dir")
            webinspect_dict['default_size'] = config.get("webinspect_default_size", "default")
            webinspect_dict['mapped_policies'] = [[option, config.get('webinspect_policies', option)] for option in
                                                  config.options('webinspect_policies')]

            # python 2.7 config parser doesn't offer cross-section interpolation so be a bit magical about
            # which entries under webinspect_endpoints get list comp'd. i.e. starts with e
            webinspect_endpoints = [[option, config.get('webinspect_endpoints', option)] for option in
                                    config.options('webinspect_endpoints')]
            webinspect_dict['endpoints'] = [[endpoint[1].split('|')[0], endpoint[1].split('|')[1]] for endpoint in
                                            webinspect_endpoints if endpoint[0].startswith('e')]
            webinspect_dict['size_list'] = [[option, config.get('webinspect_size', option)] for option in
                                            config.options('webinspect_size')]

        except (configparser.NoOptionError, CalledProcessError) as noe:
            Logger.app.error("{} has incorrect or missing values {}".format(webinspect_setting, noe))
        except configparser.Error as e:
            Logger.app.error("Error reading webinspect settings {} {}".format(webinspect_setting, e))
        Logger.app.debug("Got webinspect settings from config.ini")
        return webinspect_dict

    def __getScanTargets__(self, settings_file_path):
        """
        Given a settings file at the provided path, return a set containing
        the targets for the scan.
        :param settings_file_path: Path to WebInspect settings file
        :return: unordered set of targets
        """
        targets = set()
        try:
            tree = ElementTree.parse(settings_file_path)
            root = tree.getroot()
            for target in root.findall("xmlns:HostFolderRules/"
                                       "xmlns:List/"
                                       "xmlns:HostFolderRuleData/"
                                       "xmlns:HostMatch/"
                                       "xmlns:List/"
                                       "xmlns:LookupList/"
                                       "xmlns:string",
                                       namespaces={'xmlns': 'http://spidynamics.com/schemas/scanner/1.0'}):
                targets.add(target.text)
        except Exception as e:
            Logger.app.error("Unable to read the config file {0}".format(e))

        return targets

    def parse_webinspect_options(self, options):
        webinspect_dict = {}

        # Remove any unneeded file extentions
        if options['settings'] is not None and options['settings'][-4:] == '.xml':
            options['settings'] = options['settings'][:-4]

        if options['upload_webmacros'] is not None and options['upload_webmacros'][-9:] == '.webmacro':
            options['upload_webmacros'] = options['upload_webmacros'][:-9]

        if options['upload_policy'] is not None and options['upload_policy'][-7:] == '.policy':
            options['upload_policy'] = options['upload_policy'][:-7]

        if options['scan_policy'] is not None and options['scan_policy'][-7:] == '.policy':
            options['scan_policy'] = options['scan_policy'][:-7]

        if not options['scan_name']:
            try:
                if runenv == "jenkins":
                    options['scan_name'] = os.getenv("JOB_NAME")
                    if "/" in options['scan_name']:
                        options['scan_name'] = os.getenv("BUILD_TAG")
                else:
                    options['scan_name'] = "webinspect" + "-" + "".join(
                        random.choice(string.ascii_uppercase + string.digits) for _ in range(5))
            except AttributeError as e:
                Logger.app.error("The {0} is unable to be created! {1}".format(options['scan_name'], e))

        if options['upload_settings']:
            # Full path is specified in settings
            # TODO: Move al os.path functions to helper class
            if os.path.isfile(options['upload_settings'] + '.xml'):
                options['upload_settings'] = options['upload_settings'] + '.xml'
            if not os.path.isfile(options['upload_settings']):
                try:
                    options['upload_scan_settings'] = str("{}".format(os.path.join(os.path.dirname(__file__),
                                                                                   self.webinspect_dir, 'settings',
                                                                                   options[
                                                                                       'upload_settings'] + '.xml')))
                except (AttributeError, TypeError) as e:
                    Logger.app.error("The {0} is unable to be assigned! {1}".format(options['upload_settings'], e))
            else:
                options['upload_scan_settings'] = options['upload_settings']
        else:
            if os.path.isfile(options['settings'] + '.xml'):
                options['settings'] = options['settings'] + '.xml'
            if not os.path.isfile(options['settings']) and options['settings'] != 'Default':
                options['upload_settings'] = str("{}".format(os.path.join(os.path.dirname(__file__),
                                                                          self.webinspect_dir, 'settings',
                                                                          options['settings'] + '.xml')))
            elif options['settings'] == 'Default':
                # All WebInspect servers come with a Default.xml settings file, no need to upload it
                options['upload_settings'] = None
            else:
                options['upload_settings'] = options['settings']
                # Settings is used later by the api so we need to cut off the filepath info
                options['settings'] = re.search('.*/(.*)\.xml', options['settings']).group(1)

        # if login macro has been specified, ensure it's uploaded.
        if options['login_macro']:
            if options['upload_webmacros']:
                # add macro to existing list.
                options['upload_webmacros'].append(options['login_macro'])
            else:
                # add macro to new list
                options['upload_webmacros'] = []
                options['upload_webmacros'].append(options['login_macro'])

        # if workflow macros have been provided, ensure they are uploaded
        if options['workflow_macros']:
            if options['upload_webmacros']:
                # add macros to existing list
                options['upload_webmacros'].extend(options['workflow_macros'])
            else:
                # add macro to new list
                options['upload_webmacros'] = list(options['workflow_macros'])

        if options['upload_webmacros']:
            try:
                # trying to be clever, remove any duplicates from our upload list
                options['upload_webmacros'] = list(set(options['upload_webmacros']))
                corrected_paths = []
                for webmacro in options['upload_webmacros']:
                    if os.path.isfile(webmacro + '.webmacro'):
                        webmacro = webmacro + '.webmacro'
                    if not os.path.isfile(webmacro):
                        corrected_paths.append(str("{}".format(os.path.join(os.path.dirname(__file__),
                                                                            self.webinspect_dir, 'webmacros',
                                                                            webmacro + '.webmacro'))))
                    else:
                        corrected_paths.append(webmacro)
                options['upload_webmacros'] = corrected_paths

            except (AttributeError, TypeError) as e:
                Logger.app.error("The {0} is unable to be assigned! {1}".format(options['upload_webmacros'], e))

        # if upload_policy provided explicitly, follow that. otherwise, default to scan_policy if provided
        if options['upload_policy']:
            if os.path.isfile(options['upload_policy'] + '.policy'):
                options['upload_policy'] = options['upload_policy'] + '.policy'
            if not os.path.isfile(options['upload_policy']):
                options['upload_policy'] = str("{}".format(os.path.join(os.path.dirname(__file__),
                                                                        self.webinspect_dir, 'policies',
                                                                        options['upload_policy'] + '.policy')))

        elif options['scan_policy']:
            if os.path.isfile(options['scan_policy'] + '.policy'):
                options['scan_policy'] = options['scan_policy'] + '.policy'
            if not os.path.isfile(options['scan_policy']):
                options['upload_policy'] = str("{}".format(os.path.join(os.path.dirname(__file__),
                                                                        self.webinspect_dir, 'policies',
                                                                        options['scan_policy'] + '.policy')))
            else:
                options['upload_policy'] = options['scan_policy']

        # Determine the targets specified in a settings file
        if options['upload_settings']:
            targets = self.__getScanTargets__(options['upload_settings'])
        else:
            targets = None
        # Unless explicitly stated --allowed_hosts by default will use all values from --start_urls
        if not options['allowed_hosts']:
            options['allowed_hosts'] = options['start_urls']

        try:
            webinspect_dict['webinspect_settings'] = options['settings']
            webinspect_dict['webinspect_scan_name'] = options['scan_name']
            webinspect_dict['webinspect_upload_settings'] = options['upload_settings']
            webinspect_dict['webinspect_upload_policy'] = options['upload_policy']
            webinspect_dict['webinspect_upload_webmacros'] = options['upload_webmacros']
            webinspect_dict['webinspect_overrides_scan_mode'] = options['scan_mode']
            webinspect_dict['webinspect_overrides_scan_scope'] = options['scan_scope']
            webinspect_dict['webinspect_overrides_login_macro'] = options['login_macro']
            webinspect_dict['webinspect_overrides_scan_policy'] = options['scan_policy']
            webinspect_dict['webinspect_overrides_scan_start'] = options['scan_start']
            webinspect_dict['webinspect_overrides_start_urls'] = options['start_urls']
            webinspect_dict['webinspect_scan_targets'] = targets
            webinspect_dict['webinspect_workflow_macros'] = options['workflow_macros']
            webinspect_dict['webinspect_allowed_hosts'] = options['allowed_hosts']
            webinspect_dict['webinspect_scan_size'] = options['size'] if options['size'] else self.default_size
            webinspect_dict['fortify_user'] = options['fortify_user']

        except argparse.ArgumentError as e:
            Logger.app.error("There was an error in the options provided!: ".format(e))

        Logger.app.debug("Completed webinspect settings parse")
        return webinspect_dict

    # TODO: Move to the WebbreakerConfig class
    def fetch_webinspect_configs(self, options):
        config_helper = Config()
        etc_dir = config_helper.etc
        git_dir = os.path.join(config_helper.git, '.git')
        
        try:
            if options['settings'] == 'Default':
                Logger.app.debug("Default settings were used")
            elif os.path.exists(git_dir):
                Logger.app.info("Updating your WebInspect configurations from {}".format(etc_dir))
                check_output(['git', 'init', etc_dir])
                check_output(['git', '--git-dir=' + git_dir, '--work-tree=' + str(config_helper.git), 'reset', '--hard'])
                check_output(['git', '--git-dir=' + git_dir, '--work-tree=' + str(config_helper.git), 'pull', '--rebase'])
                sys.stdout.flush()
            elif not os.path.exists(git_dir):
                Logger.app.info("Cloning your specified WebInspect configurations to {}".format(config_helper.git))
                check_output(['git', 'clone', self.webinspect_git, config_helper.git])
            else:
                Logger.app.error(
                    "No GIT Repo was declared in your config.ini, therefore nothing will be cloned!")
        except (CalledProcessError, AttributeError) as e:
            Logger.app.error("Uh oh something is wrong with your WebInspect configurations!!\nError: {}".format(e))
        Logger.app.debug("Completed webinspect config fetch")
