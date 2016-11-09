#!/bin/bash

tpcc_dir=$HOME/src/tpcc-mysql

mysql_user=nobody
mysql_pass=nobody123
mysql_host=192.168.5.51
mysql_db=tpcc


$tpcc_dir/tpcc_start -u $mysql_user -p $mysql_pass -h $mysql_host -d $mysql_db -i 1 -w 10 -c 10 -r 10 -l 600

