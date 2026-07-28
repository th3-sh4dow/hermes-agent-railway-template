FROM nousresearch/hermes-agent:v2026.7.20@sha256:f7b35053268f532f98955195c909f15a230470fbcbdacaa9fdecb95707dad04a

# Install Supabase Python client into Hermes's venv
COPY requirements.txt /tmp/requirements.txt
RUN /opt/hermes/.venv/bin/python3 -m ensurepip --upgrade && \
    /opt/hermes/.venv/bin/python3 -m pip install --no-cache-dir -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt

# Copy custom scripts
COPY --chmod=0755 docker-entrypoint.sh /usr/local/bin/hermes-railway-entrypoint
COPY --chmod=0755 supabase_storage.py /usr/local/bin/supabase_storage.py
COPY --chmod=0755 storage-monitor.sh /usr/local/bin/storage-monitor.sh

ENV HERMES_HOME=/data/.hermes \
    HERMES_WRITE_SAFE_ROOT=/data/.hermes \
    HERMES_LAZY_INSTALL_TARGET=/data/.hermes/lazy-packages \
    HERMES_DASHBOARD=1 \
    HERMES_DASHBOARD_HOST=0.0.0.0 \
    HERMES_GATEWAY_BOOTSTRAP_STATE=running

ENTRYPOINT ["/usr/local/bin/hermes-railway-entrypoint"]
CMD ["gateway", "run"]
