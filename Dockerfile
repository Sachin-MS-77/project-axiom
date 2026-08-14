FROM ubuntu:22.04

RUN apt-get update && \
    apt-get install -y openssh-server iproute2 && \
    apt-get clean

# Deliberately insecure config — explicit, not just defaulted —
# so ssh_root_login and ssh_password_auth return real FAIL verdicts,
# not UNKNOWN.
RUN echo "PermitRootLogin yes" >> /etc/ssh/sshd_config && \
    echo "PasswordAuthentication yes" >> /etc/ssh/sshd_config

# Deliberately world-writable file under /etc, so world_writable_files
# returns a real FAIL too.
RUN touch /etc/broken_permissions_test.conf && \
    chmod 666 /etc/broken_permissions_test.conf

CMD ["tail", "-f", "/dev/null"]
