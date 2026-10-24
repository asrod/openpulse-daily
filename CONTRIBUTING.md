# Contributing

This repository publishes snapshots from OpenPulse's public API. Rankings follow
the website's existing methodology. Please do not edit generated README, daily,
or data files by hand; report data issues with links and observation timestamps.

Run `python -m unittest discover -s tests -v` before submitting exporter changes.
Python 3.12 is used in CI. The exporter has no third-party dependencies.

The scheduled workflow runs daily at 09:17 Asia/Shanghai. GitHub can delay a run;
the workflow can also be started manually under Actions. Public-repository
scheduled workflows may be disabled after 60 days without repository activity.
The first successful snapshot for a date is retained; another run that day
validates the source but does not replace the archive. A failed fetch or invalid
dataset leaves published files untouched.

The workflow uses this repository's `GITHUB_TOKEN`. It needs no OpenPulse admin
credential, database access, or personal access token. Optional OpenPulse admin
integration uses a GitHub App with Actions write and Contents read permissions
to request this workflow and inspect its status.
