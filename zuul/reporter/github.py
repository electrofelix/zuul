# Copyright 2015 Puppet Labs
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

import logging
import voluptuous as v
import time

from zuul.reporter import BaseReporter
from zuul.exceptions import MergeFailure


class GithubReporter(BaseReporter):
    """Sends off reports to Github."""

    name = 'github'
    log = logging.getLogger("zuul.GithubReporter")

    def __init__(self, reporter_config={}, sched=None, connection=None):
        super(GithubReporter, self).__init__(
            reporter_config, sched, connection)
        self._github_status_value = None
        self._set_commit_status = self.reporter_config.get('status', False)
        self._create_comment = self.reporter_config.get('comment', False)
        self._merge = self.reporter_config.get('merge', False)

    def postConfig(self):
        github_status_values = {
            'start': 'pending',
            'success': 'success',
            'failure': 'failure',
            'merge-failure': 'failure'
        }
        self._github_status_value = github_status_values[self._action]

    def report(self, source, pipeline, item, message=None):
        """Comment on PR and set commit status."""
        if self._create_comment:
            self.addPullComment(pipeline, item, message)
        if (self._set_commit_status and
            hasattr(item.change, 'patchset') and
            item.change.patchset is not None):
            self.setPullStatus(pipeline, item)
        if (self._merge and
            hasattr(item.change, 'number')):
            self.mergePull(item)

    def addPullComment(self, pipeline, item, message):
        if message is None:
            message = self._formatItemReport(pipeline, item)
        owner, project = item.change.project.name.split('/')
        pr_number = item.change.number
        self.log.debug(
            'Reporting change %s, params %s, message: %s' %
            (item.change, self.reporter_config, message))
        self.connection.commentPull(owner, project, pr_number, message)

    def setPullStatus(self, pipeline, item):
        owner, project = item.change.project.name.split('/')
        sha = item.change.patchset
        context = pipeline.name
        state = self._github_status_value
        url = ''
        if self.sched.config.has_option('zuul', 'status_url'):
            url = self.sched.config.get('zuul', 'status_url')
        description = ''
        if pipeline.description:
            description = pipeline.description

        self.log.debug(
            'Reporting change %s, params %s, status:\n'
            'context: %s, state: %s, description: %s, url: %s' %
            (item.change, self.reporter_config, context, state,
             description, url))

        self.connection.setCommitStatus(
            owner, project, sha, state, url, description, context)

    def mergePull(self, item):
        owner, project = item.change.project.name.split('/')
        pr_number = item.change.number
        sha = item.change.patchset
        self.log.debug('Reporting change %s, params %s, merging via API' %
                       (item.change, self.reporter_config))
        try:
            self.connection.mergePull(owner, project, pr_number, sha)
        except MergeFailure:
            time.sleep(2)
            self.log.debug('Trying to merge change %s again...' % item.change)
            self.connection.mergePull(owner, project, pr_number, sha)
        item.change.is_merged = True


def getSchema():
    github_reporter = v.Schema({
        'status': bool,
        'comment': bool,
        'merge': bool
    })
    return github_reporter
