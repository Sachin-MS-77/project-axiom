FROM ubuntu:22.04

RUN apt-get update && \
    apt-get install -y openssh-server iproute2 && \
    apt-get clean

# Leave root login and password auth at Ubuntu's default-commented state
# so ssh_root_login / ssh_password_auth will come back UNKNOWN — realistic
# for a "clean-ish but not perfectly hardened" starter target.

# Keep the container alive so docker exec can run commands against it
CMD ["tail", "-f", "/dev/null"]
