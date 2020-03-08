#!/usr/bin/env bash

# add configuration file to systemd-tmpfiles to create tmpfs directory for temporary data
sudo mv ~/app/mvbs_tmpfiles.d.conf /usr/lib/tmpfiles.d/mvbs.conf

# Copy current crontab
crontab -l > crontab_temp.txt

# Echo new cron into crontab file
echo "* * * * * >/dev/null 2>&1
@reboot python /home/pi/app/mvbs.py start -a > /home/pi/app/logs/mvbs.log
@reboot sudo python /home/pi/StatusServer/manage.py runserver 0.0.0.0:80 > /home/pi/app/logs/status_server.log 2>&1" \
>> crontab_temp.txt

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