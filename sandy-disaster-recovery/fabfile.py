
import os
from tempfile import mkdtemp

from distutils.dir_util import copy_tree

from fabric.api import env, task, local, abort
from fabric.colors import yellow
from fabric.utils import warn as raw_warn
from fabric.contrib.console import confirm

import yaml


# constants

APP_YAML_FILENAME = 'app.yaml'
APP_YAML_TEMPLATE_FILENAME = 'app.yaml.template'


# find GAE appcfg

GAE_APPCFG_POSSIBLE_LOCATIONS = [
    '../../google_appengine/appcfg.py',
]

try:
    _appcfg_path = (
        path for path in GAE_APPCFG_POSSIBLE_LOCATIONS
        if os.path.exists(path)
    ).next()
except StopIteration:
    abort('appcfg.py not found - edit GAE_APPCFG_POSSIBLE_LOCATIONS')


# define env

env.master_branch = "master"
env.appcfg = os.path.realpath(_appcfg_path)


# define apps

MINI_YAML = """ 
- application: sandy-helping-hands
  secure: always
  allow_unclean_deploy: true
  sandbox: true

- application: sandy-disaster-recovery
  secure: always

- application: crisiscleanup-demo
  secure: optional

- application: crisis-cleanup-au
  secure: always

- application: crisis-cleanup-au-demo
  secure: optional
"""

APPS = {
    d['application']:d for d in yaml.load(MINI_YAML)
}

LOCAL_APP = {
    'application': 'local',
    'secure': 'optional'
}


# functions

def warn(msg):
    return raw_warn(yellow(msg))


def app_yaml_template_present():
    " Check that the app.yaml template is present. "
    if APP_YAML_TEMPLATE_FILENAME not in os.listdir('.'):
        abort("%s not found" % APP_YAML_TEMPLATE_FILENAME)
    return True


def working_directory_clean(app_defn):
    " Check that the working directory is clean. "
    git_status = local("git status", capture=True)
    if "working directory clean" not in git_status:
        if app_defn.get('allow_unclean_deploy', False):
            warn("Working directory not clean (ignoring for %s)" % app_defn['application'])
        else:
            abort("Working directory must be clean to deploy to %s" % app_defn['application'])
    return True


def on_master_branch(app_defn):
    " Check master branch is checked out. "
    checked_out_branch = local("git rev-parse --abbrev-ref HEAD", capture=True)
    if checked_out_branch != env.master_branch:
        if app_defn.get('allow_unclean_deploy', False):
            warn("Branch is %s (ignoring for %s)" % (checked_out_branch, app_defn['application']))
        else:
            abort("%s branch must be checked out to deploy to %s" % (
                env.master_branch, app_defn['application']))
    return True


def master_pushed_to_remote(app_defn):
    " Check that the master branch is pushed to origin. "
    local_master_ref = local("git rev-parse %s" % env.master_branch, capture=True)
    origin_master_ref = local("git rev-parse origin/%s" % env.master_branch, capture=True)
    if local_master_ref != origin_master_ref:
        if app_defn.get('allow_unclean_deploy', False):
            warn("%s and origin/%s differ (ignoring for %s)" % (
                env.master_branch, env.master_branch, app_defn['application']))
        else:
            abort("%s must be pushed to origin to deploy to %s" % (
                env.master_branch, app_defn['application']))
    return True


def ok_to_deploy(app_defn):
    return (
        app_yaml_template_present() and
        working_directory_clean(app_defn) and
        on_master_branch(app_defn) and
        master_pushed_to_remote(app_defn)
    )


def write_app_yaml(app_defn, preamble=None):
    # set preamble
    if preamble is None:
        preamble = "\n# *** AUTOMATICALLY GENERATED BY FABRIC ***\n"

    # open template
    with open(APP_YAML_TEMPLATE_FILENAME)as app_yaml_template_fd:
        yaml = app_yaml_template_fd.read()

        # replace placeholders
        for key, val in app_defn.items():
            placeholder_name = ("$%s_PLACEHOLDER" % key).upper()
            if placeholder_name in yaml:
                yaml = yaml.replace(placeholder_name, val)

    # write app.yaml
    with open(APP_YAML_FILENAME, 'w') as app_yaml_fd:
        app_yaml_fd.write(preamble)
        app_yaml_fd.write(yaml)


def delete_app_yaml():
    os.remove(APP_YAML_FILENAME)


def update():
    " Update GAE from working dir. "
    local("%(appcfg)s --oauth2 update . " % env)


def get_app_definitions(app_names_or_all):
    if app_names_or_all == ['all']:
        return [defn for name,defn in APPS.items() if not defn.get('sandbox')]
    else:
        try:
            return [APPS[name] for name in app_names_or_all]
        except KeyError, e:
            abort("'%s' is not a known application." % e.message)


@task
def list():
    " List known application names. "
    for name in APPS:
        print name


@task
def deploy(apps, tag='HEAD'):
    """
    Deploy to one or more applications
    (semicolon-separated values or 'all').
    """
    # if deploying to all, check
    if apps == 'all':
        if not confirm("Deploy to ALL apps, excluding sandbox? Are you sure?", default=False):
            abort("Deploy to all except sandbox unconfirmed")

    # get app definitions
    app_defns = get_app_definitions(apps.split(';'))

    # before doing anything, check if *all* apps are ok to deploy to
    map(ok_to_deploy, app_defns)

    # check tag
    if not (tag == 'HEAD' or tag in local('git tag -l', capture=True)):
        abort("Unknown tag '%s'" % tag)

    # log that we are deploying
    print "\n\n** Deploying %s to %s **\n\n" % (tag, ', '.join(
        app_defn['application'] for app_defn in app_defns
    ))

    # copy dir for deployment
    build_dir = mkdtemp()
    print "Building to %s" % build_dir
    local("git archive %s | tar -x -C %s" % (tag, build_dir))
    os.chdir(build_dir)

    # deploy to all specified apps
    for app_defn in app_defns:
        write_app_yaml(app_defn)
        update()
        delete_app_yaml()

    # output success message
    print "\nSuccessfully deployed to %s." % ', '.join(
        app_defn['application'] for app_defn in app_defns
    )


@task
def write_local_app_yaml():
    " Write out app.yaml for local dev use. "
    write_app_yaml(
        LOCAL_APP,
        preamble=(
            "\n# ** GENERATED BY FABRIC FOR LOCAL USE ONLY **\n" + 
            "#\n" + 
            "# (edit %s instead)\n\n" % APP_YAML_TEMPLATE_FILENAME
        )
    )
