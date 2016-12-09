# -*- python -*-
# ex: set filetype=python:
"""buildbot master script for cite"""
import os
import json
import string
import ConfigParser
from buildbot.reporters.github import GitHubStatusPush
from buildbot.plugins import *
from buildbot.process import results
from twisted.internet import defer
from twisted.python import log

CONFIG_PATH = os.getenv('CONFIG_PATH', '/var/lib/buildbot/build.conf')

Config = ConfigParser.ConfigParser()
Config.read(CONFIG_PATH)

c = BuildmasterConfig = {}
c['buildbotNetUsageData'] = None
c['title'] = Config.get("buildbot", "title")
c['titleURL'] = Config.get("buildbot", "title_url")
c['buildbotURL'] = Config.get("buildbot", "url")



class CiteGitHubStatusPush(GitHubStatusPush):
    @defer.inlineCallbacks
    def send(self, build):
        if build['complete']:
            if build['results'] == results.SUCCESS:
                self.endDescription = util.Interpolate('Build %(kw:state)s. imageName:%(kw:imageName)s',
                    state=results.Results[build['results']],
                    imageName=getImage)
            else:
                steps = yield self.master.data.get(('builds', build['buildid'], "steps"))
                logURL = ''
                for step in reversed(steps):
                    if step['results'] != results.SUCCESS:
                        logs = yield self.master.data.get(("steps", step['stepid'], 'logs'))
                        logURL = '{buildbotURL}api/v2/logs/{logid}/contents'.format(
                            buildbotURL=self.master.config.buildbotURL,
                            logid=logs[0]['logid']
                        )
                        break

                self.endDescription = util.Interpolate(
                    'Build %(kw:state)s. logURL:%(kw:logURL)s',
                    state=results.Results[build['results']],
                    logURL=logURL)

        yield GitHubStatusPush.send(self, build)

def _getImage(rawProjectName):
    pl = rawProjectName.lower().split('/')
    for i in range(0, len(pl)):
        pl[i] = pl[i].translate(None, string.punctuation + string.whitespace)

    return '/'.join(pl)

@util.renderer
def getImageName(props):
    rawProjectName = str(props.getProperty('project'))
    projectName = _getImage(rawProjectName)

    return '{}/{}'.format(Config.get("docker", "registry"), projectName)

@util.renderer
def getImage(props):
    rawProjectName = str(props.getProperty('project'))
    projectName = _getImage(rawProjectName)

    return '{}/{}:{}'.format(Config.get("docker", "registry"), projectName, props.getProperty('revision'))

@util.renderer
def getLatestImage(props):
    rawProjectName = str(props.getProperty('project'))
    projectName = _getImage(rawProjectName)
    return '{}/{}:latest'.format(Config.get("docker", "registry"), projectName)

####### WORKERS
workernames = []
for wh in json.loads(Config.get("buildbot", "workers")):
    for i in range(1, int(Config.get("buildbot", "worker_instance"))+1):
        workernames.append("%s-%02d" % (wh, i))

# The 'workers' list defines the set of recognized workers. Each element is
# a Worker object, specifying a unique worker name and password.  The same
# worker name and password must be configured on the worker.
workers = []
for wn in workernames:
    workers.append(worker.Worker(wn, Config.get("buildbot", "worker_password")))
c['workers'] = workers

# 'protocols' contains information about protocols which master will use for
# communicating with workers. You must define at least 'port' option that workers
# could connect to your master with this protocol.
# 'port' must match the value configured into the workers (with their
# --master option)
c['protocols'] = {'pb': {'port': 9989}}

####### CHANGESOURCES

# the 'change_source' setting tells the buildmaster how it should find out
# about source code changes.  Here we point to the buildbot clone of pyflakes.
c['change_source'] = []

####### SCHEDULERS

# Configure the Schedulers, which decide how to react to incoming changes.  In this
# case, just kick off a 'runtests' build
c['schedulers'] = []
c['schedulers'].append(schedulers.AnyBranchScheduler(
    name="all",
    builderNames=["cite-build"]))
c['schedulers'].append(schedulers.ForceScheduler(
    name="force",
    builderNames=["cite-build"]))

####### BUILDERS

# The 'builders' list defines the Builders, which tell Buildbot how to perform a build:
# what steps, and which workers can execute them.  Note that any particular build will
# only take place on one worker.
factory = util.BuildFactory()

# change workdir for each projects
factory.workdir = util.Interpolate('%(src::project)s')

# check out the source
factory.addStep(steps.Git(
    name="source checkout",
    logEnviron=False,
    repourl=util.Interpolate('%(kw:github_base_url)s/%(src::project)s.git', github_base_url=Config.get("github", "base_url")),
    mode='incremental',
    haltOnFailure=True)
)

# pull latest image for build cache
factory.addStep(steps.ShellCommand(
    name="docker pull latest(for cache, ignore error)",
    logEnviron=False,
    command=["docker", "pull", getLatestImage],
    haltOnFailure=False,
    warnOnFailure=False,
    flunkOnFailure=False)
)

# docker build
factory.addStep(steps.ShellCommand(
    name="docker build",
    logEnviron=False,
    command=["docker", "build", "-t", getImage, "."],
    haltOnFailure=True)
)

# tag current image as latest
factory.addStep(steps.ShellCommand(
    name="docker tag latest",
    logEnviron=False,
    command=["docker", "tag", getImage, getLatestImage],
    haltOnFailure=True)
)

# docker push
factory.addStep(steps.ShellCommand(
    name="docker push",
    logEnviron=False,
    command=["docker", "push", getImage],
    haltOnFailure=True)
)

factory.addStep(steps.ShellCommand(
    name="docker push latest(for cache, ignore error)",
    logEnviron=False,
    command=["docker", "push", getLatestImage],
    haltOnFailure=True)
)

factory.addStep(steps.ShellCommand(
    name="untag pushed docker image",
    logEnviron=False,
    command=["docker", "rmi", getImage],
    haltOnFailure=False,
    warnOnFailure=False,
    flunkOnFailure=False)
)

# factory.addStep(steps.ShellCommand(
#     name="remove dangling docker images",
#     logEnviron=False,
#     command=["/bin/sh", "-c", "docker images --filter dangling=true --quiet | xargs docker rmi"],
#     haltOnFailure=False,
#     warnOnFailure=False,
#     flunkOnFailure=False)
# )

c['builders'] = []
c['builders'].append(
    util.BuilderConfig(name="cite-build",
                       workernames=workernames,
                       factory=factory))

####### REPORTERS
c['services'] = [
    GitHubStatusPush(
        baseURL=Config.get("github", "api_url"),
        token=Config.get("github", "api_token"),
        verbose=True
    )
]

# minimalistic config to activate new web UI
c['www'] = dict(port=8010,
                plugins=dict(waterfall_view={}, console_view={}),
                change_hook_dialects={'github':{ }})

####### DB URL
c['db'] = {
    # This specifies what database buildbot uses to store its state.  You can leave
    # this at its default for all but the largest installations.
    # 'db_url' : "sqlite:///state.sqlite",
    'db_url' : Config.get("buildbot", "database"),
}
