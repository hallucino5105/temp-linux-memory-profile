#!/bin/bash

mysql -uroot -e "create user if not exists nobody@'127.0.0.1'"
mysql -uroot -e "grant all privileges on *.* to nobody@'127.0.0.1'"
mysql -uroot -e "set password for nobody@'127.0.0.1' = 'nobody123'"

mysql -uroot -e "create user if not exists nobody@'%'"
mysql -uroot -e "grant all privileges on *.* to nobody@'%'"
mysql -uroot -e "set password for nobody@'%' = 'nobody123'"

mysql -uroot -e "create database if not exists tpcc"
