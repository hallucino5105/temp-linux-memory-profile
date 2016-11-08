#!/bin/bash

tpcc_dir=$HOME/src/tpcc-mysql

mysql_user=nobody
mysql_pass=nobody123
mysql_host=192.168.5.51
mysql_db=tpcc



mysql -u$mysql_user -p$mysql_pass -h$mysql_host -e "drop database $mysql_db"
mysql -u$mysql_user -p$mysql_pass -h$mysql_host -e "create database $mysql_db"

mysql -u$mysql_user -p$mysql_pass -h$mysql_host $mysql_db < $tpcc_dir/create_table.sql
mysql -u$mysql_user -p$mysql_pass -h$mysql_host $mysql_db < $tpcc_dir/add_fkey_idx.sql

$tpcc_dir/tpcc_load -u $mysql_user -p $mysql_pass -h $mysql_host -d $mysql_db -w 10 -l  1 -m 1 -n 10 >> load_1.out
$tpcc_dir/tpcc_load -u $mysql_user -p $mysql_pass -h $mysql_host -d $mysql_db -w 10 -l  2 -m 1 -n 10 >> load_2.out &
$tpcc_dir/tpcc_load -u $mysql_user -p $mysql_pass -h $mysql_host -d $mysql_db -w 10 -l  3 -m 1 -n 10 >> load_3.out &
$tpcc_dir/tpcc_load -u $mysql_user -p $mysql_pass -h $mysql_host -d $mysql_db -w 10 -l  4 -m 1 -n 10 >> load_4.out &

wait
