#!/usr/bin/env bash

# Copy current crontab
crontab -l > crontab_temp.txt

# Abort if cron already contains a record
cat crontab_temp.txt | grep -q \
"@reboot python /home/pi/app/mvbs.py -a > /home/pi/app/mvbs_stdout.log
" && exit

# Echo new cron into crontab file
echo "  * * *   *   *      >/dev/null 2>&1
@reboot python /home/pi/app/mvbs.py -a > /home/pi/app/mvbs_stdout.log" \
>> crontab_temp.txt

# Install new cron file
crontab crontab_temp.txt

# CleanUp
rm crontab_temp.txt
