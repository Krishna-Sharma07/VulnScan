FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends unzip \
    && rm -rf /var/lib/apt/lists/* \
    # safety pinned to the last version whose `check` subcommand queries
    # PyUp's open vulnerability DB directly - 3.x moved that command behind a
    # required account/API-key login, which this offline static-analysis
    # container has no business depending on.
    && pip install --no-cache-dir bandit==1.7.9 "safety==2.3.5"

# put_archive() (app/services/code_scanner.py) writes into this container
# before it's started, i.e. before the entrypoint script gets a chance to
# create anything - the directory has to already exist in the image itself.
RUN mkdir -p /code

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
