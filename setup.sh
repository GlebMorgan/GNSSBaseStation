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
sudo bash -c "echo 'console=tty1 root=PARTUUID=6c586e13-02 rootfstype=ext4 \\
elevator=deadline fsck.repair=yes rootwait' > /boot/cmdline.txt"

# Add 'l' and 'll' aliases to bash
echo "
export LS_OPTIONS='--color=auto'
eval \"\`dircolors\`\"
alias ls='ls $LS_OPTIONS'
alias l='ls $LS_OPTIONS -l'
alias ll='ls $LS_OPTIONS -lA'
" >> ~/.profile

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

#########################################################################

echo RTKLIB

# Download RTKLIB package from GitHub
# "master" - old stable RTKLIB 2.4.2
# "rtklib_2.4.3" - latest RTKLIB 2.4.3 b33
RTKLIB_VERSION="rtklib_2.4.3"
cd ~
sudo wget https://github.com/tomojitakasu/RTKLIB/archive/$RTKLIB_VERSION.zip

# Unzip to /home directory and rename to RTKLIB
unzip $RTKLIB_VERSION.zip
sudo mv RTKLIB-$RTKLIB_VERSION RTKLIB
sudo rm $RTKLIB_VERSION.zip

# Correct RTKLIB makefile
cd ~/RTKLIB/app/str2str/gcc
sed -i 's@BINDIR = /usr/local/bin@BINDIR = /home/pi/RTKLIB/bin@' makefile
sed -i 's@SRC    = ../../../src@SRC = /home/pi/RTKLIB/src@' makefile

# Create str2str binary
sudo make
sudo mv str2str /home/pi/RTKLIB/bin/str2str
sudo chmod +x /home/pi/RTKLIB/bin/str2str

#########################################################################

echo APP

# Create 'app' directory
mkdir ~/app

# Create symlink to 'str2str'
cd ~/app
ln -s /home/pi/RTKLIB/bin/str2str str2str

# Add aliases to bash
echo "
alias mvbs='/home/pi/app/mvbs.py'
alias sps='ps -A | grep'
" >> ~/.profile

#########################################################################

echo UCENTER

# uBlox <-> uCenter forwarding
cd ~/app
sudo apt-get install socat
echo "sudo socat tcp-listen:2020,reuseaddr /dev/serial0,b115200,raw,echo=0" > ucenter_forward.sh
sudo chmod +x ucenter_forward.sh

#########################################################################

echo UBXTOOL

# Get GPSD/gps from GitLab to /app directory
cd ~/app
sudo apt-get install scons
wget https://gitlab.com/gpsd/gpsd/-/archive/master/gpsd-master.zip
unzip gpsd-master.zip
rm gpsd-master.zip

cd gpsd-master
scons minimal=yes ublox=yes
cd ..

mv gpsd-master/gps .
sudo rm -r gpsd-master

#########################################################################

echo ZERO2GO

# Download Zero2Go installer script
cd ~
wget http://www.uugear.com/repo/Zero2GoOmini/installZero2Go.sh

# Run the installation
sudo sh installZero2Go.sh

# Clean up and remove unused libraries
sudo apt autoremove
rm installZero2Go.sh

#########################################################################

echo VIM

# Install vim
sudo apt-get -y install vim

# Install vim-plug
sudo apt-get -y install git
curl -fLo ~/.vim/autoload/plug.vim --create-dirs \
    https://raw.githubusercontent.com/junegunn/vim-plug/master/plug.vim

# Add plugins: vim-toml
echo "call plug#begin('~/.vim/plugged')
Plug 'cespare/vim-toml'
call plug#end()
" > ~/.vimrc

# Install plugins
vim +PlugInstall +qall
