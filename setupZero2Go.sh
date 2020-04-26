#!/usr/bin/env bash

my_dir="`pwd`"

echo 'Source utilities.sh script to import functions and variables'
. ~/zero2go/utilities.sh

echo 'Set blinking interval = 2s'
i2c_write 0x01 $I2C_SLAVE_ADDRESS $I2C_CONF_BLINK_INTERVAL 0x07 && sleep 2

echo 'Set power cut delay = 3s'
i2c_write 0x01 $I2C_SLAVE_ADDRESS $I2C_CONF_POWER_CUT_DELAY 30 && sleep 2

echo 'Set low voltage threshold = 3.2V'
i2c_write 0x01 $I2C_SLAVE_ADDRESS $I2C_CONF_LOW_VOLTAGE 32 && sleep 2

echo 'Set recovery voltage threshold = 4.0V'
i2c_write 0x01 $I2C_SLAVE_ADDRESS $I2C_CONF_RECOVERY_VOLTAGE 40 && sleep 2

echo 'Set Step-Down engine always ON'
i2c_write 0x01 $I2C_SLAVE_ADDRESS $I2C_CONF_BULK_ALWAYS_ON 0x01 && sleep 2

echo 'All done'
