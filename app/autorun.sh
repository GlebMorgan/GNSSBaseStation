#!/usr/bin/env bash

# Add configuration to systemd-tmpfiles to create tmpfs directory for temporary data
echo "# Type  Path            Mode  UID  GID  Age  Argument
  d     /run/user/bs    1775  pi   pi   -
" > /usr/lib/tmpfiles.d/mvbs.conf

# Copy current crontab
crontab -l > crontab_temp.txt

# Echo new cron into crontab file
echo "* * * * * >/dev/null 2>&1
@reboot python /home/pi/app/mvbs.py start -a
@reboot python /home/pi/app/mvbs.py server start
@reboot python /home/pi/app/mvbs.py dog -a > /home/pi/app/logs/watchdog.log
" > crontab_temp.txt

# Install new cron file
crontab crontab_temp.txt

# CleanUp
rm crontab_temp.txt

echo -e "\ncrontab:"
crontab -l

echo -e "\ntmpfiles.d:"
cat /usr/lib/tmpfiles.d/mvbs.conf

echo -e "\n/run/user:"
ls -l /run/user
