#!/usr/bin/env bash

# Copy current crontab
crontab -l > crontab_temp.txt

# Echo new cron into crontab file
echo "* * * * * >/dev/null 2>&1
@reboot sudo mkdir /run/user/test && sudo chown pi: /run/user/test && sudo chmod 775 /run/user/test/
@reboot python /home/pi/app/mvbs.py start -a > /home/pi/app/mvbs.log" \
>> crontab_temp.txt

# Install new cron file
crontab crontab_temp.txt

# CleanUp
rm crontab_temp.txt
