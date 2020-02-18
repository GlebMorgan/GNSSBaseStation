#!/bin/bash

# Beforehand, create empty .ssh file in root folder of SD card

#########################################################################

echo GENERAL

# Expand Filesystem
sudo raspi-config --expand-rootfs

# Raspbian update
sudo apt update
sudo apt -y full-upgrade

# Enable UART
sudo bash -c "echo -e '\nenable_uart=1' >> /boot/config.txt"

# Disable serial console output
sudo bash -c "echo 'console=tty1 root=PARTUUID=6c586e13-02 rootfstype=ext4 elevator=deadline fsck.repair=yes rootwait' > /boot/cmdline.txt"

#########################################################################

echo PYTHON

# Install python3
sudo apt-get update
sudo apt-get -y install python3-pip

# Install pySerial package
pip3 install pyserial

# Reassign 'python' symlink to 'python3'
cd /usr/bin
sudo rm python
sudo ln -s python3 python
cd ~

#########################################################################

echo RTKLIB

# Download RTKLIB package from GitHub
sudo wget https://github.com/tomojitakasu/RTKLIB/archive/master.zip

# Unzip to /home directory and rename to RTKLIB
unzip master.zip
sudo mv RTKLIB-master RTKLIB
sudo rm master.zip

# Correct RTKLIB makefile
cd ~/RTKLIB/app/str2str/gcc
sed -i 's@BINDIR = /usr/local/bin@BINDIR = /home/pi/RTKLIB/bin@' makefile
sed -i 's@SRC    = ../../../src@SRC = /home/pi/RTKLIB/src@' makefile

# Create str2str binary
sudo make
sudo cp str2str /home/pi/RTKLIB/bin/str2str
sudo chmod +x /home/pi/RTKLIB/bin/str2str
cd ~

#########################################################################

echo APP

# Create 'app' directory
mkdir app

# Create symlink to 'str2str'
cd ~/app
ln -s /home/pi/RTKLIB/bin/str2str str2str
cd ~

#########################################################################

echo UCENTER

# uBlox <-> uCenter forwarding
sudo apt-get install socat
cd ~/app
echo "sudo socat tcp-listen:2020,reuseaddr /dev/serial0,b115200,raw,echo=0" > ucenter_forward.sh
sudo chmod +x ucenter_forward.sh
cd ~

#########################################################################

echo UBXTOOL

# Get GPSD/ubxtool from GitHub with necessary dependencies to /app directory
cd ~
wget https://github.com/bzed/gpsd-mirror/archive/master.zip
unzip master.zip gpsd-mirror-master/ubxtool gpsd-mirror-master/gps/*
mv gpsd-mirror-master/* .
mv ubxtool ubxtool.py
rm -r gpsd-mirror-master
rm master.zip
python ubxtool.py -h
